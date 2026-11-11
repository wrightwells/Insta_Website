# Development and maintenance

Follow [INSTALL.md](../INSTALL.md) for installation and upgrades. This page covers
the current source tree and verification commands rather than deployment history.

## Source layout

| Directory | Responsibility |
| --- | --- |
| `config/` | Django settings, runtime selection and URL mount configuration |
| `domain/content/` | Models, restricted public views, migrations, editorial writes, imports and media |
| `web/public/` | Public pages, contact form, metadata and policy rendering/export |
| `web/administration/` | Authenticated owner pages, uploads, previews and discovery guidance |
| `agent/instagram_poc/` | Isolated Instagram adapter, control service and diagnostic UI |
| `deploy/` | Development Docker images, database-role setup and policy-only service |
| `tests/` | Django feature, boundary and PostgreSQL permission tests |
| `locales/` | Owner/public form translations |

`APP_RUNTIME` selects `public`, `admin` or `migration`. The public runtime does
not mount owner routes or load owner sessions. The named `SiteOwner` binding,
not ordinary superuser status, grants owner access. Administration currently
requires `APP_LOCAL=1`.

PostgreSQL public views expose eligible published content. `site_public` also has
limited contact-delivery/rate-counter writes, which contain no enquiry bodies.
`site_admin` has restricted editorial/auth/session privileges. Migrations and
owner provisioning use the operator identity. Audit events and revisions are
append-only. SQLite is convenient for local checks but does not exercise the
PostgreSQL role boundary.

## Verify changes

```bash
uv sync --frozen
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py check
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py test --noinput
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemigrations --check --dry-run
uv run python tools/check_translations.py
```

Use the existing development database service for PostgreSQL checks. Django
creates and removes a separate test database:

```bash
docker compose run --rm --no-deps migration python manage.py test --noinput
docker compose config --quiet
```

The tests use synthetic data and an in-memory mail backend; they do not send
external email or log into Instagram. Optional adapter tests have their own environment:

```bash
uv sync --project agent/instagram_poc --frozen
agent/instagram_poc/.venv/bin/python -m unittest discover -s agent/instagram_poc/tests -v
```

For French text changes, install GNU gettext and regenerate/compile the catalog:

```bash
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemessages -l fr --no-obsolete
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py compilemessages -l fr
uv run python tools/check_translations.py
```

Translate new entries and resolve fuzzy entries before compiling. Keep the `.po`
and compiled `.mo` files together in commits.

## Database and media maintenance

Create schema migrations in the migration runtime, then apply them with the
operator identity. Do not run migrations as a public or owner database login.

```bash
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemigrations
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py migrate
```

Inspect managed media without changing files or quotas:

```bash
docker compose run --rm --no-deps media-audit
```

Expire security counters, expired sessions and delivery records older than seven days:

```bash
docker compose run --rm --no-deps migration python manage.py cleanup_security
```

Republish the saved policy artifact if needed:

```bash
docker compose run --rm --no-deps migration python manage.py export_policy
```

Media replacement and story deletion retain historical records and binaries.
Do not delete files manually or reverse populated migrations to reclaim space.
For current feature operations, use the [documentation index](README.md).
