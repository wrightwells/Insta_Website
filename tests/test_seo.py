import io
import tempfile
from datetime import timedelta
from xml.etree import ElementTree
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from config.origin import public_origin
from domain.content.editing import SITE_FIELDS, _snapshot, edit_content
from domain.content.media import stage_image
from domain.content.metadata import SEO_FIELDS
from domain.content.models import AuditEvent, ContentRevision, PresentationItem, PublicSiteContent, SiteContent, SiteOwner, SourceAccount, Status
from domain.content.restoration import restore_settings
from unittest.mock import patch


class OriginTests(SimpleTestCase):
    def test_origin_validation_and_local_http(self):
        self.assertEqual(public_origin('https://example.com/', local=False), 'https://example.com')
        self.assertEqual(public_origin('http://localhost:8000', local=True), 'http://localhost:8000')
        self.assertEqual(public_origin('', local=False), '')
        for value in ('http://example.com', '//example.com', 'javascript:alert(1)', 'https://user:secret@example.com', 'https://example.com/path', 'https://example.com?', 'https://example.com#', 'https://example.com/?token=secret', 'https://example.com:99999', 'https://example.com\n', 'https://example.com/#'):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                public_origin(value, local=False)


@override_settings(ROOT_URLCONF='web.public.urls', PUBLIC_ORIGIN='https://public.example', PUBLIC_INDEXING_ENABLED=False)
class PublicMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = SiteContent.objects.create(name='Synthetic Journal', seo_feed_title_en='Custom feed', seo_feed_title_fr='Fil personnalisé', seo_feed_description_en='Custom description', seo_feed_description_fr='Description personnalisée')
        cls.account = SourceAccount.objects.create(source_account_id='seo-fixture')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def item(self, identifier, status=Status.PUBLISHED):
        item = PresentationItem.objects.create(account=self.account, source_post_id=identifier, canonical_url=f'https://www.instagram.com/p/{identifier}/', source_published_at=timezone.now()-timedelta(days=1), publish_at=timezone.now()-timedelta(minutes=1), status=status, original_caption='Original caption remains unchanged')
        stream=io.BytesIO()
        Image.new('RGB', (16,12), 'blue').save(stream, format='PNG')
        stream.seek(0)
        return item, stage_image(item, stream, alt_en='Public test image', alt_fr='Image publique')

    def test_configured_titles_descriptions_and_localized_social_metadata(self):
        for code, title, description in [('en','Custom feed','Custom description'), ('fr','Fil personnalisé','Description personnalisée')]:
            response=self.client.get(f'/{code}/')
            self.assertContains(response, f'<title>{title}</title>')
            self.assertContains(response, f'name="description" content="{description}"')
            self.assertContains(response, f'property="og:title" content="{title}"')
            self.assertContains(response, f'name="twitter:description" content="{description}"')
            self.assertContains(response, f'rel="canonical" href="https://public.example/{code}/"')
            self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')

    def test_metadata_fallbacks_and_escaping_preserve_source_language(self):
        SiteContent.objects.filter(pk=1).update(seo_feed_title_fr=' ', seo_feed_description_fr='', seo_reviews_title_fr='<script>unsafe</script>', seo_reviews_description_fr='" onload="unsafe')
        self.assertContains(self.client.get('/fr/'), '<title>Custom feed</title>')
        response=self.client.get('/fr/reviews/')
        self.assertContains(response, '&lt;script&gt;unsafe&lt;/script&gt;')
        self.assertContains(response, '&quot; onload=&quot;unsafe')
        self.assertNotContains(response, '<script>')
        item, asset=self.item('caption')
        self.assertContains(self.client.get('/fr/'), item.original_caption)

    def test_absolute_urls_ignore_untrusted_forwarding_and_allowed_alias_hosts(self):
        with override_settings(ALLOWED_HOSTS=['alias.example']):
            response=self.client.get('/en/', HTTP_HOST='alias.example', HTTP_X_FORWARDED_HOST='attacker.example', HTTP_X_FORWARDED_PROTO='http')
        self.assertContains(response, 'href="https://public.example/en/"')
        self.assertNotContains(response, 'attacker.example')
        self.assertNotContains(response, 'alias.example')

    def test_social_image_is_publication_gated(self):
        hidden, hidden_asset=self.item('hidden', Status.HIDDEN)
        response=self.client.get('/en/')
        self.assertNotContains(response, 'property="og:image"')
        item, asset=self.item('visible')
        response=self.client.get('/fr/')
        self.assertContains(response, f'property="og:image" content="https://public.example/media/{asset.pk}/"')
        self.assertContains(response, 'property="og:image:alt" content="Image publique"')
        self.assertNotContains(response, str(hidden_asset.pk))
        item.status=Status.HIDDEN
        item.save()
        self.assertNotContains(self.client.get('/en/'), 'property="og:image"')
        self.assertEqual(self.client.get(f'/media/{asset.pk}/').status_code, 404)

    def test_sitemap_has_only_enabled_ready_public_pages_and_reciprocal_alternates(self):
        response=self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/xml', response['Content-Type'])
        root=ElementTree.fromstring(response.content)
        ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9','x':'http://www.w3.org/1999/xhtml'}
        urls=root.findall('s:url',ns)
        self.assertEqual({node.find('s:loc',ns).text for node in urls}, {'https://public.example/en/','https://public.example/fr/','https://public.example/en/reviews/','https://public.example/fr/reviews/','https://public.example/en/contact/','https://public.example/fr/contact/'})
        for node in urls:
            links=node.findall('x:link',ns)
            self.assertEqual({link.attrib['hreflang'] for link in links}, {'en','fr','x-default'})
        for word in ('manage-local','media/','cursor=','health','synthetic'):
            self.assertNotIn(word, response.content.decode())
        SiteContent.objects.filter(pk=1).update(french_enabled=False)
        root=ElementTree.fromstring(self.client.get('/sitemap.xml').content)
        self.assertEqual(len(root.findall('s:url',ns)),3)
        self.assertNotIn('hreflang="fr"', ElementTree.tostring(root).decode())
        self.assertEqual(self.client.get('/fr/').status_code,404)

    def test_indexing_defaults_and_production_opt_in(self):
        self.assertEqual(self.client.get('/robots.txt').content.decode(),'User-agent: *\nDisallow: /\n')
        with override_settings(PUBLIC_INDEXING_ENABLED=True):
            self.assertContains(self.client.get('/en/'),'content="noindex, follow"')
            self.assertIn('Disallow: /',self.client.get('/robots.txt').content.decode())
        with override_settings(LOCAL=False,PUBLIC_INDEXING_ENABLED=True):
            self.assertEqual(self.client.get('/en/')['X-Robots-Tag'],'index, follow')
            self.assertIn('Sitemap: https://public.example/sitemap.xml',self.client.get('/robots.txt').content.decode())
            response=self.client.get('/en/contact/')
            self.assertEqual(response['X-Robots-Tag'],'index, follow')
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.client.get('/missing/')['X-Robots-Tag'],'noindex, nofollow')

    def test_paginated_canonical_keeps_valid_cursor_and_remains_noindex(self):
        SiteContent.objects.filter(pk=1).update(page_size=1)
        self.item('first')
        self.item('second')
        first=self.client.get('/en/')
        cursor=first.context['next_cursor']
        with override_settings(LOCAL=False,PUBLIC_INDEXING_ENABLED=True):
            response=self.client.get('/en/',{'cursor':cursor})
            self.assertEqual(response['X-Robots-Tag'],'noindex, follow')
            self.assertContains(response, 'rel="canonical" href="https://public.example/en/?cursor=')
            self.assertEqual(parse_qs(urlsplit(response.context['seo']['canonical']).query)['cursor'],[cursor])
            invalid=self.client.get('/en/?cursor=forged')
            self.assertEqual(invalid.status_code,400)
            self.assertNotContains(invalid,'rel="canonical"',status_code=400)

    def test_public_landing_honors_default_without_browser_preference(self):
        SiteContent.objects.filter(pk=1).update(default_locale='fr')
        for header in ('','de','en;q=0','*'):
            response=Client().get('/',HTTP_ACCEPT_LANGUAGE=header)
            self.assertEqual(response['Location'],'/fr/')
        self.assertEqual(Client().get('/',HTTP_ACCEPT_LANGUAGE='en')['Location'],'/en/')
        self.assertEqual(Client().get('/',HTTP_ACCEPT_LANGUAGE='fr-CA')['Location'],'/fr/')

    def test_missing_origin_and_database_failures_do_not_advertise_wrong_urls(self):
        with override_settings(PUBLIC_ORIGIN=''):
            self.assertNotContains(self.client.get('/en/'),'rel="canonical"')
            self.assertEqual(self.client.get('/sitemap.xml').status_code,503)
        with patch('web.public.views.PublicSiteContent.objects.first',side_effect=DatabaseError('private connection secret')):
            response=self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code,503)
        self.assertNotIn(b'private connection secret',response.content)


