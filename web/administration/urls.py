"""Owner-only URL map, never imported by the public runtime."""
from django.conf import settings
from django.urls import include, path

from web.public.views import health, robots
from . import views

prefix = f"{settings.ADMIN_SLUG}/"
urlpatterns = [
    path("health/", health),
    path("robots.txt", robots),
    path(prefix, views.items, name="owner_items"),
    path(prefix + "policy/", views.policy_edit, name="owner_policy"),
    path(prefix + "password/", views.password_change, name="owner_password"),
    path(prefix + "contact/email/", views.contact_mail_edit, name="owner_contact_mail"),
    path(prefix + "contact/", views.contact_edit, name="owner_contact"),
    path(prefix + "reviews/", views.reviews_edit, name="owner_reviews"),
    path(prefix + "items/<uuid:item_id>/delete/", views.item_delete, name="owner_item_delete"),
    path(prefix + "preview/", include("web.administration.preview_urls")),
    path(prefix + "login/", views.login, name="owner_login"),
    path(prefix + "language/", views.set_language, name="owner_language"),
    path(prefix + "logout/", views.logout, name="owner_logout"),
    path(prefix + "items/<uuid:item_id>/", views.item_edit, name="owner_item"),
    path(prefix + "items/<uuid:item_id>/image/", views.item_image, name="owner_item_image"),
    path(prefix + "image/item/<uuid:asset_id>/", views.private_image, {"kind": "item"}, name="owner_private_image"),
    path(prefix + "image/theme/<uuid:asset_id>/", views.private_image, {"kind": "theme"}, name="owner_theme_image"),
    path(prefix + "theme/", views.theme_edit, name="owner_theme"),
    path(prefix + "theme/preview.css", views.theme_preview, name="owner_theme_preview"),
    path(prefix + "discovery/", views.discovery_edit, name="owner_discovery"),
    path(prefix + "site/", views.site_edit, name="owner_site"),
    path(prefix + "instagram/", views.instagram_setup, name="owner_instagram"),
    path(prefix + "audit/", views.audit, name="owner_audit"),
    path(prefix + "history/<uuid:revision_id>/", views.revision, name="owner_revision"),
    path(prefix + "history/<uuid:revision_id>/restore/", views.settings_restore, name="owner_settings_restore"),
]
