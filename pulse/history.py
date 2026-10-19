"""Published JSON is the durable record even when Actions checkpoints expire."""

import shutil
from pathlib import Path

from pulse.publication import SECTIONS, digest, read_json, verify_manifest
from pulse.source_history import SourceHistory, fingerprint
from pulse.event_history import EventHistory


def histories(previous):
    """Merge verified migration seeds with durable history, never erase either."""
    source_path = Path(previous) / 'data/source-history.json'
    event_path = Path(previous) / 'data/event-history.json'
    sources = SourceHistory(read_json(source_path) if source_path.exists() else None)
    events = EventHistory(read_json(event_path) if event_path.exists() else None)
    seed_path = Path(__file__).with_name('history-seed.json')
    if seed_path.exists():
        seed = read_json(seed_path)
        sources.exact.update(SourceHistory(seed['sources']).exact)
        for row in EventHistory(seed['events']).rows.values():
            events.add(row['section'], row['date'], row)
    return sources, events


def exclude_published(research, previous, date):
    if previous is None:
        return research
    ledger, events = histories(previous)
    same_day = set()
    for manifest_path in (Path(previous) / "releases").glob("*/release.json"):
        manifest = read_json(manifest_path)
        if manifest.get("status") != "ready" or manifest["publish_date"] > date:
            continue
        for section in SECTIONS:
            entry = manifest["editions"][section]
            if entry["file"] != section + ".json":
                raise ValueError("Invalid archive entry")
            path = manifest_path.parent / entry["file"]
            if digest(path) != entry["sha256"]:
                raise ValueError("Historical JSON hash mismatch")
            data = read_json(path)
            if (
                data["section"] != section
                or data["publish_date"] != manifest["publish_date"]
            ):
                raise ValueError("Historical edition identity mismatch")
            for story in data["stories"]:
                if manifest['publish_date'] == date:
                    # Revisions may retain today's approved news; only previous
                    # days are forbidden. Ordinary reruns restore the release.
                    same_day.add(fingerprint(story['source_url']))
                else:
                    ledger.add(story["source_url"])
                    events.add(section, manifest["publish_date"], story)
    clean = {**research, "sections": {}, "previous_events": {
        section: [r for r in events.record(date)['events'] if r['section'] == section and r['date'] < date]
        for section in SECTIONS}}
    clean['legacy_history_uncertain'] = sum(ledger.uncertain(s['source_url'])
        for section in SECTIONS for s in research['sections'][section])
    for section in SECTIONS:
        clean["sections"][section] = [
            s
            for s in research["sections"][section]
            if fingerprint(s["source_url"]) in same_day or not ledger.contains(s["source_url"])
        ]
        if len(clean["sections"][section]) < 3:
            raise ValueError(
                "Insufficient fresh, previously unpublished stories: " + section
            )
    return clean


def restore_published(destination, previous, date, game_start):
    if previous is None:
        return False
    previous, destination = Path(previous), Path(destination)
    path = previous / "data/publication.json"
    if not path.exists():
        return False
    manifest = read_json(path)
    if manifest.get("status") != "ready" or manifest.get("publish_date") != date:
        return False
    if manifest["game_start"] != game_start:
        raise ValueError("Published numbering epoch mismatch")
    root = previous / "releases" / manifest["release_id"]
    verify_manifest(root, manifest)
    files = [root / "release.json"]
    for section in SECTIONS:
        files.append(root / (section + ".json"))
        files.extend(
            root / section / (kind + ".mp3") for kind in ("summary", "podcast")
        )
    # Preflight the entire restore before writing any file; preserve conflicting work.
    for source in files:
        target = destination / source.relative_to(root)
        if target.exists() and digest(target) != digest(source):
            raise ValueError(
                "A published issue already exists; preserve/reconcile conflicting local draft first"
            )
    for source in files:
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return True
