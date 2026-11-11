from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone, translation

from domain.content.models import PresentationItem, SiteContent, SiteOwner, SourceAccount


@override_settings(ROOT_URLCONF="web.administration.urls")
class AdminLocaleTests(TestCase):
    prefix = "/manage-local/"

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("locale-owner", password="Synthetic locale passphrase 42!", is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        cls.site = SiteContent.objects.create()
        account = SourceAccount.objects.create(source_account_id="locale-fixture")
        cls.item = PresentationItem.objects.create(account=account, source_post_id="locale-fixture", canonical_url="https://www.instagram.com/p/locale-fixture/", source_published_at=timezone.now(), original_caption="Original English caption <untouched>")

    def signin(self):
        self.client.post(self.prefix + "login/", {"username": "locale-owner", "password": "Synthetic locale passphrase 42!"})

    def test_browser_preference_cookie_and_request_isolation(self):
        before = translation.get_language()
        response = self.client.get(self.prefix + "login/", HTTP_ACCEPT_LANGUAGE="fr-CA,fr;q=0.8,en;q=0.5")
        self.assertContains(response, 'lang="fr"')
        self.assertContains(response, "Se connecter")
        self.assertEqual(response["Content-Language"], "fr")
        self.assertIn("Accept-Language", response["Vary"])
        self.assertEqual(translation.get_language(), before)
        self.assertContains(Client().get(self.prefix + "login/"), "Sign in")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        self.assertContains(self.client.get(self.prefix + "login/", HTTP_ACCEPT_LANGUAGE="fr"), "Sign in")

    def test_site_default_and_disabled_language(self):
        SiteContent.objects.filter(pk=self.site.pk).update(default_locale="fr")
        for header in ("", "de", "en;q=0"):
            response = self.client.get(self.prefix + "login/", HTTP_ACCEPT_LANGUAGE=header)
            self.assertContains(response, "Se connecter")
        SiteContent.objects.filter(pk=self.site.pk).update(english_enabled=False)
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(self.prefix + "login/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertContains(response, "Se connecter")
        self.assertNotContains(response, 'value="en"')
        response = self.client.post(self.prefix + "language/", {"language": "en"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_anonymous_switch_requires_csrf_and_restricts_redirect(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(self.prefix + "language/", {"language": "fr"}).status_code, 403)
        strict.get(self.prefix + "login/")
        token = strict.cookies["csrftoken"].value
        response = strict.post(self.prefix + "language/", {"language": "fr", "csrfmiddlewaretoken": token, "next": self.prefix + "login/?next=x"})
        self.assertEqual(response["Location"], self.prefix + "login/?next=x")
        cookie = response.cookies[settings.LANGUAGE_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertContains(strict.get(response["Location"]), "Se connecter")
        for destination in ("https://evil.example/manage-local/", "//evil.example/manage-local/", "/en/", "/manage-local-other/"):
            response = strict.post(self.prefix + "language/", {"language": "en", "csrfmiddlewaretoken": token, "next": destination})
            self.assertEqual(response["Location"], self.prefix + "login/")
        self.assertEqual(strict.get(self.prefix + "language/").status_code, 405)
        strict.post(self.prefix + "language/", {"language": "fr", "csrfmiddlewaretoken": token})
        with self.settings(ROOT_URLCONF="web.public.urls"):
            self.assertEqual(strict.get(self.prefix + "login/").status_code, 404)
            self.assertEqual(strict.get("/")["Location"], "/fr/")

    def test_french_editors_preserve_original_content_and_translate_errors(self):
        self.signin()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        for path, text in (("", "Publications"), ("site/", "Enregistrer les paramètres"), ("theme/", "Enregistrer le thème"), ("audit/", "Journal"), (f"items/{self.item.pk}/", "Enregistrer la publication"), (f"items/{self.item.pk}/image/", "Enregistrer l’image")):
            response = self.client.get(self.prefix + path)
            self.assertContains(response, text)
            self.assertEqual(response["Content-Language"], "fr")
        response = self.client.get(self.prefix + f"items/{self.item.pk}/")
        self.assertContains(response, "Original English caption &lt;untouched&gt;")
        response = self.client.get(self.prefix, {"start": "2026-02-02", "end": "2026-01-01"})
        self.assertContains(response, "La date de début", status_code=400)
        response = self.client.post(self.prefix + f"items/{self.item.pk}/", {"version": self.item.version, "priority": 0, "status": "published", "display_caption": "Keep this submitted text"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Keep this submitted text", status_code=400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "draft")
        self.assertEqual(self.item.original_caption, "Original English caption <untouched>")

    def test_french_save_history_conflict_and_audit_codes(self):
        from domain.content.editing import ITEM_FIELDS
        from domain.content.models import AuditEvent, ContentRevision

        self.signin()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        data = {field: getattr(self.item, field) or "" for field in ITEM_FIELDS}
        data.update(version=self.item.version, priority=0, display_caption="Untranslated editorial input")
        response = self.client.post(self.prefix + f"items/{self.item.pk}/", data)
        self.assertContains(response, "Enregistré.")
        revision = ContentRevision.objects.get(entity_id=str(self.item.pk))
        response = self.client.get(self.prefix + f"history/{revision.pk}/")
        self.assertContains(response, "Version précédente")
        response = self.client.post(self.prefix + f"items/{self.item.pk}/", {**data, "display_caption": "Keep this stale input"})
        self.assertContains(response, "Votre saisie est conservée", status_code=409)
        self.assertContains(response, "Keep this stale input", status_code=409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.display_caption, "Untranslated editorial input")
        self.assertTrue(AuditEvent.objects.filter(action="edit", entity_id=str(self.item.pk)).exists())

    def test_french_login_throttle_and_invalid_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.signin()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"
        response = self.client.post(self.prefix + f"items/{self.item.pk}/image/", {"version": self.item.version, "alt_en": "Original description", "image": SimpleUploadedFile("invalid.png", b"not an image", content_type="image/png")})
        self.assertContains(response, "Image non valide", status_code=400)
        for index in range(5):
            self.client.post(self.prefix + "login/", {"username": "locale-owner", "password": "wrong"})
        response = self.client.post(self.prefix + "login/", {"username": "locale-owner", "password": "wrong"})
        self.assertContains(response, "Trop de tentatives de connexion", status_code=429)
