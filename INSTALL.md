# Installation guide

This guide installs the current **local development** application. Docker runs
PostgreSQL and separate public, owner, Instagram and policy services. The supplied
credentials and `APP_LOCAL=1` configuration are for development; administration
is deliberately disabled in non-local mode pending production deployment work.

## Prerequisites

- Git and access to `wrightwells/Insta_Website`.
- Docker Engine with the Docker Compose v2 plugin for the recommended setup.
- An interactive terminal to set the owner password.
- For the alternative Python setup: Python 3.11+ and `uv`.
- GNU gettext only if you will modify French translations.

Clone the repository and run the following commands from its root:

```bash
git clone https://github.com/wrightwells/Insta_Website.git
cd Insta_Website
```

Use your existing authenticated SSH remote instead if preferred. Installation
does not change DNS, TLS, Tailscale routing or public access.

## Docker and PostgreSQL: fresh installation

### 1. Build the application and start the database

```bash
docker compose --profile administration --profile privacy build migration web admin instagram-agent privacy
docker compose up -d --wait db
```

The database initializes the non-login roles from `deploy/roles.sql` on its first
start. PostgreSQL has no published host port.

### 2. Apply schema migrations

```bash
docker compose run --rm --no-deps migration python manage.py migrate --noinput
```

Migrations create the public views, runtime grants, initial theme/media quota and
editable policy. They run as the database operator, not as a web runtime.

### 3. Create the two runtime database logins

