> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Private Tailscale path deployment — 22 October 2026

Status: historical deployment, superseded by the owner-authorized [root deployment on 23 October](2026-10-23-tailnet-root.md). The commands below describe the previous configuration.

Website: https://dell-linux-mint.bandicoot-pumpkinseed.ts.net/mysite/

The owner selected `/mysite/` on the verified node hostname and access only from
Tailscale for now. Preserve the existing HTTPS root, which serves Box Storage,
and the other existing host route. No Funnel/public-internet exposure is enabled.

A separate Compose `tailnet` service uses the public runtime and restricted
`public_dev` login, loopback `127.0.0.1:8002`, source/media read-only mounts and the
existing persistent database/media. The original root-mounted public service on
8000 and local-only owner service on 8001 remain available. The Tailscale service
has no owner portal or OAuth callback route.

`APP_SCRIPT_PREFIX=/mysite` selects an explicit public URL mount. It prefixes
reverse-generated navigation, media/theme paths, sitemap/alternate/canonical
URLs and static assets. Prefix configuration rejects malformed paths, dot/escaped
segments, whitespace, query and fragment. Current support is public-runtime only;
this does not make the local owner portal a production admin deployment.

The tailnet service uses an explicit HTTPS `PUBLIC_ORIGIN`, approved Host values,
`PUBLIC_INDEXING_ENABLED=0` and a distinct `instagram_site_language` cookie with
Secure/HttpOnly/SameSite=Lax and Path `/mysite/`. Its locale preference neither
overwrites nor travels to the Box Storage root. Proxy/forwarding headers cannot
select an arbitrary application prefix or metadata origin. No trust in forwarded
HTTPS headers was enabled for this public-only GET service.

Tailscale Serve strips its mount before proxying. The backend destination restores
it, yielding:

```text
/mysite/ -> http://127.0.0.1:8002/mysite
```

`tools/configure_tailnet.py` prints the plan by default. With `--apply`, it verifies
the node identity, rejects existing Funnel exposure/conflicting path handlers,
snapshots current configuration to a mode-0600 temporary JSON file, merges only
the selected path using the CLI, then verifies all other Serve state is unchanged.
It does not reset Serve or replace Box Storage. The actual pre-change snapshot
from deployment is `/tmp/insta-mysite-serve-before-al72t_8u.json` on this host.

Reapply after source/image changes:

```bash
docker compose --profile tailnet up -d --build --wait tailnet
python3 tools/configure_tailnet.py
python3 tools/configure_tailnet.py --apply
```

The CLI requires operator access to Tailscale. If a conflict/drift check fails,
inspect the current state and snapshot; do not blindly overwrite all Serve config.
To remove this site's route alone, use:

```bash
tailscale serve --bg --https=443 --set-path=/mysite/ off
docker compose --profile tailnet stop tailnet
```

Preserve database/media volumes. Do not use global `tailscale serve reset` or
Docker `down -v` to remove this path.

Verified on 22 October 2026:

- All 110 PostgreSQL tests pass. SQLite passes 102 with eight PostgreSQL-only
  skips. Ten new tests cover validated mount configuration, development static
  CSS, redirects, links/media/canonicals, cookie isolation, sitemap/robots,
  image/background publication gates, localized errors, public-route isolation,
  signed pagination and the actual public database-role boundary.
- The prefixed Docker backend is healthy. Real HTTPS requests through Serve
  passed landing/locale redirects, EN/FR HTML, prefixed links/CSS, PNG delivery,
  theme CSS, reviews, four-page sitemap, robots and secure scoped cookie checks.
- Serve's pre-existing root/other-host handlers were preserved exactly. Box
  Storage's HTTPS root returned its original page. No site locale cookie was sent
  to it. Admin and OAuth callback routes returned 404 under the mounted site.
- Existing localhost public/admin endpoints remain available. There are no schema,
  dependency or database-grant changes, and no Instagram authorization or token
  provisioning occurred. Temporary PostgreSQL verification state was removed.
- Browser tools returned no apps/browsers. Visual, device, keyboard/screen-reader
  review and checks from a separate tailnet device remain unverified. This is a
  private development preview; production release/review and Instagram integration
  remain separate work.

References: [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
and the [Serve proxy implementation](https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go).
