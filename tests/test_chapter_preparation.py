from pulse.clips import story_fingerprint
import unittest
import tempfile
import json
import io
import os
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from scripts.prepare_chapters import ChapterReviewRejected, prepare, propose


class ChapterPreparationTests(unittest.TestCase):
    def setUp(self):
        self.asset = {'sha256': 'a' * 64, 'duration': 100}
        self.transcript = {'audio_sha256': 'a' * 64, 'segments': [
            {'start': 0.1, 'text': 'Merhaba.'},
            {'start': 12.8, 'text': 'Çip üretiminden bahsedelim.'},
            {'start': 40, 'text': 'Bugünlük bu kadar.'}]}

    def generate(self, approved=True, index=1):
        responses = iter([{'chapters': [{'segment_id': 0, 'title': 'Açılış'},
                                       {'segment_id': index, 'title': 'Çip üretimi'}]},
                          {'approved': approved},
                          {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': index, 'title': 'Çip üretimi'}]},
                          {'approved': approved}])
        return lambda *args, **kwargs: next(responses)

    def test_start_times_come_from_final_audio_sentences_not_model_numbers(self):
        result = propose(self.transcript, self.asset, self.generate())
        self.assertEqual([x['start'] for x in result['chapters']], [0.1, 12.8])

    def test_all_main_topics_can_be_covered_without_a_ten_topic_quota(self):
        transcript = {'audio_sha256': self.asset['sha256'], 'segments': [
            {'start': i * 5, 'text': f'Ana konu {i}'} for i in range(17)]}
        responses = iter([{'chapters': [{'segment_id': i, 'title': f'Ana konu {i}'} for i in range(17)]}, {'approved': True}])
        result = propose(transcript, self.asset, lambda *args, **kwargs: next(responses))
        self.assertEqual(len(result['chapters']), 17)

    def test_recovery_receives_previous_reviewer_feedback_and_skips_approved_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other_asset = {**self.asset, 'sha256': 'b' * 64}
            for section, asset in [('teknoloji', self.asset), ('oyun', other_asset)]:
                path = root / 'chapter-transcripts' / (section + '.json'); path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps({**self.transcript, 'audio_sha256': asset['sha256']}))
                (root / (section + '.json')).write_text(json.dumps({'podcast': asset, 'stories': []}))
            def accepted(asset):
                return {'schema_version': 1, 'reviewed': True, 'audio_sha256': asset['sha256'],
                        'clips_reviewed': True, 'story_ranges': [], 'stories_sha256': story_fingerprint([]),
                        'chapters': [{'start': 0, 'title': 'Açılış'}, {'start': 20, 'title': 'Konu'}]}
            with patch('scripts.transcribe_podcasts.transcribe'), patch('scripts.prepare_chapters.propose',
                    side_effect=[ChapterReviewRejected('Include the omitted main science topics'), accepted(other_asset)]), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'teknoloji'):
                    prepare(root)
            feedback_path = root / 'chapter-feedback' / (self.asset['sha256'] + '.json')
            self.assertTrue(feedback_path.exists())
            with patch('scripts.transcribe_podcasts.transcribe'), patch('scripts.prepare_chapters.propose',
                    return_value=accepted(self.asset)) as review, redirect_stdout(io.StringIO()):
                prepare(root)
            self.assertEqual(review.call_count, 1)
            self.assertEqual(review.call_args.args[0]['review_feedback'], 'Include the omitted main science topics')
            self.assertFalse(feedback_path.exists())

    def test_rejected_review_unknown_sentence_or_changed_audio_is_not_published(self):
        for generate in (self.generate(False), self.generate(index=99)):
            with self.assertRaises(ValueError):
                propose(self.transcript, self.asset, generate)
        with self.assertRaises(ValueError):
            propose(self.transcript, {**self.asset, 'sha256': 'b' * 64}, self.generate())

    def test_failed_topic_analysis_does_not_discard_the_other_program(self):
        from scripts.prepare_chapters import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'chapter-transcripts').mkdir()
            for section in ('teknoloji', 'oyun'):
                (root / (section + '.json')).write_text(json.dumps({'podcast': self.asset}))
                (root / 'chapter-transcripts' / (section + '.json')).write_text(json.dumps(self.transcript))
            accepted = {'schema_version': 1, 'reviewed': True, 'audio_sha256': self.asset['sha256'],
                        'clips_reviewed': True, 'story_ranges': [], 'stories_sha256': story_fingerprint([]),
                        'chapters': [{'start': 0.1, 'title': 'Açılış'}]}
            output = io.StringIO()
            with patch('scripts.transcribe_podcasts.transcribe'), patch(
                'scripts.prepare_chapters.propose', side_effect=[ValueError('rejected fixture-only-secret https://service.test/private'), accepted]
            ) as generate, patch.dict(os.environ, {'GEMINI_API_KEY': 'fixture-only-secret'}), redirect_stdout(output), self.assertRaisesRegex(ValueError, 'teknoloji'):
                prepare(root)
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(json.loads((root / 'chapters' / (self.asset['sha256'] + '.json')).read_text()), accepted)
            self.assertIn('::warning title=PULSE chapter review incomplete::teknoloji', output.getvalue())
            self.assertNotIn('fixture-only-secret', output.getvalue())
            self.assertNotIn('https://service.test/private', output.getvalue())

    def test_verified_published_metadata_is_reused_without_transcription_or_api_calls(self):
        from scripts.prepare_chapters import prepare
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'work'
            root.mkdir()
            previous = Path(folder) / 'published'
            cache = previous / 'assets/chapters'
            cache.mkdir(parents=True)
            accepted = {'schema_version': 1, 'reviewed': True, 'audio_sha256': self.asset['sha256'],
                        'clips_reviewed': True, 'story_ranges': [], 'stories_sha256': story_fingerprint([]),
                        'chapters': [{'start': 0.1, 'title': 'Açılış'}]}
            (cache / (self.asset['sha256'] + '.json')).write_text(json.dumps(accepted))
            for section in ('teknoloji', 'oyun'):
                (root / (section + '.json')).write_text(json.dumps({'podcast': self.asset}))
            with patch('scripts.transcribe_podcasts.transcribe') as transcribe, patch(
                'scripts.prepare_chapters.propose'
            ) as generate:
                prepare(root, previous)
            transcribe.assert_not_called()
            generate.assert_not_called()
            self.assertEqual(json.loads((root / 'chapters' / (self.asset['sha256'] + '.json')).read_text()), accepted)

    def test_overlapping_ranges_are_repaired_then_independently_reviewed(self):
        from unittest.mock import Mock
        from scripts.prepare_chapters import ChapterProposalInvalid
        transcript={**self.transcript,'section':'teknoloji',
                    'canonical_stories':[{'id':'a','title':'Çip','brief':'Çip haberi'}, {'id':'b','title':'Uzay','brief':'Uzay haberi'}],
                    'segments':[{'start':0,'end':10,'text':'Çip haberi.'},
                                {'start':10,'end':20,'text':'Çip ayrıntıları.'},
                                {'start':20,'end':30,'text':'Uzay haberi.'}]}
        bad={'chapters':[{'segment_id':0,'title':'Çip'}, {'segment_id':2,'title':'Uzay'}],
             'story_ranges':[{'story_id':'a','start_segment_id':0,'end_segment_id':2},
                             {'story_id':'b','start_segment_id':2,'end_segment_id':2}]}
        good={**bad,'story_ranges':[{'story_id':'a','start_segment_id':0,'end_segment_id':1},
                                   {'story_id':'b','start_segment_id':2,'end_segment_id':2}]}
        generate=Mock(side_effect=[bad,good,{'approved':True}])
        result=propose(transcript,self.asset,generate)
        self.assertEqual([(r['start'],r['end']) for r in result['story_ranges']],[(0,20),(20,30)])
        self.assertEqual(generate.call_count,3)
        self.assertIn('overlap',generate.call_args_list[1].args[0])
        self.assertIn('proposal',generate.call_args_list[1].args[0])
        self.assertIn('bağımsız denetle',generate.call_args_list[2].args[0])
        invalid=Mock(side_effect=[bad,bad])
        with self.assertRaises(ChapterProposalInvalid) as raised:
            propose(transcript,self.asset,invalid)
        self.assertEqual(raised.exception.proposal,bad)
        self.assertEqual(invalid.call_count,2)
