import copy
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

from fixtures import DATE, GAME_START, edition, ready_release, tone
from pulse.controls import audio_kinds, podcast_enabled, require_running, settings
from pulse.publication import audio_info, not_before, read_json, seal_release, verify_manifest, write_json

ROOT = Path(__file__).resolve().parents[1]
ENV = {'PULSE_AUTOMATION_ENABLED': 'true', 'PULSE_TECH_PODCAST_ENABLED': 'true', 'PULSE_GAME_PODCAST_ENABLED': 'true'}


class ControlsTests(unittest.TestCase):
    def test_defaults_preserve_both_podcasts_and_global_false_overrides_both(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings(), {'schema_version': 1, 'enabled': True, 'automation_enabled': True,
                                          'podcasts': {'teknoloji': True, 'oyun': True}})
        with patch.dict(os.environ, {**ENV, 'PULSE_AUTOMATION_ENABLED': 'false'}):
            with self.assertRaisesRegex(RuntimeError, 'paused'):
                require_running()
            self.assertFalse(podcast_enabled('teknoloji'))
            self.assertFalse(podcast_enabled('oyun'))
        with patch.dict(os.environ, {**ENV, 'PULSE_TECH_PODCAST_ENABLED': 'false'}):
            self.assertFalse(podcast_enabled('teknoloji'))
            self.assertTrue(podcast_enabled('oyun'))
        with patch.dict(os.environ, {**ENV, 'PULSE_GAME_PODCAST_ENABLED': 'false'}):
            self.assertTrue(podcast_enabled('teknoloji'))
            self.assertFalse(podcast_enabled('oyun'))
        with patch.dict(os.environ, {**ENV, 'PULSE_AUTOMATION_ENABLED': 'maybe'}):
            with self.assertRaises(ValueError): settings()

    def test_disabled_is_explicit_and_cannot_conceal_an_existing_or_malformed_asset(self):
        self.assertEqual(audio_kinds({'podcast_enabled': False, 'podcast': None}), ('summary',))
        for data in ({'podcast_enabled': False}, {'podcast_enabled': False, 'podcast': {}},
                     {'podcast_enabled': 'false', 'podcast': None}):
            with self.subTest(data=data), self.assertRaises(ValueError): audio_kinds(data)

    def test_paused_podcast_never_enters_writer_voice_or_review_and_partner_remains_enabled(self):
        from pulse.pipeline import generate_audio
        for section, variable in [('teknoloji', 'PULSE_TECH_PODCAST_ENABLED'), ('oyun', 'PULSE_GAME_PODCAST_ENABLED')]:
            with self.subTest(section=section), tempfile.TemporaryDirectory() as tmp, \
                 patch.dict(os.environ, {**ENV, variable: 'false'}), \
                 patch('pulse.pipeline.valid_audio', return_value=True), \
                 patch('pulse.pipeline.audio_info', return_value={'duration': 60, 'bytes': 40000, 'sha256': 'f' * 64}), \
                 patch('pulse_podcast_writer.generate', side_effect=AssertionError('No script API')) as writer, \
                 patch('pulse_podcast_audio.render', side_effect=AssertionError('No TTS API')) as voice:
                result = generate_audio(Path(tmp), edition(section))
                self.assertIsNone(result['podcast'])
                self.assertIs(result['podcast_enabled'], False)
                self.assertTrue(result['ready'])
                self.assertIn('summary', result)
                self.assertTrue(podcast_enabled('oyun' if section == 'teknoloji' else 'teknoloji'))
                writer.assert_not_called(); voice.assert_not_called()

    def test_global_pause_stops_before_generation_or_any_provider(self):
        from pulse.pipeline import generate_audio, run
        with patch.dict(os.environ, {**ENV, 'PULSE_AUTOMATION_ENABLED': 'false'}), \
             patch('pulse.pipeline.research', side_effect=AssertionError('No external work')) as research:
            with self.assertRaisesRegex(RuntimeError, 'paused'): run('/unused', DATE, GAME_START)
            with self.assertRaisesRegex(RuntimeError, 'paused'): generate_audio(Path('/unused'), edition('oyun'))
            research.assert_not_called()

    def test_production_workflows_have_global_guards_and_only_controller_stays_active(self):
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            if path.name in ('quality.yml', 'apply-controls.yml'): continue
            text = path.read_text()
            self.assertIn("vars.PULSE_AUTOMATION_ENABLED != 'false'", text, path.name)
            self.assertNotIn('PULSE_CHAPTERS_ENABLED', text, path.name)
            for variable in ENV: self.assertIn(variable + ':', text, path.name)


class PublicationControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.root = Path(cls.tmp.name)
        release = cls.root / 'template'
        ready_release(release, tone(cls.root / 'tone.mp3'))
        # Independent audio hashes bind each section's own chapter catalogue.
        game = release / 'oyun/podcast.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(game), '-c', 'copy',
                        '-metadata', 'title=synthetic-game', str(cls.root / 'game.mp3')], check=True)
        shutil.copyfile(cls.root / 'game.mp3', game)
        for section in ('teknoloji', 'oyun'):
            data = read_json(release / (section + '.json'))
            if section == 'oyun': data['podcast'].update(audio_info(game, 40))
            for story in data['stories']: story['image_url'] = ''
            write_json(release / (section + '.json'), data)
            from pulse.clips import story_fingerprint
            write_json(release / 'chapters' / (data['podcast']['sha256'] + '.json'), {
                'schema_version': 1, 'reviewed': True, 'audio_sha256': data['podcast']['sha256'],
                'chapters': [{'start': 0, 'title': 'Açılış'}, {'start': 10, 'title': 'Haberler'}],
                'clips_reviewed': True, 'stories_sha256': story_fingerprint(data['stories']), 'story_ranges': []})
        seal_release(release, DATE, GAME_START)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def stage(self, root, flags):
        release = Path(root) / 'release'
        shutil.copytree(self.root / 'template', release)
        for section, enabled in zip(('teknoloji', 'oyun'), flags):
            if not enabled:
                data = read_json(release / (section + '.json'))
                data.update(podcast_enabled=False, podcast=None)
                write_json(release / (section + '.json'), data)
        return release, seal_release(release, DATE, GAME_START)

    def test_all_four_combinations_publish_only_intended_audio_and_keep_the_site_working(self):
        from pulse.build import build
        from pulse.release_checks import check
        for flags in itertools.product((False, True), repeat=2):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, ENV):
                release, manifest = self.stage(tmp, flags)
                verify_manifest(release, manifest); check(release)
                output = Path(tmp) / 'site'
                build(ROOT / 'site', output, release=release, at=not_before(DATE))
                self.assertEqual((output / 'podcastler/index.html').read_text().count('<section class="program-card"'), sum(flags))
                for section, enabled in zip(('teknoloji', 'oyun'), flags):
                    folder = output / 'releases' / manifest['release_id'] / section
                    self.assertTrue((folder / 'summary.mp3').is_file())
                    self.assertEqual((folder / 'podcast.mp3').exists(), enabled)
                    self.assertIn('Günün Özeti', (output / section / 'dinle/index.html').read_text())

    def test_offline_backup_still_contains_complete_news_and_summaries_when_both_podcasts_paused(self):
        from pulse.build import build
        from pulse.archive import package, verify_package
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, ENV):
            release, manifest = self.stage(tmp, (False, False))
            output = Path(tmp) / 'site'
            build(ROOT / 'site', output, release=release, at=not_before(DATE))
            target = Path(tmp) / 'archive.zip'
            package(output, target, fetch=lambda _: self.fail('No image network work expected'))
            verify_package(target)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(sum(name.endswith('/summary.mp3') for name in archive.namelist()), 2)
                self.assertFalse(any(name.endswith('/podcast.mp3') for name in archive.namelist()))
                self.assertNotIn('assets/controls.js?', archive.read('index.html').decode())

    def test_disabled_sections_are_skipped_by_recovery_and_transcription_without_loading_models(self):
        from pulse.chapter_completion import missing
        from scripts.prepare_chapters import prepare
        from scripts.transcribe_podcasts import transcribe
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {**ENV, 'PULSE_TECH_PODCAST_ENABLED': 'false', 'PULSE_GAME_PODCAST_ENABLED': 'false'}):
            release, manifest = self.stage(tmp, (False, False))
            self.assertEqual(missing(Path(tmp), manifest, release), [])
            with patch('scripts.transcribe_podcasts.transcribe', side_effect=AssertionError('No ASR')):
                prepare(release)
            # Works without importing faster_whisper at all.
            with patch.dict('sys.modules', {'faster_whisper': None}): transcribe(release, Path(tmp) / 'transcripts')


