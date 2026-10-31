"""Apply owner controls without changing news/audio or calling an AI service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.request import Request, urlopen

from pulse.controls import settings
from pulse.publication import read_json, write_json
from pulse.site_visibility import apply_visibility


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


CONTROL_ASSETS = {'controls.js': '3', 'publication.js': '7', 'printing.js': '12'}


def apply(root, desired, source='site'):
    root = Path(root)
    path = root / 'data/controls.json'
    previous = read_json(path) if path.exists() else None
    old = previous or {'enabled': True, 'podcasts': {'teknoloji': True, 'oyun': True}}
    state = dict(desired)
    state.setdefault('automation_enabled', True)
    changed = False
    # Migrate a site closed by the former master switch, even if production is off.
    if old['enabled'] is False and old.get('resume_commit'):
        commit = old.get('resume_commit', '')
        if not re.fullmatch('[a-f0-9]{40}', commit):
            raise ValueError('Unsafe resume commit')
        try:
            git(root, 'cat-file', '-e', commit + '^{commit}')
        except subprocess.CalledProcessError:
            git(root, 'fetch', '--depth=1', 'origin', commit)
        for name in git(root, 'ls-tree', '-r', '--name-only', commit).decode().splitlines():
            if name.endswith('.html'):
                destination = root / name
                if destination.is_symlink() or not destination.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Unsafe resume page')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(git(root, 'show', commit + ':' + name))
                changed = True
    manifest_path = root / 'data/publication.json'
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    if state['automation_enabled'] is False and manifest.get('status') == 'ready':
        identity = manifest.get('release_id', '')
        if not isinstance(identity, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-f0-9]{16}', identity):
            raise ValueError('A valid published release is required for retention')
        state['retained_release_id'] = (old.get('retained_release_id')
                                        if old.get('automation_enabled') is False and old.get('retained_release_id')
                                        else identity)
    (root / 'assets').mkdir(exist_ok=True)
    for name in CONTROL_ASSETS:
        src, dst = Path(source) / 'assets' / name, root / 'assets' / name
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            shutil.copyfile(src, dst)
            changed = True
    for page in root.rglob('*.html'):
        if '.git' in page.relative_to(root).parts:
            continue
        if page.is_symlink() or not page.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe control page')
        content = updated = page.read_text()
        for name, version in CONTROL_ASSETS.items():
            updated = re.sub(r'(assets/' + re.escape(name) + r')(?:\?v=\d+)?(?=["\'])', r'\g<1>?v=' + version, updated)
        if updated != content:
            page.write_text(updated)
            changed = True
    changed = apply_visibility(root, state['enabled']) or changed
    if previous != state:
        write_json(path, state)
        changed = True
    return changed


def cancel_paused_runs(repo, desired, previous):
    """Cancel active work; requests already sent to a provider cannot be undone."""
    global_pause = not desired.get('automation_enabled', True)
    newly_disabled = any(not on and (previous or {}).get('podcasts', {}).get(section, True)
                         for section, on in desired['podcasts'].items())
    if not global_pause and not newly_disabled:
        return
    podcast_work = {'daily-publish.yml', 'complete-chapters.yml', 'podcast-chapters.yml', 'publish-ready.yml'}
    for status in ('in_progress', 'queued', 'waiting', 'pending', 'requested'):
        result = subprocess.run(['gh', 'api', '--paginate', f'repos/{repo}/actions/runs?status={status}&per_page=100',
                                 '--jq', '.workflow_runs[].id'], check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if not line.isdigit() or line == os.environ.get('GITHUB_RUN_ID'):
                continue
            run = json.loads(subprocess.run(['gh', 'api', f'repos/{repo}/actions/runs/{line}'],
                                           check=True, capture_output=True, text=True).stdout)
            name = run['path'].rsplit('/', 1)[-1]
            if name in ('quality.yml', 'apply-controls.yml'):
                continue
            if not global_pause and name not in podcast_work:
                continue
            result = subprocess.run(['gh', 'api', '--method', 'POST', f'repos/{repo}/actions/runs/{line}/cancel'], capture_output=True)
            if result.returncode:
                # Completed jobs may race cancellation; fail on a still-active job.
                check = json.loads(subprocess.run(['gh', 'api', f'repos/{repo}/actions/runs/{line}'], check=True, capture_output=True).stdout)
                if check['status'] != 'completed':
                    raise RuntimeError('Could not cancel paused production run ' + line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('--cancel-runs', action='store_true')
    parser.add_argument('--cancel-only', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    desired = settings()
    path = Path(args.root) / 'data/controls.json'
    previous = read_json(path) if path.exists() else None
    if args.verify:
        for attempt in range(30):
            try:
                def fetch(relative):
                    request = Request('https://yasargny.github.io/' + relative + '?controls=' + str(time.time_ns()),
                                      headers={'Cache-Control': 'no-cache'})
                    with urlopen(request, timeout=20) as response:
                        return response.read()
                actual = json.loads(fetch('data/controls.json'))
                html = fetch('').decode()
                assets_ready = all(
                    hashlib.sha256(fetch('assets/' + name)).digest() == hashlib.sha256((Path(args.root) / 'assets' / name).read_bytes()).digest()
                    and f'assets/{name}?v={version}' in html
                    for name, version in CONTROL_ASSETS.items())
                if (actual == previous and ('data-pulse-paused="true"' in html) == (not previous['enabled'])
                        and assets_ready):
                    print('Live owner controls verified; no news or audio changed.')
                    return
            except (OSError, ValueError):
                pass
            time.sleep(10)
        raise RuntimeError('Owner controls did not reach the live site before timeout')
    if args.cancel_only:
        cancel_paused_runs(os.environ['GITHUB_REPOSITORY'], desired, previous)
        return
    print('Owner controls updated:', apply(args.root, desired))
    if args.cancel_runs:
        cancel_paused_runs(os.environ['GITHUB_REPOSITORY'], desired, previous)


if __name__ == '__main__':
    main()
