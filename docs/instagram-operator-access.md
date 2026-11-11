# Instagram operator setup

Use the current [website connection flow](instagram-connection.md). The retired
Meta dashboard/token provisioning and refresh command is no longer provided.
Do not supply Meta developer tokens, app secrets or callback addresses.

## Docker (current website)

```bash
docker compose --profile administration build instagram-agent
docker compose run --rm migration python manage.py migrate --noinput
docker compose --profile administration up -d --wait instagram-agent admin
```

The migration extends `site_admin` with the source/import writes needed for
owner-triggered imports. Checkpoint contents, user privilege changes and history
mutation remain denied; `site_public` reads publication views and has separate limited writes for contact delivery metadata.
No credentials are added to source-account checkpoints.

New installations still require the normal owner account provisioning in the
[installation guide](../INSTALL.md). Existing installations retain that account.
Do not use the standalone PoC's terminal password on the website owner login.

Persistent Docker volumes:

- `instagram-data`: encrypted `private-api.fernet` and private staging downloads.
- `instagram-key`: separate `private-api.key` encryption key.
- `instagram-control`: private `control.key`, readable only by agent/admin UID
  10001, mounted read-only in admin. It authenticates internal control requests.
- Existing `private-media`: website PNGs; mounted read-only in the public services.

Never mount `instagram-data` or `instagram-key` into admin/public services. Back up
the encrypted record and its key separately. The credential directories are 0700
and files are 0600. Do not use `docker compose down -v` to restart the application.
The Instagram service runs one worker to retain the pending MFA client safely;
restart requires repeating an unfinished two-factor flow.

## Local Python without Docker

```bash
UV_CACHE_DIR=/tmp/instagram-poc-uv uv sync --project agent/instagram_poc --frozen
./tools/instagram-agent
# In another terminal:
APP_LOCAL=1 APP_RUNTIME=admin uv run manage.py runserver 8001 --insecure
```

The service binds to 127.0.0.1:8769, using the PoC's existing default encrypted
store outside the repository. It creates a separate private control key at
`~/.local/share/mysite-instagram-control/control.key`. Django defaults to that
key and loopback address. `INSTAGRAM_AGENT_URL` and `INSTAGRAM_CONTROL_KEY_FILE`
are operator configuration, not owner-editable URLs. Never expose the control
service with a public proxy or port mapping. The standalone `tools/instagram-poc`
remains available for isolated debugging but should not concurrently control the
same account while importing through the website.

## Verification and operation

The owner can reconnect or load posts from `/manage-local/instagram/`. Imported
records use `(platform, account ID, post ID)` as their unique identity. Audit
entries contain field names, not passwords, codes, control keys or SDK errors.
The page reports per-post counts; errors retain existing data. Imports are manual.

Run the application suite against PostgreSQL to exercise runtime grants:

```bash
docker compose run --rm migration python manage.py test -v 1
agent/instagram_poc/.venv/bin/python -m unittest discover -s agent/instagram_poc/tests -v
```

An operator restoring the old PoC account to Docker must copy both encrypted
record and separate key into the respective agent volumes with UID 10001 and
mode 0600, while the agent is stopped. Never print/decrypt credentials to perform
the transfer. Otherwise, enter the account again through the website settings.
Legacy Meta credentials are not read or mounted; any external backups remain an
operator retention concern.
