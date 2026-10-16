"""Published JSON is the durable record even when Actions checkpoints expire."""

import shutil
from pathlib import Path

from pulse.publication import SECTIONS, digest, read_json, verify_manifest


def exclude_published(research, previous, date):
    if previous is None:
        return research
    seen = {section: set() for section in SECTIONS}
    for manifest_path in (Path(previous) / "releases").glob("*/release.json"):
        manifest = read_json(manifest_path)
        if manifest.get("status") != "ready" or manifest["publish_date"] >= date:
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
            seen[section].update(s["source_url"] for s in data["stories"])
    clean = {**research, "sections": {}}
    for section in SECTIONS:
        clean["sections"][section] = [
            s
            for s in research["sections"][section]
            if s["source_url"] not in seen[section]
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
