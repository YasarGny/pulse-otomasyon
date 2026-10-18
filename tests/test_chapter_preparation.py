import unittest
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
