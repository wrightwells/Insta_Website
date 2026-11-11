import io
import tempfile
from datetime import timedelta
from html.parser import HTMLParser
from xml.etree import ElementTree

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.handlers.wsgi import WSGIHandler
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from config.mount import script_prefix
from domain.content.media import decode_image, persist_image, stage_image
from domain.content.models import AuditEvent, PresentationItem, SiteContent, SiteTheme, SourceAccount, Status, ThemeImage


class MountConfigurationTests(SimpleTestCase):
    def test_prefix_validation(self):
        for value, expected in (('', ''), ('/', ''), ('/mysite', '/mysite'), ('/mysite/', '/mysite'), ('/nested/site', '/nested/site')):
            self.assertEqual(script_prefix(value),expected)
        for value in ('mysite','//mysite','/../other','/mysite//x','/mysite?x','/mysite#x','/my%2fsite','/my site','/mysite\n','https://example.com'):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                script_prefix(value)

    @override_settings(STATIC_URL='/mysite/static/')
    def test_development_static_handler_serves_prefixed_css(self):
        application=StaticFilesHandler(WSGIHandler())
        environ=RequestFactory().get('/mysite/static/public/site.css').environ
        result={}
        def start_response(status,headers,exc_info=None):
            result.update(status=status,headers=dict(headers))
        response=application(environ,start_response)
        try:
            body=b''.join(response)
        finally:
            if hasattr(response,'close'):
                response.close()
        self.assertTrue(result['status'].startswith('200'))
        self.assertIn('text/css',result['headers']['Content-Type'])
        self.assertIn(b'.masthead',body)


@override_settings(ROOT_URLCONF='web.public.prefixed_urls',APP_SCRIPT_PREFIX='/mysite',STATIC_URL='/mysite/static/',PUBLIC_ORIGIN='https://node.example',LANGUAGE_COOKIE_PATH='/mysite/',LANGUAGE_COOKIE_SECURE=True,MIDDLEWARE=settings.PUBLIC_MIDDLEWARE)
class PublicMountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site=SiteContent.objects.create()
        cls.account=SourceAccount.objects.create(source_account_id='mount-fixture')

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override=override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def image(self):
        stream=io.BytesIO()
        Image.new('RGB',(16,12),'blue').save(stream,format='PNG')
        stream.seek(0)
        return stream

    def item(self,identifier):
        item=PresentationItem.objects.create(account=self.account,source_post_id=identifier,canonical_url=f'https://www.instagram.com/p/{identifier}/',source_published_at=timezone.now()-timedelta(days=1),publish_at=timezone.now()-timedelta(minutes=1),status=Status.PUBLISHED,original_caption='Original-language caption')
        return item,stage_image(item,self.image(),alt_en='Public fixture',alt_fr='Image publique')

    def test_landing_and_trailing_slash_redirects_remain_under_mount(self):
        self.assertEqual(self.client.get('/mysite')['Location'],'/mysite/')
        self.assertEqual(self.client.get('/mysite/')['Location'],'/mysite/en/')
        self.client.cookies['site_language']='fr'
        self.assertEqual(self.client.get('/mysite/')['Location'],'/mysite/fr/')
        self.assertEqual(self.client.get('/mysite/health/').status_code,200)

    def test_rendered_links_assets_and_canonicals_use_mount(self):
        item,asset=self.item('links')
        response=self.client.get('/mysite/en/')
        self.assertContains(response,'href="/mysite/static/public/site.css"')
        self.assertContains(response,'href="/mysite/theme.css"')
        self.assertContains(response,f'src="/mysite/media/{asset.pk}/"')
        self.assertContains(response,'rel="canonical" href="https://node.example/mysite/en/"')
        class Links(HTMLParser):
            values=[]
            def handle_starttag(self,tag,attrs):
                for name,value in attrs:
                    if name in ('href','src') and value.startswith('/'):
                        self.values.append(value)
        parser=Links();parser.feed(response.content.decode())
        self.assertTrue(parser.values)
        self.assertTrue(all(value.startswith('/mysite/') for value in parser.values))
        self.assertEqual(reverse('feed',kwargs={'locale':'fr'}),'/mysite/fr/')

    def test_cookie_is_secure_and_scoped_away_from_other_applications(self):
        response=self.client.get('/mysite/fr/')
        cookie=response.cookies['site_language']
        self.assertEqual(cookie['path'],'/mysite/')
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'],'Lax')

    def test_sitemap_and_robots_stay_within_mount(self):
        response=self.client.get('/mysite/sitemap.xml')
        root=ElementTree.fromstring(response.content)
        locations=root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        self.assertEqual(len(locations),6)
        self.assertTrue(all(node.text.startswith('https://node.example/mysite/') for node in locations))
        self.assertNotIn('manage-local',response.content.decode())
        self.assertEqual(self.client.get('/mysite/robots.txt').content,b'User-agent: *\nDisallow: /\n')

    def test_media_and_theme_background_keep_publication_gates(self):
        item,asset=self.item('media')
        self.assertEqual(self.client.get(f'/mysite/media/{asset.pk}/').status_code,200)
        item.status=Status.HIDDEN;item.save()
        self.assertEqual(self.client.get(f'/mysite/media/{asset.pk}/').status_code,404)
        with transaction.atomic():
            image=persist_image(ThemeImage,decode_image(self.image()))
        SiteTheme.objects.filter(pk=1).update(background_image=image)
        self.assertContains(self.client.get('/mysite/theme.css'),f'/mysite/theme/image/{image.pk}/')
        self.assertEqual(self.client.get(f'/mysite/theme/image/{image.pk}/').status_code,200)
        SiteTheme.objects.filter(pk=1).update(background_image=None)
        self.assertEqual(self.client.get(f'/mysite/theme/image/{image.pk}/').status_code,404)

    def test_errors_are_localized_and_root_admin_and_callback_routes_absent(self):
        self.assertContains(self.client.get('/mysite/fr/missing/'),'introuvable',status_code=404)
        for path in ('/en/','/mysite-other/en/','/mysite/manage-local/','/mysite/instagram/callback/'):
            self.assertEqual(self.client.get(path).status_code,404)
        response=self.client.get('/mysite/en/',HTTP_X_FORWARDED_PREFIX='/attacker')
        self.assertNotContains(response,'/attacker')
        self.assertEqual(response['X-Robots-Tag'],'noindex, follow')

    def test_signed_pagination_links_preserve_mount_and_cursor(self):
        SiteContent.objects.filter(pk=1).update(page_size=1)
        self.item('one');self.item('two')
        first=self.client.get('/mysite/en/')
        cursor=first.context['next_cursor']
        second=self.client.get('/mysite/en/',{'cursor':cursor})
        self.assertEqual(len(second.context['cards']),1)
        self.assertNotEqual(first.context['cards'][0]['item'].pk,second.context['cards'][0]['item'].pk)
        self.assertTrue(second.context['seo']['canonical'].startswith('https://node.example/mysite/en/?cursor='))

    def test_postgres_prefixed_public_runtime_retains_read_boundary(self):
        if connection.vendor!='postgresql':
            self.skipTest('Requires PostgreSQL runtime grants.')
        self.item('role')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE site_public')
            self.assertEqual(self.client.get('/mysite/en/').status_code,200)
            self.assertEqual(self.client.get('/mysite/sitemap.xml').status_code,200)
            with self.assertRaises(DatabaseError),transaction.atomic():
                AuditEvent.objects.count()
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
