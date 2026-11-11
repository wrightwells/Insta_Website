from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from domain.content.editing import ITEM_FIELDS, SITE_FIELDS, edit_content
from domain.content.models import AuditEvent, ContentRevision, LoginCounter, MediaAsset, PresentationItem, SiteContent, SiteOwner, SourceAccount, Status
from web.administration.security import counter_key, reserve_login


@override_settings(ROOT_URLCONF="web.administration.urls")
class AdministrationTests(TestCase):
    password = "A private synthetic passphrase 49!"
    prefix = "/manage-local/"

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("owner", password=cls.password, is_staff=True)
        cls.other = get_user_model().objects.create_user("other", password=cls.password, is_staff=True, is_superuser=True)
        SiteOwner.objects.create(user=cls.owner)
        cls.site = SiteContent.objects.create()
        account = SourceAccount.objects.create(source_account_id="synthetic")
        cls.item = PresentationItem.objects.create(account=account, source_post_id="testpost", canonical_url="https://www.instagram.com/p/testpost/", source_published_at=timezone.now() - timedelta(days=1), original_caption="Original source caption")
        MediaAsset.objects.create(item=cls.item, storage_key="a" * 32 + ".png", checksum="b" * 64, size=1, width=1, height=1, alt_en="Synthetic fixture", validated=True)

    def signin(self, client=None):
        return (client or self.client).post(self.prefix + "login/", {"username": "owner", "password": self.password})

    def item_data(self, **changes):
        values = {field: getattr(self.item, field) for field in ITEM_FIELDS}
        values = {key: value if value is not None else "" for key, value in values.items()}
        values["version"] = self.item.version
        values.update(changes)
        return values

    def test_owner_login_rotates_session_and_rejects_other_superuser(self):
        client = Client()
        session = client.session
        session["anonymous"] = True
        session.save()
        before = session.session_key
        response = self.signin(client)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(before, client.session.session_key)
        self.assertEqual(client.get(self.prefix).status_code, 200)
        signed_in_key = client.session.session_key
        self.assertEqual(self.signin(client).status_code, 302)
        self.assertNotEqual(signed_in_key, client.session.session_key)
        self.assertTrue(self.owner.password.startswith("argon2$"))
        other = Client()
        response = other.post(self.prefix + "login/", {"username": "other", "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", other.session)
        self.assertEqual(other.get(self.prefix).status_code, 302)

    def test_login_counter_shared_between_clients_and_expires(self):
        for index in range(5):
            response = Client().post(self.prefix + "login/", {"username": "owner", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
        response = self.signin(Client())
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        keys = list(LoginCounter.objects.values_list("key", flat=True))
        self.assertTrue(all(len(key) == 64 and "owner" not in key for key in keys))
        LoginCounter.objects.update(window_started=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.signin(Client()).status_code, 302)

    def test_ip_limit_and_unicode_account_alias_cannot_bypass_limits(self):
        self.assertEqual(counter_key("account", "ｏｗｎｅｒ"), counter_key("account", "owner"))
        for index in range(20):
            self.assertEqual(reserve_login(f"account{index}", "127.0.0.77"), 0)
        self.assertGreater(reserve_login("another", "127.0.0.77"), 0)

    def test_csrf_and_safe_redirects_and_logout_post_only(self):
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(self.signin(strict).status_code, 403)
        response = strict.get(self.prefix + "login/", secure=True)
        token = response.cookies["csrftoken"].value
        response = strict.post(self.prefix + "login/", {"username": "owner", "password": self.password, "csrfmiddlewaretoken": token, "next": "https://evil.example/"}, secure=True, HTTP_ORIGIN="https://testserver")
        self.assertEqual(response["Location"], self.prefix)
        self.assertEqual(strict.get(self.prefix + "logout/").status_code, 405)
        response = strict.post(self.prefix + "logout/", secure=True)
        self.assertEqual(response.status_code, 403)
        token = strict.cookies["csrftoken"].value
        response = strict.post(self.prefix + "logout/", {"csrfmiddlewaretoken": token}, secure=True, HTTP_ORIGIN="https://testserver")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", strict.session)

    def test_idle_absolute_expiry_disable_and_logout_revoke_access(self):
        for key, age in (("owner_seen_at", 1801), ("owner_login_at", 12 * 3600 + 1)):
            self.signin()
            session = self.client.session
            session[key] = timezone.now().timestamp() - age
            session.save()
            self.assertEqual(self.client.get(self.prefix).status_code, 302)
            self.assertNotIn("_auth_user_id", self.client.session)
        self.signin()
        self.assertEqual(self.client.post(self.prefix + "logout/").status_code, 302)
        self.assertEqual(self.client.get(self.prefix).status_code, 302)
        self.signin()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.prefix).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_session_cookie_flags(self):
        response = self.signin()
        cookie = response.cookies["instagram_admin_session"]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")

    def test_editor_preserves_source_with_revision_and_conflict(self):
        self.signin()
        url = self.prefix + f"items/{self.item.pk}/"
        original = self.item.original_caption
        response = self.client.post(url, self.item_data(display_caption="Edited display"))
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.original_caption, original)
        self.assertEqual(self.item.version, 2)
        self.assertEqual(ContentRevision.objects.get().snapshot["original_caption"], original)
        event = AuditEvent.objects.get(action="edit")
        self.assertEqual(event.changed_fields, ["display_caption"])
        self.assertNotIn("Edited display", str(event.changed_fields))
        response = self.client.post(url, self.item_data(version=1, display_caption="Stale input"))
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "Stale input", status_code=409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.display_caption, "Edited display")

    def test_hidden_confirmation_and_publication_readiness(self):
        published = edit_content(actor=self.owner, model=PresentationItem, pk=self.item.pk, expected_version=1, changes={"status": Status.PUBLISHED, "publish_at": timezone.now()})
        with self.assertRaises(ValidationError):
            edit_content(actor=self.owner, model=PresentationItem, pk=published.pk, expected_version=2, changes={"publish_at": timezone.now() + timedelta(days=1)})
        with self.assertRaises(ValidationError):
            edit_content(actor=self.owner, model=PresentationItem, pk=published.pk, expected_version=2, changes={"status": Status.HIDDEN})
        edit_content(actor=self.owner, model=PresentationItem, pk=published.pk, expected_version=2, changes={"status": Status.HIDDEN}, confirm_hide=True)
        MediaAsset.objects.filter(item=published).update(validated=False)
        with self.assertRaises(ValidationError):
            edit_content(actor=self.owner, model=PresentationItem, pk=published.pk, expected_version=3, changes={"status": Status.PUBLISHED})

    def test_audit_failure_rolls_back_content_and_revision(self):
        with patch("domain.content.editing.AuditEvent.objects.create", side_effect=DatabaseError("synthetic audit outage")):
            with self.assertRaises(DatabaseError):
                edit_content(actor=self.owner, model=PresentationItem, pk=self.item.pk, expected_version=1, changes={"display_caption": "Must roll back"})
        self.item.refresh_from_db()
        self.assertIsNone(self.item.display_caption)
        self.assertEqual(self.item.version, 1)
        self.assertFalse(ContentRevision.objects.exists())

    def test_failed_login_audit_never_creates_authenticated_session(self):
        with patch("web.administration.views.AuditEvent.objects.create", side_effect=DatabaseError("sensitive diagnostic")):
            response = self.signin()
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "sensitive diagnostic", status_code=503)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_database_rejects_history_rewrites_and_deletions(self):
        edit_content(actor=self.owner, model=PresentationItem, pk=self.item.pk, expected_version=1, changes={"display_caption": "Change"})
        for model in (AuditEvent, ContentRevision):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.all().update(entity="tampered")
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.all().delete()

    def test_direct_service_denies_other_owner_and_source_changes(self):
        for actor, changes in ((self.other, {"display_caption": "unauthorised"}), (self.owner, {"original_caption": "overwrite source"})):
            with self.assertRaises((PermissionDenied, ValidationError)):
                edit_content(actor=actor, model=PresentationItem, pk=self.item.pk, expected_version=1, changes=changes)

    def test_settings_preview_escapes_without_writing_and_rejects_stale(self):
        self.signin()
        data = {field: getattr(self.site, field) for field in SITE_FIELDS}
        data.update(version=1, footer_en='<script>alert("x")</script>', preview="1")
        response = self.client.post(self.prefix + "site/", data)
        self.assertContains(response, "&lt;script&gt;")
        self.site.refresh_from_db()
        self.assertNotIn("<script>", self.site.footer_en)
        data.pop("preview")
        self.assertEqual(self.client.post(self.prefix + "site/", data).status_code, 200)
        self.assertEqual(self.client.post(self.prefix + "site/", data).status_code, 409)
        self.site.refresh_from_db()
        data.update(version=2, default_locale="en", english_enabled="")
        self.assertEqual(self.client.post(self.prefix + "site/", data).status_code, 400)

    def test_search_and_object_access_are_protected_and_bounded(self):
        for suffix in ("", f"items/{self.item.pk}/", "site/", "audit/"):
            self.assertEqual(self.client.get(self.prefix + suffix).status_code, 302)
        self.signin()
        response = self.client.get(self.prefix, {"q": "testpost"})
        self.assertContains(response, "Original source caption")
        self.assertEqual(self.client.get(self.prefix, {"q": "x" * 201}).status_code, 400)
        self.assertEqual(self.client.get(self.prefix, {"start": "2026-10-21", "end": "2026-10-01"}).status_code, 400)

    def test_provisioning_is_operator_only_and_single_owner(self):
        with self.assertRaises(CommandError):
            call_command("provision_owner", "second", stdout=StringIO())

    def test_provisioning_validates_password_and_creates_non_superuser_owner(self):
        SiteOwner.objects.all().delete()
        with patch("domain.content.management.commands.provision_owner.getpass", return_value="weak"):
            with self.assertRaises(CommandError):
                call_command("provision_owner", "newowner", stdout=StringIO())
        self.assertFalse(get_user_model().objects.filter(username="newowner").exists())
        with patch("domain.content.management.commands.provision_owner.getpass", return_value=self.password):
            call_command("provision_owner", "newowner", stdout=StringIO())
        newowner = SiteOwner.objects.get(pk=1).user
        self.assertTrue(newowner.check_password(self.password))
        self.assertFalse(newowner.is_superuser)
        self.assertEqual(AuditEvent.objects.get().action, "provision")

    def test_history_is_read_only_and_unsafe_source_urls_are_not_links(self):
        self.signin()
        edit_content(actor=self.owner, model=PresentationItem, pk=self.item.pk, expected_version=1, changes={"display_caption": "Display"})
        revision = ContentRevision.objects.get()
        response = self.client.get(self.prefix + f"history/{revision.pk}/")
        self.assertContains(response, "Original source caption")
        self.assertEqual(self.client.post(self.prefix + f"history/{revision.pk}/", {}).status_code, 405)
        PresentationItem.objects.filter(pk=self.item.pk).update(canonical_url="javascript:alert(1)")
        response = self.client.get(self.prefix + f"items/{self.item.pk}/")
        self.assertNotContains(response, 'href="javascript:')

    def test_postgres_admin_role_can_edit_but_cannot_rewrite_history_or_auth(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL role grants.")
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE site_admin")
            try:
                self.assertEqual(self.signin().status_code, 302)
                response = self.client.post(self.prefix + f"items/{self.item.pk}/", self.item_data(display_caption="Restricted login edit"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get(self.prefix + "audit/").status_code, 200)
                for sql in (
                    "UPDATE auth_user SET is_superuser = TRUE",
                    "DELETE FROM content_auditevent",
                    "UPDATE content_contentrevision SET entity = 'tampered'",
                    "SELECT checkpoint FROM content_sourceaccount",
                    "SELECT * FROM django_migrations",
                ):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        cursor.execute(sql)
            finally:
                cursor.execute("RESET ROLE")
