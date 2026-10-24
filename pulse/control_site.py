"""Apply owner controls without changing news/audio or calling an AI service."""
import argparse
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


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


def paused_page(prefix):
    return '''<!doctype html><html lang="tr" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><meta name="theme-color" content="#151618"><title>Yayınlara ara verdik · PULSE</title><link rel="stylesheet" href="''' + prefix + '''assets/style.css"><script src="''' + prefix + '''assets/controls.js?v=1" defer></script><style>body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#151618;color:#f2f1ed;font-family:system-ui,sans-serif}main{width:min(440px,calc(100vw - 48px));padding:48px 0}.brand{font-size:40px;letter-spacing:-2px}h1{font-size:clamp(30px,7vw,42px);line-height:1.15;margin:64px 0 20px}p{color:#babbc1;font-size:17px;line-height:1.7}.brand span{color:#ff3d85}</style></head><body data-pulse-paused="true"><main><div class="brand">PULSE<span>.</span></div><h1>Yayınlara kısa bir ara verdik.</h1><p>Yeniden buluşmak üzere.</p></main></body></html>'''


def apply(root, desired, source='site'):
    root = Path(root)
    path = root / 'data/controls.json'
    previous = read_json(path) if path.exists() else None
    old = previous or {'enabled': True, 'podcasts': {'teknoloji': True, 'oyun': True}}
    state = dict(desired)
    if not state['enabled']:
        commit = old.get('resume_commit') if old['enabled'] is False else git(root, 'rev-parse', 'HEAD').decode().strip()
        if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
            raise ValueError('Verified resume commit is required')
        state['resume_commit'] = commit
    if previous == state:
        return False
    if old['enabled'] is False and state['enabled']:
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
    if not state['enabled']:
        for page in root.rglob('*.html'):
            if '.git' in page.relative_to(root).parts:
                continue
            if page.is_symlink() or not page.resolve().is_relative_to(root.resolve()):
                raise ValueError('Unsafe maintenance page')
            prefix = '../' * len(page.parent.relative_to(root).parts) or './'
            page.write_text(paused_page(prefix))
    (root / 'assets').mkdir(exist_ok=True)
    shutil.copyfile(Path(source) / 'assets/controls.js', root / 'assets/controls.js')
    write_json(path, state)
    return True


def cancel_paused_runs(repo, desired, previous):
    """Cancel active work; requests already sent to a provider cannot be undone."""
    global_pause = not desired['enabled']
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
                if actual == previous and ('data-pulse-paused="true"' in html) == (not previous['enabled']):
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
