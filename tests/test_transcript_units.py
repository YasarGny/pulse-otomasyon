import json
import unittest
from unittest.mock import Mock

from pulse.transcript_units import sentence_units
from scripts.prepare_chapters import propose


class SentenceUnitTests(unittest.TestCase):
    def test_legacy_mid_sentence_continuation_is_not_a_selectable_start(self):
        data = {'audio_sha256': 'a' * 64, 'segments': [
            {'start': 1, 'end': 4, 'text': 'Yeni kararın ardından'},
            {'start': 4, 'end': 8, 'text': 'da kaçınılmaz son geliyor zaten.'},
            {'start': 9, 'end': 12, 'text': 'Şimdi başka bir haber.'}]}
        before = json.dumps(data)
        result = sentence_units(data)
        self.assertEqual([(r['start'], r['end']) for r in result['segments']], [(1, 8), (9, 12)])
        self.assertIn('ardından da kaçınılmaz', result['segments'][0]['text'])
        self.assertEqual(json.dumps(data), before)

    def test_word_measurements_split_multiple_sentences_inside_one_asr_row(self):
        data = {'segments': [{'start': 0, 'end': 10, 'text': 'Microsoft kararı. Yeni oyun.', 'words': [
            {'word': 'Microsoft', 'start': .2, 'end': 2},
            {'word': ' kararı.', 'start': 2.4, 'end': 4},
            {'word': ' Yeni', 'start': 6.2, 'end': 7},
            {'word': ' oyun.', 'start': 7.5, 'end': 9.8}]}]}
        rows = sentence_units(data)['segments']
        self.assertEqual([(r['start'], r['end']) for r in rows], [(.2, 4), (6.2, 9.8)])
        self.assertEqual([r['text'] for r in rows], ['Microsoft kararı.', 'Yeni oyun.'])

    def test_invalid_or_incomplete_word_alignment_falls_back_to_measured_asr_row(self):
        for words in ([{'word': 'wrong.', 'start': 2, 'end': 4}],
                      [{'word': 'Gerçek.', 'start': 2, 'end': 40}],
                      [{'word': 'Gerçek.', 'start': True, 'end': 4}]):
            with self.subTest(words=words):
                row = sentence_units({'segments': [{'start': 1, 'end': 5, 'text': 'Gerçek.', 'words': words}]})['segments'][0]
                self.assertEqual((row['start'], row['end'], row['text']), (1, 5, 'Gerçek.'))

    def test_abbreviation_does_not_end_sentence_and_unfinished_tail_is_flagged(self):
        rows = sentence_units({'segments': [
            {'start': 0, 'end': 1, 'text': 'Prof.'},
            {'start': 1, 'end': 3, 'text': 'Ada açıkladı.'},
            {'start': 4, 'end': 5, 'text': 'ama bu yüzden'}]})['segments']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['text'], 'Prof. Ada açıkladı.')
        self.assertTrue(rows[0]['complete_end'])
        self.assertFalse(rows[1]['complete_end'])

    def test_corrupt_timestamps_cannot_become_chapter_boundaries(self):
        for value in (float('nan'), float('inf'), True, -0.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sentence_units({'segments': [{'start': value, 'end': 3, 'text': 'Haber.'}]})

    def test_incomplete_end_uses_one_correction_then_independent_review(self):
        transcript = sentence_units({'audio_sha256': 'a' * 64, 'section': 'oyun',
            'canonical_stories': [{'id': 'a', 'title': 'Oyun', 'brief': 'Oyun haberi'}],
            'segments': [{'start': 0, 'end': 4, 'text': 'Merhaba.'},
                         {'start': 5, 'end': 9, 'text': 'Oyun haberi.'},
                         {'start': 10, 'end': 13, 'text': 'henüz tamamlanmayan'}]})
        bad = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 1, 'title': 'Oyun'}],
               'story_ranges': [{'story_id': 'a', 'start_segment_id': 1, 'end_segment_id': 2}]}
        good = {**bad, 'story_ranges': [{'story_id': 'a', 'start_segment_id': 1, 'end_segment_id': 1}]}
        generate = Mock(side_effect=[bad, good, {'approved': True}])
        result = propose(transcript, {'sha256': 'a' * 64, 'duration': 20}, generate)
        self.assertEqual(result['story_ranges'], [{'story_id': 'a', 'start': 5, 'end': 9}])
        self.assertEqual(generate.call_count, 3)
        self.assertIn('complete measured sentence boundaries', generate.call_args_list[1].args[0])
        self.assertIn('bağımsız denetle', generate.call_args_list[2].args[0])

    def test_legacy_transcript_gets_measured_words_once_without_changing_audio(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.transcribe_podcasts import transcribe
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'oyun').mkdir()
            audio = root / 'oyun/podcast.mp3'
            audio.write_bytes(b'existing recording fixture')
            sha = hashlib.sha256(audio.read_bytes()).hexdigest()
            (root / 'oyun.json').write_text(json.dumps({'publish_date': '2026-10-28', 'podcast': {
                'file': 'oyun/podcast.mp3', 'sha256': sha, 'duration': 5}}))
            output = root / 'transcripts'
            output.mkdir()
            target = output / 'oyun.json'
            target.write_text(json.dumps({'audio_sha256': sha, 'segments': [{'start': 0, 'end': 5, 'text': 'Merhaba.'}]}))
            word = SimpleNamespace(start=.2, end=4.8, word='Merhaba.')
            segment = SimpleNamespace(start=0, end=5, text='Merhaba.', words=[word])
            model = Mock()
            model.transcribe.return_value = ([segment], None)
            factory = Mock(return_value=model)
            with patch.dict('sys.modules', {'faster_whisper': SimpleNamespace(WhisperModel=factory)}):
                transcribe(root, output, sections=['oyun'], require_words=True)
                transcribe(root, output, sections=['oyun'], require_words=True)
            factory.assert_called_once()
            model.transcribe.assert_called_once()
            self.assertEqual(json.loads(target.read_text())['segments'][0]['words'][0]['start'], .2)
            self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), sha)
            self.assertFalse((output / 'teknoloji.json').exists())
