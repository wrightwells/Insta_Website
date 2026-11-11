from django.conf import settings
from django.db import DatabaseError
from django.utils import translation
from django.utils.cache import patch_vary_headers

from domain.content.models import SiteContent
from web.locales import enabled_locales, preferred_locale


class AdminLocaleMiddleware:
    """Activate packaged translations without translating stored user content."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.ROOT_URLCONF != "web.administration.urls":
            return self.get_response(request)
        try:
            site = SiteContent.objects.first() or SiteContent()
        except DatabaseError:
            site = SiteContent()
        request.admin_site = site
        locale = preferred_locale(request, site)
        request.LANGUAGE_CODE = locale
        with translation.override(locale):
            response = self.get_response(request)
        response.setdefault("Content-Language", locale)
        patch_vary_headers(response, ["Cookie", "Accept-Language"])
        return response


def administration_context(request):
    site = getattr(request, "admin_site", None) or SiteContent()
    return {"admin_site": site, "admin_locales": enabled_locales(site)}
