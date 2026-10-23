import copy
import datetime as dt
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fixtures import DATE, ready_release, tone
from pulse.build import build
from pulse.chapter_completion import bootstrap_daily, copy_state, current, missing, rebuild, stage
from pulse.publication import audio_info, digest, not_before, read_json, seal_release, write_json
from scripts.prepare_chapters import cached_editor
from scripts.prepare_chapters import propose
from pulse.clips import story_fingerprint


class ChapterResponseCacheTests(unittest.TestCase):
    def test_checkpoint_sync_does_not_resurrect_evicted_responses_or_stale_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            work, state = Path(tmp) / 'work', Path(tmp) / 'state'
            write_json(work / 'chapter-requests/rejected.json', {'approved': False})
            write_json(work / 'chapter-requests/approved.json', {'approved': True})
            write_json(work / 'chapter-feedback/old.json', {'reason': 'Previous failure'})
            copy_state(work, state)
            (work / 'chapter-requests/rejected.json').unlink()
            (work / 'chapter-feedback/old.json').unlink()
            copy_state(work, state)
            self.assertFalse((state / 'chapter-requests/rejected.json').exists())
            self.assertFalse((state / 'chapter-feedback/old.json').exists())
            self.assertTrue((state / 'chapter-requests/approved.json').exists())

    def test_resume_reuses_response_but_model_evidence_and_options_invalidate_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(return_value={'approved': True})
            generate = cached_editor(tmp, provider, 'fixture-model')
            generate('Source A', system='Review')
            cached_editor(tmp, provider, 'fixture-model')('Source A', system='Review')
            self.assertEqual(provider.call_count, 1)
            generate('Source B', system='Review')
            generate('Source A', system='Different review')
            cached_editor(tmp, provider, 'other-model')('Source A', system='Review')
            self.assertEqual(provider.call_count, 4)
            cached_editor(tmp, provider, 'fixture-model', context={'audio_sha256': 'b' * 64})('Source A', system='Review')
            self.assertEqual(provider.call_count, 5)

    def test_review_interruption_reuses_the_valid_proposal_without_bypassing_review(self):
        asset = {'sha256': 'a' * 64, 'duration': 100}
        transcript = {'audio_sha256': asset['sha256'], 'segments': [
            {'start': 0, 'text': 'Açılış'}, {'start': 20, 'text': 'Konu'}]}
        proposal = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 1, 'title': 'Konu'}]}
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[proposal, RuntimeError('review unavailable'), {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            with self.assertRaisesRegex(RuntimeError, 'review unavailable'):
                propose(transcript, asset, generate)
            self.assertTrue(propose(transcript, asset, generate)['reviewed'])
            self.assertEqual(provider.call_count, 3)

    def test_failed_provider_call_is_not_cached_and_corrupt_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[RuntimeError('offline'), {'approved': True}, {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            with self.assertRaises(RuntimeError):
                generate('Review source')
            generate('Review source')
            path = next(Path(tmp).glob('*.json'))
            data = read_json(path); data['response'] = {'approved': False}; write_json(path, data)
            self.assertEqual(generate('Review source'), {'approved': True})
            self.assertEqual(provider.call_count, 3)

    def test_bad_sentence_id_is_not_reused_forever_and_review_is_still_required(self):
        asset = {'sha256': 'a' * 64, 'duration': 100}
        transcript = {'audio_sha256': asset['sha256'], 'segments': [
            {'start': 0, 'text': 'Açılış'}, {'start': 20, 'text': 'Konu'}]}
        bad = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 99, 'title': 'Yanlış'}]}
        good = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 1, 'title': 'Konu'}]}
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[bad, good, {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            with self.assertRaisesRegex(ValueError, 'Unknown transcript'):
                propose(transcript, asset, generate)
            result = propose(transcript, asset, generate)
            self.assertEqual(len(result['chapters']), 2)
            self.assertEqual(provider.call_count, 3)
            self.assertEqual(propose(transcript, asset, generate), result)
            self.assertEqual(provider.call_count, 3)

    def test_chapter_checkpoint_requires_its_own_workflow_provenance(self):
        from scripts.state import restore
        from unittest.mock import patch
        import os
        artifact = {'id': 1, 'name': 'pulse-chapter-state-2026-10-19-12-1',
                    'expired': False, 'created_at': '2026-10-19T09:00:00Z',
                    'workflow_run': {'id': 12, 'head_branch': 'main'},
                    'archive_download_url': 'https://fixture.test/private-archive'}
        listing = Mock(); listing.json.return_value = {'artifacts': [artifact]}
        run = Mock(); run.json.return_value = {'path': '.github/workflows/untrusted.yml', 'event': 'workflow_run'}
        session = Mock(); session.get.side_effect = [listing, run]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GITHUB_TOKEN': 'fixture-only'}), \
             patch('scripts.state.requests.Session', return_value=session):
            with self.assertRaisesRegex(ValueError, 'untrusted workflow'):
                restore('owner/repo', '2026-10-19', tmp, artifact_prefix='pulse-chapter-state-',
                        workflow_path='.github/workflows/complete-chapters.yml', allowed_events=('workflow_run',))
            self.assertEqual(session.get.call_count, 2)

    def test_rejected_proposals_do_not_trap_later_recovery_in_cached_failures(self):
        asset = {'sha256': 'a' * 64, 'duration': 100}
        transcript = {'audio_sha256': asset['sha256'], 'segments': [
            {'start': 0, 'text': 'Açılış'}, {'start': 20, 'text': 'Konu'}]}
        proposal = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 1, 'title': 'Konu'}]}
        rejected = {'approved': False, 'reason': 'Topic needs a better boundary'}
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[proposal, rejected, proposal, rejected, proposal, {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            with self.assertRaisesRegex(ValueError, 'Topic review rejected'):
                propose(transcript, asset, generate)
            self.assertFalse(list(Path(tmp).glob('*.json')))
            self.assertTrue(propose(transcript, asset, generate)['reviewed'])
            self.assertEqual(provider.call_count, 6)


class ChapterCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        root = Path(cls.shared.name)
        release = root / 'release'
        ready_release(release, tone(root / 'tone.mp3'))
        converted = root / 'game.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(release / 'oyun/podcast.mp3'),
                        '-af', 'volume=0.5', str(converted)], check=True)
        shutil.copyfile(converted, release / 'oyun/podcast.mp3')
        data = read_json(release / 'oyun.json')
        data['podcast'].update(audio_info(release / 'oyun/podcast.mp3', 40))
        write_json(release / 'oyun.json', data)
        seal_release(release, DATE, DATE)
        cls.published = root / 'published'
        build('site', cls.published, release=release, at=not_before(DATE))

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.previous = self.root / 'published'
        shutil.copytree(self.published, self.previous)
        self.work = self.root / 'work'
        self.state = self.root / 'state'
        self.at = not_before(DATE) + dt.timedelta(hours=3)
        self.addCleanup(patch.stopall)
        patch('pulse.chapter_completion.now', return_value=self.at).start()
        patch('pulse.build.now', return_value=self.at).start()
        self.manifest, self.release = current(self.previous)

    def metadata(self, section):
        asset = read_json(self.release / (section + '.json'))['podcast']
        return {'schema_version': 1, 'reviewed': True, 'audio_sha256': asset['sha256'],
                'clips_reviewed': True, 'story_ranges': [],
                'stories_sha256': story_fingerprint(read_json(self.release / (section + '.json'))['stories']),
                'chapters': [{'start': 0, 'title': 'Açılış'}, {'start': 12, 'title': 'Günün konusu'}]}

    def prepare_metadata(self, section):
        data = self.metadata(section)
        write_json(self.work / 'chapters' / (data['audio_sha256'] + '.json'), data)

    def test_late_ready_publication_still_qualifies_and_next_six_does_not(self):
        self.assertEqual(missing(self.previous, self.manifest, self.release), ['teknoloji', 'oyun'])
        self.assertIsNotNone(current(self.previous, self.at))
        self.assertIsNone(current(self.previous, not_before(DATE) + dt.timedelta(hours=22, minutes=30)))

    def test_partial_completion_publishes_only_reviewed_metadata_preserving_all_audio(self):
        stage(self.previous, self.work, self.state)
        self.prepare_metadata('teknoloji')
        output = self.root / 'dist'
        changed, complete = rebuild(self.previous, self.work, output)
        self.assertTrue(changed)
        self.assertFalse(complete)
        self.assertEqual(read_json(output / 'data/publication.json'), self.manifest)
        registry = read_json(output / 'assets/chapters/index.json')
        self.assertEqual(list(registry), [self.metadata('teknoloji')['audio_sha256']])
        for section in ('teknoloji', 'oyun'):
            for kind in ('summary', 'podcast'):
                relative = Path(section) / (kind + '.mp3')
                self.assertEqual(digest(self.release / relative), digest(output / 'releases' / self.manifest['release_id'] / relative))
        self.assertNotIn('chapter-transcripts', [p.name for p in output.rglob('*')])

    def test_successful_completion_is_idempotent_and_missing_registry_can_be_repaired(self):
        stage(self.previous, self.work, self.state)
        for section in ('teknoloji', 'oyun'):
            self.prepare_metadata(section)
        output = self.root / 'dist'
        self.assertEqual(rebuild(self.previous, self.work, output), (True, True))
        self.assertEqual(missing(output, self.manifest, output / 'releases' / self.manifest['release_id']), [])
        self.assertEqual(rebuild(output, self.work, self.root / 'unchanged'), (False, True))
        write_json(output / 'assets/chapters/index.json', {})
        self.assertEqual(rebuild(output, self.work, self.root / 'repaired'), (True, True))

    def test_changed_publication_and_corrupt_recording_cannot_be_deployed(self):
        stage(self.previous, self.work, self.state)
        changed = copy.deepcopy(self.manifest); changed['release_id'] = 'different'
        write_json(self.work / 'release.json', changed)
        with self.assertRaisesRegex(ValueError, 'changed'):
            rebuild(self.previous, self.work, self.root / 'dist')
        (self.release / 'teknoloji/podcast.mp3').write_bytes(b'broken')
        with self.assertRaises(Exception):
            stage(self.previous, self.work, self.state)

    def test_checkpoint_carries_private_metadata_but_no_mp3_or_source_text(self):
        stage(self.previous, self.work, self.state)
        self.prepare_metadata('teknoloji')
        write_json(self.work / 'chapter-transcripts/teknoloji.json', {'audio_sha256': 'a' * 64, 'segments': []})
        write_json(self.work / 'chapter-requests/request.json', {'response': {'approved': True}})
        (self.work / 'private-source.txt').write_text('Must not enter checkpoint')
        copy_state(self.work, self.state)
        self.assertEqual(len(list(self.state.rglob('*.json'))), 3)
        self.assertFalse(list(self.state.rglob('*.mp3')))
        self.assertFalse(list(self.state.rglob('*.txt')))

    def test_daily_bootstrap_uses_only_the_exact_published_release(self):
        checkpoint = self.root / 'daily'
        other = copy.deepcopy(self.manifest); other['release_id'] = 'different'
        write_json(checkpoint / 'release.json', other)
        write_json(checkpoint / 'chapter-transcripts/teknoloji.json', {'audio_sha256': 'a' * 64})
        self.assertFalse(bootstrap_daily(self.previous, checkpoint, self.state))
        self.assertFalse(self.state.exists())
        write_json(checkpoint / 'release.json', self.manifest)
        self.assertTrue(bootstrap_daily(self.previous, checkpoint, self.state))
        self.assertTrue((self.state / 'chapter-transcripts/teknoloji.json').exists())
