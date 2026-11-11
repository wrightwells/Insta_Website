import io
import tempfile
from copy import deepcopy
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction, DatabaseError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from domain.content.instagram_import import import_post, load_recent
from domain.content.models import (AuditEvent, InstagramImport, InstagramSync, MediaAsset,
                                   PresentationItem, PublicItem, SiteContent, SiteOwner, Status)
from domain.content.uploads import edit_item_image
from web.administration.instagram_client import InstagramUnavailable


class FakeAgent:
    def __init__(self):
        self.posts = [{'source_platform': 'instagram', 'source_account_id': '123', 'source_post_id': '456',
                       'source_url': 'https://www.instagram.com/p/source456/',
                       'source_published_at': '2026-01-01T12:00:00+00:00',
                       'original_caption': 'Original caption <script>unsafe</script>', 'media_type': 'image',
                       'assets': [{'kind': 'image', 'has_image': True}]}]
        self.calls = []
        self.color = 'red'

    def image(self):
        image = io.BytesIO()
        Image.new('RGB', (12, 10), self.color).save(image, 'PNG')
        image.seek(0)
        return image

    def call(self, operation, data=None, image=False):
        self.calls.append((operation, data))
        if operation == 'status':
            return dict(username='demo', configured=True, connected=True, verified_at='2026-01-01', account_id='123')
        if operation == 'recent':
            return {'items': deepcopy(self.posts)}
        if operation == 'image':
            return self.image()
        return {'saved': True}


