"""Verified story/audio ranges and real bounded clips; never synthesize speech."""
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from pulse.publication import digest, read_json, write_json


def story_fingerprint(stories):
    catalogue = [{'id': story['id'], 'title': story['title'], 'brief': story.get('brief', story.get('summary', ''))} for story in stories]
    return hashlib.sha256(json.dumps(catalogue, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_ranges(data, asset, stories):
    if (not isinstance(data, dict) or data.get('reviewed') is not True or
        data.get('audio_sha256') != asset.get('sha256') or data.get('clips_reviewed') is not True):
        raise ValueError('Story ranges require independent review')
    if data.get('stories_sha256') != story_fingerprint(stories):
        raise ValueError('Story catalogue identity mismatch')
    known = {story['id'] for story in stories}
    rows = data.get('story_ranges')
    if not isinstance(rows, list) or len(rows) > 80:
        raise ValueError('Invalid story ranges')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid story range object')
        start, end = row.get('start'), row.get('end')
        if (row.get('story_id') not in known or
            any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end)) or
            not 0 <= start < end <= asset['duration'] or end - start < 1 or
            (start, end) in seen):
            raise ValueError('Invalid story/audio boundary')
        seen.add((start, end))
    ordered = sorted(rows, key=lambda row: row['start'])
    if any(a['end'] > b['start'] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Story clips overlap')
    return rows


def build_clips(output, manifest, editions, registry, previous=None):
    """Build only independently reviewed exact mappings for this sealed daily issue."""
    output = Path(output)
    folder = output / 'releases' / manifest['release_id'] / 'clips'
    # Never carry yesterday's clips through a source/previous tree copy.
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    index = {'schema_version': 1, 'release_id': manifest['release_id'], 'stories': {}}
    old = {}
    if previous:
        try:
            old = read_json(Path(previous) / 'assets/clips/index.json')
        except (OSError, ValueError):
            pass
    if not isinstance(old, dict) or not isinstance(old.get('stories', {}), dict):
        old = {}
    for section, edition in editions.items():
        if not edition.get('podcast'):
            continue
        asset = edition['podcast']
        data = registry.get(asset['sha256'], {})
        if data.get('section', section) != section or data.get('clips_reviewed') is not True:
            continue
        rows = validate_ranges(data, asset, edition['stories'])
        source = output / 'releases' / manifest['release_id'] / asset['file']
        if digest(source) != asset['sha256']:
            raise ValueError('Clip source audio identity mismatch')
        for row in rows:
            identity = f"{section}:{row['story_id']}"
            name = f"{asset['sha256']}-{row['start']:.3f}-{row['end']:.3f}.mp3"
            target = folder / name
            reused = False
            if previous and old.get('release_id') == manifest['release_id']:
                candidates = old.get('stories', {}).get(identity, [])
                for entry in candidates if isinstance(candidates, list) else []:
                    if isinstance(entry, dict) and entry.get('file') == 'releases/' + manifest['release_id'] + '/clips/' + name:
                        candidate = Path(previous) / 'releases' / manifest['release_id'] / 'clips' / name
                        if candidate.is_file() and digest(candidate) == entry.get('sha256'):
                            shutil.copyfile(candidate, target)
                            reused = True
                            break
            if not reused:
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(row['start']),
                                '-i', str(source), '-t', str(row['end'] - row['start']),
                                '-map', '0:a:0', '-c:a', 'copy', '-map_metadata', '-1', str(target)], check=True)
            duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(target)]))
            if not math.isfinite(duration) or abs(duration - (row['end'] - row['start'])) > .2:
                raise ValueError('Clip duration does not match reviewed range')
            subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(target), '-f', 'null', '-'], check=True)
            index['stories'].setdefault(identity, []).append({
                'file': 'releases/' + manifest['release_id'] + '/clips/' + name, 'sha256': digest(target),
                'bytes': target.stat().st_size, 'duration': duration,
                'audio_sha256': asset['sha256'], 'start': row['start'], 'end': row['end']})
    write_json(output / 'assets/clips/index.json', index)
    return index
