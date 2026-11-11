from urllib.parse import parse_qs, urlsplit
import io
from pathlib import Path
import tempfile
from datetime import timedelta
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from domain.content.editing import SITE_FIELDS, delete_story
from domain.content.instagram_import import import_post
from domain.content.models import (AuditEvent, ContentRevision, MediaAsset, PresentationItem,
    PublicItem, PublicMedia, SiteContent, SiteOwner, SiteTheme, SourceAccount, Status)
from domain.content.theme import THEME_FIELDS


@override_settings(ROOT_URLCONF='web.administration.urls')
class OwnerControlsTests(TestCase):
    password = 'Synthetic owner passphrase 93!'
    new_password = 'Another private passphrase 75!'
    prefix = '/manage-local/'

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(POLICY_EXPORT_FILE=str(Path(directory.name)/'privacy.html'))
        override.enable()
        self.addCleanup(override.disable)

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('control-owner', password=cls.password, is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        cls.site = SiteContent.objects.create()
        account = SourceAccount.objects.create(source_account_id='123')
        cls.item = PresentationItem.objects.create(account=account, source_post_id='456',
            canonical_url='https://www.instagram.com/p/456/', original_caption='An actual feed story',
            source_published_at=timezone.now()-timedelta(days=1), status=Status.PUBLISHED,
            publish_at=timezone.now()-timedelta(hours=1))
        cls.asset = MediaAsset.objects.create(item=cls.item, storage_key='a'*32+'.png', checksum='b'*64,
            size=1, width=1, height=1, alt_en='A real feed image', validated=True)

    def signin(self, client=None):
        client = client or self.client
        client.post(self.prefix+'login/', {'username':self.owner.username, 'password':self.password})

    def test_new_routes_require_owner_and_csrf(self):
        paths = ('contact/', 'reviews/', 'password/', f'items/{self.item.pk}/delete/', 'preview/en/', f'preview/media/{self.asset.pk}/')
        for path in paths:
            self.assertEqual(self.client.get(self.prefix+path).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        self.signin()
        strict.cookies = self.client.cookies
        for path in paths[:4]:
            self.assertEqual(strict.post(self.prefix+path, {}).status_code, 403)
        other = get_user_model().objects.create_user('other-control', is_staff=True)
        with self.assertRaises(PermissionDenied):
            delete_story(actor=other, pk=self.item.pk, expected_version=1)

    def test_password_validation_changes_hash_preserves_session_and_revokes_other_sessions(self):
        other = Client()
        self.signin(other)
        self.signin()
        url = self.prefix+'password/'
        for values in ({'old_password':'wrong', 'new_password1':self.new_password, 'new_password2':self.new_password},
                       {'old_password':self.password, 'new_password1':'weak', 'new_password2':'weak'}):
            self.assertEqual(self.client.post(url, values).status_code, 400)
        response = self.client.post(url, {'old_password':self.password, 'new_password1':self.new_password, 'new_password2':self.new_password})
        self.assertEqual(response.status_code, 302)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password(self.new_password))
        self.assertEqual(self.client.get(self.prefix).status_code, 200)
        self.assertEqual(other.get(self.prefix).status_code, 302)
        event = AuditEvent.objects.get(action='change_password')
        self.assertEqual(event.changed_fields, [])
        self.assertNotIn(self.new_password, self.client.get(url+'?saved=1').content.decode())

    def test_password_audit_failure_rolls_back(self):
        self.signin()
        with patch('web.administration.views.AuditEvent.objects.create', side_effect=DatabaseError('private')):
            response = self.client.post(self.prefix+'password/', {'old_password':self.password,
                'new_password1':self.new_password, 'new_password2':self.new_password})
        self.assertEqual(response.status_code, 503)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password(self.password))

    def test_contact_save_validation_locales_escape_and_conflict(self):
        self.signin()
        url = self.prefix+'contact/'
        self.assertEqual(self.client.post(url, {'version':1, 'contact_email':'invalid'}).status_code, 400)
        values = {'version':1, 'contact_email':'hello@example.com', 'contact_phone':'+44 (0)1234 567890',
            'contact_address':'First line\nSecond line', 'contact_intro_en':'<script>unsafe</script>',
            'contact_intro_fr':'Bonjour', 'contact_hours_en':'Weekdays 9–5'}
        self.assertEqual(self.client.post(url, values).status_code, 200)
        self.assertEqual(self.client.post(url, values).status_code, 409)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            response = self.client.get('/en/contact/')
            self.assertContains(response, 'mailto:hello@example.com')
            self.assertContains(response, 'tel:+4401234567890')
            self.assertContains(response, '&lt;script&gt;unsafe&lt;/script&gt;')
            self.assertContains(self.client.get('/fr/contact/'), 'Bonjour')
            self.assertContains(self.client.get('/fr/contact/'), 'Weekdays 9–5')
            self.assertEqual(self.client.post('/en/contact/', values).status_code, 400)

    def test_reviews_toggle_controls_navigation_route_sitemap_and_reenabling(self):
        self.signin()
        self.assertEqual(self.client.post(self.prefix+'reviews/', {'version':1}).status_code, 200)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertNotContains(self.client.get('/en/'), '/en/reviews/')
            self.assertEqual(self.client.get('/en/reviews/').status_code, 404)
            self.assertEqual(self.client.get('/fr/reviews/').status_code, 404)
            self.assertNotContains(self.client.get('/sitemap.xml'), '/reviews/')
        self.assertEqual(self.client.get(self.prefix+'reviews/').status_code, 200)
        self.client.post(self.prefix+'reviews/', {'version':2, 'reviews_enabled':'on'})
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertEqual(self.client.get('/fr/reviews/').status_code, 200)
            self.assertContains(self.client.get('/en/'), '/en/reviews/')

    def test_delete_confirmation_conflict_history_public_gates_and_import_tombstone(self):
        self.signin()
        url = self.prefix+f'items/{self.item.pk}/delete/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIsNone(PresentationItem.objects.get(pk=self.item.pk).deleted_at)
        self.assertEqual(self.client.post(url, {'version':1}).status_code, 400)
        self.assertEqual(self.client.post(url, {'version':2, 'confirm':'on'}).status_code, 409)
        self.assertEqual(self.client.post(url, {'version':1, 'confirm':'on'}).status_code, 302)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.deleted_at)
        self.assertEqual(self.item.status, Status.ARCHIVED)
        self.assertFalse(PublicItem.objects.exists())
        self.assertFalse(PublicMedia.objects.exists())
        self.assertNotContains(self.client.get(self.prefix), 'An actual feed story')
        self.assertEqual(self.client.get(self.prefix+f'items/{self.item.pk}/').status_code, 404)
        self.assertEqual(self.client.get(self.prefix+f'items/{self.item.pk}/image/').status_code, 404)
        event = AuditEvent.objects.get(action='delete_story')
        self.assertEqual(event.revision.snapshot['original_caption'], 'An actual feed story')
        self.assertEqual(len(event.revision.snapshot['media']), 1)
        with tempfile.TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=directory):
            image = io.BytesIO()
            Image.new('RGB', (10,10), 'blue').save(image, 'PNG')
            image.seek(0)
            outcome = import_post(actor=self.owner, post={'source_account_id':'123', 'source_post_id':'456',
                'source_url':self.item.canonical_url, 'source_published_at':timezone.now().isoformat(),
                'original_caption':'Changed at source', 'media_type':'image'}, images=[image])
        self.assertEqual(outcome, 'unchanged')
        self.assertEqual(PresentationItem.objects.count(), 1)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertEqual(self.client.get(f'/media/{self.asset.pk}/').status_code, 404)

    def test_delete_audit_failure_rolls_back(self):
        with patch('domain.content.editing.AuditEvent.objects.create', side_effect=DatabaseError('private')):
            with self.assertRaises(DatabaseError):
                delete_story(actor=self.owner, pk=self.item.pk, expected_version=1)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.deleted_at)
        self.assertFalse(ContentRevision.objects.exists())
        self.assertTrue(PublicItem.objects.exists())

    def test_appearance_preview_uses_actual_feed_images_and_proposed_theme_without_saving(self):
        self.signin()
        theme = SiteTheme.objects.get(pk=1)
        response = self.client.get(self.prefix+'theme/')
        self.assertNotContains(response, '<iframe')
        self.assertContains(response, 'formtarget="_blank"')
        self.assertIn("frame-src 'none'", response['Content-Security-Policy'])
        data = {field:getattr(theme,field) for field in THEME_FIELDS}
        response = self.client.post(self.prefix+'theme/', {**data, 'version':theme.version, 'accent_color':'#853d30', 'preview':'1'})
        self.assertEqual(response.status_code, 302)
        token = parse_qs(urlsplit(response['Location']).query)['theme_token'][0]
        response = self.client.get(self.prefix+'preview/en/', {'theme_token':token})
        self.assertContains(response, 'An actual feed story')
        self.assertContains(response, self.prefix+f'preview/media/{self.asset.pk}/')
        self.assertContains(response, 'full=1&amp;token=')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertIn("frame-ancestors 'self'", response['Content-Security-Policy'])
        css = self.client.get(self.prefix+'theme/preview.css', {'token':token, 'full':'1'})
        self.assertContains(css, ':root')
        self.assertContains(css, '#853d30')
        self.assertEqual(SiteTheme.objects.get(pk=1).accent_color, theme.accent_color)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertEqual(self.client.get(self.prefix+'preview/en/').status_code, 404)
            self.assertIn("frame-ancestors 'none'", self.client.get('/en/')['Content-Security-Policy'])

    def test_site_copy_edits_journal_label_and_heading_with_preview_and_language_fallback(self):
        self.signin()
        url = self.prefix+'site/'
        response = self.client.get(url)
        self.assertContains(response, 'Main feed introduction')
        self.assertContains(response, 'placeholder="THE JOURNAL"')
        self.assertContains(response, 'placeholder="Moments worth keeping."')
        values = {field:getattr(self.site, field) for field in SITE_FIELDS}
        values.update(version=1, journal_en='LATEST NEWS', journal_fr='ACTUALITÉS',
            feed_heading_en='<em>Our latest projects</em>', feed_heading_fr='Nos derniers projets')
        response = self.client.post(url, {**values, 'preview':'1'})
        self.assertContains(response, '&lt;em&gt;Our latest projects&lt;/em&gt;')
        self.site.refresh_from_db()
        self.assertEqual(self.site.journal_en, '')
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertContains(self.client.get('/en/'), 'Moments worth keeping.')
        self.assertEqual(self.client.post(url, values).status_code, 200)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertContains(self.client.get('/en/'), '<p class="eyebrow">LATEST NEWS</p>')
            self.assertContains(self.client.get('/en/'), '<h1>&lt;em&gt;Our latest projects&lt;/em&gt;</h1>')
            self.assertContains(self.client.get('/fr/'), '<h1>Nos derniers projets</h1>')
        self.assertContains(self.client.get(self.prefix+'preview/en/'), 'LATEST NEWS')
        values.update(version=2, journal_fr='', feed_heading_fr='')
        self.assertEqual(self.client.post(url, values).status_code, 200)
        with override_settings(ROOT_URLCONF='web.public.urls'):
            self.assertContains(self.client.get('/fr/'), 'LATEST NEWS')
            self.assertContains(self.client.get('/fr/'), '<h1>&lt;em&gt;Our latest projects&lt;/em&gt;</h1>')
        self.assertEqual(self.client.post(url, values).status_code, 409)

    def test_postgres_owner_can_change_password_delete_and_preview_with_runtime_role(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL runtime role grants.')
        with connection.cursor() as cursor:
            cursor.execute('SET LOCAL ROLE site_admin')
            try:
                self.signin()
                values = {field:getattr(self.site, field) for field in SITE_FIELDS}
                values.update(version=1, journal_en='THE JOURNAL', feed_heading_en='Our projects')
                self.assertEqual(self.client.post(self.prefix+'site/', values).status_code, 200)
                self.assertContains(self.client.get(self.prefix+'preview/en/'), 'Our projects')
                self.assertEqual(self.client.post(self.prefix+'contact/', {'version':2, 'contact_email':'hello@example.com'}).status_code, 200)
                self.assertEqual(self.client.post(self.prefix+'password/', {'old_password':self.password,
                    'new_password1':self.new_password,'new_password2':self.new_password}).status_code, 302)
                self.assertEqual(self.client.post(self.prefix+f'items/{self.item.pk}/delete/', {'version':1, 'confirm':'on'}).status_code, 302)
            finally:
                cursor.execute('RESET ROLE')
