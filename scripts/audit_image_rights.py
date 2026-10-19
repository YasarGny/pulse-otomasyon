"""Read-only evidence collection. Never treats HTTP 200 or credits as a licence."""
import concurrent.futures
import html
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = 'https://yasargny.github.io/'
POLICIES = [
    'https://news.mit.edu/terms-of-use',
    'https://www.nasa.gov/nasa-brand-center/images-and-media/',
    'https://www.sciencedaily.com/terms.htm',
    'https://www.sciencedaily.com/copyright.htm',
    'https://www.bbc.co.uk/usingthebbc/terms/',
    'https://www.bleepingcomputer.com/terms-of-use/',
    'https://futureplc.com/terms-conditions/',
]


def evidence(url):
    result = {'url': url, 'decision': 'unverified'}
    try:
        response = requests.get(url, timeout=25)
        result['http'] = response.status_code
        if response.status_code != 200:
            return result
        markup = response.content.decode('utf-8', errors='replace')
        visible = re.sub(r'<(script|style|head)\b[^>]*>.*?</\1\s*>', ' ', markup, flags=re.I | re.S)
        text = html.unescape(re.sub('<[^>]+>', ' ', visible))
        text = re.sub(r'\s+', ' ', text)
        result['excerpts'] = [text[max(0, m.start()-100):m.end()+350] for m in re.finditer(
            r'(?i)image credit|photo credit|image:|credit:|credits:|courtesy|licensed under|CC BY|creative commons|©|getty images|reuters|permission|re-use|republish|copyright', text)][:20]
        result['policy_links'] = [urljoin(url, link) for link in re.findall(
            r'''href=["']([^"']*(?:terms|copyright|licens|permission)[^"']*)["']''', markup, re.I)[-15:]]
    except requests.RequestException as error:
        result['error'] = type(error).__name__
    return result


def main():
    manifest_response = requests.get(ROOT + 'data/publication.json', timeout=25)
    manifest_response.raise_for_status()
    manifest = manifest_response.json()
    if manifest.get('status') != 'ready':
        raise ValueError('No ready publication to audit')
    rows = []
    for section, entry in manifest['editions'].items():
        response = requests.get(ROOT + 'releases/' + manifest['release_id'] + '/' + entry['file'], timeout=25)
        response.raise_for_status()
        for number, story in enumerate(response.json()['stories'], 1):
            rows.append({'section': section, 'number': number, 'title': story['title'],
                         'image_url': story['image_url'], 'source_url': story['source_url']})
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        articles = list(pool.map(evidence, [r['source_url'] for r in rows]))
        policies = list(pool.map(evidence, POLICIES))
    for row, article in zip(rows, articles):
        row['evidence'] = article
    result = {'publish_date': manifest['publish_date'], 'release_id': manifest['release_id'],
              'notice': 'Evidence collection only. No image is automatically approved.',
              'images': rows, 'policies': policies}
    Path('image-rights-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    for section in manifest['editions']:
        compact = [{'n': r['number'], 'http': r['evidence'].get('http', r['evidence'].get('error')),
                    'evidence': [e[:220] for e in r['evidence'].get('excerpts', [])[:3]],
                    'links': r['evidence'].get('policy_links', [])[:2]} for r in rows if r['section'] == section]
        for start in range(0, len(compact), 4):
            annotation(section + ' ' + str(start + 1), json.dumps(compact[start:start+4], ensure_ascii=False))
    for start in range(0, len(policies), 3):
        compact = [{**p, 'excerpts': [e[:300] for e in p.get('excerpts', [])[:3]]} for p in policies[start:start+3]]
        annotation('publisher policies ' + str(start + 1), json.dumps(compact, ensure_ascii=False))


def annotation(title, text):
    safe = text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print(f'::notice title={title}::{safe}', flush=True)


if __name__ == '__main__':
    main()
