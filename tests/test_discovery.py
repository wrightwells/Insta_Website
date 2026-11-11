import json
import re
from xml.etree import ElementTree

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from domain.content.discovery import DISCOVERY_FIELDS
from domain.content.editing import _snapshot, edit_content
from domain.content.metadata import SEO_FIELDS
from domain.content.models import AuditEvent, ContentRevision, PublicSiteContent, SiteContent, SiteOwner
from domain.content.restoration import restore_settings
from web.administration.forms import DiscoveryForm


class DiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteContent.objects.create()
        cls.owner = get_user_model().objects.create_user('discovery-owner', password='Synthetic discovery password 42!', is_staff=True)
        SiteOwner.objects.create(user=cls.owner)

    def data(self, **changes):
        self.site.refresh_from_db()
        data = {key: getattr(self.site, key) for key in ('name', *SEO_FIELDS, *DISCOVERY_FIELDS)}
        return {**data, 'version': self.site.version, **changes}

    def signin(self):
        with self.settings(ROOT_URLCONF='web.administration.urls'):
            self.client.post('/manage-local/login/', {'username': 'discovery-owner', 'password': 'Synthetic discovery password 42!'})

    def configure(self, **changes):
        fields = dict(seo_public_origin='https://brand.example', seo_home_canonical_en='https://brand.example/',
            seo_feed_title_en='Primary title', seo_feed_description_en='Primary description',
            seo_social_site_name='Brand', seo_og_title_en='Social title', seo_og_description_en='Social description',
            seo_social_image='https://brand.example/cover.jpg', seo_image_alt_en='Living room',
            seo_twitter_title_en='Twitter title', seo_twitter_description_en='Twitter description',
            seo_twitter_image='https://brand.example/twitter.jpg', seo_twitter_card='summary_large_image',
            seo_favicon='/favicon.ico', seo_apple_icon='/apple-touch-icon.png', seo_theme_color='#ffffff',
            seo_google_verification='google-token', seo_bing_verification='ABC123', seo_max_image_preview='large',
            seo_business_enabled=True, seo_business_name='Real Brand', seo_business_street='1 Test Street',
            seo_business_town='London', seo_business_postcode='AB1 2CD', seo_business_area_served='United Kingdom',
            seo_business_price_range='££', seo_business_description_en='Interior design services')
        fields.update(changes)
        edit_content(actor=self.owner, model=SiteContent, pk=1, expected_version=1, changes=fields)

    @override_settings(ROOT_URLCONF='web.public.urls', PUBLIC_ORIGIN='https://fallback.example')
    def test_requested_head_fields_and_parseable_structured_data(self):
        self.configure()
        response = self.client.get('/en/')
        for fragment in (
            '<title>Primary title</title>', 'name="description" content="Primary description"',
            'rel="canonical" href="https://brand.example/"', 'property="og:title" content="Social title"',
            'property="og:description" content="Social description"', 'property="og:site_name" content="Brand"',
            'property="og:image" content="https://brand.example/cover.jpg"',
            'property="og:image:width" content="1200"', 'property="og:image:height" content="630"',
            'property="og:image:alt" content="Living room"', 'property="og:locale" content="en_GB"',
            'name="twitter:card" content="summary_large_image"', 'name="twitter:title" content="Twitter title"',
            'name="twitter:description" content="Twitter description"', 'name="twitter:image" content="https://brand.example/twitter.jpg"',
            'rel="icon" href="/favicon.ico"', 'rel="apple-touch-icon" href="/apple-touch-icon.png"',
            'name="theme-color" content="#ffffff"', 'name="google-site-verification" content="google-token"',
            'name="msvalidate.01" content="ABC123"',
        ):
            self.assertContains(response, fragment)
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow, max-image-preview:large')
        nonce, raw = re.search(r'<script type="application/ld\+json" nonce="([^"]+)">(.*?)</script>', response.content.decode(), re.S).groups()
        data = json.loads(raw)
        self.assertEqual(data['name'], 'Real Brand')
        self.assertEqual(data['@id'], 'https://brand.example/#business')
        self.assertEqual(data['priceRange'], '££')
        self.assertEqual(data['address']['addressCountry'], 'GB')
        self.assertEqual(data['areaServed']['name'], 'United Kingdom')
        self.assertIn("'nonce-" + nonce + "'", response['Content-Security-Policy'])
        self.assertNotIn("'unsafe-inline'", response['Content-Security-Policy'])

    @override_settings(ROOT_URLCONF='web.public.urls', PUBLIC_ORIGIN='https://fallback.example')
    def test_sitemap_canonicals_languages_and_other_page_urls(self):
        self.configure(seo_home_canonical_fr='https://brand.example/francais/', seo_og_title_fr='Titre social')
        self.assertContains(self.client.get('/fr/'), 'property="og:title" content="Titre social"')
        self.assertContains(self.client.get('/en/reviews/'), 'rel="canonical" href="https://brand.example/en/reviews/"')
        root = ElementTree.fromstring(self.client.get('/sitemap.xml').content)
        urls = {node.text for node in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
        self.assertIn('https://brand.example/', urls)
        self.assertIn('https://brand.example/francais/', urls)
        self.assertNotIn('https://fallback.example/en/', urls)

    @override_settings(ROOT_URLCONF='web.public.urls')
    def test_no_placeholder_schema_and_script_breakout_is_escaped(self):
        self.assertNotContains(self.client.get('/en/'), 'application/ld+json')
        self.configure(seo_business_description_en='</script><script>alert("unsafe")</script>', seo_og_title_en='<unsafe>')
        response = self.client.get('/en/')
        self.assertNotContains(response, '<script>alert')
        self.assertContains(response, '\\u003C/script\\u003E')
        self.assertContains(response, 'content="&lt;unsafe&gt;"')
        raw = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', response.content.decode(), re.S)[1]
        self.assertEqual(json.loads(raw)['description'], '</script><script>alert("unsafe")</script>')

    def test_rejects_unsafe_urls_bad_tokens_colours_locales_and_incomplete_business(self):
        for field, value in (
            ('seo_social_image', 'javascript:alert(1)'), ('seo_favicon', '//evil.example/icon.ico'),
            ('seo_public_origin', 'https://brand.example/path'), ('seo_business_url', 'https://user:secret@example.com'),
            ('seo_theme_color', 'red" onload="x'), ('seo_google_verification', '<meta content=x>'),
            ('seo_locale_en', 'english'), ('seo_business_country', 'United Kingdom'),
        ):
            with self.subTest(field=field):
                form = DiscoveryForm(self.data(**{field: value}), instance=SiteContent.objects.get(pk=1))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        form = DiscoveryForm(self.data(seo_business_enabled=True), instance=SiteContent.objects.get(pk=1))
        self.assertFalse(form.is_valid())
        self.assertIn('seo_business_name', form.errors)

    @override_settings(ROOT_URLCONF='web.administration.urls')
    def test_owner_page_preview_save_stale_version_and_restore(self):
        self.assertEqual(self.client.get('/manage-local/discovery/').status_code, 302)
        self.signin()
        response = self.client.post('/manage-local/discovery/', self.data(seo_og_title_en='Draft social', preview='1'))
        self.assertContains(response, 'Draft social')
        self.assertEqual(SiteContent.objects.get().seo_og_title_en, '')
        response = self.client.post('/manage-local/discovery/', self.data(seo_og_title_en='Saved social'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Discovery settings saved')
        self.assertEqual(PublicSiteContent.objects.get().seo_og_title_en, 'Saved social')
        event = AuditEvent.objects.get(action='edit')
        stale = self.data(seo_og_title_en='stale')
        stale['version'] = 1
        self.assertEqual(self.client.post('/manage-local/discovery/', stale).status_code, 409)
        restore_settings(actor=self.owner, revision_id=event.revision_id, expected_version=2, confirmed=True)
        self.assertEqual(SiteContent.objects.get().seo_og_title_en, '')
        self.assertEqual(self.client.get('/manage-local/discovery/')['Cache-Control'], 'no-store')

    @override_settings(ROOT_URLCONF='web.administration.urls')
    def test_owner_csrf_public_isolation_and_legacy_history(self):
        self.signin()
        strict = Client(enforce_csrf_checks=True)
        strict.cookies = self.client.cookies
        self.assertEqual(strict.post('/manage-local/discovery/', self.data()).status_code, 403)
        with self.settings(ROOT_URLCONF='web.public.urls', MIDDLEWARE=settings.PUBLIC_MIDDLEWARE):
            self.assertEqual(Client().get('/manage-local/discovery/').status_code, 404)
        snapshot = {key: value for key, value in _snapshot(self.site).items() if key not in DISCOVERY_FIELDS}
        source = ContentRevision.objects.create(entity='site_content', entity_id='1', version=1, actor=self.owner, snapshot=snapshot)
        SiteContent.objects.filter(pk=1).update(name='Changed', version=2, seo_google_verification='keep-token')
        result = restore_settings(actor=self.owner, revision_id=source.pk, expected_version=2, confirmed=True)
        self.assertEqual(result.seo_google_verification, 'keep-token')

    @override_settings(ROOT_URLCONF='web.public.urls', LOCAL=False, PUBLIC_INDEXING_ENABLED=True, PUBLIC_ORIGIN='https://brand.example')
    def test_robots_setting_keeps_header_meta_and_robots_txt_consistent(self):
        self.configure(seo_robots='noindex')
        self.assertIn('noindex', self.client.get('/en/')['X-Robots-Tag'])
        self.assertIn(b'Disallow: /', self.client.get('/robots.txt').content)
        SiteContent.objects.filter(pk=1).update(seo_robots='index')
        self.assertContains(self.client.get('/en/'), 'content="index, follow, max-image-preview:large"')
        self.assertIn(b'Allow: /', self.client.get('/robots.txt').content)
        with self.settings(LOCAL=True):
            self.assertIn('noindex', self.client.get('/en/')['X-Robots-Tag'])

    def test_postgres_discovery_grants_preserve_public_read_only(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL roles.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_admin')
            edit_content(actor=self.owner, model=SiteContent, pk=1, expected_version=1, changes={'seo_og_title_en': 'Role title'})
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_public')
            self.assertEqual(PublicSiteContent.objects.get().seo_og_title_en, 'Role title')
            with self.assertRaises(DatabaseError), transaction.atomic():
                SiteContent.objects.update(seo_google_verification='forbidden')
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
