"""Optional chapter sidecars are bound to final MP3 bytes, never estimated timings."""
import argparse
import json
import math
import re
from pathlib import Path


def validate_chapters(data, asset):
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or data.get('reviewed') is not True
            or data.get('audio_sha256') != asset.get('sha256')
            or not re.fullmatch(r'[a-f0-9]{64}', str(asset.get('sha256', '')))):
        raise ValueError('Chapter/audio identity or review mismatch')
    duration = asset.get('duration')
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid audio duration')
    chapters = data.get('chapters')
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 40:
        raise ValueError('Invalid chapter count')
    previous = -10
    for chapter in chapters:
        if not isinstance(chapter, dict):
            raise ValueError('Invalid chapter')
        start, title = chapter.get('start'), chapter.get('title')
        if (isinstance(start, bool) or not isinstance(start, (int, float))
                or not math.isfinite(start) or not 0 <= start < duration or start - previous < 5
                or not isinstance(title, str) or not title.strip() or len(title) > 240
                or re.search(r'[\x00-\x1f]', title)):
            raise ValueError('Invalid chapter timing or title')
        previous = start
    return data


def load_chapters(folder, asset):
    """Missing/invalid optional metadata must not break a valid publication."""
    sha = asset.get('sha256', '')
    if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{64}', sha):
        return None
    try:
        path = Path(folder) / (sha + '.json')
        if path.stat().st_size > 65536:
            return None
        return validate_chapters(json.loads(path.read_text()), asset)
    except (OSError, ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True)
    parser.add_argument('--source', default='site/assets/chapters')
    args = parser.parse_args()
    for section in ('teknoloji', 'oyun'):
        edition = json.loads((Path(args.release) / (section + '.json')).read_text())
        asset = edition['podcast']
        data = load_chapters(args.source, asset)
        print(section, str(len(data['chapters'])) + ' verified chapter markers' if data else 'no verified chapters; audio remains available')


if __name__ == '__main__':
    main()
