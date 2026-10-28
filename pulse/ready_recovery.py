"""Recover only an existing sealed daily recording; never produce content."""
from pathlib import Path

from pulse.publication import read_json
from scripts.state import restore


def restore_ready(repo, date, target, *, automatic=False):
    restored = restore(repo, date, target)
    source = Path(target) / date
    manifest_path = source / 'release.json'
    if not restored or not manifest_path.is_file():
        if automatic:
            return None
        raise ValueError('No trusted sealed current-day checkpoint available')
    manifest = read_json(manifest_path)
    if manifest.get('publish_date') != date:
        raise ValueError('Checkpoint publication date mismatch')
    if manifest.get('status') != 'ready':
        if automatic:
            return None
        raise ValueError('Audio checkpoint is incomplete')
    return source
