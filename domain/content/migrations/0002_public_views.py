from django.db import migrations


VIEW_SQL = [
    """CREATE VIEW public_feed AS
       SELECT i.id, i.canonical_url,
              COALESCE(i.display_caption, i.original_caption) AS caption,
              COALESCE(i.display_date, i.source_published_at) AS effective_date,
              i.source_published_at
       FROM content_presentationitem i
       WHERE i.status = 'published' AND i.publish_at <= CURRENT_TIMESTAMP
         AND EXISTS (SELECT 1 FROM content_mediaasset m
                     WHERE m.item_id = i.id AND m.validated = TRUE
                       AND m.mime_type = 'image/png' AND m.alt_en <> '')""",
    """CREATE VIEW public_media AS
       SELECT m.id, m.item_id, m.storage_key, m.width, m.height,
              m.alt_en, m.alt_fr, m.sequence
       FROM content_mediaasset m
       JOIN public_feed p ON p.id = m.item_id
       WHERE m.validated = TRUE AND m.mime_type = 'image/png' AND m.alt_en <> ''""",
    """CREATE VIEW public_site_content AS
       SELECT id, name, intro_en, intro_fr, footer_en, footer_fr,
              empty_en, empty_fr, default_locale, english_enabled,
              french_enabled, page_size
       FROM content_sitecontent""",
    """CREATE VIEW public_reviews AS
       SELECT id, reviewer_name, text_en, text_fr, rating, published_at, priority
       FROM content_review
       WHERE status = 'published' AND published_at <= CURRENT_TIMESTAMP""",
]


def create_views(apps, schema_editor):
    for statement in VIEW_SQL:
        schema_editor.execute(statement)
    if schema_editor.connection.vendor == "postgresql":
        # NOLOGIN roles are provisioned explicitly by the database operator.
        # Runtime logins inherit these privileges, never the migration owner's.
        schema_editor.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC")
        schema_editor.execute("GRANT USAGE ON SCHEMA public TO site_public")
        schema_editor.execute("GRANT SELECT ON public_feed, public_media, public_reviews, public_site_content TO site_public")


def drop_views(apps, schema_editor):
    for name in ("public_media", "public_feed", "public_reviews", "public_site_content"):
        schema_editor.execute(f"DROP VIEW {name}")


class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]
    operations = [migrations.RunPython(create_views, drop_views)]
