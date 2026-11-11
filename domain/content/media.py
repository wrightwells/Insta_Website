"""Bounded raster decoding and immutable private image files; no URL fetching."""
from django.utils.translation import gettext_lazy as _
import hashlib
import io
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import MediaAsset, MediaQuota, PresentationItem

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    width: int
    height: int


def decode_image(source: BinaryIO) -> PreparedImage:
    raw = source.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValidationError(_("Image exceeds 10 MiB."))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise ValidationError(_("Use a single PNG, JPEG or WebP image within the dimension limit."))
                image.load()
                image = ImageOps.exif_transpose(image)
                output = io.BytesIO()
                clean = Image.new("RGB", image.size)
                clean.paste(image.convert("RGB"))
                clean.save(output, format="PNG")
                width, height = clean.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, ValueError) as exc:
        raise ValidationError(_("Invalid image.")) from exc
    data = output.getvalue()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError(_("Decoded image exceeds storage limit."))
    return PreparedImage(data, width, height)


def lock_media_quota() -> MediaQuota:
    return MediaQuota.objects.select_for_update().get(pk=1)


def remove_private_file(key: str) -> None:
    (Path(settings.PRIVATE_MEDIA_ROOT) / key).unlink(missing_ok=True)


def discard_uncommitted_image(asset) -> None:
    # A connection can fail after the server commits. Do not delete a binary
    # that may already be referenced by a committed record.
    try:
        if type(asset).objects.filter(pk=asset.pk).exists():
            return
    except DatabaseError:
        return
    remove_private_file(asset.storage_key)


def persist_image(model, prepared: PreparedImage, **fields):
    """Caller owns a transaction and cleans up on any later rollback."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Image persistence requires a transaction.")
    quota = lock_media_quota()
    if quota.bytes_used + len(prepared.data) > settings.MEDIA_STORAGE_LIMIT_BYTES:
        raise ValidationError(_("Media storage limit reached. Existing images were retained. Contact your operator."))
    key = f"{uuid.uuid4().hex}.png"
    asset = model(storage_key=key, checksum=hashlib.sha256(prepared.data).hexdigest(), size=len(prepared.data), width=prepared.width, height=prepared.height, validated=True, **fields)
    asset.full_clean()
    root = Path(settings.PRIVATE_MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    path = root / key
    try:
        with path.open("xb") as handle:
            handle.write(prepared.data)
        asset.save()
        quota.bytes_used += len(prepared.data)
        quota.save(update_fields=["bytes_used"])
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return asset


def stage_image(item: PresentationItem, source: BinaryIO, *, alt_en: str, alt_fr: str = "", sequence: int = 0) -> MediaAsset:
    """Migration/fixture helper. Owner uploads use audited upload services."""
    if not alt_en.strip():
        raise ValidationError(_("An image description is required."))
    prepared = decode_image(source)
    asset = None
    try:
        with transaction.atomic():
            asset = persist_image(MediaAsset, prepared, item=item, alt_en=alt_en, alt_fr=alt_fr, sequence=sequence)
        return asset
    except Exception:
        if asset:
            discard_uncommitted_image(asset)
        raise
