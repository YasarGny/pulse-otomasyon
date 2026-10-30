"""Copy the reviewed public build to a checked-out Pages repository. Does not push."""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulse.build import PUBLIC_ROOTS, assert_public_tree
from pulse.publication import expected_date, not_before, now, read_json, verify_manifest


def sync(source, target, *, at=None):
    source, target = Path(source), Path(target)
    controls = target / 'data/controls.json'
    if controls.is_file() and (read_json(controls).get('enabled') is False or read_json(controls).get('automation_enabled') is False):
        raise ValueError('Owner pause blocks normal site deployment; use Apply owner controls to resume')
    assert_public_tree(source)
    manifest = read_json(source / "data/publication.json")
    if manifest.get("status") == "ready":
        at = at or now()
        if expected_date(at) != manifest["publish_date"] or at < not_before(
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
    # These illustrations were superseded by the optimized photographic covers.
    # Remove only known obsolete paths, after the replacement assets were copied.
    for name in ("assets/covers/teknoloji.svg", "assets/covers/oyun.svg", "assets/og.svg"):
        obsolete = target / name
        if not (source / name).exists() and (obsolete.is_file() or obsolete.is_symlink()):
            obsolete.unlink()
    # No historical browsing catalog is published; recordings live in private ZIPs.
    obsolete = target / 'assets/episodes'
    if obsolete.is_symlink():
        raise ValueError('Unexpected episode catalog symlink')
    if obsolete.exists():
        shutil.rmtree(obsolete)
    # Releases are removed separately, only after verified Drive readback.
    # The target's existing Pages workflow is retained.
    # No source code or generated prompts are copied to the publication repository.


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    p.add_argument("target")
    a = p.parse_args()
    sync(a.source, a.target)
