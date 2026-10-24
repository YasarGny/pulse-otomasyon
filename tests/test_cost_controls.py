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
    def test_tts_speech_config_uses_supported_speaker_schema_and_existing_voices(self):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = {'steps': [{'content': [{'type': 'audio',
            'data': base64.b64encode(b'RIFF-synthetic-audio').decode()}]}]}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-key'}), \
                patch.object(audio.requests, 'post', return_value=response) as post, \
                patch.object(audio, 'run', return_value=''), \
                patch.object(audio, 'duration', return_value=3):
            audio.synthesize([{'speaker': 'Yaşar', 'text': 'Sentetik kontrol.'}],
                             Path(tmp) / 'part.wav', 0, strict_audio=True)
        request = post.call_args.kwargs['json']
        self.assertEqual(request['generation_config']['speech_config'], {
            'speakers': [{'speaker': speaker, 'voice': voice}
                         for speaker, voice in audio.VOICES.items()]})
        self.assertEqual(request['model'], audio.MODEL)
        self.assertEqual(request['input'][0]['content'][0]['annotations'],
                         [{'type': 'speech_metadata', 'speaker': 'Yaşar'}])

    def test_tts_rejection_reports_safe_labels_without_echoing_provider_text(self):
        response = Mock(ok=False, status_code=400)
        response.json.return_value = {'error': {'status': 'INVALID_ARGUMENT',
            'message': 'Voice not found. PRIVATE-SOURCE-TEXT api_key=PRIVATE-KEY'}}
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'PRIVATE-KEY'}), \
                patch.object(audio.requests, 'post', return_value=response) as post:
            with self.assertRaisesRegex(RuntimeError, 'INVALID_ARGUMENT.*voice.*not-found') as error:
                audio._provider_audio({}, 2, strict_audio=True)
        self.assertNotIn('PRIVATE', str(error.exception))
        self.assertEqual(post.call_count, 1)
        response.json.side_effect = ValueError('non-JSON error')
        response.text = 'PRIVATE-TEXT: invalid API key'
        self.assertEqual(audio.rejection_details(response), 'nonstandard: api-key, invalid')
        response.json.side_effect = None
        response.json.return_value = {'detail': [{'msg': 'required speech_config parameter PRIVATE-TEXT'}]}
        self.assertEqual(audio.rejection_details(response), 'detail: required, schema, speech-config')
        response.json.return_value = {'error': 'Model not supported PRIVATE-TEXT'}
        self.assertEqual(audio.rejection_details(response), 'error: model, unsupported')
        response.json.return_value = [{'error': {'status': 'INVALID_ARGUMENT',
            'message': 'Invalid speech_config field PRIVATE-TEXT'}}]
        self.assertEqual(audio.rejection_details(response),
                         'nonstandard: INVALID_ARGUMENT, invalid, schema, speech-config')

    def test_selection_is_smaller_without_mutating_full_source_evidence(self):
        source = {'id': 'a', 'original_title': 'Source headline', 'source_name': 'Publisher',
                  'source_published_at': '2026-10-18T03:00:00Z', 'source_excerpt': 'x'*5000,
                  'source_url': 'https://publisher.test/story', 'image_url': 'https://cdn.test/'+'y'*3000,
                  'source_full_text': 'all of the source evidence ' * 200}
        original = json.dumps(source)
        packed = selection_sources({'a': source})
        self.assertLess(len(json.dumps(packed)), len(original)*0.4)
        self.assertEqual(packed[0]['id'], 'a')
        self.assertEqual(json.dumps(source), original)
        self.assertEqual(len(packed[0]['source_excerpt']), 2200)
        self.assertTrue(packed[0]['source_excerpt'].startswith('all of the source evidence'))
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

    def test_transcription_failure_in_one_program_preserves_the_other(self):
        from scripts.transcribe_podcasts import transcribe
        from types import SimpleNamespace
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for section in ('teknoloji','oyun'):
                (root/section).mkdir()
                (root/section/'podcast.mp3').write_bytes(b'fixture-audio')
                sha=hashlib.sha256(b'fixture-audio').hexdigest() if section=='oyun' else 'a'*64
                (root/(section+'.json')).write_text(json.dumps({'publish_date':'2026-10-18','podcast':{'file':section+'/podcast.mp3','sha256':sha,'duration':3}}))
            model=Mock()
            model.transcribe.return_value=([SimpleNamespace(start=0,end=3,text='Test')],None)
            factory=Mock(return_value=model)
            with patch.dict('sys.modules', {'faster_whisper':SimpleNamespace(WhisperModel=factory)}), self.assertRaisesRegex(ValueError,'teknoloji'):
                transcribe(root,root/'transcripts')
            self.assertTrue((root/'transcripts/oyun.json').exists())
            self.assertFalse((root/'transcripts/teknoloji.json').exists())
            self.assertEqual(factory.call_count,1)

    def test_render_recovers_paid_response_after_private_checkpoint_restore(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wav=root/'provider.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=24000','-t','3',str(wav)],check=True)
            response=Mock(ok=True,status_code=200)
            response.json.return_value={'steps':[{'content':[{'type':'audio','data':base64.b64encode(wav.read_bytes()).decode()}]}]}
            work=root/'2026-10-18';cache=work/'teknoloji/tts-parts'
            turns=[{'speaker':'Yaşar','text':'Test kaydı.'}]
            with patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-only'}), patch.object(audio.requests,'post',return_value=response) as post:
                with patch.object(audio,'run',side_effect=OSError('temporary local conversion failure')), self.assertRaises(OSError):
                    audio.render(turns,root/'failed.mp3',strict_audio=True,checkpoint_dir=cache)
                self.assertEqual(len(list(cache.rglob('*.raw'))),1)
                state=io.BytesIO()
                with zipfile.ZipFile(state,'w') as archive:
                    for path in cache.rglob('*'):
                        if path.is_file():archive.write(path,path.relative_to(root))
                restored=root/'restored'
                unpack(state.getvalue(),restored,'2026-10-18')
                audio.render(turns,root/'recovered.mp3',strict_audio=True,checkpoint_dir=restored/'2026-10-18/teknoloji/tts-parts')
                self.assertEqual(post.call_count,1)
                self.assertGreater(audio.duration(root/'recovered.mp3'),2.9)
