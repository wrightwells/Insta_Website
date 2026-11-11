> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Public metadata and discovery — 20 October 2026

Status: implemented locally for WP-04 and AC-036/071 portions. Production indexing,
identity/domain approval and browser/accessibility acceptance remain outstanding.

The owner can edit English/French titles and descriptions for Feed, Reviews and
Contact in **Site copy**. Fields are optional plain text, limited to 160 characters
for titles and 320 for descriptions. Preview shows each page/language without
saving. Edits share the existing version check, atomic audit and immutable
revision workflow. Confirmed settings restoration also restores metadata. A
pre-metadata revision preserves the current optional metadata values while
restoring its recorded site-copy fields; missing required legacy fields still
reject restoration.

Public HTML emits escaped title/description, absolute canonical and alternate
language URLs, a default-language alternate, Open Graph and summary-card metadata.
Blank/whitespace metadata falls back through the requested/default/other language,
then the page label/site name and introduction. Metadata whitespace is normalized;
post captions remain unchanged. The first eligible public feed image supplies a
social image/alt/size when available. Hidden, draft, future or replaced media stay
behind the existing publication gate and disappear from metadata on the next
request. Reviews/contact use a text card when no public page image is selected.

`PUBLIC_ORIGIN` is operator configuration. It accepts an absolute HTTPS origin
without credentials, path, query or fragment; local development also accepts
HTTP. Canonical/sitemap/social URLs never derive from Host or forwarding headers.
Local Compose defaults to `http://localhost:8000`; the environment can override
that origin before recreating services. Production has no implicit origin. With
no origin, canonical links are omitted and the sitemap returns 503.

`PUBLIC_INDEXING_ENABLED` defaults off. Enabling it requires non-local mode and a
configured HTTPS origin. Local Compose fixes it off. Local/error/administration
responses remain `noindex`; admin robots always disallows crawling and admin has
no sitemap route. Public `/robots.txt` disallows all while indexing is off. An
explicitly enabled public runtime advertises the configured sitemap. This is
readiness configuration, not an assertion that search engines will index a page.

`/sitemap.xml` lists only enabled-language feed/reviews URLs and reciprocal
language/default alternates. It omits contact while contact returns 503, signed
pagination, management, health and media routes. It does not invent modification
dates. The sitemap remains inspectable locally while robots/indexing stay off.
Signed pagination retains its own validated cursor in canonical/alternate URLs
and remains `noindex`; unsafe/invalid cursors do not receive canonical links.

The locale preference policy is now shared between public/admin entry points:
valid enabled-language cookie, highest-priority enabled browser preference, then
the configured default. This fixes the public landing page choosing global English
when no actual browser preference was supplied and the site default was French.

Migration `0007` adds twelve optional public-copy fields, recreates the narrowly
scoped public settings view, restores its public SELECT grant and grants admin
UPDATE only on the new columns. Apply the migration before the new application
code. An application rollback can retain this compatible additive schema.
Reversing `0007` removes the new live metadata columns; use that operation only
in a disposable verification database. Core copy, versions and immutable JSON
history survive that reversal, including metadata already preserved in snapshots.

Verification on 20 October 2026:

- All 94 PostgreSQL tests pass. SQLite passes 88 with six explicit PostgreSQL
  skips. Fourteen new tests cover origin validation, localization/fallback,
  escaping, host isolation, social publication gates, sitemap/robots, index opt-in,
  cursor metadata, safe failure, owner preview/edit/restore, legacy revisions,
  validation limits, French labels and real database-role grants.
- `0007` reversal/reapplication on synthetic PostgreSQL and SQLite preserved core
  copy/version and audit/revision rows, restored the public view and retained
  metadata in immutable snapshots. No live schema reversal was performed.
- Real HTTP using packaged `public_dev`/`admin_dev` runtimes passed French login,
  metadata preview/save, public/social tags, sitemap/robots, audited restoration
  and stale 409 in disposable PostgreSQL. Synthetic credentials were not displayed
  or exported. Temporary verification services were removed.
- Development/testing happened in an isolated source copy. After tests/builds,
  the additive live migration preceded code deployment. The existing one owner,
  three posts, two audit events, zero revisions and 32,870 quota bytes were
  preserved. Live metadata/sitemap/robots/login/health checks pass; media checksum
  audit remains clean. No live owner metadata was edited during testing.
- Django checks, migration drift, catalog verification, Compose validation and
  development image builds pass. There are no dependency changes. Browser tools
  reported no connected browser; visual, keyboard and screen-reader QA remain open.

Primary guidance: [canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls),
[sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
and [noindex](https://developers.google.com/search/docs/crawling-indexing/block-indexing).
These inform URL/indexing signals; local implementation and tests supply the
evidence recorded above.
