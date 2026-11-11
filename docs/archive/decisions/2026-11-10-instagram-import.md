> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Owner-selected Instagram connection and recent imports

The owner confirmed the instagrapi PoC works and requested website integration,
removal of Meta OAuth/token setup, and loading recent post images/text into the
public site. This decision supersedes the earlier integration recommendation.

The existing owner-only `/manage-local/instagram/` route now provides account
configuration, connection verification/MFA and recent-post imports. A private,
authenticated control API isolates encrypted Instagram credentials and SDK sessions
from Django. Only admin and the agent share its Docker network/control capability;
the public container has no route or credential/control mounts. The working
prototype encrypted record/key were transferred separately without decryption.
No default-location legacy Meta credential files existed. The old Graph client,
token CLI and active registration instructions were retired.

The owner app orchestrates bounded manual imports. This deliberately extends
`site_admin` to insert source accounts/posts and update source metadata, while
retaining checkpoint secrecy, append-only history and public read-only grants.
Images use existing bounded re-encoding, quotas and publication-gated delivery.
Valid new stories publish automatically; duplicate imports update source values,
retaining owner overrides and publication decisions. Source snapshots and prior
versions are kept without provider credential fields or temporary CDN URLs.
Carousel images display together. Video posts display downloaded cover images;
video playback, embeds, schedules and full archive/deletion reconciliation are
separate future capabilities. The per-batch deadline is ten minutes (plus one
in-flight bounded request), and an individual post's downloaded image data is
limited to 50 MiB. The database lease prevents overlapping owner imports.

Verification: complete 113-test website suites passed on SQLite and PostgreSQL;
15 isolated agent tests passed. An additional importer deadline regression was
added and exercised with the import tests. Checks cover publication and real
public media responses, EN/FR captions, duplicate updates, owner media/status
preservation, failures/leases, PostgreSQL grants, CSRF and credential redaction.
The running owner page was rendered using the existing owner identity and private
service, and actual HTTP checks confirmed public feed availability and protected
management routes. No live Instagram request/import was executed during integration;
the operator's earlier PoC acceptance supplied the account session.

Deployment applies additive migration 0008 and starts the `instagram-agent` and
`admin` services; existing public/DB/media/owner data is preserved. Roll back code
and stop the new services if needed, retaining volumes. Do not reverse populated
schema changes or delete media volumes as part of a routine rollback. The
unofficial integration's platform-term/availability limitations still apply.
