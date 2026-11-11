import io
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image

from domain.content.media import decode_image, persist_image, stage_image
from domain.content.models import AuditEvent, ContentRevision, MediaAsset, MediaQuota, PresentationItem, SiteOwner, SiteTheme, SourceAccount, ThemeImage
from domain.content.storage_audit import audit_media
from domain.content.theme import THEME_FIELDS
from domain.content.uploads import edit_item_image, edit_theme


class StorageAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('inventory-owner', is_staff=True)
        SiteOwner.objects.create(user=cls.owner)
        account = SourceAccount.objects.create(source_account_id='inventory-fixture')
        cls.item = PresentationItem.objects.create(account=account, source_post_id='inventory', source_published_at=timezone.now(), canonical_url='https://www.instagram.com/p/inventory/', original_caption='Private caption must never enter the report')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.asset = stage_image(self.item, self.image(), alt_en='Private description')
        self.path = Path(self.directory.name) / self.asset.storage_key

    def image(self, color='blue'):
        stream = io.BytesIO()
        Image.new('RGB', (8, 8), color).save(stream, format='PNG')
        stream.seek(0)
        return stream

    def theme_values(self, **changes):
        theme = SiteTheme.objects.get(pk=1)
        return {**{field:getattr(theme, field) for field in THEME_FIELDS}, **changes}

    def test_clean_inventory_and_verification_do_not_change_state(self):
        before = self.path.read_bytes(), MediaQuota.objects.get(pk=1).bytes_used, ContentRevision.objects.count(), AuditEvent.objects.count()
        report = audit_media(verify=True)
        self.assertTrue(report['ok'])
        self.assertEqual(report['assets'][0]['file_state'], 'verified')
        self.assertEqual(report['assets'][0]['reference_state'], 'current')
        self.assertEqual(report['summary']['recorded_bytes'], self.asset.size)
        self.assertGreater(report['summary']['filesystem_free_bytes'], 0)
        self.assertEqual(before, (self.path.read_bytes(), MediaQuota.objects.get(pk=1).bytes_used, ContentRevision.objects.count(), AuditEvent.objects.count()))
        encoded = json.dumps(report)
        self.assertNotIn('Private caption', encoded)
        self.assertNotIn('Private description', encoded)
        self.assertNotIn(self.directory.name, encoded)

    def test_replaced_story_and_old_theme_remain_protected_by_history(self):
        edit_item_image(actor=self.owner, item_id=self.item.pk, expected_version=1, alt_en='Replacement', image=self.image('red'))
        edit_theme(actor=self.owner, expected_version=1, changes=self.theme_values(), image=self.image())
        edit_theme(actor=self.owner, expected_version=2, changes=self.theme_values(), clear_background=True)
        report = audit_media(verify=True)
        self.assertTrue(report['ok'])
        self.assertEqual(report['summary']['reference_counts'], {'current': 1, 'history': 2})
        old = next(asset for asset in report['assets'] if asset['id'] == str(self.asset.pk))
        self.assertEqual(old['history_references'], 1)
        self.assertEqual(old['reference_state'], 'history')
        self.assertTrue(self.path.exists())

    def test_registered_unreferenced_record_is_retained(self):
        with transaction.atomic():
            image = persist_image(ThemeImage, decode_image(self.image()))
        report = audit_media(verify=True)
        self.assertTrue(report['ok'])
        retained = next(asset for asset in report['assets'] if asset['id'] == str(image.pk))
        self.assertEqual(retained['reference_state'], 'retained')
        self.assertEqual(report['summary']['reference_counts']['retained'], 1)
        self.assertTrue((Path(self.directory.name) / image.storage_key).exists())

    def test_metadata_scan_does_not_claim_checksum_verification(self):
        original = self.path.read_bytes()
        self.path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        quick = audit_media()
        self.assertTrue(quick['ok'])
        self.assertFalse(quick['verify_requested'])
        self.assertEqual(quick['assets'][0]['file_state'], 'not_verified')
        verified = audit_media(verify=True)
        self.assertFalse(verified['ok'])
        self.assertEqual(verified['issue_counts']['file_checksum_mismatch'], 1)

    def test_missing_size_mismatch_and_quota_mismatch_are_reported(self):
        self.path.write_bytes(b'wrong size')
        report = audit_media()
        self.assertEqual(report['issue_counts']['file_size_mismatch'], 1)
        self.path.unlink()
        MediaQuota.objects.filter(pk=1).update(bytes_used=123456)
        report = audit_media(verify=True)
        self.assertEqual(report['issue_counts']['file_missing'], 1)
        self.assertEqual(report['issue_counts']['quota_mismatch'], 1)
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, 123456)

    def test_untracked_and_unexpected_files_are_reported_without_payloads(self):
        untracked = Path(self.directory.name) / (uuid4().hex + '.png')
        untracked.write_bytes(b'Private untracked content')
        unexpected = Path(self.directory.name) / 'private-token-name.txt'
        unexpected.write_bytes(b'Secret unexpected content')
        report = audit_media(verify=True)
        self.assertEqual(report['summary']['untracked_file_count'], 1)
        self.assertEqual(report['summary']['unexpected_entry_count'], 1)
        self.assertEqual(report['untracked_files'][0]['storage_key'], untracked.name)
        text = json.dumps(report)
        self.assertNotIn('Private untracked content', text)
        self.assertNotIn('Secret unexpected content', text)
        self.assertNotIn('private-token-name', text)
        self.assertEqual(untracked.read_bytes(), b'Private untracked content')
        self.assertTrue(unexpected.exists())

    def test_symlinks_and_fifos_are_never_read(self):
        self.path.unlink()
        target = Path(self.directory.name) / 'private-target.txt'
        target.write_bytes(b'not a media file')
        self.path.symlink_to(target)
        report = audit_media(verify=True)
        self.assertEqual(report['issue_counts']['unsafe_entry'], 1)
        self.assertNotEqual(report['assets'][0]['file_state'], 'verified')
        self.path.unlink()
        os.mkfifo(self.path)
        report = audit_media(verify=True)
        self.assertEqual(report['issue_counts']['unsafe_entry'], 1)
        self.assertEqual(target.read_bytes(), b'not a media file')

    def test_storage_root_symlink_and_missing_root_are_rejected(self):
        link = Path(self.directory.name) / 'root-link'
        link.symlink_to(self.directory.name, target_is_directory=True)
        for root in (link, Path(self.directory.name) / 'absent'):
            with self.subTest(root=root), override_settings(PRIVATE_MEDIA_ROOT=root):
                self.assertEqual(audit_media()['issue_counts']['storage_unavailable'], 1)

    def test_invalid_storage_key_never_traverses_or_exposes_it(self):
        MediaAsset.objects.filter(pk=self.asset.pk).update(storage_key='../private-secret.png')
        report = audit_media(verify=True)
        self.assertEqual(report['issue_counts']['invalid_storage_key'], 1)
        self.assertIsNone(report['assets'][0]['storage_key'])
        self.assertNotIn('private-secret', json.dumps(report))
        self.assertTrue(self.path.exists())

    def test_broken_history_references_and_schema_are_reported(self):
        snapshots = [
            {'media':[{'id':str(uuid4())}]},
            {'media':[{'id':str(self.asset.pk), 'storage_key':uuid4().hex + '.png'}]},
            {'media':['private malformed content']},
            {'media':'private malformed content'},
            {'background_image_id':'private invalid identifier'},
            [],
        ]
        for version, snapshot in enumerate(snapshots, 1):
            ContentRevision.objects.create(entity='presentation_item', entity_id=str(self.item.pk), version=version, actor=self.owner, snapshot=snapshot)
        report = audit_media()
        self.assertEqual(report['issue_counts']['missing_asset_reference'], 1)
        self.assertEqual(report['issue_counts']['history_storage_key_mismatch'], 1)
        self.assertEqual(report['issue_counts']['invalid_media_reference'], 3)
        self.assertEqual(report['issue_counts']['unsupported_history'], 1)
        self.assertNotIn('private malformed', json.dumps(report))

    def test_duplicate_keys_and_invalid_metadata_are_detected(self):
        ThemeImage.objects.create(storage_key=self.asset.storage_key, checksum=self.asset.checksum, size=self.asset.size, width=8, height=8, validated=True)
        MediaAsset.objects.filter(pk=self.asset.pk).update(validated=False)
        report = audit_media(verify=True)
        self.assertEqual(report['issue_counts']['duplicate_storage_key'], 1)
        self.assertEqual(report['issue_counts']['invalid_asset_metadata'], 1)
        self.assertEqual(report['issue_counts']['quota_mismatch'], 1)

    def test_issue_details_are_bounded_but_counts_are_complete(self):
        for index in range(205):
            (Path(self.directory.name) / f'unexpected-{index}.txt').write_bytes(b'fixture')
        report = audit_media()
        self.assertEqual(report['issue_counts']['unexpected_entry'], 205)
        self.assertEqual(len(report['issues']), 200)
        self.assertTrue(report['issues_truncated'])


