> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Confirmed settings restoration — 20 October 2026

Status: implemented locally for site copy and appearance. Production review,
retention policy and integration decisions remain outstanding.

The next WP-06 increment implements the settings recovery described in technical
specification sections 13 and 17. From **Site copy** or **Appearance**, choose
**View settings history**, open a previous version, then **Review restoration**.
The comparison shows changed fields and background previews. A checked
confirmation and CSRF-protected POST are required before applying the saved
values. GET requests only display the comparison.

Restoration applies only the current allowlisted `SiteContent`/`SiteTheme`
settings schema. Source captions, story publication, accounts, recipients and
credentials are outside this operation. Old values are revalidated against the
current model rules, including enabled/default locale, page size, approved fonts
and contrast. Incompatible snapshots produce an error rather than a partial save.

The operation locks the current record and requires the version displayed by the
comparison. A competing edit or restoration returns HTTP 409 and requires a fresh
comparison/confirmation. Theme restoration follows the existing quota-before-theme
lock order. A retained background must have a valid PNG record, a
non-symlink file within the image size bound, and matching size/SHA-256. Missing
or damaged images reject the whole restoration. Existing retained binaries are
reused; quota usage does not increase and no image is deleted.

A successful change increments the current version and appends a revision of the
displaced state plus a `restore_settings` audit event in one database transaction.
The new revision's reserved `restored_from_revision` metadata identifies the
immutable source revision. The event links to the displaced state, and history
also links to the source, so both directions remain inspectable. The displaced
state can be restored through the same confirmation flow. Matching values are a
no-op and do not create duplicate history. Audit failure rolls back all writes.
Existing history triggers and database grants remain unchanged; this increment
adds no database migration or dependency.

The new comparison, confirmation, failure and success messages are packaged in
English and French. The post-restoration redirect recomputes the enabled language
from the saved settings. Settings history links filter the latest 100 audit events
by settings entity so unrelated story edits do not crowd out these entries.

Verification on 20 October 2026:

- All 64 PostgreSQL tests pass; SQLite passes 60 with four explicit role skips.
  Fifteen new tests cover confirmation/owner/CSRF, safe comparison output,
  validation, stale writes, audit rollback, restoration provenance and reversibility,
  no-ops, retained backgrounds, corruption/symlinks, French messages and locale
  changes. PostgreSQL checks exercise site and theme restoration as `site_admin`
  while history mutation and settings deletion remain denied.
- A disposable PostgreSQL concurrency probe using `site_admin` produced one
  committed restoration and one conflict from two requests for the same version.
- A real HTTP service from the rebuilt admin image using `admin_dev` passed French
  login/comparison, explicit confirmation, site/theme restoration, source-history
  links and stale 409. Synthetic owner credentials existed only in disposable
  verification state and were not displayed or exported.
- Docker build, Compose validation, Django public/admin checks, migration drift,
  catalog completeness/compiled output and whitespace checks pass. Live previews
  passed health, feeds, reviews, login, CSS and public/admin route isolation checks.
  The existing three posts, media and owner state were preserved.
- Browser tools returned no connected apps/browsers. Visual, responsive, keyboard
  and screen-reader checks remain unverified. Both local preview services remain
  running; only temporary verification services were removed.
