import io
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from domain.content.media import stage_image
from domain.content.models import (
    MediaAsset, PresentationItem, PublicItem, PublicMedia, Review,
    SiteContent, SourceAccount, Status,
)
from domain.content.validators import validate_instagram_url


class PublicSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = SourceAccount.objects.create(source_account_id="synthetic")
        cls.site = SiteContent.objects.create()

    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.setting_override = override_settings(PRIVATE_MEDIA_ROOT=self.media_dir.name)
        self.setting_override.enable()
        self.addCleanup(self.setting_override.disable)

    def item(self, *, status=Status.PUBLISHED, publish_at=None, source_id="one", caption="Original caption"):
        item = PresentationItem.objects.create(
            account=self.account, source_post_id=source_id,
            canonical_url=f"https://www.instagram.com/p/{source_id}/",
            source_published_at=timezone.now() - timedelta(days=1),
            original_caption=caption, status=status,
            publish_at=publish_at or timezone.now() - timedelta(minutes=1),
        )
        image = io.BytesIO()
        Image.new("RGB", (32, 24), "#9e4934").save(image, "PNG")
        image.seek(0)
        asset = stage_image(item, image, alt_en="Synthetic test image", alt_fr="Image de test")
        return item, asset

    def test_database_views_and_media_hide_all_ineligible_statuses(self):
        item, asset = self.item()
        self.assertEqual(self.client.get(reverse("media", args=[asset.pk])).status_code, 200)
        for status in (Status.DRAFT, Status.HIDDEN, Status.ERROR, Status.ARCHIVED):
            item.status = status
            item.save()
            self.assertFalse(PublicItem.objects.exists())
            self.assertFalse(PublicMedia.objects.exists())
            self.assertEqual(self.client.get(reverse("media", args=[asset.pk])).status_code, 404)
        item.status = Status.PUBLISHED
        item.publish_at = timezone.now() + timedelta(days=1)
        item.save()
        self.assertFalse(PublicItem.objects.exists())

    def test_media_validation_controls_publication_readiness(self):
        item, asset = self.item()
        MediaAsset.objects.filter(pk=asset.pk).update(validated=False)
        self.assertFalse(PublicItem.objects.exists())
        with self.assertRaises(ValidationError):
            stage_image(item, io.BytesIO(b'<svg onload="alert(1)"></svg>'), alt_en="unsafe", sequence=1)
        with self.assertRaises(ValidationError):
            stage_image(item, io.BytesIO(b""), alt_en="", sequence=1)

    def test_caption_is_escaped_and_original_language_preserved(self):
        caption = '<script>alert("x")</script>\n\nBonjour https://example.com'
        self.item(caption=caption)
        for locale in ("en", "fr"):
            response = self.client.get(f"/{locale}/")
            self.assertContains(response, "&lt;script&gt;")
            self.assertNotContains(response, "<script>")
            self.assertContains(response, "Bonjour")
            self.assertContains(response, 'href="https://example.com"')
            self.assertContains(response, 'rel="noopener noreferrer"')
            self.assertEqual(response.headers["Content-Language"], locale)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_pagination_25_items_and_signed_cursor(self):
        for index in range(25):
            self.item(source_id=f"post{index}")
        seen = []
        url = "/en/"
        for count in (12, 12, 1):
            response = self.client.get(url)
            self.assertEqual(len(response.context["cards"]), count)
            seen.extend(card["item"].id for card in response.context["cards"])
            cursor = response.context.get("next_cursor")
            url = f"/en/?cursor={cursor}" if cursor else ""
        self.assertEqual(len(set(seen)), 25)
        self.assertEqual(self.client.get("/en/?cursor=forged").status_code, 400)

    def test_locale_cookie_disabled_language_and_fallback(self):
        self.site.footer_en = "English fallback"
        self.site.footer_fr = ""
        self.site.save()
        self.assertContains(self.client.get("/fr/"), "English fallback")
        self.assertRedirects(self.client.get("/"), "/fr/")
        self.site.french_enabled = False
        self.site.save()
        self.assertEqual(self.client.get("/fr/").status_code, 404)
        self.assertRedirects(self.client.get("/"), "/en/")

    def test_reviews_filter_and_never_offer_public_submission(self):
        for status in (Status.PUBLISHED, Status.HIDDEN):
            Review.objects.create(reviewer_name=status, text_en=f"{status} review", status=status, published_at=timezone.now() - timedelta(days=1))
        response = self.client.get("/fr/reviews/")
        self.assertContains(response, "published review")
        self.assertNotContains(response, "hidden review")
        self.assertEqual(self.client.post("/en/reviews/", {"text": "spam"}).status_code, 405)

    def test_contact_displays_details_and_validates_submissions(self):
        self.assertEqual(self.client.get("/en/contact/").status_code, 200)
        self.assertEqual(self.client.post("/en/contact/", {"email": "test@example.com"}).status_code, 400)

    def test_database_failure_is_safe_and_distinct_from_empty(self):
        self.assertEqual(self.client.get("/en/").status_code, 200)
        with patch("web.public.views.PublicSiteContent.objects.first", side_effect=DatabaseError("secret password")):
            response = self.client.get("/fr/")
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Référence", status_code=503)
        self.assertNotContains(response, "secret password", status_code=503)

    def test_public_process_has_no_admin_routes(self):
        self.assertEqual(self.client.get("/manage-local/").status_code, 404)
        self.assertEqual(self.client.get("/admin/").status_code, 404)
        self.assertContains(self.client.get("/fr/unknown/"), "introuvable", status_code=404)

    def test_canonical_urls_reject_unsafe_hosts_ports_and_queries(self):
        for url in ("javascript:alert(1)", "https://www.instagram.com.evil/p/abc/", "https://www.instagram.com:443/p/abc/", "https://www.instagram.com/p/abc/?token=secret", "https://www.instagram.com@evil.com/p/abc/"):
            with self.assertRaises(ValidationError):
                validate_instagram_url(url)

    def test_database_constraints_reject_duplicate_source_and_invalid_config(self):
        self.item()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.item()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SiteContent.objects.filter(pk=1).update(page_size=49)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SiteContent.objects.filter(pk=1).update(english_enabled=False)

    def test_postgres_runtime_role_denies_private_tables_and_writes(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL and deploy/roles.sql, not SQLite.")
        self.item()
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE site_public")
            try:
                cursor.execute("SELECT count(*) FROM public_feed")
                self.assertEqual(cursor.fetchone()[0], 1)
                # An admin cookie sent to the public host must not cause session
                # loading or a write through admin middleware.
                with override_settings(MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
                    from django.test import Client
                    public_client = Client()
                    public_client.cookies["instagram_admin_session"] = "untrusted"
                    self.assertContains(public_client.get("/en/"), "Original caption")
                for table in ("content_presentationitem", "content_mediaasset", "content_sourceaccount", "auth_user", "django_session"):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        cursor.execute(f"SELECT * FROM {table}")
                with self.assertRaises(DatabaseError), transaction.atomic():
                    cursor.execute("UPDATE public_site_content SET name = 'forbidden'")
            finally:
                cursor.execute("RESET ROLE")
