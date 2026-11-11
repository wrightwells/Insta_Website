"""Read adapter and normalized data contract, independent of HTTP and Django."""
import contextlib
import io
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
import urllib.request
import uuid
import time

from agent.credentials import AccessError, NoRedirect


class PocError(AccessError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_media(media, account_id):
    """Stable, JSON-compatible source record for a future presentation-item upsert."""
    if str(media.user.pk) != str(account_id):
        raise PocError('wrong_account', 'Instagram returned media from a different account.')
    post_id, code = str(media.pk), media.code
    if not re.fullmatch(r'[0-9]{1,40}', post_id) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', code):
        raise PocError('invalid_media', 'Instagram returned an invalid post identity.')
    kind = {1: 'image', 2: 'video', 8: 'carousel'}.get(media.media_type)
    if not kind:
        raise PocError('unsupported_media', 'This media type is not supported by the PoC.')
    resources = media.resources if kind == 'carousel' else [media]
    assets = []
    for resource in resources:
        resource_kind = {1: 'image', 2: 'video'}.get(resource.media_type)
        if not resource_kind:
            raise PocError('unsupported_media', 'A carousel contains an unsupported media type.')
        image = getattr(resource, 'thumbnail_url', None)
        video = getattr(resource, 'video_url', None)
        assets.append({'kind': resource_kind, 'image_url': str(image) if image else None,
                       'video_url': str(video) if video else None})
    return {'schema_version': 1, 'source_platform': 'instagram',
            'source_account_id': str(account_id), 'source_post_id': post_id,
            'source_url': f'https://www.instagram.com/p/{code}/',
            'source_published_at': media.taken_at.astimezone(timezone.utc).isoformat(),
            'original_caption': media.caption_text or '', 'media_type': kind,
            'assets': assets, 'fetched_at': utc_now()}


ERRORS = {
    'TwoFactorRequired': ('two_factor_required', 'Enter a fresh two-factor code and connect again.'),
    'ChallengeRequired': ('challenge_required', 'Resolve the account challenge in Instagram, then connect again.'),
    'ChallengeUnknownStep': ('challenge_required', 'Resolve the account challenge in Instagram, then connect again.'),
    'LoginRequired': ('login_required', 'The session expired. Connect again.'),
    'BadPassword': ('login_rejected', 'Instagram rejected login. Check the account details in Instagram.'),
    'ClientThrottledError': ('rate_limited', 'Instagram rate limited this request. Pause and try later.'),
    'PleaseWaitFewMinutes': ('rate_limited', 'Instagram requested a pause. Try later.'),
    'FeedbackRequired': ('restricted', 'Instagram restricted this request. Inspect the account in Instagram.'),
}


@contextlib.contextmanager
def safe_provider():
    # SDK exceptions/diagnostics can contain credentials and account responses.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    except AccessError:
        raise
    except Exception as exc:
        code, message = ERRORS.get(type(exc).__name__, (
            'provider_failed', 'Instagram request failed. Stored results were preserved.'))
        raise PocError(code, message) from None
    finally:
        logging.disable(previous_logging)


class InstagramService:
    def __init__(self, store, client_factory=None):
        self.store = store
        if client_factory is None:
            from instagrapi import Client
            client_factory = Client
        self.client_factory = client_factory
        self.pending_login = None

    def status(self):
        with self.store.locked():
            record = self.store.load() or {}
            return {'username': record.get('username', ''), 'configured': bool(record),
                    'connected': bool(record.get('settings')), 'account_id': record.get('account_id'),
                    'verified_at': record.get('verified_at'), 'last_fetch_at': record.get('last_fetch_at'),
                    'posts': list(record.get('posts', {}).values()), 'cursor': record.get('cursor', '')}

    def save_account(self, username, password):
        username = username.strip().lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9._]{1,30}', username):
            raise PocError('invalid_username', 'Enter an Instagram username, not a profile URL.')
        if not isinstance(password, str) or len(password) > 1024:
            raise PocError('invalid_password', 'Invalid password length.')
        with self.store.locked():
            old = self.store.load() or {}
            same = old.get('username', '').casefold() == username.casefold()
            if not password and not (same and old.get('password')):
                raise PocError('password_required', 'Enter a password for this account.')
            record = old if same else {'schema': 'instagrapi-poc-v1', 'posts': {}}
            # Changed password invalidates the saved session and verification.
            if password and password != old.get('password'):
                for key in ('settings', 'verified_at', 'cursor'):
                    record.pop(key, None)
            record.update(username=username, password=password or old['password'])
            self.store.save(record)
            self.pending_login = None

    def _record(self):
        record = self.store.load()
        if not record:
            raise PocError('not_configured', 'Save account details first.')
        return record

    def _client(self, record):
        client = self.client_factory()
        client.delay_range = [1, 3]
        client.request_timeout = 20
        if record.get('settings'):
            client.set_settings(record['settings'])
        client.challenge_code_handler = lambda *_: self._challenge()
        client.change_password_handler = lambda *_: self._challenge()
        return client

    @staticmethod
    def _challenge():
        raise PocError('challenge_required', 'Resolve the account challenge directly in Instagram.')

    def connect(self, verification_code=''):
        if verification_code and not re.fullmatch(r'[0-9]{6,8}', verification_code):
            raise PocError('invalid_code', 'Enter a six to eight digit verification or backup code.')
        with self.store.locked(), safe_provider():
            record = self._record()
            pending = self.pending_login
            client = (pending[2] if verification_code and pending and pending[0] == record['username']
                      and time.monotonic() - pending[1] < 300 else self._client(record))
            self.pending_login = None
            try:
                client.login(record['username'], record['password'], verification_code=verification_code)
            except Exception as exc:
                if type(exc).__name__ == 'TwoFactorRequired':
                    self.pending_login = (record['username'], time.monotonic(), client)
                raise
            self._verify_identity(client, record)
            record.update(settings=client.get_settings(), verified_at=utc_now())
            self.store.save(record)
            return {'account_id': record['account_id'], 'verified_at': record['verified_at']}

    def _verify_identity(self, client, record):
        account = client.account_info()
        actual_id = str(account.pk)
        if (not re.fullmatch(r'[0-9]{1,40}', actual_id)
                or account.username.casefold() != record['username'].casefold()
                or record.get('account_id', actual_id) != actual_id):
            raise PocError('wrong_account', 'Connected identity does not match the saved account.')
        record['account_id'] = actual_id

    def _reader(self, record):
        if not record.get('settings'):
            raise PocError('not_connected', 'Connect and verify the account first.')
        client = self._client(record)
        # Reads never automatically perform a new password login.
        self._verify_identity(client, record)
        return client

    def fetch_posts(self, limit=12, next_page=False):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise PocError('invalid_limit', 'Choose between 1 and 50 posts.')
        with self.store.locked(), safe_provider():
            record = self._record()
            client = self._reader(record)
            cursor = record.get('cursor', '') if next_page else ''
            if next_page and not cursor:
                raise PocError('no_next_page', 'No next page is available. Fetch recent posts instead.')
            medias, cursor = client.user_medias_paginated_v1(record['account_id'], amount=limit, end_cursor=cursor)
            posts = [normalize_media(media, record['account_id']) for media in medias]
            if len(posts) > limit:
                raise PocError('invalid_page', 'Instagram exceeded the requested page size.')
            cached = record.setdefault('posts', {})
            for post in posts:
                cached[post['source_post_id']] = post
            # This is a bounded PoC cache, not the final website database.
            while len(cached) > 100:
                del cached[next(iter(cached))]
            record.update(cursor=cursor or '', settings=client.get_settings(), last_fetch_at=utc_now())
            self.store.save(record)
            return {'items': posts, 'has_next_page': bool(cursor)}

    def fetch_post(self, post_id):
        if not re.fullmatch(r'[0-9]{1,40}', str(post_id)):
            raise PocError('invalid_id', 'Enter a numeric Instagram post ID.')
        with self.store.locked(), safe_provider():
            record = self._record()
            client = self._reader(record)
            post = normalize_media(client.media_info_v1(str(post_id)), record['account_id'])
            cached = record.setdefault('posts', {})
            if post['source_post_id'] not in cached and len(cached) >= 100:
                del cached[next(iter(cached))]
            cached[post['source_post_id']] = post
            record.update(settings=client.get_settings(), last_fetch_at=utc_now())
            self.store.save(record)
            return post

    def download_media(self, post_id, asset_index=0, thumbnail=False):
        """Download only a cached provider asset, bounded and staged outside the web root."""
        with self.store.locked():
            record = self._record()
            post = record.get('posts', {}).get(str(post_id))
            if not post or type(asset_index) is not int or not 0 <= asset_index < len(post['assets']):
                raise PocError('invalid_asset', 'Fetch the post first and choose a valid asset.')
            asset = post['assets'][asset_index]
            video = asset['kind'] == 'video' and not thumbnail
            url = asset['video_url'] if video else asset['image_url']
            parsed = urlsplit(url or '')
            host = parsed.hostname or ''
            if (parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password
                    or not any(host.endswith('.' + domain) for domain in ('cdninstagram.com', 'fbcdn.net'))):
                raise PocError('invalid_asset_url', 'No supported Instagram CDN URL is available. Refresh the post.')
            folder = self.store.data_dir / 'downloads'
            self.store.private_dir(folder)
            if sum(path.stat().st_size for path in folder.iterdir() if path.is_file()) > 400 * 1024 * 1024:
                raise PocError('storage_full', 'PoC downloads reached their budget. Archive old downloads before continuing.')
            key = uuid.uuid4().hex
            stage = folder / (key + '.part')
            limit = 100 * 1024 * 1024 if video else 20 * 1024 * 1024
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            try:
                with opener.open(url, timeout=30) as response, stage.open('xb') as output:
                    stage.chmod(0o600)
                    total = 0
                    while chunk := response.read(65536):
                        total += len(chunk)
                        if total > limit:
                            raise PocError('asset_too_large', 'Media exceeds the PoC download limit.')
                        output.write(chunk)
                if video:
                    with stage.open('rb') as handle:
                        header = handle.read(16)
                    if len(header) < 12 or header[4:8] != b'ftyp':
                        raise PocError('invalid_media', 'Downloaded video is not a supported MP4 container.')
                    extension = '.mp4'
                else:
                    from PIL import Image
                    with Image.open(stage) as image:
                        extension = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}.get(image.format)
                        if not extension or image.width * image.height > 40_000_000:
                            raise PocError('invalid_media', 'Unsupported image format or dimensions.')
                        image.verify()
                destination = folder / (key + extension)
                stage.replace(destination)
                return {'storage_key': destination.name, 'bytes': total, 'kind': 'video' if video else 'image'}
            except AccessError:
                raise
            except Exception:
                raise PocError('download_failed', 'Download failed. Refresh the post if its media URL expired.') from None
            finally:
                stage.unlink(missing_ok=True)
