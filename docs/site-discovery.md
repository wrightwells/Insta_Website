# SEO, social previews and business settings

Open **http://localhost:8001/manage-local/discovery/** with the website owner
account, or choose **SEO & business** in the owner navigation. This is a separate
management page. The public runtime has no management route.

Every visible field includes an example and fallback guidance. Where available,
the editor also shows the resolved current fallback value.

The grouped EN/FR form configures:

- Primary titles/descriptions for Feed, Reviews and Contact, reusing the existing
  Site copy fields. Changing them in either editor updates the same values.
- Public website origin, exact homepage canonical URLs for EN/FR, indexing policy
  and `max-image-preview`. Other pages retain their own generated canonicals.
- Open Graph type/site name, localized titles/descriptions, optional homepage
  Open Graph URLs, a default image URL, actual image dimensions, alt text and
  locale codes (initially `en_GB` / `fr_FR`).
- X/Twitter card style, localized titles/descriptions and an optional distinct
  image. Blank image values fall back to the configured social image, then the
  first published feed image when available. Card style can be automatic.
- Favicon and Apple icon URLs/paths, plus the browser theme colour. Icons must
  already exist at the supplied address; these fields do not upload assets.
- Google/Bing verification token values, rendered only when nonempty. Enter only
  the public verification value, not HTML or account credentials.
- Business JSON-LD: enablement, schema type, identity URL, business name, URL,
  image, EN/FR descriptions, price range, real postal address/country and country
  served. It is emitted on the first homepage page only, not pagination or errors.

Use **Preview metadata** before saving. Previews do not persist changes. The
preview shows the generated search/social text, canonicals and business JSON-LD.
Saving retains the prior version and adds a field-level audit event. The common
site-settings version protects against overwriting edits from another tab.
Settings history/restoration covers these fields; older snapshots retain current
values for fields introduced after that snapshot.

UTF-8 and the responsive viewport remain automatic. Optional URLs and business
text start blank; no example brand, example address or verification token is
published. Enabling business markup requires the real business name and address.
The sample `InteriorDesignBusiness` is not present in the Schema.org hierarchy;
the supported default is `HomeAndConstructionBusiness`, with `LocalBusiness` as
an alternative. See [Schema.org](https://schema.org/HomeAndConstructionBusiness).
Schema markup does not guarantee a particular search result appearance.

## Public rendering and URL rules

Text is escaped as HTML. URLs require HTTPS, without embedded credentials;
root-relative paths are also accepted for icons. Business `@id` may have a fragment.
Colours, tokens, locale codes, image sizes and schema choices are validated.
Business data is serialized to JSON with HTML-sensitive characters escaped, using
a response-specific CSP nonce. The editor never accepts executable head markup.
External icon origins are permitted narrowly in that public response's image CSP;
they are not fetched by the server during configuration.

The public origin in these settings overrides the deployment fallback for
canonicals, locale alternates, sitemap entries and absolute social image links.
Exact homepage canonical overrides are reflected in the sitemap and language
alternates too. User-supplied request Host/forwarding headers never select URLs.
The canonical homepage URL also supplies the default Open Graph URL; an optional
separate home Open Graph URL can override it.

Search indexing still requires the public deployment's indexing opt-in and a
non-local runtime. A settings choice cannot accidentally index the private local
preview. A `noindex` choice applies consistently to tags, headers and robots.txt;
contact pages follow the normal public indexing rules; error and paginated pages remain noindex.
The public website origin changes metadata, not DNS, TLS or the serving address.

## Deployment and verification

Schema migrations maintain the public settings view and narrowly scoped owner
update rights. Apply all outstanding migrations with the operator identity,
then reload the web/admin processes:

```bash
docker compose run --rm migration python manage.py migrate --noinput
docker compose restart web tailnet admin
```

Relevant checks:

```bash
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py test
APP_LOCAL=1 APP_RUNTIME=migration uv run manage.py makemigrations --check --dry-run
uv run python tools/check_translations.py
docker compose run --rm migration python manage.py test
```

Tests exercise head output, JSON-LD parsing/escaping and CSP, validation, canonical
and sitemap consistency, locale fallbacks, private-preview indexing protection,
owner/CSRF isolation, revisions/stale saves/restoration, legacy snapshots, and
PostgreSQL public-read/owner-write permissions.
