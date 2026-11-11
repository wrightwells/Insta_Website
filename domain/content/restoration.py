"""Confirmed settings restoration creates a new version; history stays immutable."""
import copy
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from .editing import EditConflict, FEED_COPY_FIELDS, PAGE_FIELDS, SITE_FIELDS, _snapshot, require_owner
from .media import MAX_IMAGE_BYTES, lock_media_quota
from .metadata import SEO_FIELDS
from .discovery import DISCOVERY_FIELDS
from .models import AuditEvent, ContentRevision, SiteContent, SitePolicy, SiteTheme, ThemeImage
from .theme import THEME_FIELDS
from .policy import POLICY_FIELDS

SETTINGS_MODELS = {
    "site_content": (SiteContent, (*SITE_FIELDS, *DISCOVERY_FIELDS, *PAGE_FIELDS)),
    "site_policy": (SitePolicy, POLICY_FIELDS),
    "site_theme": (SiteTheme, (*THEME_FIELDS, "background_image_id")),
}


def settings_model(revision):
    if revision.entity not in SETTINGS_MODELS or revision.entity_id != "1":
        raise ValidationError(_("Only site settings and appearance can be restored here."))
    return SETTINGS_MODELS[revision.entity]


def _check_background(image_id):
    if image_id is None:
        return
    message = _("The saved background image is missing or invalid. No settings were changed.")
    try:
        image = ThemeImage.objects.get(pk=image_id, validated=True, mime_type="image/png")
        image.full_clean()
        path = Path(settings.PRIVATE_MEDIA_ROOT) / image.storage_key
        if path.is_symlink() or not 0 < image.size <= MAX_IMAGE_BYTES:
            raise ValidationError(message)
        with path.open("rb") as handle:
            digest = hashlib.sha256()
            size = 0
            while chunk := handle.read(64 * 1024):
                size += len(chunk)
                if size > image.size:
                    raise ValidationError(message)
                digest.update(chunk)
        if size != image.size or digest.hexdigest() != image.checksum:
            raise ValidationError(message)
    except (ThemeImage.DoesNotExist, OSError, ValidationError) as exc:
        raise ValidationError(message) from exc


def prepare_restoration(record, revision):
    """Revalidate only the current editable schema, never source or version fields."""
    model, fields = settings_model(revision)
    snapshot = revision.snapshot
    # Pre-metadata revisions retain current values for the newly added optional fields.
    required = set(fields) - set(SEO_FIELDS) - set(DISCOVERY_FIELDS) - set(PAGE_FIELDS) - set(FEED_COPY_FIELDS) if model is SiteContent else set(fields)
    if not isinstance(record, model) or not isinstance(snapshot, dict) or not required <= snapshot.keys() or revision.version >= record.version:
        raise ValidationError(_("This saved version is incompatible with the current settings. No changes were made."))
    target = copy.deepcopy(record)
    for field in fields:
        if field in snapshot:
            setattr(target, field, snapshot[field])
    target.full_clean()
    if model is SiteTheme:
        _check_background(target.background_image_id)
    changes = {field: getattr(target, field) for field in fields if getattr(record, field) != getattr(target, field)}
    return target, changes


@transaction.atomic
def restore_settings(*, actor, revision_id, expected_version, confirmed=False):
    require_owner(actor)
    if not confirmed:
        raise ValidationError(_("Confirm the restoration before applying these settings."))
    source = ContentRevision.objects.get(pk=revision_id)
    model = settings_model(source)[0]
    if model is SiteTheme:
        # Match upload lock order and coordinate with future reference-aware cleanup.
        lock_media_quota()
    current = model.objects.select_for_update().get(pk=1)
    if current.version != expected_version:
        raise EditConflict
    _target, changes = prepare_restoration(current, source)
    if not changes:
        return current
    snapshot = _snapshot(current)
    snapshot["restored_from_revision"] = str(source.pk)
    before = ContentRevision.objects.create(entity=source.entity, entity_id="1", version=current.version, actor=actor, snapshot=snapshot)
    updates = {**changes, "version": F("version") + 1}
    if model.objects.filter(pk=1, version=expected_version).update(**updates) != 1:
        raise EditConflict
    AuditEvent.objects.create(actor=actor, action="restore_settings", entity=source.entity, entity_id="1", changed_fields=sorted(field.removesuffix("_id") for field in changes), revision=before)
    current.refresh_from_db()
    return current
