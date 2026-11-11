import json
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings

from domain.content.contact_mail import DEFAULTS, read_mail_settings, save_mail_settings
from domain.content.models import AuditEvent, ContactDelivery, ContactRate, SiteContent, SiteOwner
from web.administration.forms import ContactMailForm, DiscoveryForm


@override_settings(ROOT_URLCONF='web.public.urls', CONTACT_EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ContactDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteContent.objects.create(contact_email='public@example.com', contact_phone='+44 1234 567890',
            contact_address='10 Example Street', contact_hours_en='Monday to Friday')
        cls.owner = get_user_model().objects.create_user('mail-owner', password='Synthetic mail password 45!', is_staff=True)
        SiteOwner.objects.create(user=cls.owner)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'private'/'smtp.json'
        self.override = override_settings(CONTACT_MAIL_SETTINGS_FILE=str(self.path), POLICY_EXPORT_FILE=str(Path(self.directory.name)/'privacy.html'))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.configure()
        mail.outbox = []

    def configure(self, **changes):
        values = {**DEFAULTS, 'enabled':True, 'host':'smtp.example.com', 'from_email':'sender@example.com',
            'username':'smtp-user', 'password':'synthetic SMTP secret', **changes}
        values['version'] = read_mail_settings()['version']
        return save_mail_settings(actor=self.owner, values=values)

    def data(self, client=None, **changes):
        response = (client or self.client).get('/en/contact/')
        return {'email':'visitor@example.com', 'mobile':'+44 7700 900123', 'message':'Synthetic enquiry text',
            'submission_token':response.context['enquiry_form'].initial['submission_token'], **changes}

    def test_keeps_details_and_sends_valid_enquiry_to_current_public_address(self):
        response = self.client.get('/en/contact/')
        for text in ('public@example.com', '+44 1234 567890', '10 Example Street', 'Monday to Friday',
                     'Email address', 'Mobile number', 'Message'):
            self.assertContains(response, text)
        data = self.data()
        SiteContent.objects.filter(pk=1).update(contact_email='new-public@example.com')
        response = self.client.post('/en/contact/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['new-public@example.com'])
        self.assertEqual(message.from_email, 'sender@example.com')
        self.assertEqual(message.reply_to, ['visitor@example.com'])
        self.assertIn('+44 7700 900123', message.body)
        self.assertIn('Synthetic enquiry text', message.body)
        self.assertEqual(ContactDelivery.objects.get().state, 'sent')
        self.assertEqual({field.name for field in ContactDelivery._meta.fields}, {'id','created_at','state'})
        self.assertContains(self.client.get(response['Location']), 'Your message has been sent.')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post('/en/contact/', data).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_validation_csrf_binding_and_honeypot_do_not_send(self):
        for changes in ({'email':'bad'}, {'mobile':'-------'}, {'message':''}, {'message':'x'*5001},
                        {'email':'bad@example.com\nBcc: other@example.com'}, {'submission_token':'forged'}):
            self.assertEqual(self.client.post('/en/contact/', self.data(**changes)).status_code, 400)
        other = Client()
        self.assertEqual(other.post('/en/contact/', self.data()).status_code, 400)
        strict = Client(enforce_csrf_checks=True)
        data = self.data(strict)
        self.assertEqual(strict.post('/en/contact/', data).status_code, 403)
        strict.get('/en/contact/')
        csrf = strict.cookies['csrftoken'].value
        self.assertEqual(strict.post('/en/contact/', {**data,'csrfmiddlewaretoken':csrf}).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post('/en/contact/', self.data(website='https://spam.example')).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        with patch('web.public.views.signing.loads', side_effect=signing.SignatureExpired):
            response = self.client.post('/en/contact/', self.data())
        self.assertContains(response, 'form has expired', status_code=400)
        self.assertEqual(len(mail.outbox), 1)

    def test_delivery_failure_and_unconfigured_email_do_not_claim_success(self):
        with patch('domain.content.contact_mail.EmailMessage.send', side_effect=OSError('private provider diagnostic')):
            response = self.client.post('/en/contact/', self.data())
        self.assertContains(response, 'cannot send messages', status_code=503)
        self.assertNotContains(response, 'private provider diagnostic', status_code=503)
        self.assertNotContains(response, 'Your message has been sent.', status_code=503)
        self.assertEqual(ContactDelivery.objects.get().state, 'failed')
        self.configure(enabled=False)
        self.assertEqual(self.client.post('/en/contact/', self.data()).status_code, 503)
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_form_hidden_until_delivery_settings_and_recipient_are_ready(self):
        for missing in ({'enabled':False}, {'host':''}, {'from_email':''}, {'password':'', 'clear_password':True}):
            self.configure(**missing)
            response = self.client.get('/en/contact/')
            self.assertNotContains(response, '<form')
            self.assertNotContains(response, 'Send us a message')
            self.assertNotContains(response, 'cannot send messages')
            self.assertContains(response, '10 Example Street')
            self.assertContains(response, 'contact-details-only')
        self.configure()
        SiteContent.objects.filter(pk=1).update(contact_email='')
        self.assertNotContains(self.client.get('/en/contact/'), '<form')
        SiteContent.objects.filter(pk=1).update(contact_email='email@site.eu')
        self.assertNotContains(self.client.get('/en/contact/'), '<form')
        SiteContent.objects.filter(pk=1).update(contact_email='public@example.com')
        self.assertContains(self.client.get('/en/contact/'), '<form')

    def test_shared_rate_limit_and_french_labels(self):
        for index in range(5):
            self.assertEqual(self.client.post('/en/contact/', self.data()).status_code, 302)
        response = self.client.post('/en/contact/', self.data())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(ContactRate.objects.get().attempts, 5)
        self.assertNotIn('127.0.0.1', ContactRate.objects.get().key)
        response = self.client.get('/fr/contact/')
        self.assertContains(response, 'Adresse e-mail')
        self.assertContains(response, 'Numéro de mobile')

    @override_settings(ROOT_URLCONF='web.administration.urls')
    def test_mail_settings_owner_only_password_retention_conflict_and_no_disclosure(self):
        url = '/manage-local/contact/email/'
        self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.client.post('/manage-local/login/', {'username':self.owner.username,'password':'Synthetic mail password 45!'})
        response = self.client.get('/manage-local/contact/')
        self.assertContains(response, 'Email delivery')
        self.assertNotContains(response, 'synthetic SMTP secret')
        values = {**read_mail_settings(), 'password':'new synthetic password'}
        response = self.client.post(url, values)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(read_mail_settings()['password'], 'new synthetic password')
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(self.client.post(url, values).status_code, 409)
        values.update(version=read_mail_settings()['version'], password='')
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(read_mail_settings()['password'], 'new synthetic password')
        values.update(version=read_mail_settings()['version'], clear_password='on')
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(read_mail_settings()['password'], '')
        self.assertNotIn('synthetic SMTP secret', str(list(AuditEvent.objects.values())))
        values.update(version=read_mail_settings()['version'], host='https://invalid-host')
        values['password'] = 'must never appear in errors'
        response = self.client.post(url, values)
        self.assertNotContains(response, values['password'], status_code=400)

    def test_mail_configuration_validation_and_audit_failure_rollback(self):
        self.assertFalse(ContactMailForm({'version':1, 'enabled':'on', 'port':587, 'security':'starttls'}).is_valid())
        before = self.path.read_bytes()
        with patch('domain.content.contact_mail.AuditEvent.objects.create', side_effect=DatabaseError('private')):
            with self.assertRaises(DatabaseError):
                self.configure(host='new.example.com')
        self.assertEqual(self.path.read_bytes(), before)

    def test_discovery_examples_cover_all_fields_and_show_actual_fallbacks(self):
        SiteContent.objects.filter(pk=1).update(name='Our Site', seo_feed_title_en='Custom feed title')
        site = SiteContent.objects.get(pk=1)
        form = DiscoveryForm(instance=site)
        for name,field in form.fields.items():
            if name != 'version':
                self.assertTrue(field.example, name)
                self.assertTrue(field.fallback, name)
        self.assertEqual(form.fields['seo_og_title_en'].fallback_value, 'Custom feed title')
        self.assertEqual(form.fields['seo_feed_title_en'].fallback_value, 'Main feed · Our Site')

    def test_postgres_public_role_can_send_without_access_to_private_content(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL runtime role grants.')
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE site_public')
            try:
                response = self.client.post('/en/contact/', self.data())
                self.assertEqual(response.status_code, 302)
                self.assertEqual(len(mail.outbox), 1)
            finally:
                cursor.execute('RESET ROLE')
