"""Authenticated editorial writes and their audit records share one transaction."""
from django.utils.translation import gettext_lazy as _
from datetime import date, datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .policy import POLICY_FIELDS
from .metadata import SEO_FIELDS
from .discovery import DISCOVERY_FIELDS
from .models import AuditEvent, ContentRevision, MediaAsset, PresentationItem, SiteContent, SiteOwner, SitePolicy, Status

ITEM_FIELDS = ("display_caption", "display_date", "priority", "status", "publish_at")
CONTACT_FIELDS = ("contact_email", "contact_phone", "contact_address", "contact_intro_en", "contact_intro_fr", "contact_hours_en", "contact_hours_fr")
REVIEW_FIELDS = ("reviews_enabled",)
PAGE_FIELDS = (*CONTACT_FIELDS, *REVIEW_FIELDS)
FEED_COPY_FIELDS = ("journal_en", "journal_fr", "feed_heading_en", "feed_heading_fr")
SITE_FIELDS = ("name", "intro_en", "intro_fr", "footer_en", "footer_fr", "empty_en", "empty_fr", "default_locale", "english_enabled", "french_enabled", "page_size") + SEO_FIELDS + FEED_COPY_FIELDS


class EditConflict(Exception):
    pass


def require_owner(actor) -> None:
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        raise PermissionDenied
    if not SiteOwner.objects.filter(pk=1, user_id=actor.pk, user__is_active=True, user__is_staff=True).exists():
        raise PermissionDenied


def _snapshot(obj) -> dict:
    result = {}
    for field in obj._meta.concrete_fields:
        value = getattr(obj, field.attname)
        if isinstance(value, (date, datetime)):
            value = value.isoformat()
        elif isinstance(value, UUID):
            value = str(value)
        result[field.attname] = value
    return result


@transaction.atomic
def edit_content(*, actor, model, pk, expected_version: int, changes: dict, confirm_hide: bool = False):
    require_owner(actor)
    if model not in (PresentationItem, SiteContent, SitePolicy):
        raise PermissionDenied
    allowed = ITEM_FIELDS if model is PresentationItem else POLICY_FIELDS if model is SitePolicy else (*SITE_FIELDS, *DISCOVERY_FIELDS, *PAGE_FIELDS)
    if set(changes) - set(allowed):
        raise ValidationError(_("Unsupported editorial fields."))
    obj = model.objects.select_for_update().get(pk=pk)
    if model is PresentationItem and obj.deleted_at is not None:
        raise ValidationError(_("This story has been deleted."))
    if obj.version != expected_version:
        raise EditConflict
    changed = sorted(key for key, value in changes.items() if getattr(obj, key) != value)
    if not changed:
        return obj
    snapshot = _snapshot(obj)
    if model is PresentationItem and obj.status == Status.PUBLISHED and changes.get("status", obj.status) != Status.PUBLISHED and not confirm_hide:
        raise ValidationError(_("Confirm removal of this published story before saving."))
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.full_clean()
    if model is PresentationItem and snapshot["status"] == Status.PUBLISHED:
        prior_date = datetime.fromisoformat(snapshot["publish_at"]) if snapshot["publish_at"] else None
        if prior_date and prior_date <= timezone.now() and obj.publish_at and obj.publish_at > timezone.now() and not confirm_hide:
            raise ValidationError(_("Confirm removing this story from public view before scheduling it for the future."))
    if model is PresentationItem and obj.status == Status.PUBLISHED:
        if not MediaAsset.objects.filter(item=obj, active=True, validated=True, mime_type="image/png").exclude(alt_en="").exists():
            raise ValidationError(_("Publishing requires a validated image and alternative text."))
    entity = "presentation_item" if model is PresentationItem else "site_policy" if model is SitePolicy else "site_content"
    revision = ContentRevision.objects.create(entity=entity, entity_id=str(pk), version=expected_version, actor=actor, snapshot=snapshot)
    update = {key: getattr(obj, key) for key in changed}
    update["version"] = F("version") + 1
    if model is PresentationItem:
        update["updated_at"] = timezone.now()
    if model.objects.filter(pk=pk, version=expected_version).update(**update) != 1:
        raise EditConflict
    AuditEvent.objects.create(actor=actor, action="edit", entity=entity, entity_id=str(pk), changed_fields=changed, revision=revision)
    obj.refresh_from_db()
    return obj


@transaction.atomic
def delete_story(*, actor, pk, expected_version):
    """Retain a tombstone and historical media so imports cannot republish a deletion."""
    require_owner(actor)
    item = PresentationItem.objects.select_for_update().get(pk=pk, deleted_at__isnull=True)
    if item.version != expected_version:
        raise EditConflict
    snapshot = _snapshot(item)
    snapshot["media"] = [_snapshot(asset) for asset in item.media.filter(active=True)]
    revision = ContentRevision.objects.create(entity="presentation_item", entity_id=str(pk),
        version=item.version, actor=actor, snapshot=snapshot)
    now = timezone.now()
    PresentationItem.objects.filter(pk=pk, version=expected_version).update(
        deleted_at=now, status=Status.ARCHIVED, version=F("version") + 1, updated_at=now)
    AuditEvent.objects.create(actor=actor, action="delete_story", entity="presentation_item",
        entity_id=str(pk), changed_fields=["deleted_at", "status"], revision=revision)
