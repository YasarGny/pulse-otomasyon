"""Remove only verified Drive-backed releases outside two most recent issue dates.
Does not rewrite Git history; that is a separate, explicitly approved migration.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulse.publication import SECTIONS, read_json, write_json, verify_manifest


def prune(target, receipts):
    target = Path(target)
    record = read_json(receipts)
    entries = record['releases']
    superseded = record.get('superseded', {})
    current = read_json(target / 'data/publication.json')
    folders = sorted((target / 'releases').glob('*/release.json'))
    manifests = [(p.parent, read_json(p)) for p in folders]
    keep_dates = set(sorted({m['publish_date'] for _, m in manifests})[-2:])
    candidates = [(root, m) for root, m in manifests if m['publish_date'] not in keep_dates and m['release_id'] != current.get('release_id')]
    # Preflight everything: missing/failed receipt means delete nothing.
    for root, manifest in candidates:
        verify_manifest(root, manifest)
        archived_id = superseded.get(manifest['release_id'], manifest['release_id'])
        receipt = entries.get(archived_id, {})
        if receipt.get('verified') is not True or receipt.get('release_id') != archived_id or receipt.get('publish_date') != manifest['publish_date'] or not receipt.get('file_id') or not isinstance(receipt.get('sha256'), str) or len(receipt['sha256']) != 64:
            raise ValueError('No verified Drive readback receipt; nothing removed')
    ledger_path = target / 'data/source-history.json'
    ledger = read_json(ledger_path) if ledger_path.exists() else {s: [] for s in SECTIONS}
    for root, manifest in candidates:
        for section in SECTIONS:
            stories = read_json(root / f'{section}.json')['stories']
            ledger[section] = sorted(set(ledger[section]) | {hashlib.sha256(s['source_url'].encode()).hexdigest() for s in stories})
    if candidates:
        write_json(ledger_path, ledger)  # Keep deduplication after archive moves to Drive.
    retained_ids = {s: set() for s in SECTIONS}
    candidate_roots = {root for root, _ in candidates}
    for root, manifest in manifests:
        if root not in candidate_roots:
            for section in SECTIONS:
                retained_ids[section].update(s['id'] for s in read_json(root / f'{section}.json')['stories'])
    for root, manifest in candidates:
        for section in SECTIONS:
            for story in read_json(root / f'{section}.json')['stories']:
                identity = story['id']
                import re
                if re.fullmatch(r'[A-Za-z0-9_-]{1,100}', identity) and identity not in retained_ids[section]:
                    detail = target / section / 'haber' / identity
                    if detail.is_symlink():
                        raise ValueError('Unexpected detail symlink')
                    if detail.exists():
                        shutil.rmtree(detail)
        shutil.rmtree(root)
    return len(candidates)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('target')
    p.add_argument('receipts')
    a = p.parse_args()
    print('Drive-verified old release folders removed:', prune(a.target, a.receipts))
