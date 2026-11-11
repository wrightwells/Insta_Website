import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.credentials import AccessError
from agent.instagram_poc.app import create_app
from agent.instagram_poc.service import InstagramService, PocError
from agent.instagram_poc.storage import PocStore


class FakeClient:
    def __init__(self):
        self.settings = {}
        self.failure = None
        self.owner = '123'
        self.code = None

    def set_settings(self, settings):
        self.settings = settings

    def get_settings(self):
        return {'authorization_data': {'sessionid': 'synthetic-session-secret'}}

    def login(self, username, password, verification_code=''):
        self.code = verification_code
        if self.failure:
            raise self.failure
        return True

    def account_info(self):
        return SimpleNamespace(pk=self.owner, username='demo')

    def media(self, pk='456'):
        return SimpleNamespace(pk=pk, code='post_456', user=SimpleNamespace(pk=self.owner),
                               taken_at=datetime(2026, 1, 1, tzinfo=timezone.utc), media_type=1,
                               resources=[], caption_text='<script>alert("caption")</script>',
                               thumbnail_url='https://scontent.cdninstagram.com/photo.jpg', video_url=None)

    def user_medias_paginated_v1(self, account, amount, end_cursor):
        self.last_cursor = end_cursor
        return [self.media()], 'next-cursor'

    def media_info_v1(self, pk):
        return self.media(pk)


class PocTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        base = Path(self.directory.name)
        self.store = PocStore(base / 'data', base / 'keys')
        self.sdk = FakeClient()
        self.service = InstagramService(self.store, lambda: self.sdk)

    def configured(self):
        self.service.save_account('demo', 'synthetic-password')
        self.service.connect()

    def test_encryption_and_redaction(self):
        self.configured()
        encrypted = self.store.record_path.read_bytes()
        for secret in (b'synthetic-password', b'synthetic-session-secret'):
            self.assertNotIn(secret, encrypted)
            self.assertNotIn(secret.decode(), json.dumps(self.service.status()))
        self.assertEqual(self.store.record_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.key_path.parent.stat().st_mode & 0o777, 0o700)

    def test_upsert_pagination_and_original_caption(self):
        self.configured()
        first = self.service.fetch_posts()
        self.service.fetch_posts(next_page=True)
        self.assertEqual(self.sdk.last_cursor, 'next-cursor')
        self.assertEqual(len(self.service.status()['posts']), 1)
        self.assertEqual(first['items'][0]['original_caption'], '<script>alert("caption")</script>')
        self.assertEqual(first['items'][0]['source_url'], 'https://www.instagram.com/p/post_456/')
        self.service.fetch_post('456')
        self.assertEqual(len(self.service.status()['posts']), 1)

    def test_wrong_identity_preserves_previous_state(self):
        self.configured()
        before = self.store.record_path.read_bytes()
        self.sdk.owner = '999'
        with self.assertRaises(PocError):
            self.service.fetch_posts()
        self.assertEqual(before, self.store.record_path.read_bytes())

    def test_mfa_continuation_and_safe_errors(self):
        self.service.save_account('demo', 'synthetic-password')
        self.sdk.failure = type('TwoFactorRequired', (Exception,), {})('secret provider body')
        with self.assertRaisesRegex(PocError, 'fresh two-factor'):
            self.service.connect()
        self.assertFalse(self.service.status()['connected'])
        self.sdk.failure = None
        self.service.connect('123456')
        self.assertEqual(self.sdk.code, '123456')
        self.assertTrue(self.service.status()['connected'])

    def test_failed_read_preserves_results(self):
        self.configured()
        self.service.fetch_posts()
        before = self.store.record_path.read_bytes()
        with patch.object(self.sdk, 'user_medias_paginated_v1', side_effect=RuntimeError('synthetic-password')):
            with self.assertRaises(PocError) as error:
                self.service.fetch_posts()
        self.assertNotIn('synthetic-password', str(error.exception))
        self.assertEqual(before, self.store.record_path.read_bytes())

    def test_account_change_and_password_change(self):
        self.configured()
        self.service.save_account('demo', '')
        self.assertTrue(self.service.status()['connected'])
        self.service.save_account('demo', 'new-secret')
        self.assertFalse(self.service.status()['connected'])
        self.service.save_account('other', 'new-secret')
        self.assertIsNone(self.service.status()['account_id'])
        self.assertEqual(self.service.status()['posts'], [])

    def test_bounds_and_unconnected_reads(self):
        self.service.save_account('demo', 'secret')
        with self.assertRaises(PocError):
            self.service.fetch_posts()
        for limit in (0, 51, True):
            with self.assertRaises(PocError):
                self.service.fetch_posts(limit)
        with self.assertRaises(PocError):
            self.service.fetch_post('../etc/passwd')

    def test_storage_corruption_and_repository_rejection(self):
        with self.assertRaises(AccessError):
            PocStore(Path(__file__).resolve().parents[1] / 'secrets', Path(self.directory.name) / 'key2')
        self.configured()
        self.store.record_path.write_bytes(b'corrupt')
        with self.assertRaises(AccessError):
            self.service.status()

    def login(self):
        app = create_app(self.service, 'operator-password')
        app.testing = True
        client = app.test_client()
        kwargs = {'base_url': 'http://127.0.0.1:8768'}
        login_page = client.get('/login', **kwargs)
        self.assertEqual(login_page.headers['Referrer-Policy'], 'same-origin')
        with client.session_transaction(**kwargs) as session:
            csrf = session['csrf']
        response = client.post('/login', data={'csrf': csrf, 'password': 'operator-password'},
                               headers={'Origin': kwargs['base_url']}, **kwargs)
        self.assertEqual(response.status_code, 302)
        with client.session_transaction(**kwargs) as session:
            csrf = session['csrf']
        return client, kwargs, csrf

    def test_ui_auth_csrf_origin_host_and_xss(self):
        self.configured()
        self.service.fetch_posts()
        app = create_app(self.service, 'operator-password')
        client = app.test_client()
        kwargs = {'base_url': 'http://127.0.0.1:8768'}
        self.assertEqual(client.get('/', **kwargs).status_code, 302)
        self.assertEqual(client.get('/posts.json', **kwargs).status_code, 302)
        self.assertEqual(client.get('/', base_url='http://evil.test').status_code, 403)
        client, kwargs, csrf = self.login()
        page = client.get('/', **kwargs)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'&lt;script&gt;', page.data)
        self.assertNotIn(b'<script>', page.data)
        self.assertNotIn(b'synthetic-password', page.data)
        self.assertNotIn(b'synthetic-session-secret', page.data)
        self.assertEqual(page.headers['Cache-Control'], 'no-store')
        self.assertEqual(page.headers['Referrer-Policy'], 'same-origin')
        self.assertEqual(client.post('/action/fetch', data={}, **kwargs).status_code, 403)
        self.assertEqual(client.post('/action/fetch', data={'csrf': csrf},
                                     headers={'Origin': 'http://evil.test'}, **kwargs).status_code, 403)
        self.assertEqual(client.post('/action/fetch', data={'csrf': csrf},
                                     headers={'Origin': 'null'}, **kwargs).status_code, 403)
        result = client.post('/action/fetch', data={'csrf': csrf, 'limit': '1'},
                             headers={'Origin': kwargs['base_url']}, **kwargs)
        self.assertEqual(result.status_code, 200)
        exported = client.get('/posts.json', **kwargs).json
        self.assertEqual(len(exported['items']), 1)
        self.assertNotIn('synthetic-password', json.dumps(exported))

    def test_download_rejects_non_cdn_and_preserves_cache(self):
        self.configured()
        self.service.fetch_posts()
        with self.store.locked():
            record = self.store.load()
            record['posts']['456']['assets'][0]['image_url'] = 'http://127.0.0.1/secrets'
            self.store.save(record)
        with patch('urllib.request.build_opener') as network:
            with self.assertRaises(PocError):
                self.service.download_media('456')
            network.assert_not_called()

    def test_image_download_validation_and_cleanup(self):
        import io
        from PIL import Image
        self.configured()
        self.service.fetch_posts()
        image = io.BytesIO()
        Image.new('RGB', (2, 2)).save(image, 'PNG')
        with patch('urllib.request.build_opener') as factory:
            factory.return_value.open.return_value = io.BytesIO(image.getvalue())
            result = self.service.download_media('456')
        self.assertEqual(result['kind'], 'image')
        self.assertTrue((self.store.data_dir / 'downloads' / result['storage_key']).exists())
        with patch('urllib.request.build_opener') as factory:
            factory.return_value.open.return_value = io.BytesIO(b'not an image')
            with self.assertRaises(PocError):
                self.service.download_media('456')
        self.assertEqual(list((self.store.data_dir / 'downloads').glob('*.part')), [])


if __name__ == '__main__':
    unittest.main()
