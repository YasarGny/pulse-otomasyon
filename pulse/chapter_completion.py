"""Complete current-publication metadata without generating or changing audio."""
import argparse
import os
import shutil
from pathlib import Path

from pulse.chapters import load_chapters
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
    result = []
    for section in SECTIONS:
        entry = manifest['editions'][section]
        if entry['file'] != section + '.json' or digest(release / entry['file']) != entry['sha256']:
            raise ValueError('Edition identity/hash mismatch')
        asset = read_json(release / entry['file'])['podcast']
        data = load_chapters(previous / 'assets/chapters', asset)
        if not data or not isinstance(registry, dict) or registry.get(asset['sha256']) != data:
            result.append(section)
    return result


def copy_state(source, target):
    """Only private metadata is checkpointed; never copy sources or MP3s."""
    source, target = Path(source), Path(target)
    for name in ('chapters', 'chapter-transcripts', 'chapter-requests'):
        folder = source / name
        if folder.exists():
            for path in folder.glob('*.json'):
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
        files.extend([section + '.json', section + '/summary.mp3', section + '/podcast.mp3'])
    for name in files:
        destination = work / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release / name, destination)
    copy_state(state, work)
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
        asset = read_json(work / (section + '.json'))['podcast']
        prepared = load_chapters(work / 'chapters', asset)
        published = load_chapters(Path(previous) / 'assets/chapters', asset)
        if (prepared and prepared != published) or ((prepared or published) and section in missing_before):
            changed = True
        if not prepared and not published:
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