@override_settings(ROOT_URLCONF='web.administration.urls')
class InstagramIntegrationTests(TestCase):
    path = '/manage-local/instagram/'
    password = 'Synthetic Instagram setup phrase 42!'

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('setup-owner', password=cls.password, is_staff=True)
        cls.other = get_user_model().objects.create_user('setup-other', is_staff=True, is_superuser=True)
        SiteOwner.objects.create(user=cls.owner)
        SiteContent.objects.create()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.agent = FakeAgent()
        self.mock = patch('web.administration.instagram_client.InstagramAgent', return_value=self.agent)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def signin(self, client=None):
        (client or self.client).post('/manage-local/login/', {'username': 'setup-owner', 'password': self.password})

    def test_owner_csrf_and_public_boundaries(self):
        self.assertEqual(self.client.get(self.path).status_code, 302)
        self.assertEqual(self.client.post(self.path, {'action': 'recent', 'limit': 1}).status_code, 302)
        self.client.force_login(self.other)
        session = self.client.session
        session['owner_login_at'] = session['owner_seen_at'] = timezone.now().timestamp()
        session.save()
        self.assertEqual(self.client.get(self.path).status_code, 302)
        strict = Client(enforce_csrf_checks=True)
        self.signin()
        # Session authentication does not replace Django CSRF checks.
        strict.cookies = self.client.cookies
        self.assertEqual(strict.post(self.path, {'action': 'recent', 'limit': 1}).status_code, 403)
        with self.settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            self.assertEqual(Client().get(self.path).status_code, 404)
        self.assertEqual(self.agent.calls, [])

    def test_settings_connection_and_secrets_never_rendered(self):
        self.signin()
        response = self.client.get(self.path)
        self.assertContains(response, 'Load recent posts')
        self.assertNotContains(response, 'OAuth')
        self.assertNotContains(response, 'instagram_business_basic')
        self.assertEqual(response['Cache-Control'], 'no-store')
        response = self.client.post(self.path, {'action': 'account', 'username': 'demo', 'password': 'synthetic-secret'})
        self.assertContains(response, 'saved securely')
        self.assertNotContains(response, 'synthetic-secret')
        self.assertNotIn('synthetic-secret', str(dict(self.client.session)))
        response = self.client.post(self.path, {'action': 'connect', 'verification_code': '123456'})
        self.assertContains(response, 'account verified')
        self.assertNotContains(response, 'value="123456"')
        self.assertIn(('connect', {'verification_code': '123456'}), self.agent.calls)
        self.assertEqual(self.client.get(self.path + 'callback/').status_code, 404)

    def test_import_reaches_public_feed_and_images_in_both_languages(self):
        self.signin()
        response = self.client.post(self.path, {'action': 'recent', 'limit': 1})
        self.assertEqual(response.status_code, 200)
        item = PresentationItem.objects.get()
        self.assertEqual(item.status, Status.PUBLISHED)
        self.assertEqual(item.original_caption, self.agent.posts[0]['original_caption'])
        self.assertEqual(MediaAsset.objects.count(), 1)
        self.assertTrue(PublicItem.objects.filter(pk=item.pk).exists())
        self.assertNotIn('password', str(InstagramImport.objects.get().source_snapshot))
        with self.settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            for locale in ('en', 'fr'):
                page = Client().get(f'/{locale}/')
                self.assertContains(page, 'Original caption &lt;script&gt;')
                self.assertNotContains(page, '<script>unsafe</script>')
            self.assertEqual(Client().get(f'/media/{MediaAsset.objects.get().pk}/').status_code, 200)

    def test_repeat_updates_source_preserves_hidden_editorial_values_and_no_duplicate_media(self):
        load_recent(actor=self.owner, agent=self.agent, limit=1)
        first = MediaAsset.objects.get()
        item = PresentationItem.objects.get()
        PresentationItem.objects.filter(pk=item.pk).update(display_caption='Owner override', status=Status.HIDDEN)
        self.agent.posts[0]['original_caption'] = 'Changed source caption'
        summary = load_recent(actor=self.owner, agent=self.agent, limit=1)
        item.refresh_from_db()
        self.assertEqual(summary['updated'], 1)
        self.assertEqual(item.original_caption, 'Changed source caption')
        self.assertEqual(item.display_caption, 'Owner override')
        self.assertEqual(item.status, Status.HIDDEN)
        self.assertEqual(MediaAsset.objects.get().pk, first.pk)
        self.assertEqual(PresentationItem.objects.count(), 1)
        self.assertEqual(load_recent(actor=self.owner, agent=self.agent, limit=1)['unchanged'], 1)

    def test_owner_image_override_survives_multiple_source_updates(self):
        load_recent(actor=self.owner, agent=self.agent, limit=1)
        item = PresentationItem.objects.get()
        self.agent.color = 'blue'
        edit_item_image(actor=self.owner, item_id=item.pk, expected_version=item.version,
                        alt_en='Owner alt text', image=self.agent.image())
        owner_asset = MediaAsset.objects.get(active=True)
        for caption in ('source revision two', 'source revision three'):
            self.agent.posts[0]['original_caption'] = caption
            self.agent.color = 'green'
            load_recent(actor=self.owner, agent=self.agent, limit=1)
            self.assertEqual(MediaAsset.objects.get(active=True).pk, owner_asset.pk)
            self.assertEqual(MediaAsset.objects.get(active=True).alt_en, 'Owner alt text')

    def test_bad_download_preserves_existing_public_content_and_releases_lease(self):
        load_recent(actor=self.owner, agent=self.agent, limit=1)
        before = PresentationItem.objects.get().original_caption
        self.agent.posts[0]['original_caption'] = 'should not replace good content'
        with patch.object(self.agent, 'image', return_value=io.BytesIO(b'not an image')):
            self.assertEqual(load_recent(actor=self.owner, agent=self.agent, limit=1)['failed'], 1)
        self.assertEqual(PresentationItem.objects.get().original_caption, before)
        self.assertTrue(PublicItem.objects.exists())
        self.assertIsNone(InstagramSync.objects.get().running_until)

    def test_carousel_and_video_cover_images(self):
        self.agent.posts[0]['media_type'] = 'carousel'
        self.agent.posts[0]['assets'].append({'kind': 'video', 'has_image': True})
        load_recent(actor=self.owner, agent=self.agent, limit=1)
        self.assertEqual(MediaAsset.objects.filter(active=True).count(), 2)
        with self.settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            self.assertContains(Client().get('/en/'), '<img ', count=2)

    def test_agent_failure_is_safe_and_lease_overlap_is_rejected(self):
        self.signin()
        with patch.object(self.agent, 'call', side_effect=InstagramUnavailable('Service temporarily unavailable')):
            response = self.client.post(self.path, {'action': 'recent', 'limit': 1})
            self.assertEqual(response.status_code, 400)
        self.assertFalse(PresentationItem.objects.exists())
        from datetime import timedelta
        InstagramSync.objects.create(running_until=timezone.now() + timedelta(minutes=5))
        with self.assertRaises(ValidationError):
            load_recent(actor=self.owner, agent=self.agent, limit=1)

    def test_import_deadline_stops_downloads_and_releases_lease(self):
        with patch('domain.content.instagram_import.time.monotonic', side_effect=[0, 601]):
            summary = load_recent(actor=self.owner, agent=self.agent, limit=1)
        self.assertEqual(summary['failed'], 1)
        self.assertFalse(PresentationItem.objects.exists())
        self.assertFalse(any(operation == 'image' for operation, data in self.agent.calls))
        self.assertIsNone(InstagramSync.objects.get().running_until)

    def test_postgres_import_uses_admin_grants_but_checkpoint_and_public_writes_denied(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL runtime grants.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_admin')
            summary = load_recent(actor=self.owner, agent=self.agent, limit=1)
            self.assertEqual(summary['created'], 1)
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SELECT checkpoint FROM content_sourceaccount')
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_public')
            self.assertTrue(PublicItem.objects.exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                PresentationItem.objects.update(original_caption='forbidden')
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
