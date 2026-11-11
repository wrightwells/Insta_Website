> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Bilingual owner administration — 20 October 2026

Status: implemented for local development; production gate remains in place.

The owner portal now provides EN/FR navigation, forms, help, validation, login
throttling, upload errors, conflict messages and history headings. It uses Django
gettext resources rather than maintaining a second set of templates. Dates use
Django's locale-aware display with the existing Europe/London timezone. Editorial
datetime inputs still accept the documented ISO-style format.

Language selection uses a valid shared `site_language` cookie first, then the
browser's highest-priority enabled EN/FR language (including regional variants),
then the site's configured default. Disabled languages are omitted from the
switcher and rejected on POST. Responses expose `Content-Language` and vary on
Cookie and Accept-Language. Translation activation is scoped to one request.
The public runtime retains its independent URL-based language handling and does
not load the administration middleware or private site model.

An anonymous user can switch language before signing in. Switching requires
CSRF and POST, sets the existing HttpOnly/SameSite=Lax preference cookie (Secure
outside local mode), and accepts only same-host management destinations. The
cookie is shared with the public site's landing-page preference. No account,
privilege, publication status or database schema changes are required.

Original captions, editorial text, source identifiers and audit/revision keys
retain their stored values. Image previews select the French description when
available, falling back to English. Machine identifiers in audit/history remain
unchanged so an operator can compare them across languages.

Maintain `locales/fr/LC_MESSAGES/django.po` and commit its compiled `.mo` alongside
it. Docker copies both; its runtime does not require GNU gettext. On the
maintenance host, GNU gettext is required to extract/compile/check resources:

```bash
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemessages -l fr --no-wrap --no-obsolete --ignore=.venv --ignore=tests --ignore=docs
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py compilemessages -l fr --ignore=.venv
uv run python tools/check_translations.py
```

The checker rejects untranslated/fuzzy entries and compiled catalogs that differ
from their source. Django's bundled resources provide standard form/authentication
messages. Reference: [Django 5.2 translation documentation](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/).

Verification covers browser/cookie/default precedence, disabled locales, request
isolation, anonymous CSRF and redirect boundaries, public cookie reuse, French
editors/history, unchanged source text, saved values/audit codes, 409 conflicts,
invalid images and login throttling. All 49 PostgreSQL tests pass; SQLite passes
46 with three explicit PostgreSQL-role skips. An actual HTTP process from the
rebuilt Docker image using `admin_dev` in disposable PostgreSQL passed French
browser detection, anonymous language switching, cookie persistence and CSS.
The running public preview passed health/EN/FR/reviews/CSS smoke checks and retained
its three existing posts. Temporary verification services were removed. Browser,
responsive, keyboard and screen-reader review remain outstanding.
