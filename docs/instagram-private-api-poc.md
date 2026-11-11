> Website integration is available: [connect and import through owner settings](instagram-connection.md). This page describes the retained standalone PoC.

# Instagram private API proof of concept

This owner-requested PoC evaluates `instagrapi` as the foundation of the website’s isolated Instagram service. It provides a local settings page and reusable read
functions. It does not enable scheduled imports or publish to the website.
It is an experiment with an unofficial integration, not verification of the
functional specification's approved-integration/platform-terms requirement.

## Start the settings page

From the repository root:

```bash
UV_CACHE_DIR=/tmp/instagram-poc-uv uv sync --project agent/instagram_poc --frozen
./tools/instagram-poc
```

Open **http://127.0.0.1:8768/**. Enter the **operator password printed in the
terminal**. This password is generated on every launch and is different from
your Instagram password. Keep the terminal private. Ctrl+C stops the server.
Dependencies are installed in a separate virtual environment; the main website
dependencies remain separate from this diagnostic tool.

1. Enter your Instagram username and password; select **Save account details**.
   Saving alone does not contact Instagram. A blank password retains the existing
   password only for the same username. Changing usernames starts a separate
   empty PoC record; the previous account's cache/session is not carried over.
2. Select **Connect & verify** to authenticate and confirm account identity.
3. If prompted for two-factor authentication, enter a fresh code and connect
   again. The pending client remains in memory for up to five minutes; restarting
   the tool requires restarting login. Account challenges/password changes must
   be resolved directly in Instagram. No automatic challenge solver is enabled.
4. Choose a page size (1–50) and **Fetch posts**. Select **Next page** to continue,
   or **Recent posts** to start again. A post ID is updated in place; the PoC
   retains at most 100 normalized posts, evicting older cache entries at capacity.
5. Inspect captions and source records; **Refresh** retrieves a post again.
   **Download** stages media in private operator storage. **Export JSON** exports
   the normalized cache without passwords, session settings or provider cursors.

These are synchronous actions and can take time. Avoid submitting them repeatedly.
The server serializes requests and storage operations. It performs no scheduled
polling, posting, likes, follows, messaging or comment-management operations.
Read responses can contain incidental comment metadata inside the SDK; the
normalized output does not retain it. The login flow can make Instagram's own
supporting authentication requests.

This address is local to the machine running the tool. It is not added to the
public website, owner portal, Docker Compose, or Tailscale reverse proxy. For
remote use, forward the port through SSH rather than exposing the listener:

```bash
ssh -L 8768:127.0.0.1:8768 your-user@your-host
```

Then open the same loopback URL on your computer. No host infrastructure changes
are needed. Do not reverse proxy or publish this development server.

## Storage and access

Defaults:

- Encrypted account/password/session/cache:
  `~/.local/share/mysite-instagram-poc/private-api.fernet`
- Separate encryption key:
  `~/.config/mysite-instagram-poc/private-api.key`
- Private downloaded media:
  `~/.local/share/mysite-instagram-poc/downloads/`

`--data-dir`, `--key-dir` and `--port` override these defaults. Credential paths
must be outside the repository and its website source mount, without symlinks.
Directories require mode 0700; key and encrypted files require mode 0600. Do not
mount them into web/admin containers. The encrypted record uses authenticated
Fernet encryption and atomic replacement, using the shared private operator store.
Back up the encrypted record and key separately. Downloaded binaries are private
files, not encrypted, and are not served by this tool.

The local page requires an unpredictable launch password, a 30-minute browser
session and CSRF tokens. Host/origin checks restrict it to the loopback URL.
Response caching and framing are disabled. Captions are escaped. Passwords,
sessions and raw SDK errors are never returned to the page or exported; access
logging/debug mode are disabled. The local OS operator/root remains trusted.

Downloads accept only cached provider HTTPS URLs on supported Instagram/Facebook
CDN subdomains, reject redirects, use timeouts, and stage before validation.
Images are checked with Pillow; videos have a preliminary MP4 container signature
check. Limits are 20 MiB/image and 100 MiB/video, with a 500 MiB effective maximum
download budget (a new download is refused once existing files exceed 400 MiB).
A failed download removes its staging file. MP4 checks do not replace a production
media scanner/transcoder. Signed media URLs may expire; refresh the post first.
No arbitrary URL downloader or API proxy is exposed.

## Reusable functions

`agent/instagram_poc/service.py` contains an HTTP-independent adapter:

| Function | Purpose |
| --- | --- |
| `save_account(username, password)` | Encrypt configuration; retain same-account password if blank |
| `connect(verification_code='')` | Login/reuse session; verify username and pinned account ID |
| `status()` | Return safe configuration status and normalized cache |
| `fetch_posts(limit=12, next_page=False)` | Fetch one account-media page and update cached source records |
| `fetch_post(post_id)` | Refresh a single post, checking source account ownership |
| `download_media(post_id, asset_index=0, thumbnail=False)` | Stage a cached asset in private downloads |
| `normalize_media(media, account_id)` | Map SDK media to the versioned source record |

Example initialization inside this isolated environment:

```python
from pathlib import Path
from agent.instagram_poc.storage import PocStore
from agent.instagram_poc.service import InstagramService

service = InstagramService(PocStore(
    Path.home() / '.local/share/mysite-instagram-poc',
    Path.home() / '.config/mysite-instagram-poc',
))
# After provisioning and connecting through the settings page:
page = service.fetch_posts(limit=12)
for item in page['items']:
    source_key = (item['source_platform'], item['source_account_id'], item['source_post_id'])
    # Future adapter: upsert a source revision using source_key.
```

The normalized JSON contract contains `schema_version`, `source_platform`,
`source_account_id`, `source_post_id`, `source_url`, `source_published_at` (UTC),
`original_caption`, `media_type`, `assets`, and `fetched_at`. Each asset has a
kind and image/video URL references. These URLs are temporary source references,
not durable local media paths. Exports contain source content and should be
handled accordingly.

The PoC uses explicit authenticated mobile read methods. It does not rely on
anonymous public scraping. Reads do not automatically perform fresh password
logins. Account restrictions stop the operation; failures preserve the last good
encrypted cache. A saved session is not a guarantee of current access.

## Extending into the project

Keep the service outside the public runtime. Add a dedicated ingestion identity
and database adapter that uses the unique source key, retains source revisions,
and preserves owner display overrides. Add a bounded look-back policy for caption
edits, media quarantine/transcoding, publication readiness, source-availability
handling, scheduler overlap protection, backoff and redacted run metrics.

Account feeds can include pinned/ranked posts. Do not assume the first old-looking
post proves the scan complete. This PoC's small cache/cursor is not a durable
production checkpoint, complete archive, revision history or deletion detector.
The preferred official-embed path still needs its own proof and CSP/privacy work;
this PoC tests media metadata and local download staging.

## Verification

```bash
agent/instagram_poc/.venv/bin/python -m unittest discover -s agent/instagram_poc/tests -v
```

Tests use synthetic SDK responses and local image bytes. They cover encryption,
redaction, identity mismatch, MFA continuation, cache upserts/pagination, safe
failure, account switching, input bounds, corruption, browser authentication,
CSRF/host/origin checks, caption escaping, JSON export and download checks.
The real installed SDK was also imported and its settings serialization and
method signatures checked without network requests. No real Instagram account
has been connected by this implementation; live login and media coverage remain
operator acceptance steps. Browser visual QA was unavailable in this session;
HTTP/template/form behavior was exercised with Flask's test client. A real
loopback server smoke check also passed operator login, settings-page rendering
and response-header checks using temporary storage; that server was stopped.
