"""Expose only fully verified recordings within the existing two-date retention."""
from pathlib import Path
from pulse.publication import SECTIONS, read_json, verify_manifest


def catalog(current, previous=None):
    current = Path(current)
    active = read_json(current / 'release.json')
    selected = {}
    paths = list((Path(previous) / 'releases').glob('*/release.json')) if previous else []
    paths.append(current / 'release.json')
    for path in paths:
        try:
            manifest = read_json(path)
            if manifest.get('status') != 'ready' or manifest['publish_date'] > active['publish_date']:
                continue
            verify_manifest(path.parent, manifest)
            date = manifest['publish_date']
            if date not in selected or path.parent == current or manifest['validated_at'] > selected[date][1]['validated_at']:
                selected[date] = (path.parent, manifest)
        except (ValueError, OSError, KeyError, TypeError):
            continue  # A broken historical recording is never advertised.
    rows = []
    for date in sorted(selected, reverse=True)[:2]:
        folder, manifest = selected[date]
        for section in SECTIONS:
            edition = read_json(folder / (section + '.json'))
            rows.append({'section': section, 'publish_date': date,
                         'release_id': manifest['release_id'], 'podcast': edition['podcast']})
    return {'schema_version': 1, 'episodes': rows}
