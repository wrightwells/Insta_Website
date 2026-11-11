> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Privacy policy preparation — 23 October 2026

Update, 11 November 2026: the current policy is editable at `/manage-local/policy/`.
Its contact email is now `ReginnalGreatDane@outlook.com`. The policy-only service
reads the published artifact from a read-only volume, and saved changes are visible
without rebuilding its image. See [current policy editing](../../site-policy.md).
The notes below describe the original preparation.

The owner encountered Meta's required Privacy Policy URL field and supplied
`ReginaldGreatDane@outlook.com` as the public privacy/deletion contact. The operator's
personal/business name has not been supplied; the policy identifies the app as
MySite and provides the supplied contact rather than inventing an identity.

The reviewable policy is at the existing private HTTPS `/privacy/` route:
https://dell-linux-mint.bandicoot-pumpkinseed.ts.net/privacy/

Source: `web/public/templates/public/privacy.html`. A footer link is included in
English and French website chrome. The policy itself is currently English. It
accurately distinguishes the private preview, token verification and future
imports, explains data categories, purpose, access storage, cookies, technical
request processing, retention limitations, revocation and email deletion requests.
It sets no invented legal deadline or retention schedule and makes no claim of
Meta acceptance or legal certification. Owner review remains necessary before
public publication. Privacy text must be updated as functionality changes.

## Prepared isolated publication service

Compose profile `privacy` builds `deploy/privacy/Dockerfile` and runs the static
policy service on **127.0.0.1:8003**. Its image contains only Python, a narrowly
routed server and the policy artifact. There are no source/data/secret mounts,
database dependencies or credentials. It runs as UID 10001 with a read-only
filesystem, capabilities dropped, no privilege escalation, memory/PID limits.

Only GET/HEAD `/privacy/` and `/robots.txt` are served. Other paths return 404;
there is no directory listing or website reverse proxy. The standalone service
sets restrictive CSP, no-store, no-referrer and nosniff, and sets no cookies or
request logs. Robots allows `/privacy/` while disallowing other paths. Its privacy
page has no scripts, forms or third-party resources.

```bash
docker compose --profile privacy up -d --build --wait privacy
```

## Public access requires an explicit exception

The owner's standing choice is tailnet-only website access. A policy URL that
only tailnet members can reach is not a publicly reachable Meta policy URL.
Publishing this policy is therefore a separate scope decision, not authorization
to expose the whole site.

One prepared option is Funnel on **8443**, targeting **127.0.0.1:8003**, with the
candidate URL:
`https://dell-linux-mint.bandicoot-pumpkinseed.ts.net:8443/privacy/`.
This has not been enabled and Meta acceptance of this non-default HTTPS port has
not been tested. Standard-port public static hosting is an alternative if Meta
rejects it. Before any apply, inspect/snapshot all Serve state, verify port 8443
is unused and preserve existing 443 and other-host routes exactly. Public 8443
must target only the isolated policy service. Never enable Funnel on existing
port 443, because that would make the private website publicly reachable.

After any approval and activation, verify public policy access without tailnet
credentials, 404s for non-policy routes on 8443, preservation of private 443 and
other-host settings, and Meta's URL validation. Existing `configure_tailnet.py`
currently rejects all Funnel exposure; it must be revised to explicitly allow
only this approved isolated policy endpoint if publication proceeds. Do not use
Serve/Funnel reset. No public access was enabled during preparation.

## Verification

- Django checks and whitespace checks pass.
- Real private HTTPS `/privacy/` returns 200, contact/deletion text and no cookie,
  scripts or forms.
- The independent policy image builds and is healthy. Local HTTP checks pass
  policy/robots/HEAD and restrictive headers. Root, feed, owner, media and
  filesystem-probing paths return 404.
- Serve state remains unchanged: MySite's root is private on 443; the other-host
  route is preserved; there is no AllowFunnel entry.
