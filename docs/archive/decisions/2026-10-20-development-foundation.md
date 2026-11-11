> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Development foundation — 20 October 2026

Status: provisional implementation choices, reviewable before production.

The owner requested reading the docs and starting development on 20 October.
This authorises local implementation; it does not resolve the outstanding
account conversion, provider, visual identity or production decisions.
The earlier documentation-only deliverable remains preserved as historical scope.

Use the proposed Python/Django 5.2 LTS/PostgreSQL stack. Django is pinned to
5.2.18, the [6 October security patch](https://docs.djangoproject.com/en/5.2/releases/5.2.18/).
`uv.lock` pins transitive dependencies; `requirements.lock` exports hashes for
the Docker build. Base image digests remain a production release requirement.

The first increment covers WP-02 and part of WP-04/05. WP-01's live API proof
is deferred without blocking synthetic local development. The importer has no
implementation or credentials; no personal-account scraping is introduced.

Contracts for this increment:

- Feed order follows the original functional source: effective display date,
  source date, then UUID, descending. Priority is stored but does not change feed
  order until D-06 is resolved. Signed keyset cursors keep unchanged datasets
  stable; page size defaults to 12 and is constrained to 1–48.
- Source account/post identity is unique. Source captions are preserved;
  a nullable editorial caption is separate and stays in the original language.
  Imports and source revisions are deferred; no UI can currently overwrite them.
- Public reads target owner-defined database views. Published, due posts require
  validated media. Public PostgreSQL credentials have only SELECT on four
  public views; base content, auth, sessions and agent/account tables are denied.
- Local PNG/JPEG/WebP input is decoded and re-encoded to PNG with byte/pixel
  limits. Only validated PNG assets are delivered, through a publication-gated
  endpoint. Embeds, video, uploads and remote downloads remain later work;
  the preferred embed policy has not changed.
- EN/FR URLs, packaged labels, cookie preference and site-copy fallback are
  implemented. English and Europe/London are provisional defaults. Site copy is
  plain text with output escaping until a controlled editor is built.
- Contact accepts no submissions and returns an honest unavailable state.
  Accepted/Failed/Unknown delivery, provider idempotency, shared throttling and
  privacy text must be implemented together before enabling it.
- Reviews have a provisional manually managed schema and public read model;
  no submission form or administrative review editor exists yet. Confirm D-04
  before implementing the editorial workflow.
- The public URL map never mounts admin. A local-only Django admin foundation
  is separate; production admin is blocked until throttling, audit, stale-write
  controls and least-privilege writes are implemented.

SQLite is explicitly local-only and cannot demonstrate role isolation. PostgreSQL
is required outside `APP_LOCAL=1`. Development Compose uses disposable credentials
and a privileged migration identity. Its optional admin service uses that identity
for local scaffolding only; do not deploy this Compose file to production.
