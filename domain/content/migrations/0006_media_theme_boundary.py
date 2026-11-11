from importlib import import_module

from django.db import migrations
from django.db.models import Sum

THEME_VIEWS = [
    """CREATE VIEW public_theme AS
       SELECT t.id, t.background_color, t.text_color, t.muted_color, t.accent_color, t.font,
              CASE WHEN m.validated = TRUE AND m.mime_type = 'image/png' THEN m.id ELSE NULL END AS background_image_id
       FROM content_sitetheme t LEFT JOIN content_themeimage m ON m.id = t.background_image_id""",
    """CREATE VIEW public_theme_image AS
       SELECT m.id, m.storage_key FROM content_themeimage m
       JOIN content_sitetheme t ON t.background_image_id = m.id
       WHERE m.validated = TRUE AND m.mime_type = 'image/png'""",
]


def configure(apps, schema_editor):
    legacy = import_module("domain.content.migrations.0002_public_views")
    schema_editor.execute("DROP VIEW public_media")
    schema_editor.execute("DROP VIEW public_feed")
    for statement in legacy.VIEW_SQL[:2]:
        schema_editor.execute(statement.replace("m.validated = TRUE", "m.validated = TRUE AND m.active = TRUE"))
    for statement in THEME_VIEWS:
        schema_editor.execute(statement)
    total = apps.get_model("content", "MediaAsset").objects.aggregate(size=Sum("size"))["size"] or 0
    total += apps.get_model("content", "ThemeImage").objects.aggregate(size=Sum("size"))["size"] or 0
    apps.get_model("content", "MediaQuota").objects.get_or_create(pk=1, defaults={"bytes_used": total})
    apps.get_model("content", "SiteTheme").objects.get_or_create(pk=1)
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("GRANT SELECT ON public_feed, public_media, public_theme, public_theme_image TO site_public")
        schema_editor.execute("GRANT SELECT ON content_mediaquota, content_sitetheme, content_themeimage TO site_admin")
        schema_editor.execute("GRANT INSERT ON content_mediaasset, content_themeimage TO site_admin")
        schema_editor.execute("GRANT UPDATE (active, alt_en, alt_fr) ON content_mediaasset TO site_admin")
        schema_editor.execute("GRANT UPDATE (bytes_used) ON content_mediaquota TO site_admin")
        schema_editor.execute("GRANT UPDATE (background_color, text_color, muted_color, accent_color, font, background_image_id, version) ON content_sitetheme TO site_admin")


def reverse_boundary(apps, schema_editor):
    # Preserve active-media filtering during a code/boundary rollback; never
    # re-expose replaced binaries. Do not reverse the schema on populated data.
    schema_editor.execute("DROP VIEW public_theme_image")
    schema_editor.execute("DROP VIEW public_theme")
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("REVOKE INSERT ON content_mediaasset FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (active, alt_en, alt_fr) ON content_mediaasset FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (bytes_used) ON content_mediaquota FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (background_color, text_color, muted_color, accent_color, font, background_image_id, version) ON content_sitetheme FROM site_admin")
        schema_editor.execute("REVOKE ALL ON content_mediaquota, content_sitetheme, content_themeimage FROM site_admin")


class Migration(migrations.Migration):
    dependencies = [("content", "0005_publictheme_publicthemeimage_mediaquota_sitetheme_and_more")]
    operations = [migrations.RunPython(configure, reverse_boundary)]
