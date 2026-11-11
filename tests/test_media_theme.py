from urllib.parse import parse_qs, urlsplit
import io
import tempfile
from datetime import timedelta
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from domain.content.editing import EditConflict
from domain.content.media import decode_image, stage_image
from domain.content.models import AuditEvent, ContentRevision, MediaAsset, MediaQuota, PresentationItem, SiteOwner, SiteTheme, SourceAccount, ThemeImage
from domain.content.theme import THEME_FIELDS, contrast
from domain.content.uploads import edit_item_image, edit_theme
from django.contrib.auth import get_user_model


@override_settings(ROOT_URLCONF="web.administration.urls")
class MediaThemeTests(TestCase):
    password = "Synthetic media passphrase 2026!"
    prefix = "/manage-local/"

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("media-owner", password=cls.password, is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        account = SourceAccount.objects.create(source_account_id="synthetic-media")
        cls.item = PresentationItem.objects.create(account=account, source_post_id="media", canonical_url="https://www.instagram.com/p/media/", original_caption="Original caption", source_published_at=timezone.now() - timedelta(days=1), publish_at=timezone.now() - timedelta(minutes=1), status="published")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.media_settings = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.old = stage_image(self.item, self.upload(), alt_en="Original image")

    def upload(self, color="green", filename="image.png"):
        stream = io.BytesIO()
        Image.new("RGB", (32, 24), color).save(stream, "PNG")
        return SimpleUploadedFile(filename, stream.getvalue(), content_type="image/png")

    def signin(self, client=None):
        return (client or self.client).post(self.prefix + "login/", {"username": "media-owner", "password": self.password})

    def image_data(self, **changes):
        data = {"version": 1, "alt_en": "New image", "alt_fr": "Nouvelle image", "image": self.upload("blue")}
        data.update(changes)
        return data

    def theme_data(self, **changes):
        theme = SiteTheme.objects.get(pk=1)
        data = {field: getattr(theme, field) for field in THEME_FIELDS}
        data["version"] = theme.version
        data.update(changes)
        return data

    def public(self, path):
        with override_settings(ROOT_URLCONF="web.public.urls", MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            return Client().get(path)

    def test_replacement_is_audited_and_revokes_old_public_binary(self):
        self.signin()
        path = Path(self.directory.name) / self.old.storage_key
        before = path.read_bytes()
        response = self.client.post(self.prefix + f"items/{self.item.pk}/image/", self.image_data())
        self.assertEqual(response.status_code, 200)
        self.old.refresh_from_db()
        self.assertFalse(self.old.active)
        new = MediaAsset.objects.get(item=self.item, active=True)
        self.assertNotEqual(new.storage_key, self.old.storage_key)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.public(f"/media/{self.old.pk}/").status_code, 404)
        self.assertEqual(self.public(f"/media/{new.pk}/").status_code, 200)
        self.assertEqual(self.client.get(self.prefix + f"image/item/{self.old.pk}/").status_code, 200)
        self.assertEqual(ContentRevision.objects.get().snapshot["media"][0]["alt_en"], "Original image")
        self.item.refresh_from_db()
        self.assertEqual(self.item.version, 2)
        self.assertEqual(self.item.original_caption, "Original caption")

    def test_description_only_edit_and_image_share_item_version(self):
        self.signin()
        used = MediaQuota.objects.get(pk=1).bytes_used
        response = self.client.post(self.prefix + f"items/{self.item.pk}/image/", self.image_data(image="", alt_en="Updated description"))
        self.assertEqual(response.status_code, 200)
        self.old.refresh_from_db()
        self.assertEqual(self.old.alt_en, "Updated description")
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, used)
        self.assertEqual(MediaAsset.objects.count(), 1)
        with self.assertRaises(EditConflict):
            edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, alt_en="Stale", image=self.upload())

    def test_invalid_and_oversized_uploads_preserve_current_image(self):
        self.signin()
        url = self.prefix + f"items/{self.item.pk}/image/"
        invalid = SimpleUploadedFile("image.png", b'<svg onload="alert(1)"></svg>', content_type="image/png")
        self.assertEqual(self.client.post(url, self.image_data(image=invalid)).status_code, 400)
        huge = SimpleUploadedFile("large.png", b"x" * (10 * 1024 * 1024 + 1), content_type="image/png")
        self.assertEqual(self.client.post(url, self.image_data(image=huge)).status_code, 413)
        self.assertTrue(MediaAsset.objects.get(pk=self.old.pk).active)
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_anonymous_upload_rejected_before_domain_write_and_owner_upload_requires_csrf(self):
        url = self.prefix + f"items/{self.item.pk}/image/"
        self.assertEqual(self.client.post(url, self.image_data()).status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        session = strict.session
        session["owner_login_at"] = session["owner_seen_at"] = timezone.now().timestamp()
        session.save()
        self.assertEqual(strict.post(url, self.image_data()).status_code, 403)
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_audit_failure_rolls_back_file_selection_budget_and_revision(self):
        before = set(Path(self.directory.name).iterdir())
        used = MediaQuota.objects.get(pk=1).bytes_used
        with patch("domain.content.uploads.AuditEvent.objects.create", side_effect=DatabaseError("audit unavailable")):
            with self.assertRaises(DatabaseError):
                edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, image=self.upload(), alt_en="New")
        self.assertEqual(set(Path(self.directory.name).iterdir()), before)
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, used)
        self.assertTrue(MediaAsset.objects.get(pk=self.old.pk).active)
        self.assertFalse(ContentRevision.objects.exists())

    def test_quota_and_disk_failure_retain_old_image(self):
        with override_settings(MEDIA_STORAGE_LIMIT_BYTES=MediaQuota.objects.get(pk=1).bytes_used):
            with self.assertRaises(ValidationError):
                edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, image=self.upload(), alt_en="New")
        with patch("domain.content.media.Path.open", side_effect=OSError("synthetic full disk")):
            with self.assertRaises(OSError):
                edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, image=self.upload(), alt_en="New")
        self.assertTrue(MediaAsset.objects.get(pk=self.old.pk).active)
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_ambiguous_commit_never_deletes_a_referenced_binary(self):
        real_atomic = transaction.atomic
        depth = 0

        @contextmanager
        def fail_after_commit(*args, **kwargs):
            nonlocal depth
            outermost = depth == 0
            depth += 1
            try:
                with real_atomic(*args, **kwargs):
                    yield
            finally:
                depth -= 1
            if outermost:
                raise DatabaseError("synthetic ambiguous commit acknowledgement")

        with patch("domain.content.uploads.transaction.atomic", fail_after_commit):
            with self.assertRaises(DatabaseError):
                edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, image=self.upload(), alt_en="Committed image")
        current = MediaAsset.objects.get(item=self.item, active=True)
        self.assertTrue((Path(self.directory.name) / current.storage_key).exists())
        self.assertNotEqual(current.pk, self.old.pk)

    def test_decoding_strips_metadata_trailing_content_and_filename(self):
        source = io.BytesIO()
        image = Image.new("RGB", (2, 3), "red")
        exif = image.getexif()
        exif[274] = 6
        image.save(source, "JPEG", exif=exif)
        source.seek(0)
        prepared = decode_image(source)
        self.assertEqual((prepared.width, prepared.height), (3, 2))
        self.assertFalse(Image.open(io.BytesIO(prepared.data)).getexif())
        upload = self.upload(filename="../../payload.php")
        payload = upload.read() + b"<?php secret_payload ?>"
        prepared = decode_image(io.BytesIO(payload))
        self.assertNotIn(b"secret_payload", prepared.data)
        with patch("domain.content.media.MAX_IMAGE_PIXELS", 10):
            with self.assertRaises(ValidationError):
                decode_image(self.upload())

    def test_theme_preview_is_signed_scoped_and_does_not_save(self):
        self.signin()
        response = self.client.post(self.prefix + "theme/", self.theme_data(accent_color="#853d30", preview="1"))
        self.assertEqual(response.status_code, 302)
        token = parse_qs(urlsplit(response["Location"]).query)["theme_token"][0]
        css = self.client.get(self.prefix + "theme/preview.css", {"token": token})
        self.assertContains(css, ".theme-preview")
        self.assertNotContains(css, ":root")
        self.assertEqual(SiteTheme.objects.get(pk=1).accent_color, "#9e4934")
        self.assertEqual(self.client.get(self.prefix + "theme/preview.css?token=forged").status_code, 404)
        self.assertEqual(ThemeImage.objects.count(), 0)

    def test_theme_rejects_css_injection_low_contrast_and_unapproved_fonts(self):
        self.signin()
        for changes in ({"text_color": "#eeeeee"}, {"font": "remote-font"}, {"accent_color": "red;url(https://evil.example)"}):
            response = self.client.post(self.prefix + "theme/", self.theme_data(**changes))
            self.assertEqual(response.status_code, 400)
        self.assertEqual(SiteTheme.objects.get(pk=1).version, 1)
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21)

    def test_theme_background_is_gated_and_css_uses_current_settings(self):
        self.signin()
        self.assertEqual(self.client.post(self.prefix + "theme/", self.theme_data(image=self.upload(), font="system")).status_code, 200)
        theme = SiteTheme.objects.get(pk=1)
        old_id = theme.background_image_id
        css = self.public("/theme.css")
        self.assertContains(css, f"/theme/image/{old_id}/")
        self.assertEqual(css["Cache-Control"], "no-store")
        self.assertEqual(self.public(f"/theme/image/{old_id}/").status_code, 200)
        self.assertEqual(self.client.post(self.prefix + "theme/", self.theme_data(clear_background="on")).status_code, 200)
        self.assertEqual(self.public(f"/theme/image/{old_id}/").status_code, 404)
        self.assertEqual(self.client.get(self.prefix + f"image/theme/{old_id}/").status_code, 200)
        self.assertEqual(ThemeImage.objects.count(), 1)

    def test_theme_audit_failure_cleans_file_and_rejects_stale(self):
        changes = {field: getattr(SiteTheme.objects.get(pk=1), field) for field in THEME_FIELDS}
        files = set(Path(self.directory.name).iterdir())
        with patch("domain.content.uploads.AuditEvent.objects.create", side_effect=DatabaseError("audit failure")):
            with self.assertRaises(DatabaseError):
                edit_theme(actor=self.owner, expected_version=1, changes=changes, image=self.upload())
        self.assertEqual(set(Path(self.directory.name).iterdir()), files)
        self.assertIsNone(SiteTheme.objects.get(pk=1).background_image_id)
        self.assertFalse(ThemeImage.objects.exists())
        edit_theme(actor=self.owner, expected_version=1, changes=dict(changes, font="serif"))
        with self.assertRaises(EditConflict):
            edit_theme(actor=self.owner, expected_version=1, changes=changes)

    def test_postgres_upload_role_and_public_theme_boundaries(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires actual PostgreSQL grants.")
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE site_admin")
            try:
                edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, image=self.upload(), alt_en="Restricted role image")
                edit_theme(actor=self.owner, expected_version=1, changes={field: getattr(SiteTheme.objects.get(pk=1), field) for field in THEME_FIELDS}, image=self.upload())
                for sql in ("DELETE FROM content_mediaasset", "UPDATE content_mediaasset SET storage_key = 'evil.png'", "DELETE FROM content_mediaquota", "UPDATE content_themeimage SET validated = FALSE"):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        cursor.execute(sql)
            finally:
                cursor.execute("RESET ROLE")
            cursor.execute("SET LOCAL ROLE site_public")
            try:
                self.assertEqual(self.public("/theme.css").status_code, 200)
                cursor.execute("SELECT * FROM public_theme_image")
                self.assertEqual(len(cursor.fetchall()), 1)
                for table in ("content_mediaquota", "content_sitetheme", "content_themeimage"):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        cursor.execute(f"SELECT * FROM {table}")
            finally:
                cursor.execute("RESET ROLE")
