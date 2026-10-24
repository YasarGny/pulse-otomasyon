"""Complete current-publication metadata without generating or changing audio."""
import argparse
import os
import shutil
from pathlib import Path

from pulse.chapters import load_chapters
from pulse.clips import validate_ranges
from pulse.publication import SECTIONS, digest, expected_date, now, read_json, verify_manifest


def current(previous, at=None):
    previous = Path(previous)
    manifest = read_json(previous / 'data/publication.json')
    if manifest.get('status') != 'ready' or manifest.get('publish_date') != expected_date(at or now()):
        return None
    release = (previous / 'releases' / manifest['release_id']).resolve()
    if not release.is_relative_to((previous / 'releases').resolve()):
        raise ValueError('Unsafe release identity')
    return manifest, release


def missing(previous, manifest, release):
    previous = Path(previous)
    try:
        registry = read_json(previous / 'assets/chapters/index.json')
    except (OSError, ValueError):
        registry = {}
    try:
        clips = read_json(previous / 'assets/clips/index.json')
    except (OSError, ValueError):
        clips = {}
    if not isinstance(clips, dict) or not isinstance(clips.get('stories', {}), dict):
        clips = {}
    result = []
    for section in SECTIONS:
        entry = manifest['editions'][section]
        if entry['file'] != section + '.json' or digest(release / entry['file']) != entry['sha256']:
            raise ValueError('Edition identity/hash mismatch')
        edition = read_json(release / entry['file'])
        from pulse.controls import podcast_enabled
        asset = edition.get('podcast')
        if not asset or not podcast_enabled(section):
            continue
        data = load_chapters(previous / 'assets/chapters', asset)
        try:
            validate_ranges(data or {}, asset, edition['stories'])
            ranges_valid = clips.get('release_id') == manifest['release_id']
            for row in data['story_ranges']:
                entries = clips.get('stories', {}).get(section + ':' + row['story_id'], [])
                name = f"releases/{manifest['release_id']}/clips/{asset['sha256']}-{row['start']:.3f}-{row['end']:.3f}.mp3"
                if not isinstance(entries, list):
                    entries = []
                entry = next((c for c in entries if isinstance(c, dict) and c.get('file') == name and c.get('start') == row['start'] and c.get('end') == row['end'] and c.get('audio_sha256') == asset['sha256']), None)
                path = previous / name
                if not entry or not path.is_file() or path.is_symlink() or digest(path) != entry.get('sha256'):
                    ranges_valid = False
        except (ValueError, TypeError):
            ranges_valid = False
        if not data or not ranges_valid or not isinstance(registry, dict) or registry.get(asset['sha256']) != data:
            result.append(section)
    return result


def copy_state(source, target):
    """Only private metadata is checkpointed; never copy sources or MP3s."""
    source, target = Path(source), Path(target)
    for name in ('chapters', 'chapter-transcripts', 'chapter-requests', 'chapter-feedback'):
        folder = source / name
        paths = list(folder.glob('*.json')) if folder.exists() else []
        names = {path.name for path in paths}
        destination_folder = target / name
        if destination_folder.exists():
            for old in destination_folder.glob('*.json'):
                if old.name not in names:
                    old.unlink()
        if paths:
            for path in paths:
                if path.is_symlink():
                    raise ValueError('Symlink in chapter state')
                destination = target / name / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
    usage = source / 'api-usage.jsonl'
    if usage.is_file():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(usage, target / usage.name)


def stage(previous, work, state):
    selected = current(previous)
    if not selected:
        raise ValueError('No current ready publication to complete')
    manifest, release = selected
    verify_manifest(release, manifest)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    files = ['release.json']
    for section in SECTIONS:
        from pulse.controls import audio_kinds
        files.append(section + '.json')
        files.extend(section + '/' + kind + '.mp3' for kind in audio_kinds(read_json(release / (section + '.json'))))
    for name in files:
        destination = work / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release / name, destination)
    copy_state(state, work)
    for section in SECTIONS:
        from pulse.controls import podcast_enabled
        asset = read_json(work / (section + '.json')).get('podcast')
        if not asset or not podcast_enabled(section):
            continue
        try:
            transcript = read_json(work / 'chapter-transcripts' / (section + '.json'))
        except (OSError, ValueError):
            transcript = {}
        segments = transcript.get('segments') if isinstance(transcript, dict) and transcript.get('audio_sha256') == asset['sha256'] else None
        data = load_chapters(work / 'chapters', asset)
        print(f'::notice title=PULSE chapter checkpoint::{section}: {len(segments) if isinstance(segments, list) else 0} cached transcript segments; {len(data["chapters"]) if data else 0} verified markers', flush=True)
    return manifest


def bootstrap_daily(previous, checkpoint, target):
    """Reuse early-morning private work only for this exact sealed publication."""
    selected = current(previous)
    if not selected:
        return False
    manifest, _ = selected
    for path in Path(checkpoint).rglob('release.json'):
        if read_json(path) == manifest:
            copy_state(path.parent, target)
            return True
    return False


def rebuild(previous, work, output='dist'):
    from pulse.build import build
    selected = current(previous)
    if not selected:
        raise ValueError('Publication expired before chapter completion')
    manifest, release = selected
    work = Path(work)
    if read_json(work / 'release.json') != manifest:
        raise ValueError('Publication changed during chapter completion')
    changed = False
    complete = True
    missing_before = set(missing(previous, manifest, release))
    for section in SECTIONS:
        from pulse.controls import podcast_enabled
        asset = read_json(work / (section + '.json')).get('podcast')
        if not asset or not podcast_enabled(section):
            continue
        prepared = load_chapters(work / 'chapters', asset)
        published = load_chapters(Path(previous) / 'assets/chapters', asset)
        if (prepared and prepared != published) or ((prepared or published) and section in missing_before):
            changed = True
        candidate = prepared or published
        try:
            validate_ranges(candidate or {}, asset, read_json(work / (section + '.json'))['stories'])
        except (ValueError, TypeError):
            complete = False
    if changed:
        result = build('site', output, release=work, previous=previous)
        if result != manifest:
            raise ValueError('Chapter completion must preserve publication identity')
    return changed, complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inspect', 'stage', 'save', 'build'))
    parser.add_argument('--previous', default='.published')
    parser.add_argument('--work')
    parser.add_argument('--state')
    args = parser.parse_args()
    if args.action == 'inspect':
        selected = current(args.previous)
        needed = missing(args.previous, *selected) if selected else []
        values = {'needed': str(bool(needed)).lower(), 'date': selected[0]['publish_date'] if selected else ''}
        print('Missing chapter metadata:', ', '.join(needed) or 'none')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    elif args.action == 'stage':
        stage(args.previous, args.work, args.state)
    elif args.action == 'save':
        copy_state(args.work, args.state)
    else:
        changed, complete = rebuild(args.previous, args.work)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write(f'changed={str(changed).lower()}\ncomplete={str(complete).lower()}\n')
        print(f'::notice title=PULSE chapter completion::changed={changed}; both programs complete={complete}')


if __name__ == '__main__':
    main()
