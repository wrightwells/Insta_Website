from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("health/", views.health, name="health"),
    path("privacy/", views.privacy, name="privacy"),
    path("media/<uuid:asset_id>/", views.media, name="media"),
    path("theme.css", views.stylesheet, name="theme_css"),
    path("theme/image/<uuid:asset_id>/", views.theme_image, name="theme_image"),
    re_path(r"^(?P<locale>en|fr)/$", views.public_page, {"page": "feed"}, name="feed"),
    re_path(r"^(?P<locale>en|fr)/contact/$", views.public_page, {"page": "contact"}, name="contact"),
    re_path(r"^(?P<locale>en|fr)/reviews/$", views.public_page, {"page": "reviews"}, name="reviews"),
]
handler404 = views.not_found
handler500 = views.server_error
