> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Owner administration — 20 October 2026

Status: implemented for local development; production review outstanding.

The owner's request to continue the build advances WP-03 and the existing-story
and public-copy portions of WP-06. Account conversion, reviews population, mail
provider, identity and retention decisions remain unchanged.

Use a dedicated owner portal built on Django authentication/session/forms rather
than mounting generic Django model administration. A singleton `SiteOwner` binding
defines the one named owner. Neither `is_staff` nor `is_superuser` alone authorizes
this portal. Operator-only interactive provisioning validates the passphrase,
creates a non-superuser owner, and records a provisioning event.

Django supplies password hashing, session rotation and CSRF foundations; custom
owner authorization, expiry and throttling are explicit application behavior.
References: [Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/),
[Django CSRF](https://docs.djangoproject.com/en/5.2/ref/csrf/).

Authentication contract:

- Reserve shared login attempts under row locks before authentication. Fixed
  15-minute windows permit five per normalized account and twenty per peer IP.
  A successful login resets the account bucket; IP counters include successes.
  This conservative reservation bounds concurrent attempts, instead of counting
  failures after an unbounded number of expensive password checks have started.
- Do not trust arbitrary forwarded client-IP headers. Store only keyed HMAC
  identifiers; an operator cleanup command removes expired counters/sessions.
- Rotate sessions on login, enforce 30-minute idle and 12-hour absolute limits,
  and check the current owner binding and enabled/staff state on requests.
  Logout is a CSRF-protected POST. Production cookie flags remain Secure,
  HttpOnly and SameSite=Strict, preserving the foundation's stricter default.
- No public registration, password export, Instagram provisioning, browser-based
  owner replacement or privilege-changing user editor is provided.

Editorial contract:

- Allow only display caption, dates, priority and status changes for existing
  items. Captions retain their original language. Source fields remain read-only.
  Site-copy forms edit controlled plain-text EN/FR fields and locale/page size.
  HTML is escaped in previews and public pages; raw rich HTML is not enabled.
- Read a version under a row lock and update only if the expected version still
  matches. Stale saves return HTTP 409 and keep submitted values visible.
- Require explicit confirmation before removing a Published story or moving a
  currently public story into the future. Publishing requires validated media.
- Preserve the prior record in an immutable content revision. Update the record,
  increment its version and append a safe field-name-only audit event in one
  transaction. Failure to record history/audit rolls back the editorial write.
  Prior revisions are readable, not editable, through the owner portal.

Database contract:

- `site_admin` may read application owner/auth/content data and manage login
  counters/sessions. User updates are restricted to password hash/last-login
  fields needed by Django authentication. Content updates are column-scoped.
- Owner binding, user privileges, source captions and source-account checkpoint
  data are outside the role's write/read privileges as applicable.
- Audit and revision tables grant SELECT/INSERT only. Database triggers reject
  UPDATE/DELETE even when an application bug or owner-role test attempts them.
  The migration identity remains a separate operator capability.
- New migrations are additive. SQLite temporarily rebuilds public views around
  its site-content table rebuild; existing synthetic content remains intact.

The portal remains local-only pending independent security review, browser and
accessibility verification, production shared-counter load validation, Argon2
tuning, administrative EN/FR labels, operator recovery logging, retention/purge
runbooks and the production proxy/secret contract. Implemented tests are evidence
for portions of the acceptance criteria, not full staging or release sign-off.