Run these **once for a fresh database**:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d instagram < deploy/public-dev.sql
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d instagram < deploy/admin-dev.sql
```

`public_dev` inherits the limited public role; `admin_dev` inherits the owner
runtime role. These scripts contain disposable local passwords matching Compose.
On an existing installation, do not repeat role creation or recreate its volumes.

### 4. Provision the website owner

```bash
docker compose run --rm --no-deps migration python manage.py provision_owner owner
```

Enter and confirm a password of at least 14 characters. Input is hidden. The
command creates one named owner and initial site settings; it refuses to replace
an existing owner. An ordinary Django superuser is not automatically the owner.

For a new site, Contact starts with `email@site.eu`. Replace that placeholder in
the owner portal. The policy automatically uses the same Contact email.

### 5. Publish the initial policy and start the services

```bash
docker compose run --rm --no-deps migration python manage.py export_policy
docker compose --profile administration --profile privacy up -d --wait web instagram-agent admin privacy
```

| Service | Local address |
| --- | --- |
| Public website | http://localhost:8000/ |
| Owner portal | http://localhost:8001/manage-local/ |
| Policy-only page | http://localhost:8003/privacy/ |
| PostgreSQL and Instagram control service | Internal Docker networks only |

Sign in to the owner portal using the account created above. Public routes do
not expose owner pages. Host ports bind to loopback, not all network interfaces.

### 6. Verify the installation

```bash
docker compose ps
curl --fail http://localhost:8000/health/
curl --fail http://localhost:8000/en/
curl --fail http://localhost:8000/privacy/
curl --fail http://localhost:8003/privacy/
```

An empty feed is normal until you import posts. Optionally add clearly labelled
synthetic stories to a disposable development database:

```bash
docker compose run --rm --no-deps migration python manage.py seed_demo
```

`seed_demo` makes no Instagram requests.

## Configure the site

Open the following pages in **manage-local**:

| Page | Setup |
| --- | --- |
| Site copy | Site name, THE JOURNAL label, main heading, EN/FR introductions/footer, languages and page size |
| Contact | Real public email, phone/address/hours and SMTP delivery settings |
| Site policy | Site/operator details, title/date and complete policy text; email comes from Contact |
| Appearance | Colours, fonts and optional background; Preview opens the actual feed in a new tab without saving |
| SEO & business | Examples and fallback guidance for search/social metadata, icons, verification and business details |
| Reviews | Show or hide Reviews; Google review retrieval is not yet implemented |
| Instagram | Save the account, connect/MFA and manually load 1–12 recent posts |
| Password | Change the owner password; other existing sessions are revoked |
| Stories / Audit trail | Edit or delete stories, inspect previous versions and restore supported settings |

The contact form remains hidden until SMTP delivery is enabled and the sender,
host, real recipient and any required credentials are set. `email@site.eu` is a
placeholder and does not enable sending. Enquiries are emailed to the Contact
address; the website does not store their contents. See [contact email](docs/contact-email.md).

Saving Contact email changes also republishes the policy-only page. Policy
paragraphs and headings can be edited in full; placeholders keep shared details
consistent. See [site policy](docs/site-policy.md).

Instagram uses the isolated `instagrapi` service, with no Meta developer-app,
OAuth callback or developer tokens. Login challenges may require action directly
in Instagram. Imports are manual; valid new posts publish immediately. See
[connection instructions](docs/instagram-connection.md) and
[operator setup](docs/instagram-operator-access.md).

## Alternative: local Python and SQLite

This is useful for source development. SQLite does not exercise PostgreSQL's
runtime-role permissions.

```bash
uv sync --frozen
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py migrate --noinput
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py provision_owner owner
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py export_policy
```

Start the public site:

```bash
APP_LOCAL=1 uv run manage.py runserver 8000 --insecure
```

In a second terminal, start the owner portal:

```bash
APP_LOCAL=1 APP_RUNTIME=admin uv run manage.py runserver 8001 --insecure
```

`--insecure` serves development static assets while Django debug pages remain
disabled. The database is `local.sqlite3`; media is in `private-media/`. Both
are ignored by Git. SMTP settings and policy exports default to private paths
outside the checkout under `~/.local/share/`.

For local Instagram support, install and start its separate environment in
another terminal:

```bash
uv sync --project agent/instagram_poc --frozen
./tools/instagram-agent
```

The agent listens on loopback port 8769 and creates its private control key.
The standalone diagnostic PoC is optional and uses different login credentials;
it is not needed for the website owner portal.

## Upgrading an existing Docker installation

Back up persistent data first. Keep the existing owner and runtime logins.

```bash
git pull --ff-only
docker compose --profile administration --profile privacy build migration web admin instagram-agent privacy
docker compose run --rm --no-deps migration python manage.py migrate --noinput
docker compose run --rm --no-deps migration python manage.py export_policy
docker compose --profile administration --profile privacy up -d --wait web instagram-agent admin privacy
```

Run the final command only for the services enabled in your installation. An
existing optional `tailnet` service must also be rebuilt and recreated when its
image/configuration changes. Its host-specific routing is recorded in the
[historical deployment notes](docs/archive/decisions/2026-10-23-tailnet-root.md);
do not apply those hostnames or routing changes to a different machine.

Do not rerun the fresh-install login SQL, provision another owner or reverse
populated migrations as an upgrade step.

## Persistent data and routine operation

Compose uses project-prefixed named volumes, normally `instagram-dev_*`:

| Volume | Contents |
| --- | --- |
| `database` | Site content, owner account, policy, audit/history and delivery metadata |
| `private-media` | Validated images and retained historical images |
| `contact-mail` | Private SMTP configuration, including the saved password |
| `site-policy` | Rendered policy artifact shared with the policy-only service |
| `instagram-data` | Encrypted Instagram record/session and private staging files |
| `instagram-key` | Instagram encryption key; protect separately from the encrypted record |
| `instagram-control` | Private agent-control capability shared only with admin |

Use coordinated database/media backups, preserve SMTP credentials, and protect
the Instagram record and encryption key separately. Restoring only the database
without its media can leave broken images. Policy HTML can be regenerated with
`export_policy`. Private configuration files/directories use 0600/0700 permissions.

```bash
docker compose stop
docker compose --profile administration --profile privacy up -d --wait web instagram-agent admin privacy
```

A normal stop/restart preserves the volumes. Do not use `docker compose down -v`
as a restart command; it deletes persistent volumes.

Inspect media and expire security state with the operator commands:

```bash
docker compose run --rm --no-deps media-audit
docker compose run --rm --no-deps migration python manage.py cleanup_security
```

The media audit is read-only. Cleanup removes expired sessions/counters and contact
delivery records older than seven days, not enquiry bodies. Schedule cleanup and
backups to suit your deployment; installation does not create host schedules.

## Troubleshooting

- **Owner provisioning says an owner exists:** use the existing account. Password
  changes are available after login; account recovery requires operator access.
- **Runtime database login fails:** on a fresh installation, verify both login SQL
  scripts ran after migrations. On an existing installation, inspect roles rather
  than deleting the database volume.
- **Contact form is missing:** save a real Contact email, enter SMTP sender/host and
  credentials as required, and enable delivery. A missing saved password for an
  authenticated SMTP username also keeps the form hidden.
- **Policy-only page has old text:** run `export_policy` and confirm the admin and
  policy services use the same `site-policy` volume.
- **Instagram is unavailable:** check `docker compose ps`, start the administration
  profile, and reconnect through the owner page. Do not publish the control port.
- **Port conflict:** adjust loopback mappings in a local Compose override while
  keeping the owner portal private.

See [development and maintenance](docs/development.md) for checks and translations,
and the [documentation index](docs/README.md) for current feature guides.
