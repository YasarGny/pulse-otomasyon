import copy
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fixtures import DATE, ready_release, tone
from pulse.build import build
from pulse.control_site import apply, cancel_paused_runs
from pulse.controls import settings, require_running, podcast_enabled
from pulse.publication import not_before, read_json, write_json, seal_release
from pulse.site_visibility import display_page, visible_page
from scripts.sync_site import sync


class VisibilityUnitTests(unittest.TestCase):
    def test_cover_is_idempotent_and_roundtrip_preserves_original_html(self):
        original = '<!doctype html><html><body data-page="article"><noscript>Notice</noscript><main id="main">Actual news</main></body></html>'
        hidden = display_page(original, False)
        self.assertIn('data-pulse-paused="true"', hidden)
        self.assertIn('Actual news', hidden)
        self.assertEqual(display_page(hidden, False), hidden)
        self.assertEqual(visible_page(hidden), original)

    def test_site_switch_does_not_stop_production_podcasts_or_cancel_runs(self):
        with patch.dict(os.environ, {'PULSE_SITE_ENABLED':'false','PULSE_AUTOMATION_ENABLED':'true',
                                    'PULSE_TECH_PODCAST_ENABLED':'true','PULSE_GAME_PODCAST_ENABLED':'true'}):
            state = settings()
            self.assertFalse(state['enabled'])
            self.assertTrue(state['automation_enabled'])
            require_running()
            self.assertTrue(podcast_enabled('teknoloji'))
            with patch('pulse.control_site.subprocess.run') as calls:
                cancel_paused_runs('fixture/repo', state, state)
            calls.assert_not_called()


class VisibilityPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.release = cls.root / 'release'
        ready_release(cls.release, tone(cls.root / 'tone.mp3'))
        cls.source = cls.root / 'site'
        build('site', cls.source, release=cls.release, at=not_before(DATE))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_hidden_site_accepts_new_verified_publication_and_reopens_latest_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'published'
            shutil.copytree(self.source, target)
            desired = {'schema_version':1, 'enabled':False, 'automation_enabled':True,
                       'podcasts':{'teknoloji':True,'oyun':True}}
            apply(target, desired)
            self.assertFalse(apply(target, desired))
            candidate = Path(tmp) / 'release'
            shutil.copytree(self.release, candidate)
            edition = read_json(candidate / 'teknoloji.json')
            edition['stories'][0]['title'] = 'New verified technology story while the site is hidden'
            write_json(candidate / 'teknoloji.json', edition)
            manifest = seal_release(candidate, DATE, DATE)
            revised = Path(tmp) / 'revised'
            build('site', revised, release=candidate, at=not_before(DATE))
            # This queued build thinks the site is on. The applied owner switch wins.
            self.assertTrue(read_json(revised / 'data/controls.json')['enabled'])
            sync(revised, target, at=not_before(DATE))
            self.assertEqual(read_json(target / 'data/publication.json'), manifest)
            self.assertFalse(read_json(target / 'data/controls.json')['enabled'])
            hidden = (target / 'index.html').read_text()
            self.assertIn('data-pulse-paused="true"', hidden)
            self.assertIn(edition['stories'][0]['title'], hidden)
            self.assertEqual(visible_page(hidden), (revised / 'index.html').read_text())
            desired['enabled'] = True
            apply(target, desired)
            self.assertEqual((target / 'index.html').read_text(), (revised / 'index.html').read_text())
            self.assertEqual(read_json(target / 'data/publication.json'), manifest)

    def test_visibility_cover_does_not_disable_portable_drive_archive(self):
        from pulse.archive import package, verify_package
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'hidden'
            shutil.copytree(self.source, target)
            apply(target, {'schema_version':1,'enabled':False,'automation_enabled':True,
                           'podcasts':{'teknoloji':True,'oyun':True}})
            destination = Path(tmp) / 'offline.zip'
            package(target, destination, fetch=lambda _: (Path('site/assets/covers/teknoloji-768.webp').read_bytes(),'image/webp'))
            verify_package(destination)
            with zipfile.ZipFile(destination) as archive:
                html = archive.read('index.html').decode()
                self.assertNotIn('data-pulse-paused="true"', html)
                self.assertNotIn('PULSE_SITE_VISIBILITY_START', html)
                self.assertEqual(sum(name.endswith('.mp3') for name in archive.namelist()),4)
            self.assertIn('data-pulse-paused="true"', (target / 'index.html').read_text())
