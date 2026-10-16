import copy
import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from fixtures import DATE, ready_release, tone
from pulse.archive import package, verify_package
from pulse.build import build
from pulse.details import display_date
from pulse.drive_backup import Drive, backup_releases
from pulse.publication import read_json, write_json, not_before, validate_content
from pulse.source_media import article_image, public_url
from scripts.prune_backed_up import prune


class BackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.audio = tone(cls.root / 'tone.mp3')
        cls.release = cls.root / 'release'
        cls.manifest = ready_release(cls.release, cls.audio)
        cls.site = cls.root / 'site'
        build('site', cls.site, release=cls.release, at=not_before(DATE))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def media(self, url):
        return Path('site/assets/covers/teknoloji-768.webp').read_bytes(), 'image/webp'

    def test_same_day_preparation_retains_working_detail_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'prepared'
            manifest = build('site', output, preparing=DATE, previous=self.site, at=not_before(DATE))
            self.assertEqual(manifest['status'], 'ready')
            self.assertTrue((output / 'teknoloji/haber/teknoloji0/index.html').is_file())

    def test_media_refresh_preserves_issue_and_all_audio(self):
        from pulse.media_refresh import refresh
        with tempfile.TemporaryDirectory() as tmp:
            with patch('pulse.media_refresh.now', return_value=not_before(DATE)):
                result = refresh(self.site, Path(tmp) / 'media', lookup=lambda url: 'https://images.example.test/new.jpg')
            revised = Path(tmp) / 'media'
            self.assertNotEqual(result['release_id'], self.manifest['release_id'])
            for section in ('teknoloji', 'oyun'):
                self.assertEqual(read_json(revised / f'{section}.json')['issue'], 1)
                for kind in ('summary', 'podcast'):
                    self.assertEqual((revised / section / f'{kind}.mp3').read_bytes(), (self.release / section / f'{kind}.mp3').read_bytes())

    def test_encoded_feed_image_uses_largest_supplied_srcset(self):
        from pulse.editorial import parse_feed
        raw = b'''<rss><channel><item><title>A real source article with a useful image</title><link>https://www.nasa.gov/test</link><pubDate>Fri, 16 Oct 2026 02:00:00 GMT</pubDate><description><![CDATA[A source description long enough to qualify for this daily research feed with a genuinely attributable image. <img src="https://images.example.test/small.jpg" srcset="https://images.example.test/large.jpg 1200w, https://images.example.test/small.jpg 400w">]]></description></item></channel></rss>'''
        stories = parse_feed(raw, {'name': 'NASA', 'hosts': ['www.nasa.gov']}, DATE)
        self.assertEqual(stories[0]['image_url'], 'https://images.example.test/large.jpg')

    def test_browser_setup_creates_root_folder_without_folder_variable(self):
        drive = Mock()
        drive.folder.return_value = 'automatic-root'
        drive.api = 'https://www.googleapis.com/drive/v3/files'
        drive.daily_files.return_value = [{'id':'current', 'size':'100', 'name': 'PULSE-16.10.2026.zip', 'appProperties': {'release_id': self.manifest['release_id']}}]
        drive.existing.return_value = {'verified': True, 'release_id': self.manifest['release_id'], 'file_id': 'current'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'PULSE_DRIVE_FOLDER_ID': ''}):
            backup_releases(self.site, self.site, Path(tmp) / 'receipt.json', drive=drive)
        self.assertEqual(drive.folder.call_args_list[0].args, ('root', 'PULSE'))
        self.assertEqual(drive.folder.call_args_list[1].args, ('automatic-root', '2026'))

    def test_drive_refuses_a_file_with_folder_name(self):
        drive = Drive.__new__(Drive)
        drive.children = Mock(return_value=[{'id': 'file', 'mimeType': 'application/zip'}])
        with self.assertRaises(ValueError):
            drive.folder('root', 'PULSE')

    def test_numeric_date(self):
        self.assertEqual(display_date(DATE), '16.10.2026')
        self.assertEqual(display_date('2026-01-02'), '02.01.2026')

    def test_offline_archive_includes_four_audio_and_local_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / 'day.zip'
            expected = package(self.site, zip_path, fetch=self.media)
            inventory = verify_package(zip_path)
            self.assertEqual(inventory['release_id'], self.manifest['release_id'])
            self.assertEqual(expected['sha256'], hashlib.sha256(zip_path.read_bytes()).hexdigest())
            with zipfile.ZipFile(zip_path) as z:
                self.assertEqual(len([n for n in z.namelist() if n.endswith('.mp3')]), 4)
                self.assertTrue(any(n.startswith('media/') for n in z.namelist()))
                home = z.read('index.html').decode()
                self.assertIn('16.10.2026', home)
                self.assertNotIn('printing.js', home)
                self.assertNotIn('pulse-loading', home)
                self.assertIn('./teknoloji/index.html', home)
                section = z.read('teknoloji/index.html').decode()
                self.assertIn('window.PULSE_ARCHIVE=true', section)
                detail = z.read('teknoloji/haber/teknoloji0/index.html').decode()
                self.assertIn('../../../media/', detail)
                self.assertNotIn('https://images.example.test/', detail)

    def test_archive_deterministic_for_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = package(self.site, Path(tmp) / 'a.zip', fetch=self.media)
            b = package(self.site, Path(tmp) / 'b.zip', fetch=self.media)
            self.assertEqual(a['sha256'], b['sha256'])

    def test_missing_picture_prevents_successful_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'day.zip'
            with self.assertRaises(RuntimeError):
                package(self.site, destination, fetch=Mock(side_effect=RuntimeError('offline')))
            self.assertFalse(destination.exists())

    def test_drive_secrets_cannot_enter_public_bundle(self):
        from pulse.build import assert_public_tree
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'leak.json').write_text('{"bad":"synthetic-drive-secret-token-value"}')
            with patch.dict('os.environ', {'PULSE_DRIVE_REFRESH_TOKEN': 'synthetic-drive-secret-token-value'}):
                with self.assertRaisesRegex(ValueError, 'Secret value'):
                    assert_public_tree(tmp)

    def test_corrupt_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('index.html', b'changed')
                z.writestr('archive.json', json.dumps({'files': {'index.html': {'sha256': '0'*64, 'bytes': 7}}}))
            with self.assertRaises(ValueError):
                verify_package(path)

    def test_drive_corrupt_readback_rejected(self):
        drive = Drive.__new__(Drive)
        meta = Mock()
        meta.json.return_value = {'size': 3, 'appProperties': {'sha256': hashlib.sha256(b'yes').hexdigest()}}
        body = Mock()
        body.__enter__ = Mock(return_value=body)
        body.__exit__ = Mock(return_value=False)
        body.iter_content.return_value = [b'bad']
        drive.request = Mock(side_effect=[meta, body])
        with self.assertRaises(ValueError):
            drive.readback('file', {'bytes': 3, 'sha256': hashlib.sha256(b'yes').hexdigest()})

    def test_failed_backup_never_writes_receipt(self):
        drive = Mock()
        drive.folder.return_value = 'folder'
        drive.daily_files.return_value = [{'id':'current', 'size':'100', 'name': 'PULSE-16.10.2026.zip', 'appProperties': {'release_id': self.manifest['release_id']}}]
        drive.existing.side_effect = RuntimeError('Drive unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            receipts = Path(tmp) / 'receipt.json'
            with self.assertRaises(RuntimeError):
                backup_releases(self.site, self.site, receipts, drive=drive, folder='root')
            self.assertFalse(receipts.exists())

    def test_existing_verified_archive_skips_repack_and_upload(self):
        drive = Mock()
        drive.folder.return_value = 'folder'
        drive.api = 'https://www.googleapis.com/drive/v3/files'
        drive.daily_files.return_value = [{'id':'current', 'size':'100', 'name': 'PULSE-16.10.2026.zip', 'appProperties': {'release_id': self.manifest['release_id']}}]
        drive.existing.return_value = {'verified': True, 'release_id': self.manifest['release_id'], 'file_id': 'current'}
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'receipt.json'
            result = backup_releases(self.site, self.site, receipt, drive=drive, folder='root')
            self.assertTrue(result[self.manifest['release_id']]['verified'])
            drive.upload.assert_not_called()
            self.assertIn('16.10.2026', drive.folder.call_args[0])

    def test_prune_preflight_preserves_all_without_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            releases = target / 'releases'
            manifests = []
            for date in ('2026-10-16', '2026-10-17', '2026-10-18'):
                folder = releases / date
                manifest = ready_release(folder, self.audio, date=date)
                manifests.append(manifest)
            write_json(target / 'data/publication.json', manifests[-1])
            write_json(target / 'receipts.json', {'releases': {}})
            with self.assertRaises(ValueError):
                prune(target, target / 'receipts.json')
            self.assertEqual(len(list(releases.iterdir())), 3)
            old = manifests[0]
            write_json(target / 'receipts.json', {'releases': {old['release_id']: {'verified': True, 'release_id': old['release_id'], 'publish_date': old['publish_date'], 'file_id': 'verified', 'sha256': 'a'*64}}})
            self.assertEqual(prune(target, target / 'receipts.json'), 1)
            self.assertEqual(len(list(releases.iterdir())), 2)
            self.assertEqual(len(read_json(target / 'data/source-history.json')['teknoloji']), 3)

    def test_private_source_networks_rejected(self):
        with self.assertRaises(ValueError):
            public_url('https://127.0.0.1/secret')
        with self.assertRaises(ValueError):
            public_url('https://169.254.169.254/latest')

    def test_open_graph_image_from_approved_publisher_only(self):
        with patch('pulse.source_media.fetch_public', return_value=(b'<meta property="og:image" content="https://cdn.example.com/photo.jpg">', 'text/html')) as fetch:
            self.assertEqual(article_image('https://www.nasa.gov/article/real'), 'https://cdn.example.com/photo.jpg')
            self.assertIn('www.nasa.gov', fetch.call_args.kwargs['hosts'])

    def test_new_content_rejects_unapproved_sources(self):
        data = read_json(self.release / 'teknoloji.json')
        data['content_revision'] = 3
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            validate_content(data, 'teknoloji', DATE, DATE)