class MaintenanceControlTests(unittest.TestCase):
    def test_cancellation_is_scoped_and_does_not_cancel_the_controller_or_quality_tests(self):
        from pulse.control_site import cancel_paused_runs
        paths = {100:'quality.yml',200:'apply-controls.yml',300:'daily-publish.yml',
                 400:'drive-backup.yml',500:'podcast-chapters.yml',600:'refresh-website.yml'}
        cancelled = []
        def command(args, **kwargs):
            if '--paginate' in args:
                text = '\n'.join(map(str,paths)) if any('status=in_progress' in part for part in args) else ''
                return SimpleNamespace(returncode=0,stdout=text)
            if args[-1].endswith('/cancel'):
                cancelled.append(int(args[-1].split('/')[-2]))
                return SimpleNamespace(returncode=0,stdout=b'')
            identity=int(args[-1].rsplit('/',1)[-1])
            return SimpleNamespace(returncode=0,stdout=json.dumps({'path':'.github/workflows/'+paths[identity],'status':'in_progress'}))
        previous={'enabled':True,'podcasts':{'teknoloji':True,'oyun':True}}
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'600'}), patch('pulse.control_site.subprocess.run',side_effect=command) as calls:
            cancel_paused_runs('fixture/repo',{'enabled':True,'automation_enabled':False,'podcasts':previous['podcasts']},previous)
            self.assertEqual(cancelled,[300,400,500])
            cancelled.clear()
            desired={'enabled':True,'podcasts':{'teknoloji':False,'oyun':True}}
            cancel_paused_runs('fixture/repo',desired,previous)
            self.assertEqual(cancelled,[300,500])
            calls.reset_mock()
            cancel_paused_runs('fixture/repo',desired,desired)
            calls.assert_not_called()

    def test_production_pause_keeps_html_audio_and_last_release_intact(self):
        from pulse.control_site import apply, git
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            git(root, 'config', 'user.name', 'Synthetic test'); git(root, 'config', 'user.email', 'test@example.test')
            identity = '2026-10-16-' + 'a' * 16
            original = {'index.html': b'<html><body>Home</body></html>',
                        'oyun/dinle/index.html': b'<html><body>Episode</body></html>',
                        'data/publication.json': json.dumps({'status':'ready','release_id':identity}).encode(),
                        'releases/test/podcast.mp3': b'synthetic bytes'}
            for name, data in original.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            git(root, 'add', '.'); git(root, 'commit', '-qm', 'Original synthetic site')
            baseline = git(root, 'rev-parse', 'HEAD').decode().strip()
            paused = {'schema_version': 1, 'enabled': True, 'automation_enabled': False,
                      'podcasts': {'teknoloji': True, 'oyun': True}}
            self.assertTrue(apply(root, paused, ROOT / 'site'))
            self.assertFalse(apply(root, paused, ROOT / 'site'))
            self.assertEqual(read_json(root / 'data/controls.json')['retained_release_id'], identity)
            for name, data in original.items(): self.assertEqual((root / name).read_bytes(), data)
            paused['automation_enabled'] = True
            apply(root, paused, ROOT / 'site')
            self.assertNotIn('retained_release_id', read_json(root / 'data/controls.json'))
            # An installation closed with the former switch is restored even while production stays off.
            (root / 'index.html').write_text('<body data-pulse-paused="true">legacy pause</body>')
            write_json(root / 'data/controls.json', {'enabled':False,'resume_commit':baseline})
            paused['automation_enabled'] = False
            apply(root, paused, ROOT / 'site')
            for name, data in original.items(): self.assertEqual((root / name).read_bytes(), data)
            self.assertTrue(read_json(root / 'data/controls.json')['enabled'])
            self.assertFalse(read_json(root / 'data/controls.json')['automation_enabled'])

    def test_normal_deployment_cannot_override_an_owner_pause(self):
        from scripts.sync_site import sync
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); target = root / 'published'
            write_json(target / 'data/controls.json', {'enabled': True, 'automation_enabled': False})
            with self.assertRaisesRegex(ValueError, 'Owner pause'):
                sync(root / 'unused', target)
