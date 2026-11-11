"""Read-only media reconciliation. Reports never authorize deletion or quota repair."""
import hashlib
import os
import re
import stat
from collections import Counter
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from .media import MAX_IMAGE_BYTES
from .models import ContentRevision, MediaAsset, MediaQuota, SiteTheme, ThemeImage

KEY = re.compile(r"[0-9a-f]{32}\.png\Z")
CHECKSUM = re.compile(r"[0-9a-f]{64}\Z")
ISSUE_LIMIT = 200


def audit_media(*, verify=False):
    started_at = timezone.now().isoformat()
    issues, counts = [], Counter()

    def issue(code, **references):
        counts[code] += 1
        if len(issues) < ISSUE_LIMIT:
            issues.append({"code": code, **references})

    assets, by_id, by_key = [], {}, {}
    columns = ("id", "storage_key", "checksum", "size", "validated", "mime_type")
    for kind, model in (("story", MediaAsset), ("theme", ThemeImage)):
        fields = (*columns, "active") if kind == "story" else columns
        for record in model.objects.order_by("id").values(*fields).iterator(chunk_size=500):
            asset = {"kind": kind, "id": str(record["id"]), "storage_key": record["storage_key"], "recorded_bytes": record["size"], "checksum": record["checksum"], "current": bool(record.get("active", False)), "history_references": 0}
            reference = {"kind": kind, "asset_id": asset["id"]}
            if not KEY.fullmatch(asset["storage_key"]):
                issue("invalid_storage_key", **reference)
                asset["storage_key"] = None  # Never expose or traverse arbitrary stored paths.
            if not record["validated"] or record["mime_type"] != "image/png" or not 0 < record["size"] <= MAX_IMAGE_BYTES or not CHECKSUM.fullmatch(record["checksum"]):
                issue("invalid_asset_metadata", **reference)
            assets.append(asset)
            by_id[kind, asset["id"]] = asset
            if asset["storage_key"]:
                if asset["storage_key"] in by_key:
                    issue("duplicate_storage_key", **reference)
                by_key.setdefault(asset["storage_key"], []).append(asset)

    def reference(kind, value, *, revision=None, storage_key=None, seen=None):
        context = {"revision_id": str(revision.pk)} if revision else {"source": "current_theme"}
        try:
            identifier = str(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            issue("invalid_media_reference", **context)
            return
        asset = by_id.get((kind, identifier))
        if not asset:
            issue("missing_asset_reference", kind=kind, asset_id=identifier, **context)
            return
        if revision:
            marker = (kind, identifier)
            if marker not in seen:
                asset["history_references"] += 1
                seen.add(marker)
            if storage_key is not None and storage_key != asset["storage_key"]:
                issue("history_storage_key_mismatch", kind=kind, asset_id=identifier, **context)
        else:
            asset["current"] = True

    for identifier in SiteTheme.objects.exclude(background_image_id=None).values_list("background_image_id", flat=True):
        reference("theme", identifier)
    for revision in ContentRevision.objects.only("id", "entity", "snapshot").order_by("id").iterator(chunk_size=500):
        snapshot = revision.snapshot
        if not isinstance(snapshot, dict) or revision.entity not in {"presentation_item", "site_theme", "site_content"}:
            issue("unsupported_history", revision_id=str(revision.pk))
            continue
        seen = set()
        if "media" in snapshot:
            if not isinstance(snapshot["media"], list):
                issue("invalid_media_reference", revision_id=str(revision.pk))
            else:
                for media in snapshot["media"]:
                    if not isinstance(media, dict):
                        issue("invalid_media_reference", revision_id=str(revision.pk))
                        continue
                    reference("story", media.get("id"), revision=revision, storage_key=media.get("storage_key"), seen=seen)
        if snapshot.get("background_image_id") is not None:
            reference("theme", snapshot["background_image_id"], revision=revision, seen=seen)

    observed, untracked, observed_bytes, unexpected_entries = {}, [], 0, 0
    free_bytes = None
    try:
        root_fd = os.open(settings.PRIVATE_MEDIA_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        issue("storage_unavailable")
    else:
        try:
            filesystem = os.fstatvfs(root_fd)
            free_bytes = filesystem.f_bavail * filesystem.f_frsize
            with os.scandir(root_fd) as entries:
                for entry in entries:
                    managed_name = bool(KEY.fullmatch(entry.name))
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        issue("unreadable_entry")
                        continue
                    regular = stat.S_ISREG(info.st_mode)
                    if regular:
                        observed_bytes += info.st_size
                    if not managed_name:
                        unexpected_entries += 1
                        issue("unexpected_entry")
                        continue
                    file = {"bytes": info.st_size, "state": "not_verified" if regular else "unsafe"}
                    observed[entry.name] = file
                    if not regular:
                        issue("unsafe_entry", storage_key=entry.name)
                    elif entry.name not in by_key:
                        untracked.append({"storage_key": entry.name, "bytes": info.st_size})
                        issue("untracked_file", storage_key=entry.name)
                    elif verify:
                        try:
                            # Reject links and FIFOs even if the entry changed after stat().
                            fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
                            with os.fdopen(fd, "rb") as handle:
                                before = os.fstat(handle.fileno())
                                if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_IMAGE_BYTES:
                                    file["state"] = "unsafe"
                                else:
                                    digest, size = hashlib.sha256(), 0
                                    while chunk := handle.read(64 * 1024):
                                        size += len(chunk)
                                        if size > MAX_IMAGE_BYTES:
                                            break
                                        digest.update(chunk)
                                    after = os.fstat(handle.fileno())
                                    if size > MAX_IMAGE_BYTES or (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or size != before.st_size:
                                        file["state"] = "changed_during_scan"
                                    else:
                                        file.update(state="verified", checksum=digest.hexdigest(), bytes=size)
                        except OSError:
                            file["state"] = "unreadable"
        except OSError:
            issue("storage_scan_failed")
        finally:
            os.close(root_fd)

    for asset in assets:
        file = observed.get(asset["storage_key"])
        state = file["state"] if file else "missing"
        if file and file["bytes"] != asset["recorded_bytes"]:
            state = "size_mismatch"
        elif file and state == "verified" and file["checksum"] != asset["checksum"]:
            state = "checksum_mismatch"
        asset["file_state"] = state
        asset["reference_state"] = "current" if asset["current"] else "history" if asset["history_references"] else "retained"
        if state not in {"verified", "not_verified"}:
            issue("file_" + state, kind=asset["kind"], asset_id=asset["id"])

    registered_bytes = sum(asset["recorded_bytes"] for asset in assets)
    quota_bytes = MediaQuota.objects.filter(pk=1).values_list("bytes_used", flat=True).first()
    if quota_bytes is None:
        issue("quota_missing")
    elif registered_bytes != quota_bytes:
        issue("quota_mismatch")
    return {
        "schema_version": 1, "started_at": started_at, "generated_at": timezone.now().isoformat(), "verify_requested": verify,
        "summary": {"asset_count": len(assets), "recorded_bytes": registered_bytes, "quota_bytes": quota_bytes,
                    "budget_bytes": settings.MEDIA_STORAGE_LIMIT_BYTES, "budget_warning": registered_bytes * 5 >= settings.MEDIA_STORAGE_LIMIT_BYTES * 4,
                    "observed_file_bytes": observed_bytes, "filesystem_free_bytes": free_bytes,
                    "untracked_file_count": len(untracked), "unexpected_entry_count": unexpected_entries,
                    "reference_counts": dict(Counter(asset["reference_state"] for asset in assets))},
        "assets": assets, "untracked_files": sorted(untracked, key=lambda value: value["storage_key"]),
        "issue_counts": dict(sorted(counts.items())), "issues": issues,
        "issues_truncated": sum(counts.values()) > len(issues), "ok": not counts,
    }
