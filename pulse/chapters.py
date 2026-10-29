"""Optional chapter sidecars are bound to final MP3 bytes, never estimated timings."""
import argparse
import json
import math
import re
from pathlib import Path

CHAPTER_RULES = {'max_chapters': 40, 'max_title_chars': 240, 'ordered_unique_starts': True}
CHAPTER_POLICY_VERSION = 2


class ChapterValidationError(ValueError):
    def __init__(self, code, index, detail):
        self.code, self.index = code, index
        super().__init__(f'Chapter {index}: {detail}')


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
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= CHAPTER_RULES['max_chapters']:
        raise ValueError('Invalid chapter count')
    previous = -math.inf
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            raise ValueError('Invalid chapter')
        start, title = chapter.get('start'), chapter.get('title')
        if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start):
            raise ChapterValidationError('start_type', index, 'start must be a finite number')
        if not 0 <= start < duration:
            raise ChapterValidationError('start_bounds', index, f'start {start} outside recording [0, {duration})')
        if start <= previous:
            raise ChapterValidationError('start_order', index, f'start {start} must be greater than previous start {previous}')
        if not isinstance(title, str) or not title.strip():
            raise ChapterValidationError('title_empty', index, 'title must be nonempty text')
        if len(title) > CHAPTER_RULES['max_title_chars']:
            raise ChapterValidationError('title_length', index, f'title exceeds {CHAPTER_RULES["max_title_chars"]} characters')
        if re.search(r'[\x00-\x1f]', title):
            raise ChapterValidationError('title_control', index, 'title contains control characters')
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
        asset = edition.get('podcast')
        if not asset:
            continue
        data = load_chapters(args.source, asset)
        print(section, str(len(data['chapters'])) + ' verified chapter markers' if data else 'no verified chapters; audio remains available')


if __name__ == '__main__':
    main()
