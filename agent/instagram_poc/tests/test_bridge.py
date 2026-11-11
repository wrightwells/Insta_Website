import io
from pathlib import Path
import tempfile
import unittest

from agent.instagram_poc.bridge import create_bridge
from agent.instagram_poc.service import InstagramService
from agent.instagram_poc.storage import PocStore
from test_poc import FakeClient


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = PocStore(root / 'data', root / 'keys')
        self.service = InstagramService(self.store, FakeClient)
        self.client = create_bridge(self.service, 'synthetic-control-key').test_client()
        self.headers = {'Authorization': 'Bearer synthetic-control-key'}

    def call(self, operation, payload=None):
        return self.client.post('/v1/' + operation, json=payload or {}, headers=self.headers)

    def test_authentication_origin_and_fixed_operations(self):
        self.assertEqual(self.client.post('/v1/status', json={}).status_code, 401)
        self.assertEqual(self.client.post('/v1/status', json={}, headers={**self.headers, 'Origin': 'http://evil.test'}).status_code, 403)
        self.assertEqual(self.client.get('/v1/status', headers=self.headers).status_code, 403)
        self.assertEqual(self.call('not-supported').status_code, 404)

    def test_account_connect_and_recent_never_return_credentials_or_cdn_urls(self):
        response = self.call('account', {'username': 'demo', 'password': 'synthetic-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.call('connect').status_code, 200)
        status = self.call('status')
        self.assertTrue(status.json['connected'])
        self.assertNotIn('settings', status.json)
        self.assertNotIn('synthetic-password', status.text)
        posts = self.call('recent', {'limit': 1})
        self.assertEqual(posts.status_code, 200)
        self.assertNotIn('image_url', posts.text)
        self.assertNotIn('synthetic-session-secret', posts.text)
        self.assertEqual(posts.json['items'][0]['assets'], [{'kind': 'image', 'has_image': True}])
        self.assertEqual(posts.headers['Cache-Control'], 'no-store')

    def test_private_storage_permissions_and_symlinks(self):
        self.call('account', {'username': 'demo', 'password': 'synthetic-password'})
        self.store.key_path.chmod(0o644)
        self.assertEqual(self.call('status').status_code, 400)
        self.store.key_path.chmod(0o600)
        self.assertEqual(self.call('status').status_code, 200)
        from agent.credentials import AccessError
        (Path(self.temp.name) / 'link').symlink_to(self.store.data_dir, target_is_directory=True)
        with self.assertRaises(AccessError):
            PocStore(Path(self.temp.name) / 'link', Path(self.temp.name) / 'more-keys')

    def test_provider_exception_redacted(self):
        from unittest.mock import patch
        with patch.object(self.service, 'connect', side_effect=RuntimeError('private-provider-body')):
            response = self.call('connect')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-provider-body', response.text)
