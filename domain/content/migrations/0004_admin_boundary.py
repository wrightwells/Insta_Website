from django.db import migrations

IMMUTABLE_TABLES = ("content_auditevent", "content_contentrevision")


def establish_boundary(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'History is append only'; END; $$""")
        for table in IMMUTABLE_TABLES:
            schema_editor.execute(f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()")
        schema_editor.execute("GRANT USAGE ON SCHEMA public TO site_admin")
        schema_editor.execute("GRANT SELECT ON auth_user, content_siteowner, content_presentationitem, content_mediaasset, content_sitecontent, content_auditevent, content_contentrevision TO site_admin")
        schema_editor.execute("GRANT SELECT (id) ON content_sourceaccount TO site_admin")
        schema_editor.execute("GRANT UPDATE (password, last_login) ON auth_user TO site_admin")
        schema_editor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON django_session, content_logincounter TO site_admin")
        schema_editor.execute("GRANT INSERT ON content_auditevent, content_contentrevision TO site_admin")
        schema_editor.execute("GRANT UPDATE (display_caption, display_date, priority, status, publish_at, version, updated_at) ON content_presentationitem TO site_admin")
        schema_editor.execute("GRANT UPDATE (name, intro_en, intro_fr, footer_en, footer_fr, empty_en, empty_fr, default_locale, english_enabled, french_enabled, page_size, version) ON content_sitecontent TO site_admin")
    elif vendor == "sqlite":
        for table in IMMUTABLE_TABLES:
            for operation in ("UPDATE", "DELETE"):
                schema_editor.execute(f"CREATE TRIGGER {table}_immutable_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'History is append only'); END")


def reverse_boundary(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        for table in IMMUTABLE_TABLES:
            schema_editor.execute(f"DROP TRIGGER immutable_history ON {table}")
        schema_editor.execute("DROP FUNCTION reject_history_mutation()")
        schema_editor.execute("REVOKE ALL ON auth_user, content_siteowner, content_presentationitem, content_mediaasset, content_sitecontent, content_auditevent, content_contentrevision, content_sourceaccount, django_session, content_logincounter FROM site_admin")
        # Table REVOKE does not revoke column grants.
        schema_editor.execute("REVOKE SELECT (id) ON content_sourceaccount FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (password, last_login) ON auth_user FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (display_caption, display_date, priority, status, publish_at, version, updated_at) ON content_presentationitem FROM site_admin")
        schema_editor.execute("REVOKE UPDATE (name, intro_en, intro_fr, footer_en, footer_fr, empty_en, empty_fr, default_locale, english_enabled, french_enabled, page_size, version) ON content_sitecontent FROM site_admin")
    elif vendor == "sqlite":
        for table in IMMUTABLE_TABLES:
            for operation in ("update", "delete"):
                schema_editor.execute(f"DROP TRIGGER {table}_immutable_{operation}")


class Migration(migrations.Migration):
    dependencies = [("content", "0003_logincounter_sitecontent_version_contentrevision_and_more"), ("sessions", "0001_initial")]
    operations = [migrations.RunPython(establish_boundary, reverse_boundary)]
