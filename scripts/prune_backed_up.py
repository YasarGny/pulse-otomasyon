"""Remove only verified Drive-backed releases other than the active daily release.
Does not rewrite Git history; that is a separate, explicitly approved migration.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulse.publication import SECTIONS, read_json, write_json, verify_manifest
from pulse.history import histories


def prune(target, receipts):
    target = Path(target)
    record = read_json(receipts)
    entries = record['releases']
    superseded = record.get('superseded', {})
    current = read_json(target / 'data/publication.json')
    if current.get('status') not in ('ready', 'preparing') or (current.get('status') == 'ready' and not current.get('release_id')):
        raise ValueError('Invalid publication state; nothing removed')
    folders = sorted((target / 'releases').glob('*/release.json'))
    manifests = [(p.parent, read_json(p)) for p in folders]
    # During preparation yesterday is no longer a public issue. Its verified
    # portable Drive snapshot is required before removing its files.
    active = current.get('release_id') if current.get('status') == 'ready' else None
    if active:
        matches = [root for root, m in manifests if m['release_id'] == active]
        if len(matches) != 1:
            raise ValueError('Active release missing or ambiguous; nothing removed')
        verify_manifest(matches[0], current)
    candidates = [(root, m) for root, m in manifests if m['release_id'] != active]
    # Preflight everything: missing/failed receipt means delete nothing.
    for root, manifest in candidates:
        verify_manifest(root, manifest)
        archived_id = superseded.get(manifest['release_id'], manifest['release_id'])
        receipt = entries.get(archived_id, {})
        if receipt.get('verified') is not True or receipt.get('release_id') != archived_id or receipt.get('publish_date') != manifest['publish_date'] or not receipt.get('file_id') or not isinstance(receipt.get('sha256'), str) or len(receipt['sha256']) != 64:
            raise ValueError('No verified Drive readback receipt; nothing removed')
    ledger_path = target / 'data/source-history.json'
    ledger, events = histories(target)
    event_path = target / 'data/event-history.json'
    for root, manifest in manifests:
        for section in SECTIONS:
            stories = read_json(root / f'{section}.json')['stories']
            for story in stories:
                ledger.add(story['source_url'])
                events.add(section, manifest['publish_date'], story)
    retained_ids = {s: set() for s in SECTIONS}
    candidate_roots = {root for root, _ in candidates}
    for root, manifest in manifests:
        if root not in candidate_roots:
            for section in SECTIONS:
                retained_ids[section].update(s['id'] for s in read_json(root / f'{section}.json')['stories'])
    details = set()
    for root, manifest in candidates:
        for section in SECTIONS:
            for story in read_json(root / f'{section}.json')['stories']:
                identity = story['id']
                if re.fullmatch(r'[A-Za-z0-9_-]{1,100}', identity) and identity not in retained_ids[section]:
                    detail = target / section / 'haber' / identity
                    if detail.is_symlink() or any(p.is_symlink() for p in detail.parents if p != target.parent):
                        raise ValueError('Unexpected detail symlink')
                    if detail.exists():
                        details.add(detail)
    # Validate every receipt, route and ledger before removing the first file.
    # Persist even the active edition: recovery works after its files are pruned.
    history_record = ledger.record()
    event_record = events.record(current['publish_date'])
    write_json(ledger_path, history_record)
    write_json(event_path, event_record)
    for detail in details:
        shutil.rmtree(detail)
    for root, _ in candidates:
        shutil.rmtree(root)
    return len(candidates)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('target')
    p.add_argument('receipts')
    a = p.parse_args()
    print('Drive-verified old release folders removed:', prune(a.target, a.receipts))
