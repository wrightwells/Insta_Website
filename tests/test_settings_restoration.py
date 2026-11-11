import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from PIL import Image

from domain.content.editing import EditConflict, _snapshot, edit_content

from domain.content.models import AuditEvent, ContentRevision, MediaQuota, PublicTheme, SiteContent, SiteOwner, SiteTheme, ThemeImage
from domain.content.restoration import prepare_restoration, restore_settings
from domain.content.theme import THEME_FIELDS
from domain.content.uploads import edit_theme


@override_settings(ROOT_URLCONF="web.administration.urls")
class SettingsRestorationTests(TestCase):
    prefix = "/manage-local/"
    password = "Synthetic recovery passphrase 42!"

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("recovery-owner", password=cls.password, is_staff=True)
        cls.other = get_user_model().objects.create_user("other-recovery", is_staff=True, is_superuser=True)
        SiteOwner.objects.create(user=cls.owner)
        cls.site = SiteContent.objects.create(name="Original site")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.media_settings = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

    def change_site(self, **changes):
        self.site.refresh_from_db()
        edit_content(actor=self.owner, model=SiteContent, pk=1, expected_version=self.site.version, changes={"name": "New site", **changes})
        return ContentRevision.objects.filter(entity="site_content").latest("created_at")

    def signin(self, client=None):
        return (client or self.client).post(self.prefix + "login/", {"username": "recovery-owner", "password": self.password})

    def image(self, color="blue"):
        source = io.BytesIO()
        Image.new("RGB", (8, 8), color=color).save(source, format="PNG")
        source.seek(0)
        return source

    def theme_values(self, **changes):
        theme = SiteTheme.objects.get(pk=1)
        return {**{field: getattr(theme, field) for field in THEME_FIELDS}, **changes}

    def change_theme_image(self):
        edit_theme(actor=self.owner, expected_version=1, changes=self.theme_values(), image=self.image())
        background = SiteTheme.objects.get(pk=1).background_image
        edit_theme(actor=self.owner, expected_version=2, changes=self.theme_values(font="serif"), clear_background=True)
        revision = ContentRevision.objects.get(entity="site_theme", version=2)
        return revision, background

    def test_restoration_preserves_current_version_and_records_source(self):
        source = self.change_site(intro_en="Changed introduction")
        result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
        self.assertEqual((result.name, result.version), ("Original site", 3))
        before = ContentRevision.objects.get(entity="site_content", version=2)
        self.assertEqual(before.snapshot["name"], "New site")
        self.assertEqual(before.snapshot["restored_from_revision"], str(source.pk))
        event = AuditEvent.objects.get(action="restore_settings")
        self.assertEqual(event.revision, before)
        self.assertEqual(event.changed_fields, ["intro_en", "name"])
        self.assertEqual(ContentRevision.objects.get(pk=source.pk).snapshot["name"], "Original site")
        # The state displaced by restoration can itself be restored.
        result = restore_settings(actor=self.owner, revision_id=before.pk, expected_version=3, confirmed=True)
        self.assertEqual((result.name, result.version), ("New site", 4))

    def test_confirmation_owner_and_stale_version_are_required(self):
        source = self.change_site()
        with self.assertRaises(ValidationError):
            restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2)
        with self.assertRaises(PermissionDenied):
            restore_settings(actor=self.other, revision_id=source.pk, expected_version=2, confirmed=True)
        with self.assertRaises(EditConflict):
            restore_settings(actor=self.owner, revision_id=source.pk, expected_version=1, confirmed=True)
        self.assertEqual(AuditEvent.objects.filter(action="restore_settings").count(), 0)
        self.assertEqual(SiteContent.objects.get(pk=1).version, 2)

    def test_audit_failure_rolls_back_restoration_and_new_history(self):
        source = self.change_site()
        with patch("domain.content.restoration.AuditEvent.objects.create", side_effect=DatabaseError("Synthetic failure")):
            with self.assertRaises(DatabaseError):
                restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
        self.assertEqual(SiteContent.objects.get(pk=1).name, "New site")
        self.assertEqual(ContentRevision.objects.count(), 1)

    def test_current_validation_rejects_incompatible_or_invalid_snapshots(self):
        invalids = [None, {}, {**_snapshot(self.site), "page_size": 999}, {**_snapshot(self.site), "english_enabled": False, "french_enabled": False}]
        self.change_site()
        current = SiteContent.objects.get(pk=1)
        for snapshot in invalids:
            source = ContentRevision.objects.create(entity="site_content", entity_id="1", version=1, actor=self.owner, snapshot=snapshot if snapshot is not None else [])
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(ValidationError):
                    prepare_restoration(current, source)
        self.assertEqual(SiteContent.objects.get(pk=1).version, 2)

    def test_non_settings_revision_is_rejected(self):
        source = ContentRevision.objects.create(entity="presentation_item", entity_id="unrelated", version=1, actor=self.owner, snapshot={})
        with self.assertRaises(ValidationError):
            restore_settings(actor=self.owner, revision_id=source.pk, expected_version=1, confirmed=True)
        self.signin()
        self.assertEqual(self.client.get(self.prefix + f"history/{source.pk}/restore/").status_code, 404)
        self.assertNotContains(self.client.get(self.prefix + f"history/{source.pk}/"), "Review restoration")

    def test_theme_background_is_reused_without_storage_growth(self):
        source, image = self.change_theme_image()
        before = MediaQuota.objects.get(pk=1).bytes_used
        result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=3, confirmed=True)
        self.assertEqual(result.background_image_id, image.pk)
        self.assertEqual(result.font, "editorial")
        self.assertEqual(result.version, 4)
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, before)
        self.assertEqual(ThemeImage.objects.count(), 1)
        self.assertEqual(PublicTheme.objects.get(pk=1).background_image_id, image.pk)

    def test_missing_corrupt_or_symlink_background_preserves_current_theme(self):
        source, image = self.change_theme_image()
        path = Path(self.directory.name) / image.storage_key
        original = path.read_bytes()
        for state in ("missing", "corrupt", "symlink"):
            path.unlink(missing_ok=True)
            if state == "corrupt":
                path.write_bytes(b"invalid")
            elif state == "symlink":
                target = Path(self.directory.name) / "target.png"
                target.write_bytes(original)
                path.symlink_to(target)
            with self.subTest(state=state):
                with self.assertRaises(ValidationError):
                    restore_settings(actor=self.owner, revision_id=source.pk, expected_version=3, confirmed=True)
                self.assertIsNone(SiteTheme.objects.get(pk=1).background_image_id)
                self.assertEqual(ContentRevision.objects.count(), 2)

    def test_theme_restore_can_remove_background_and_revalidates_contrast(self):
        edit_theme(actor=self.owner, expected_version=1, changes=self.theme_values(), image=self.image())
        source = ContentRevision.objects.get(entity="site_theme", version=1)
        result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
        self.assertIsNone(result.background_image_id)
        self.assertEqual(ThemeImage.objects.count(), 1)
        source = ContentRevision.objects.create(entity="site_theme", entity_id="1", version=1, actor=self.owner, snapshot={**_snapshot(result), "text_color": "#ffffff"})
        with self.assertRaises(ValidationError):
            restore_settings(actor=self.owner, revision_id=source.pk, expected_version=3, confirmed=True)

    def test_same_values_are_noop_without_history_growth(self):
        source = self.change_site()
        restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
        counts = ContentRevision.objects.count(), AuditEvent.objects.count()
        result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=3, confirmed=True)
        self.assertEqual(result.version, 3)
        self.assertEqual((ContentRevision.objects.count(), AuditEvent.objects.count()), counts)

    def test_comparison_is_read_only_escaped_and_requires_explicit_confirmation(self):
        source = self.change_site(intro_en='<script>alert("synthetic")</script>')
        self.signin()
        path = self.prefix + f"history/{source.pk}/restore/"
        response = self.client.get(path)
        self.assertContains(response, "Settings comparison")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert(')
        self.assertEqual(SiteContent.objects.get(pk=1).version, 2)
        self.assertEqual(self.client.post(path, {"version": 2}).status_code, 400)
        response = self.client.post(path, {"version": 2, "confirm": "on", "name": "Untrusted posted value"})
        self.assertRedirects(response, self.prefix + "site/?restored=1")
        self.assertEqual(SiteContent.objects.get(pk=1).name, "Original site")
        self.assertContains(self.client.get(self.prefix + "audit/"), "View restoration source")

    def test_csrf_anonymous_access_and_stale_confirmation(self):
        source = self.change_site()
        path = self.prefix + f"history/{source.pk}/restore/"
        self.assertEqual(self.client.get(path).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        # OwnerSessionMiddleware requires the timestamps issued by the normal login.
        from django.utils import timezone
        session = strict.session
        session["owner_login_at"] = session["owner_seen_at"] = timezone.now().timestamp()
        session.save()
        self.assertEqual(strict.post(path, {"version": 2, "confirm": "on"}).status_code, 403)
        self.signin()
        self.assertEqual(self.client.post(path, {"version": 1, "confirm": "on"}).status_code, 409)
        self.assertEqual(SiteContent.objects.get(pk=1).version, 2)

    def test_invalid_saved_values_render_errors_without_changing_settings(self):
        source = self.change_site()
        invalid = ContentRevision.objects.create(entity="site_content", entity_id="1", version=1, actor=self.owner, snapshot={**source.snapshot, "page_size": 999})
        self.signin()
        path = self.prefix + f"history/{invalid.pk}/restore/"
        self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.post(path, {"version": 2, "confirm": "on"}).status_code, 400)
        self.assertEqual(SiteContent.objects.get(pk=1).version, 2)

    def test_postgres_runtime_role_restores_without_mutating_history(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL role grants.")
        source = self.change_site()
        theme_source, image = self.change_theme_image()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE site_admin")
            result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
            self.assertEqual(result.name, "Original site")
            theme = restore_settings(actor=self.owner, revision_id=theme_source.pk, expected_version=3, confirmed=True)
            self.assertEqual(theme.background_image_id, image.pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ContentRevision.objects.filter(pk=source.pk).update(version=99)
            with self.assertRaises(DatabaseError), transaction.atomic():
                SiteContent.objects.filter(pk=1).delete()
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

    def test_french_comparison_and_locale_restoration(self):
        SiteContent.objects.filter(pk=1).update(default_locale="fr", english_enabled=False)
        self.site.refresh_from_db()
        source = self.change_site(default_locale="en", english_enabled=True)
        self.signin()
        self.client.cookies["site_language"] = "fr"
        path = self.prefix + f"history/{source.pk}/restore/"
        response = self.client.get(path)
        self.assertContains(response, "Comparaison des paramètres")
        self.assertContains(response, "Confirmer la restauration")
        self.client.cookies["site_language"] = "en"
        response = self.client.post(path, {"version": 2, "confirm": "on"}, follow=True)
        self.assertEqual(response["Content-Language"], "fr")
        self.assertContains(response, "Paramètres restaurés")
        self.assertNotContains(response, 'name="language" value="en"')
        self.assertFalse(SiteContent.objects.get(pk=1).english_enabled)

    def test_background_comparison_shows_retained_image_and_corruption_error(self):
        source, image = self.change_theme_image()
        self.signin()
        path = self.prefix + f"history/{source.pk}/restore/"
        response = self.client.get(path)
        self.assertContains(response, self.prefix + f"image/theme/{image.pk}/")
        (Path(self.directory.name) / image.storage_key).write_bytes(b"corrupt")
        response = self.client.post(path, {"version": 3, "confirm": "on"})
        self.assertContains(response, "missing or invalid", status_code=400)
        self.assertNotContains(response, "Confirm restoration</button>", status_code=400)
        self.assertIsNone(SiteTheme.objects.get(pk=1).background_image_id)
