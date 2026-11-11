> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Private MySite at the hostname root — 23 October 2026

Status: deployed at the owner's explicit request to replace Box Storage on
`dell-linux-mint.bandicoot-pumpkinseed.ts.net` with MySite.

Current website: https://dell-linux-mint.bandicoot-pumpkinseed.ts.net/

This supersedes the [22 October path deployment](2026-10-22-tailnet-path.md).
Access remains tailnet-only. Funnel is off. The existing Box Storage application
and its data have not been deleted; only its handler on this hostname was replaced.

## Configuration

The Compose `tailnet` service still uses loopback port 8002, the existing database
and private media, restricted `public_dev` credentials and read-only source/media.
`APP_SCRIPT_PREFIX` is empty. Health checks use `/health/`. The explicit HTTPS
origin remains the same, while generated links, metadata, sitemap and assets now
use root paths. The distinct Secure language cookie now has Path `/`.

Current Tailscale Serve handlers:

```text
dell-linux-mint.bandicoot-pumpkinseed.ts.net:443
  / -> http://127.0.0.1:8002

dell-linux-mint.tailf5f423.ts.net:443
  / -> http://100.82.50.120:9119
```

The obsolete `/mysite/` handler was removed. Existing localhost public port 8000
and admin port 8001 remain available. Admin and Instagram OAuth routes are not
exposed by the public service. Instagram is still unconnected.

## Reapply and recovery

```bash
docker compose --profile tailnet up -d --build --wait tailnet
python3 tools/configure_tailnet.py
python3 tools/configure_tailnet.py --apply
```

The helper defaults to a plan. It checks node identity, Funnel state and the exact
expected previous handlers, snapshots the pre-change configuration, replaces only
the approved root and removes only the known legacy MySite path. It compares the
complete resulting configuration to the expected result to verify unrelated
settings remain unchanged. Unexpected drift causes an error requiring inspection.

Actual pre-change snapshot: `/tmp/insta-root-serve-before-v6rvb6co.json` on this host
(mode 0600; temporary files are not a permanent backup). To intentionally restore
Box Storage's root later, inspect current Serve state first, then restore its
known handler with `tailscale serve --bg --yes --https=443 --set-path=/ http://127.0.0.1:8080`.
This restores only that handler; restoring the old path deployment additionally
requires its prior Compose prefix/health settings and path handler. Do not reset
all Serve configuration or delete persistent volumes.

## Verification

On 23 October 2026:

- Compose configuration validates; the rebuilt root-mounted tailnet service is
  healthy. No application/schema/dependency/grant changes were needed.
- Actual HTTPS root redirects to `/en/` and returns MySite rather than Box Storage.
  Canonical metadata uses the root address; linked feed/review pages, images,
  static CSS and theme CSS return success without `/mysite/` paths.
- French locale and persistence work with a Secure root-scoped language cookie.
  The four-entry sitemap uses root URLs; robots still disallows indexing.
- `/mysite/`, `/manage-local/` and `/instagram/callback/` return 404.
- Local public health and local admin login return 200. The existing unconfigured
  contact service remains unavailable (503).
- Exact Serve comparison confirms all unrelated routes/settings are preserved,
  and Serve reports tailnet-only access. Source whitespace checks pass.
- The earlier 110-test PostgreSQL suite passed on 22 October; it was not rerun for
  this configuration-only deployment. Separate-device and visual/accessibility
  checks remain pending.
