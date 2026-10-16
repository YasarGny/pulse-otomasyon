"""Bound temporary Actions storage after successful, verified publication."""
import argparse
import datetime as dt
import os
import re
import requests


def obsolete(artifacts, date, run_id):
    oldest = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
    states = set()
    browsers = 0
    remove = []
    for artifact in sorted(artifacts, key=lambda a: a['created_at'], reverse=True):
        if artifact.get('expired'):
            continue
        name = artifact['name']
        if name == 'pulse-browser-results':
            browsers += 1
            discard = browsers > 2
        elif re.fullmatch(r'pulse-site-\d+', name):
            discard = name != 'pulse-site-' + str(run_id)
        elif match := re.fullmatch(r'pulse-state-(\d{4}-\d{2}-\d{2})-\d+-\d+', name):
            day = match[1]
            if day > date:
                continue
            discard = day < oldest or day in states
            states.add(day)
        else:
            continue
        if discard:
            remove.append(artifact['id'])
    return remove


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--run-id', required=True, type=int)
    args = parser.parse_args()
    session = requests.Session()
    session.headers.update({'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version':'2022-11-28'})
    base = 'https://api.github.com/repos/' + args.repo + '/actions/artifacts'
    artifacts = []
    for page in range(1, 11):
        response = session.get(base, params={'per_page':100,'page':page}, timeout=30)
        response.raise_for_status()
        batch = response.json()['artifacts']
        artifacts.extend(batch)
        if len(batch) < 100:
            break
    selected = obsolete(artifacts, args.date, args.run_id)
    for id in selected:
        response = session.delete(base + '/' + str(id), timeout=30)
        response.raise_for_status()
    print(f'Temporary Actions artifacts retired: {len(selected)}; latest checkpoints and current deployment retained.')


if __name__ == '__main__':
    main()
