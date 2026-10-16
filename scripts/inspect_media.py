"""Read-only source media diagnostics; no content, audio, Drive or site changes."""
import argparse
import re
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pulse.publication import read_json, SECTIONS
from pulse.source_media import fetch_public, article_image


def safe_url(url):
    p=urlsplit(url)
    return p._replace(query='',fragment='').geturl()


def inspect(item):
    section,story=item
    url=story.get('image_url')
    if not url:return None
    try:
        body,kind=fetch_public(url)
        if kind.lower().startswith('image/'):
            return None
        kind=re.sub(r'[^a-zA-Z0-9/+.;=-]','',kind)[:100]
        result=f"{section}/{story['id']}; MIME={kind}; header={body[:12].hex()}; image={safe_url(url)}; source={safe_url(story['source_url'])}"
        alternate=article_image(story['source_url'])
        if alternate and alternate != url:
            raw,mime=fetch_public(alternate)
            result+=f'; publisher alternative MIME={mime.split(";")[0]}; image={safe_url(alternate)}; header={raw[:12].hex()}'
        return result
    except Exception as error:
        return f"{section}/{story['id']}; image={safe_url(url)}; retrieval={type(error).__name__}"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',type=Path,required=True)
    args=parser.parse_args()
    items=[(section,story) for section in SECTIONS for story in read_json(args.release/(section+'.json'))['stories']]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for message in pool.map(inspect,items):
            if message:print('::notice title=PULSE source image diagnostic::'+message,flush=True)
    print(f'Read-only media scan finished: {len(items)} stories; nothing changed.')


if __name__=='__main__':main()