@override_settings(ROOT_URLCONF='web.administration.urls')
class AdminMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=get_user_model().objects.create_user('seo-owner',password='Synthetic SEO passphrase 42!',is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        cls.site=SiteContent.objects.create(name='SEO fixture')

    def signin(self):
        self.client.post('/manage-local/login/',{'username':'seo-owner','password':'Synthetic SEO passphrase 42!'})

    def data(self, **changes):
        self.site.refresh_from_db()
        return {**{field:getattr(self.site,field) for field in SITE_FIELDS},'version':self.site.version,**changes}

    def test_audited_metadata_edit_preview_and_restoration(self):
        self.signin()
        path='/manage-local/site/'
        response=self.client.post(path,self.data(seo_feed_title_en='Preview title',preview='1'))
        self.assertContains(response,'Search and sharing preview')
        self.assertContains(response,'Preview title')
        self.assertEqual(SiteContent.objects.get(pk=1).seo_feed_title_en,'')
        response=self.client.post(path,self.data(seo_feed_title_en='Saved title',seo_reviews_description_fr='Description avis'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(PublicSiteContent.objects.get(pk=1).seo_feed_title_en,'Saved title')
        event=AuditEvent.objects.get(action='edit')
        self.assertIn('seo_feed_title_en',event.changed_fields)
        restore_settings(actor=self.owner,revision_id=event.revision_id,expected_version=2,confirmed=True)
        self.assertEqual(SiteContent.objects.get(pk=1).seo_feed_title_en,'')

    def test_legacy_settings_revision_preserves_new_optional_metadata(self):
        snapshot={key:value for key,value in _snapshot(self.site).items() if key not in SEO_FIELDS}
        source=ContentRevision.objects.create(entity='site_content',entity_id='1',version=1,actor=self.owner,snapshot=snapshot)
        SiteContent.objects.filter(pk=1).update(name='Changed',version=2,seo_feed_title_en='Keep this new title')
        result=restore_settings(actor=self.owner,revision_id=source.pk,expected_version=2,confirmed=True)
        self.assertEqual(result.name,'SEO fixture')
        self.assertEqual(result.seo_feed_title_en,'Keep this new title')

    def test_metadata_limits_french_labels_and_admin_indexing_isolation(self):
        self.signin()
        response=self.client.post('/manage-local/site/',self.data(seo_feed_title_en='x'*161))
        self.assertEqual(response.status_code,400)
        self.assertEqual(SiteContent.objects.get(pk=1).version,1)
        self.client.cookies['site_language']='fr'
        response=self.client.get('/manage-local/site/')
        self.assertContains(response,'Titre du fil (anglais)')
        with override_settings(LOCAL=False,PUBLIC_INDEXING_ENABLED=True,PUBLIC_ORIGIN='https://public.example'):
            self.assertIn('Disallow: /',self.client.get('/robots.txt').content.decode())
            self.assertEqual(self.client.get('/sitemap.xml').status_code,404)
            self.assertEqual(self.client.get('/manage-local/login/')['X-Robots-Tag'],'noindex, nofollow')

    def test_postgres_runtime_roles_keep_metadata_boundary(self):
        if connection.vendor!='postgresql':
            self.skipTest('Requires PostgreSQL runtime grants.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_admin')
            edit_content(actor=self.owner,model=SiteContent,pk=1,expected_version=1,changes={'seo_feed_title_en':'Restricted-role title'})
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_public')
            self.assertEqual(PublicSiteContent.objects.get(pk=1).seo_feed_title_en,'Restricted-role title')
            with self.assertRaises(DatabaseError),transaction.atomic():
                SiteContent.objects.filter(pk=1).update(seo_feed_title_en='Forbidden')
            with self.assertRaises(DatabaseError),transaction.atomic():
                AuditEvent.objects.count()
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
