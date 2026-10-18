import base64
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from pulse.editorial import selection_sources
from pulse.usage import record
from scripts.state import unpack
import pulse_podcast_audio as audio


class CostControlsTests(unittest.TestCase):
    def test_selection_is_smaller_without_mutating_full_source_evidence(self):
        source = {'id': 'a', 'original_title': 'Source headline', 'source_name': 'Publisher',
                  'source_published_at': '2026-10-18T03:00:00Z', 'source_excerpt': 'x'*5000,
                  'source_url': 'https://publisher.test/story', 'image_url': 'https://cdn.test/'+'y'*3000,
                  'source_full_text': 'all of the source evidence'}
        original = json.dumps(source)
        packed = selection_sources({'a': source})
        self.assertLess(len(json.dumps(packed)), len(original)*0.4)
        self.assertEqual(packed[0]['id'], 'a')
        self.assertEqual(json.dumps(source), original)
        self.assertEqual(len(packed[0]['source_excerpt']), 2200)
        self.assertNotIn('image_url', packed[0])
        self.assertNotIn('source_full_text', packed[0])

    def test_usage_contains_counts_but_never_prompt_or_provider_content(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'PULSE_USAGE_LOG': str(Path(tmp)/'api-usage.jsonl')}):
            record('editorial', 'fixture-model', {'usageMetadata': {'promptTokenCount': 123, 'totalTokenCount': 200, 'secret': 'never-save'}, 'candidates': [{'text':'private text'}]}, 1000)
            row = json.loads((Path(tmp)/'api-usage.jsonl').read_text())
            self.assertEqual(row['tokens']['promptTokenCount'], 123)
            self.assertNotIn('never-save', str(row))
            self.assertNotIn('private text', str(row))
            self.assertEqual(row['input_chars'], 1000)

    def test_usage_failure_does_not_discard_paid_response(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'PULSE_USAGE_LOG': tmp}):
            record('editorial', 'fixture-model', {}, 10)

    def test_conversion_retry_reuses_paid_bytes_but_changed_dialogue_does_not(self):
        turns = [{'speaker': 'Yaşar', 'text': 'Test.'}]
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {'steps': [{'content': [{'type':'audio','data':base64.b64encode(b'RIFF-fixture-only-audio').decode()}]}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY':'fixture-only'}), patch.object(audio.requests, 'post', return_value=response) as post, patch.object(audio, 'run', side_effect=OSError('temporary local error')), patch.object(audio, 'duration', return_value=3):
            path = Path(tmp)/'part_000.partial.wav'
            with self.assertRaises(OSError):
                audio.synthesize(turns, path, 0, strict_audio=True)
            raw = path.with_suffix('.raw')
            self.assertTrue(raw.exists())
            with patch.object(audio, 'run', return_value=''):
                audio.synthesize(turns, path, 0, strict_audio=True)
            self.assertEqual(post.call_count, 1)
            self.assertFalse(raw.exists())
            with self.assertRaises(OSError):
                audio.synthesize(turns, path, 0, strict_audio=True)
            with patch.object(audio, 'run', return_value=''):
                audio.synthesize([{'speaker':'Yaşar','text':'A different script.'}], path, 0, strict_audio=True)
            self.assertEqual(post.call_count, 3)

    def test_private_recovery_allows_only_scoped_paid_audio_and_usage_files(self):
        date = '2026-10-18'
        for name, allowed in [(date+'/teknoloji/tts-parts/'+'a'*64+'/part_000.partial.raw',True),
                              (date+'/audio-v5/api-usage.jsonl',True),
                              (date+'/arbitrary.raw',False), (date+'/arbitrary.jsonl',False)]:
            data = io.BytesIO()
            with zipfile.ZipFile(data,'w') as archive:
                archive.writestr(name,b'fixture')
            with tempfile.TemporaryDirectory() as tmp:
                if allowed:
                    unpack(data.getvalue(),tmp,date)
                    self.assertTrue((Path(tmp)/name).exists())
                else:
                    with self.assertRaises(ValueError):
                        unpack(data.getvalue(),tmp,date)

    def test_cached_transcript_does_not_load_a_model_and_unselected_program_is_untouched(self):
        from scripts.transcribe_podcasts import transcribe
        from types import SimpleNamespace
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'teknoloji').mkdir()
            audio_path=root/'teknoloji/podcast.mp3'
            audio_path.write_bytes(b'fixture-audio')
            sha=hashlib.sha256(audio_path.read_bytes()).hexdigest()
            (root/'teknoloji.json').write_text(json.dumps({'podcast':{'file':'teknoloji/podcast.mp3','sha256':sha}}))
            output=root/'transcripts';output.mkdir()
            (output/'teknoloji.json').write_text(json.dumps({'audio_sha256':sha,'segments':[{'start':0,'text':'Test'}]}))
            model=Mock(side_effect=AssertionError('No model download or initialization'))
            with patch.dict('sys.modules', {'faster_whisper':SimpleNamespace(WhisperModel=model)}):
                transcribe(root,output,sections=['teknoloji'])
            model.assert_not_called()
            self.assertFalse((output/'oyun.json').exists())