class StorageAuditCommandTests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        MediaQuota.objects.get_or_create(pk=1)

    def test_operator_command_emits_valid_json_and_checks_clean_storage(self):
        output = io.StringIO()
        call_command('audit_media', '--verify', '--check', stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report['ok'])
        self.assertTrue(report['verify_requested'])
        self.assertEqual(report['summary']['asset_count'], 0)

    def test_check_returns_failure_after_json_without_removing_orphan(self):
        orphan = Path(self.directory.name) / (uuid4().hex + '.png')
        orphan.write_bytes(b'fixture')
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command('audit_media', '--verify', '--check', stdout=output)
        self.assertFalse(json.loads(output.getvalue())['ok'])
        self.assertTrue(orphan.exists())
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, 0)

    def test_non_operator_runtimes_are_refused(self):
        for runtime in ('public', 'admin'):
            with self.subTest(runtime=runtime), override_settings(RUNTIME=runtime):
                with self.assertRaises(CommandError):
                    call_command('audit_media', stdout=io.StringIO())

    def test_postgres_operator_transaction_refuses_accidental_database_writes(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires PostgreSQL read-only transactions.')
        def accidental_write(**options):
            MediaQuota.objects.filter(pk=1).update(bytes_used=999)
        with patch('domain.content.management.commands.audit_media.audit_media', side_effect=accidental_write):
            with self.assertRaises(CommandError):
                call_command('audit_media', stdout=io.StringIO())
        self.assertEqual(MediaQuota.objects.get(pk=1).bytes_used, 0)
