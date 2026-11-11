import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings

from domain.content.models import AuditEvent, ContentRevision, SiteOwner, SitePolicy, SiteContent
from domain.content.policy import POLICY_FIELDS


@override_settings(ROOT_URLCONF='web.administration.urls')
class PolicyTests(TestCase):
    password = 'Synthetic policy owner password 42!'
    url = '/manage-local/policy/'

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('policy-owner', password=cls.password, is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        SiteContent.objects.create(contact_email="shared@example.com")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'policy'/'privacy.html'
        self.override = override_settings(POLICY_EXPORT_FILE=str(self.path))
        self.override.enable()
        self.addCleanup(self.override.disable)

    def signin(self):
        self.client.post('/manage-local/login/', {'username':self.owner.username, 'password':self.password})

    def data(self, **changes):
        record = SitePolicy.objects.get(pk=1)
        return {**{field:getattr(record, field) for field in POLICY_FIELDS}, 'version':record.version, **changes}

    def test_seeded_policy_complete_and_has_requested_email(self):
        self.signin()
        response = self.client.get(self.url)
        self.assertContains(response, 'Full policy text')
        self.assertContains(response, 'shared@example.com')
        for text in ('Instagram account information', 'Website content and visitors', 'Sharing and external services',
                     'Retention and access removal', 'Request access, correction or deletion', 'Policy changes'):
            self.assertContains(response, text)
        with override_settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            response = Client().get('/privacy/')
            self.assertContains(response, 'mailto:shared@example.com')
            self.assertNotContains(response, 'ReginaldGreatDane@outlook.com')
            self.assertNotContains(response, '{site_name}')
            self.assertFalse(response.cookies)

    def test_owner_csrf_and_public_boundary(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.signin()
        strict = Client(enforce_csrf_checks=True)
        strict.cookies = self.client.cookies
        self.assertEqual(strict.post(self.url, self.data()).status_code, 403)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.client.post('/privacy/', {}).status_code, 405)

    def test_preview_does_not_publish_save_expands_values_and_stale_conflicts(self):
        self.signin()
        values = self.data(site_name='Our Brand', title='Our privacy policy', operator_name='Example Studio',
            contact_address='10 Example Street\nLondon', updated_on='2026-11-11',
            body='## About {site_name}\n\nContact {operator_name} at {contact_email}.\n\n<script>bad</script>')
        response = self.client.post(self.url, {**values, 'preview':'1'})
        self.assertContains(response, 'About Our Brand')
        self.assertContains(response, '&lt;script&gt;bad&lt;/script&gt;')
        self.assertFalse(self.path.exists())
        self.assertEqual(SitePolicy.objects.get(pk=1).version, 1)
        self.assertEqual(self.client.post(self.url, values).status_code, 200)
        saved = SitePolicy.objects.get(pk=1)
        self.assertEqual(saved.version, 2)
        self.assertNotIn('contact_email', POLICY_FIELDS)
        self.assertIn('Contact Example Studio at shared@example.com.', self.path.read_text())
        self.assertIn('10 Example Street<br>London', self.path.read_text())
        self.assertNotIn('<script>', self.path.read_text())
        revision = ContentRevision.objects.get(entity='site_policy')
        self.assertNotIn('contact_email', revision.snapshot)
        self.assertTrue(AuditEvent.objects.filter(entity='site_policy', action='edit').exists())
        self.assertEqual(self.client.post(self.url, values).status_code, 409)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            response = self.client.get('/privacy/')
            self.assertContains(response, 'About Our Brand')
            self.assertContains(response, 'mailto:shared@example.com')
            self.assertNotContains(response, '<script>')

    def test_invalid_email_export_failure_and_audit_failure_do_not_save(self):
        self.signin()
        self.assertEqual(self.client.post(self.url, self.data(title='')).status_code, 400)
        with patch('web.public.policy.write_policy_file', side_effect=OSError('private disk detail')):
            response = self.client.post(self.url, self.data(site_name='Do not save'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(SitePolicy.objects.get(pk=1).version, 1)
        self.assertFalse(ContentRevision.objects.exists())
        with patch('domain.content.editing.AuditEvent.objects.create', side_effect=DatabaseError('private audit detail')):
            response = self.client.post(self.url, self.data(site_name='Do not save'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(SitePolicy.objects.get(pk=1).site_name, 'MySite')
        self.assertFalse(self.path.exists())

    def test_restore_republishes_policy_and_database_outage_uses_saved_artifact(self):
        self.signin()
        self.client.post(self.url, self.data(title='Updated privacy policy'))
        revision = ContentRevision.objects.get(entity='site_policy')
        restore = f'/manage-local/history/{revision.pk}/restore/'
        self.assertEqual(self.client.get(restore).status_code, 200)
        response = self.client.post(restore, {'version':2,'confirm':'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], self.url+'?restored=1')
        self.assertIn('shared@example.com', self.path.read_text())
        with override_settings(ROOT_URLCONF='web.public.urls'):
            with patch('web.public.views.PublicPolicy.objects.first', side_effect=DatabaseError('private database detail')):
                response = self.client.get('/privacy/')
        self.assertContains(response, 'shared@example.com')
        self.assertNotContains(response, 'private database detail')

    def test_contact_email_change_updates_policy_and_published_artifact(self):
        self.signin()
        self.assertNotContains(self.client.get(self.url), 'name="contact_email"')
        site = SiteContent.objects.get(pk=1)
        response = self.client.post('/manage-local/contact/', {'version':site.version, 'contact_email':'new-contact@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('new-contact@example.com', self.path.read_text())
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertContains(self.client.get('/privacy/'), 'mailto:new-contact@example.com')
            self.assertContains(self.client.get('/en/contact/'), 'mailto:new-contact@example.com')
        self.assertContains(self.client.get(self.url), 'new-contact@example.com')
        revision = ContentRevision.objects.get(entity='site_content')
        restore = f'/manage-local/history/{revision.pk}/restore/'
        self.assertEqual(self.client.get(restore).status_code, 200)
        self.assertEqual(self.client.post(restore, {'version':site.version+1,'confirm':'on'}).status_code, 302)
        self.assertIn('shared@example.com', self.path.read_text())

    def test_fresh_site_default_email_is_shared(self):
        self.assertEqual(SiteContent().contact_email, 'email@site.eu')
        SiteContent.objects.filter(pk=1).update(contact_email='email@site.eu')
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertContains(self.client.get('/privacy/'), 'mailto:email@site.eu')
            self.assertContains(self.client.get('/en/contact/'), 'mailto:email@site.eu')

    def test_postgres_runtime_roles_save_policy_and_read_only_public_view(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL runtime roles.')
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE site_admin')
            try:
                self.signin()
                self.assertEqual(self.client.post(self.url, self.data(title='Role-test privacy policy')).status_code, 200)
            finally:
                cursor.execute('RESET ROLE')
            cursor.execute('SET LOCAL ROLE site_public')
            try:
                with override_settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
                    self.assertContains(Client().get('/privacy/'), 'Role-test privacy policy')
            finally:
                cursor.execute('RESET ROLE')
