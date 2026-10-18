import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from scripts.prepare_chapters import propose


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
                        'chapters': [{'start': 0.1, 'title': 'Açılış'}]}
            with patch('scripts.transcribe_podcasts.transcribe'), patch(
                'scripts.prepare_chapters.propose', side_effect=[ValueError('rejected'), accepted]
            ) as generate, self.assertRaisesRegex(ValueError, 'teknoloji'):
                prepare(root)
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(json.loads((root / 'chapters' / (self.asset['sha256'] + '.json')).read_text()), accepted)
