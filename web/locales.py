"""Locale preference policy shared by public and owner entry points; no DB access."""
from django.conf import settings
from django.utils.translation.trans_real import parse_accept_lang_header


def enabled_locales(site):
    return [code for code, enabled in (("en", site.english_enabled), ("fr", site.french_enabled)) if enabled]


def preferred_locale(request, site):
    enabled = enabled_locales(site)
    preference = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if preference in enabled:
        return preference
    for language, quality in parse_accept_lang_header(request.META.get("HTTP_ACCEPT_LANGUAGE", "")):
        if not quality:
            continue
        if language == "*":
            break
        code = language.split("-", 1)[0]
        if code in enabled:
            return code
    return site.default_locale
