"""One verified latest archive per date; promotion precedes reversible retirement."""
import datetime as dt
from pathlib import Path
from pulse.publication import read_json, verify_manifest


def order(manifest):
    stamp = dt.datetime.fromisoformat(manifest['validated_at'])
    if not stamp.tzinfo:
        raise ValueError('Release ordering requires a timezone')
    return stamp


def select_daily(source, published):
    grouped = {}
    for tree in (Path(published), Path(source)):
        for path in (tree / 'releases').glob('*/release.json'):
            manifest = read_json(path)
            verify_manifest(path.parent, manifest)
            grouped.setdefault(manifest['publish_date'], {})[manifest['release_id']] = (path.parent, manifest)
    chosen = {}
    for date, versions in grouped.items():
        chosen[date] = max(versions.values(), key=lambda pair: (order(pair[1]), pair[1]['release_id']))
    # The active manifest is authoritative over directory iteration/fingerprint sorting.
    active_by_date = {}
    for tree in (Path(published), Path(source)):
        path = tree / 'data/publication.json'
        if path.exists():
            active = read_json(path)
            if active.get('status') == 'ready':
                active_by_date[active['publish_date']] = active
    for date, active in active_by_date.items():
        if date in grouped:
            current = chosen[date][1]
            if active['release_id'] != current['release_id'] and order(active) < order(current):
                raise ValueError('Active release would regress a newer known revision')
            chosen[date] = grouped[date][active['release_id']]
    return chosen, grouped


def canonical_name(date):
    return 'PULSE-' + dt.date.fromisoformat(date).strftime('%d.%m.%Y') + '.zip'


def protect_order(files, manifest):
    for file in files:
        if file.get('name') != canonical_name(manifest['publish_date']):
            continue  # Incomplete pending uploads cannot prevent recovery of a valid daily archive.
        properties = file.get('appProperties', {})
        if properties.get('release_id') == manifest['release_id']:
            continue
        stamp = properties.get('release_order')
        if stamp and dt.datetime.fromisoformat(stamp) >= order(manifest):
            raise ValueError('Refusing an older or ambiguous daily archive over a newer Drive revision')


def retire_older(drive, parent, manifest, receipt):
    if receipt.get('verified') is not True or receipt.get('release_id') != manifest['release_id']:
        raise ValueError('A fully verified current archive is required before retirement')
    name = canonical_name(manifest['publish_date'])
    files = drive.daily_files(parent, manifest['publish_date'])
    protect_order(files, manifest)
    keep = receipt['file_id']
    if not any(f['id'] == keep for f in files):
        raise ValueError('Verified archive disappeared before promotion')
    drive.request('PATCH', drive.api + '/' + keep, json={'name': name, 'appProperties': {'release_order': manifest['validated_at'], 'release_id': manifest['release_id'], **({'sha256': receipt['sha256']} if receipt.get('sha256') else {})}})
    # Re-list after promotion; races fail closed. Workflow concurrency serializes all writers.
    files = drive.daily_files(parent, manifest['publish_date'])
    protect_order(files, manifest)
    for file in files:
        if file['id'] != keep and file.get('appProperties', {}).get('release_id'):
            drive.request('PATCH', drive.api + '/' + file['id'], json={'trashed': True})
    return receipt
