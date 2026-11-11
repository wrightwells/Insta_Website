"""Explicit public URL mount; upstream proxies must preserve the request path."""
from django.conf import settings
from django.urls import include, path

from .views import not_found, server_error

urlpatterns = [path(settings.APP_SCRIPT_PREFIX.lstrip('/') + '/', include('web.public.urls'))]
handler404 = not_found
handler500 = server_error
