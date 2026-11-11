> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Read-only media reconciliation — 20 October 2026

Status: implemented as an operator command. Retention/deletion policy, scheduled
monitoring, complete backups and production review remain outstanding.

The next WP-05/06 increment adds `audit_media`, providing storage reconciliation
before reference-aware cleanup or backup work. It reports registered story/theme
assets, current and historical references, retained records without an explicit
reference, untracked files, recorded/quota bytes and available filesystem space.
The command never changes files, publication, quota accounting or history.

Run it with the migration/operator identity. Public/admin runtimes reject the
command. PostgreSQL runs the report in a repeatable-read, read-only transaction;
a test deliberately attempts a database write and confirms it is rejected. The
Compose `media-audit` tool mounts source/media read-only, has a read-only root
filesystem, and publishes no network port.

The schema-versioned JSON report contains opaque record/revision IDs, safe
managed storage keys, sizes, checksums, reference counts and issue codes. It does
not include captions, descriptions, user/account data, arbitrary unexpected
filenames, file contents, absolute storage paths or raw exception messages.
Detailed issues are capped at 200, with complete aggregate counts and a truncation
flag. Asset and untracked-file inventories remain complete.

References are extracted from current active story assets, the current theme
background, historical story `media` arrays and historical `background_image_id`
values, including settings states displaced by restoration. Unknown history
schemas, dangling/invalid references and mismatched historical keys are reported.
Registered records without an explicit current/history reference remain retained;
this report supplies no deletion authorization or automatic garbage collection.
Untracked files may reflect a crash or a concurrent upload that has not committed.

Metadata scans compare presence and sizes and explicitly label file checksums as
`not_verified`. `--verify` streams registered files in bounded chunks and compares
SHA-256, size and file stability. The scanner rejects symlinks, directories and
FIFOs without reading them, confines file access to an opened storage-directory
handle, and refuses arbitrary database paths. Untracked/unexpected files are
counted without reading their contents. Corruption, unavailable storage,
invalid asset metadata, cross-table duplicate keys and quota drift produce issue
codes. `--check` exits unsuccessfully after writing the JSON if issues exist.

Database records are consistent within the report transaction. Filesystem
observations span `started_at` through `generated_at`; a concurrent writer can
create a file after the database snapshot. Pause writers for operational
reconciliation or a backup preflight, then recheck before taking any action.
`observed_file_bytes` totals regular files immediately inside managed storage;
unknown subdirectories are reported without recursion. The free-space reading
covers the underlying filesystem. Full backup consistency, encryption, restore
verification, retention periods and alert destinations need separate work.

Verified on 20 October 2026:

- All 80 PostgreSQL tests pass. SQLite passes 75 with five explicit PostgreSQL
  skips. Sixteen new tests cover current/history/retained references, checksum
  versus metadata modes, missing/corrupt/unsafe files, untracked files, storage
  path/root safety, broken history, duplicate keys, quota drift, bounded issue
  detail, runtime restriction, command exit behavior and read-only transactions.
- The packaged read-only Docker tool completed against the existing development
  preview: all three current media files verified, 32,870 bytes matched quota,
  and no untracked files, unexpected entries or discrepancies were found.
- Database/schema/dependency versions are unchanged. Django public/admin checks,
  migration drift, catalog verification, Compose validation and Docker builds pass.
  Both local previews were refreshed, retaining existing posts, owner and media.
- Temporary PostgreSQL verification state was removed after the tests. No live
  file, record, quota or publication was repaired/deleted by the audit.
