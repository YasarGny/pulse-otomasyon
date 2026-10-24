"""Transcribe existing final podcasts locally; never synthesizes or changes audio.

Optional dependency: faster-whisper==1.2.1. Downloads its published small model
with normal TLS verification. Transcript output is private editorial material.
"""
import argparse
import json
import hashlib
from pathlib import Path


def transcribe(root, output, model_name='small', sections=('teknoloji', 'oyun')):
    root, output = Path(root), Path(output)
    model = None
    if any(section not in ('teknoloji', 'oyun') for section in sections):
        raise ValueError('Unknown transcription section')
    output.mkdir(parents=True, exist_ok=True)
    failures = []
    for section in sections:
        try:
            data = json.loads((root / (section + '.json')).read_text())
            from pulse.controls import podcast_enabled
            asset = data.get('podcast')
            if not asset or not podcast_enabled(section):
                continue
            if asset['file'] != section + '/podcast.mp3':
                raise ValueError('Unexpected audio path')
            path = root / asset['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
                raise ValueError('Audio hash mismatch')
            target = output / (section + '.json')
            if target.exists():
                try:
                    existing = json.loads(target.read_text())
                except ValueError:
                    existing = {}
                if existing.get('audio_sha256') == asset['sha256'] and existing.get('segments'):
                    continue
            if model is None:
                from faster_whisper import WhisperModel
                model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=4)
            segments, _ = model.transcribe(str(path), language='tr', beam_size=3,
                                           vad_filter=True, word_timestamps=True)
            result = {'audio_sha256': asset['sha256'], 'duration': asset['duration'],
                      'publish_date': data['publish_date'], 'section': section, 'segments': []}
            for segment in segments:
                result['segments'].append({'start': segment.start, 'end': segment.end,
                                           'text': segment.text})
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(section, 'existing recording transcribed; audio unchanged', flush=True)
        except Exception as error:
            failures.append(section)
            print(section, 'transcription unavailable:', type(error).__name__, flush=True)
    if failures:
        raise ValueError('Transcription incomplete for: ' + ', '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    transcribe(args.release, args.output)
