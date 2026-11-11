"""Public metadata comes from validated owner settings, never request headers."""
import json
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse

from domain.content.discovery import validate_url
from .copy import COPY
from web.locales import enabled_locales

READY_PAGES = ("feed", "reviews", "contact")
OG_LOCALES = {"en": "en_GB", "fr": "fr_FR"}


def public_urlconf():
    return "web.public.prefixed_urls" if settings.APP_SCRIPT_PREFIX else "web.public.urls"


def safe_url(value, *, path=False, fragment=False, origin=False):
    try:
        validate_url(value, path=path, fragment=fragment, origin=origin)
        return value
    except (ValidationError, ValueError, TypeError):
        return ''


def site_origin(site=None):
    return (safe_url(getattr(site, 'seo_public_origin', ''), origin=True) or settings.PUBLIC_ORIGIN).rstrip('/')


def absolute_url(path, site=None):
    origin = site_origin(site)
    return origin + path if origin else ''


def text_fallback(site, field, locale):
    for code in dict.fromkeys((locale, site.default_locale, "fr" if site.default_locale == "en" else "en")):
        value = " ".join(getattr(site, f"{field}_{code}").split())
        if value:
            return value
    return ""


def canonical_url(site, locale, page):
    override = safe_url(getattr(site, f'seo_home_canonical_{locale}', '')) if page == 'feed' else ''
    return override or absolute_url(reverse(page, urlconf=public_urlconf(), kwargs={'locale': locale}), site)


def business_data(site, locale):
    if not site.seo_business_enabled or not site.seo_business_name:
        return None
    url = safe_url(site.seo_business_url) or absolute_url('/', site)
    if not url:
        return None
    parsed = urlsplit(url)
    default_id = urlunsplit(parsed._replace(path=parsed.path or '/', fragment='business'))
    result = {'@context': 'https://schema.org', '@type': site.seo_business_type,
              '@id': safe_url(site.seo_business_id, fragment=True) or default_id,
              'name': site.seo_business_name, 'url': url}
    for key, value in (
        ('image', safe_url(site.seo_business_image) or safe_url(site.seo_social_image)),
        ('description', text_fallback(site, 'seo_business_description', locale)),
        ('priceRange', site.seo_business_price_range),
    ):
        if value:
            result[key] = value
    if all((site.seo_business_street, site.seo_business_town, site.seo_business_postcode, site.seo_business_country)):
        result['address'] = {'@type': 'PostalAddress', 'streetAddress': site.seo_business_street,
                             'addressLocality': site.seo_business_town, 'postalCode': site.seo_business_postcode,
                             'addressCountry': site.seo_business_country}
    if site.seo_business_area_served:
        result['areaServed'] = {'@type': 'Country', 'name': site.seo_business_area_served}
    return result


def safe_json(value):
    # JSON in a script data block must not be able to terminate the HTML element.
    return json.dumps(value, ensure_ascii=True, indent=2).translate(
        {ord('<'): r'\u003C', ord('>'): r'\u003E', ord('&'): r'\u0026'})


def page_metadata(site, locale, page, *, cursor="", available=True):
    title = text_fallback(site, f"seo_{page}_title", locale) or f"{COPY[locale][page]} · {site.name}"
    description = text_fallback(site, f"seo_{page}_description", locale) or text_fallback(site, "intro", locale) or title
    canonical = canonical_url(site, locale, page) if available else ''
    # Keep the exact pagination cursor while respecting any existing canonical query.
    def paged(url):
        return url + ('&' if '?' in url else '?') + urlencode({'cursor': cursor}) if url and cursor else url
    alternatives = [(code, paged(canonical_url(site, code, page))) for code in enabled_locales(site)] if canonical else []
    indexable = bool(settings.PUBLIC_INDEXING_ENABLED and not settings.LOCAL and canonical and available
                     and page in READY_PAGES and not cursor and site.seo_robots != 'noindex')
    robots = 'index, follow' if indexable else 'noindex, follow'
    if site.seo_max_image_preview:
        robots += ', max-image-preview:' + site.seo_max_image_preview
    image = safe_url(site.seo_social_image)
    business = business_data(site, locale) if page == 'feed' and available and not cursor else None
    return {
        'page_label': COPY[locale][page], 'title': ' '.join(title.split())[:160],
        'description': ' '.join(description.split())[:320], 'robots': robots,
        'canonical': paged(canonical), 'alternatives': alternatives,
        'default_url': paged(canonical_url(site, site.default_locale, page)) if canonical else '',
        'locale': getattr(site, f'seo_locale_{locale}') or OG_LOCALES[locale],
        'alternate_locales': [getattr(site, f'seo_locale_{code}') or OG_LOCALES[code] for code in enabled_locales(site) if code != locale],
        'indexable': indexable, 'site_name': site.seo_social_site_name or site.name,
        'og_type': site.seo_og_type,
        'og_title': text_fallback(site, 'seo_og_title', locale) or title,
        'og_description': text_fallback(site, 'seo_og_description', locale) or description,
        'og_url': (safe_url(getattr(site, f'seo_og_url_{locale}')) if page == 'feed' and not cursor else '') or paged(canonical),
        'image': image, 'image_width': site.seo_image_width, 'image_height': site.seo_image_height,
        'image_alt': text_fallback(site, 'seo_image_alt', locale),
        'twitter_card_setting': site.seo_twitter_card,
        'twitter_card': site.seo_twitter_card if site.seo_twitter_card != 'auto' else 'summary_large_image' if image or site.seo_twitter_image else 'summary',
        'twitter_title': text_fallback(site, 'seo_twitter_title', locale) or title,
        'twitter_description': text_fallback(site, 'seo_twitter_description', locale) or description,
        'twitter_image': safe_url(site.seo_twitter_image),
        'favicon': safe_url(site.seo_favicon, path=True), 'apple_icon': safe_url(site.seo_apple_icon, path=True),
        'theme_color': site.seo_theme_color,
        'google_verification': site.seo_google_verification, 'bing_verification': site.seo_bing_verification,
        'business_json': safe_json(business) if business else '',
    }
