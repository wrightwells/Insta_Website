"""Owner-triggered source imports through the existing publication/media boundary."""
from datetime import timedelta
import hashlib
import uuid
import time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from .editing import _snapshot, require_owner
from .media import decode_image, discard_uncommitted_image, lock_media_quota, persist_image
from .models import (AuditEvent, ContentRevision, InstagramImport, InstagramSync,
                     MediaAsset, PresentationItem, SourceAccount, Status)
from .validators import validate_instagram_url


def import_post(*, actor, post, images):
    require_owner(actor)
    account_id, post_id = str(post['source_account_id']), str(post['source_post_id'])
    if not account_id.isdecimal() or not post_id.isdecimal() or len(account_id) > 40 or len(post_id) > 40:
        raise ValidationError(_("Instagram returned an invalid post identity."))
    validate_instagram_url(post['source_url'])
    published = parse_datetime(post['source_published_at'])
    if not published or timezone.is_naive(published) or not images:
        raise ValidationError(_("This post has no usable image or publication date."))
    prepared = [decode_image(image) for image in images]
    snapshot = {key: post[key] for key in ('source_account_id', 'source_post_id', 'source_url',
                                          'source_published_at', 'original_caption', 'media_type')}
    caption = snapshot['original_caption']
    if not isinstance(caption, str) or len(caption) > 100_000:
        raise ValidationError(_("Instagram returned invalid caption text."))
    saved_assets = []
    try:
        with transaction.atomic():
            require_owner(actor)
            lock_media_quota()
            account, account_created = SourceAccount.objects.only('id', 'platform', 'source_account_id', 'enabled').get_or_create(
                source_account_id=account_id, platform='instagram', defaults={'enabled': True})
            # Serializes imports for this source, in addition to the batch lease.
            SourceAccount.objects.only('id').select_for_update().get(pk=account.pk)
            item = PresentationItem.objects.select_for_update().filter(account=account, source_post_id=post_id).first()
            if item is not None and item.deleted_at is not None:
                return "unchanged"
            created = item is None
            if created:
                item = PresentationItem.objects.create(account=account, source_post_id=post_id,
                    canonical_url=post['source_url'], source_published_at=published,
                    original_caption=caption, status=Status.DRAFT)
            prior = InstagramImport.objects.filter(item=item).first()
            active = list(MediaAsset.objects.filter(item=item, active=True).order_by('sequence', 'id'))
            # Preserve media replaced/edited by the owner after a previous import.
            owned_media = created or (prior is not None and not prior.source_snapshot.get('_media_overridden')
                                      and prior.media_ids == [str(asset.pk) for asset in active]
                                      and not AuditEvent.objects.filter(entity_id=str(item.pk), action='edit_image',
                                                                      created_at__gt=prior.imported_at).exists())
            checksums = [hashlib.sha256(image.data).hexdigest() for image in prepared]
            replace_media = owned_media and checksums != [asset.checksum for asset in active]
            source_changed = (item.original_caption != caption or item.canonical_url != post['source_url']
                              or item.source_published_at != published)
            snapshot['_media_overridden'] = not owned_media
            if not created and not source_changed and not replace_media:
                # Do not erase the baseline detecting later editorial media overrides.
                return 'unchanged'
            revision = None
            if not created:
                before = _snapshot(item)
                before['media'] = [_snapshot(asset) for asset in active]
                revision = ContentRevision.objects.create(entity='presentation_item', entity_id=str(item.pk),
                    version=item.version, actor=actor, snapshot=before)
            if replace_media:
                # Deactivate only inside the same transaction as validated replacement.
                MediaAsset.objects.filter(item=item, active=True).update(active=False)
                for index, image in enumerate(prepared):
                    asset = persist_image(MediaAsset, image, item=item, sequence=index,
                        alt_en=(caption.strip()[:450] or f'Instagram post {post_id}') + (f' ({index + 1})' if len(prepared) > 1 else ''),
                        alt_fr='', active=True)
                    saved_assets.append(asset)
                active = saved_assets
            item.original_caption, item.canonical_url, item.source_published_at = caption, post['source_url'], published
            if created:
                item.status = Status.PUBLISHED
                item.publish_at = min(published, timezone.now().replace(microsecond=0))
            else:
                item.version += 1
            # Owner display caption, order, dates, status and publication settings stay intact.
            item.full_clean()
            item.save(update_fields=['original_caption', 'canonical_url', 'source_published_at',
                                     'status', 'publish_at', 'version', 'updated_at'])
            InstagramImport.objects.update_or_create(item=item, defaults={'source_snapshot': snapshot,
                'media_ids': [str(asset.pk) for asset in active] if owned_media else (prior.media_ids if prior else [])})
            AuditEvent.objects.create(actor=actor, action='instagram_import', entity='presentation_item',
                entity_id=str(item.pk), revision=revision,
                changed_fields=['original_caption', 'source_media'] if replace_media else ['original_caption'])
            return 'created' if created else 'updated'
    except Exception:
        for asset in saved_assets:
            discard_uncommitted_image(asset)
        raise


def load_recent(*, actor, agent, limit):
    require_owner(actor)
    if type(limit) is not int or not 1 <= limit <= 12:
        raise ValidationError(_("Choose between 1 and 12 recent posts."))
    lease = uuid.uuid4()
    now = timezone.now()
    with transaction.atomic():
        state, state_created = InstagramSync.objects.get_or_create(pk=1)
        state = InstagramSync.objects.select_for_update().get(pk=1)
        if state.running_until and state.running_until > now:
            raise ValidationError(_("An Instagram import is already running. Please wait."))
        state.lease, state.running_until = lease, now + timedelta(hours=1)
        state.save(update_fields=['lease', 'running_until'])
    summary = dict(created=0, updated=0, unchanged=0, failed=0)
    deadline = time.monotonic() + 600
    try:
        result = agent.call('recent', {'limit': limit})
        posts = result.get('items')
        if not isinstance(posts, list) or len(posts) > limit:
            raise ValidationError(_("Instagram returned an invalid post list."))
        for post in posts:
            try:
                assets = post.get('assets', [])
                if not isinstance(assets, list) or not 1 <= len(assets) <= 20:
                    raise ValidationError(_("This post has no usable image."))
                images = []
                total_bytes = 0
                for index, asset in enumerate(assets):
                    if time.monotonic() > deadline:
                        raise ValidationError(_("Instagram import time limit reached. Load fewer posts."))
                    if asset.get('has_image'):
                        image = agent.call('image', {'post_id': post['source_post_id'], 'asset_index': index}, image=True)
                        total_bytes += image.getbuffer().nbytes
                        if total_bytes > 50 * 1024 * 1024:
                            raise ValidationError(_("The images in this post exceed the import size limit."))
                        images.append(image)
                # Never publish a partial carousel as a complete source import.
                if len(images) != len(assets):
                    raise ValidationError(_("This post has unavailable images."))
                outcome = import_post(actor=actor, post=post, images=images)
                summary[outcome] += 1
            except (ValidationError, KeyError, TypeError, ValueError, OSError):
                summary['failed'] += 1
        return summary
    finally:
        InstagramSync.objects.filter(pk=1, lease=lease).update(lease=None, running_until=None,
            last_finished_at=timezone.now(), summary=summary)
