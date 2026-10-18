"""Transcribe existing final podcasts locally; never synthesizes or changes audio.

Optional dependency: faster-whisper==1.2.1. Downloads its published small model
with normal TLS verification. Transcript output is private editorial material.
"""
import argparse
import json
import hashlib
from pathlib import Path


def transcribe(root, output, model_name='small'):
    from faster_whisper import WhisperModel
    root, output = Path(root), Path(output)
    model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=4)
    output.mkdir(parents=True, exist_ok=True)
    for section in ('teknoloji', 'oyun'):
        data = json.loads((root / (section + '.json')).read_text())
        asset = data['podcast']
        if asset['file'] != section + '/podcast.mp3':
            raise ValueError('Unexpected audio path')
        path = root / asset['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError('Audio hash mismatch')
        target = output / (section + '.json')
        if target.exists():
            existing = json.loads(target.read_text())
            if existing.get('audio_sha256') == asset['sha256']:
                continue
        segments, _ = model.transcribe(str(path), language='tr', beam_size=3,
                                       vad_filter=True, word_timestamps=True)
        result = {'audio_sha256': asset['sha256'], 'duration': asset['duration'],
                  'publish_date': data['publish_date'], 'section': section, 'segments': []}
        for segment in segments:
            result['segments'].append({'start': segment.start, 'end': segment.end,
                                       'text': segment.text})
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(section, 'existing recording transcribed; audio unchanged', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    transcribe(args.release, args.output)
