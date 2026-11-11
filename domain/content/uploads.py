"""Audited image changes, with item/theme versions and a shared storage budget."""
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .editing import EditConflict, _snapshot, require_owner
from .media import decode_image, discard_uncommitted_image, lock_media_quota, persist_image
from .models import AuditEvent, ContentRevision, MediaAsset, PresentationItem, SiteTheme, ThemeImage
from .theme import THEME_FIELDS


def edit_item_image(*, actor, item_id, expected_version: int, alt_en: str, alt_fr: str = "", image=None):
    require_owner(actor)
    if not alt_en.strip():
        raise ValidationError(_("An English image description is required; French may fall back to it."))
    prepared = decode_image(image) if image is not None else None
    new_asset = None
    try:
        with transaction.atomic():
            require_owner(actor)
            lock_media_quota()
            item = PresentationItem.objects.select_for_update().get(pk=item_id)
            if item.deleted_at is not None:
                raise ValidationError(_("This story has been deleted."))
            if item.version != expected_version:
                raise EditConflict
            old = MediaAsset.objects.filter(item=item, active=True).order_by("sequence", "id").first()
            if not prepared and not old:
                raise ValidationError(_("Choose an image for this story."))
            if not prepared and old.alt_en == alt_en and old.alt_fr == alt_fr:
                return item
            snapshot = _snapshot(item)
            snapshot["media"] = [_snapshot(asset) for asset in MediaAsset.objects.filter(item=item, active=True).order_by("sequence", "id")]
            revision = ContentRevision.objects.create(entity="presentation_item", entity_id=str(item.pk), version=item.version, actor=actor, snapshot=snapshot)
            if prepared:
                new_asset = persist_image(MediaAsset, prepared, item=item, active=False, sequence=old.sequence if old else 0, alt_en=alt_en, alt_fr=alt_fr)
                if old:
                    MediaAsset.objects.filter(pk=old.pk).update(active=False)
                MediaAsset.objects.filter(pk=new_asset.pk).update(active=True)
                changed = ["media.image", "media.alt_en", "media.alt_fr"]
            else:
                old.alt_en, old.alt_fr = alt_en, alt_fr
                old.full_clean()
                MediaAsset.objects.filter(pk=old.pk).update(alt_en=alt_en, alt_fr=alt_fr)
                changed = ["media.alt_en", "media.alt_fr"]
            if PresentationItem.objects.filter(pk=item.pk, version=expected_version).update(version=F("version") + 1, updated_at=timezone.now()) != 1:
                raise EditConflict
            AuditEvent.objects.create(actor=actor, action="edit_image", entity="presentation_item", entity_id=str(item.pk), changed_fields=changed, revision=revision)
            item.refresh_from_db()
        return item
    except Exception:
        if new_asset:
            discard_uncommitted_image(new_asset)
        raise


def edit_theme(*, actor, expected_version: int, changes: dict, image=None, clear_background: bool = False):
    require_owner(actor)
    if set(changes) != set(THEME_FIELDS):
        raise ValidationError(_("Supply only the supported theme fields."))
    if image is not None and clear_background:
        raise ValidationError(_("Choose an upload or remove the background, not both."))
    prepared = decode_image(image) if image is not None else None
    new_asset = None
    try:
        with transaction.atomic():
            require_owner(actor)
            lock_media_quota()
            theme = SiteTheme.objects.select_for_update().get(pk=1)
            if theme.version != expected_version:
                raise EditConflict
            snapshot = _snapshot(theme)
            changed = [key for key, value in changes.items() if getattr(theme, key) != value]
            for key, value in changes.items():
                setattr(theme, key, value)
            theme.full_clean()
            if prepared:
                new_asset = persist_image(ThemeImage, prepared)
                theme.background_image_id = new_asset.pk
                changed.append("background_image")
            elif clear_background and theme.background_image_id:
                theme.background_image_id = None
                changed.append("background_image")
            if not changed:
                return theme
            revision = ContentRevision.objects.create(entity="site_theme", entity_id="1", version=theme.version, actor=actor, snapshot=snapshot)
            updates = {key: getattr(theme, key) for key in THEME_FIELDS}
            updates.update(background_image_id=theme.background_image_id, version=F("version") + 1)
            if SiteTheme.objects.filter(pk=1, version=expected_version).update(**updates) != 1:
                raise EditConflict
            AuditEvent.objects.create(actor=actor, action="edit_theme", entity="site_theme", entity_id="1", changed_fields=sorted(changed), revision=revision)
            theme.refresh_from_db()
        return theme
    except Exception:
        if new_asset:
            discard_uncommitted_image(new_asset)
        raise
