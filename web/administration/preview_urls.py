"""Owner-only rendering of the public site on the administration origin."""
from functools import wraps

from django.urls import URLPattern

from web.public.urls import urlpatterns as public_patterns
from .views import owner_required


def preview_view(view):
    @wraps(view)
    @owner_required
    def wrapped(request, *args, **kwargs):
        request.is_owner_preview = True
        request.theme_preview_token = request.GET.get("theme_token", "")
        if request.method == "POST":
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(["GET", "HEAD"])
        response = view(request, *args, **kwargs)
        response.owner_preview = True
        response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    return wrapped


urlpatterns = [URLPattern(pattern.pattern, preview_view(pattern.callback),
    pattern.default_args, pattern.name) for pattern in public_patterns]
