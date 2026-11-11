# Insta_Website

A bilingual Django website that displays imported Instagram images and captions,
with a separate owner portal at `/manage-local/`.

Start with the **[installation guide](INSTALL.md)**. It covers Docker/PostgreSQL,
local Python setup, owner provisioning, configuration, upgrades and persistent data.
See the [documentation index](docs/README.md) for feature and operator guides.

## Current features

- English/French main feed, editable journal heading, introductions and footer.
- Owner-triggered Instagram connection and recent-post imports through an isolated
  `instagrapi` service. No Meta app registration or developer tokens are needed.
- Story editing, image replacement, publication controls and confirmed deletion.
  Deleted stories retain history and are not republished by later imports.
- Colours, fonts and background settings, with a full-page preview of the actual feed.
- Contact details and an email/mobile/message form. The form stays hidden until
  SMTP delivery and a real recipient are configured.
- An editable site policy that shares the Contact email. Fresh sites start with
  `email@site.eu`; replace it with the site's real address.
- Optional Reviews page, SEO/social settings with examples and fallback guidance,
  password changes, audit history and settings restoration.

Google review retrieval, full video playback and scheduled Instagram importing
are not implemented. The supplied Compose setup uses disposable development
credentials and local-only administration; it is not a production deployment.

## Checks

```bash
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py test
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemigrations --check --dry-run
uv run python tools/check_translations.py
```

PostgreSQL permission checks run with:

```bash
docker compose run --rm --no-deps migration python manage.py test --noinput
```

Local databases, downloaded media, credentials and environment files are excluded
from source control. Historical requirements and design decisions are kept in the
[documentation archive](docs/archive/README.md).
