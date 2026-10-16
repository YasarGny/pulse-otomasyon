"""Copy the reviewed public build to a checked-out Pages repository. Does not push."""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulse.build import PUBLIC_ROOTS, assert_public_tree
from pulse.publication import not_before, now, read_json, verify_manifest


def sync(source, target, *, at=None):
    source, target = Path(source), Path(target)
    assert_public_tree(source)
    manifest = read_json(source / "data/publication.json")
    if manifest.get("status") == "ready":
        at = at or now()
        if at.astimezone(
            not_before(manifest["publish_date"]).tzinfo
        ).date().isoformat() != manifest["publish_date"] or at < not_before(
            manifest["publish_date"]
        ):
            raise ValueError("Refusing a stale or early deployment")
        verify_manifest(source / "releases" / manifest["release_id"], manifest)
        existing = target / "releases" / manifest["release_id"]
        if existing.exists():
            verify_manifest(
                existing, manifest
            )  # An immutable release cannot be silently replaced.
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if relative.parts[0] not in (*PUBLIC_ROOTS, "data", "releases"):
            raise ValueError("Unexpected public path")
        dest = target / relative
        if dest.is_symlink() or any(
            p.is_symlink() for p in dest.parents if p != target.parent
        ):
            raise ValueError("Destination symlink")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    # Retire only the two known, unsourced pre-migration pilot files. Real daily
    # editions live under immutable releases; unrelated repository files stay intact.
    for section in ("teknoloji", "oyun"):
        obsolete = target / "data" / (section + ".json")
        if not (source / "data" / obsolete.name).exists():
            if obsolete.is_file() or obsolete.is_symlink():
                obsolete.unlink()
    # Historical releases and the target's existing Pages workflow are retained.
    # No source code or generated prompts are copied to the publication repository.


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    p.add_argument("target")
    a = p.parse_args()
    sync(a.source, a.target)
