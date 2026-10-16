"""Source-grounded static article pages; no client routing or invented filler."""
import html
import re
from pathlib import Path

from pulse.publication import SECTIONS, read_json


def display_date(value):
    from datetime import date
    return date.fromisoformat(value).strftime('%d.%m.%Y')


def article_path(section, story):
    # No source/model supplied paths can escape the build root.
    from urllib.parse import quote
    return f"{section}/haber/{quote(story['id'], safe='')}/index.html"


def article_body(data, story, *, back='../../', image=None):
    e = html.escape
    date = display_date(data['publish_date'])
    image = story.get('image_url') if image is None else image
    figure = ''
    if image:
        figure = f'<figure><img class="story-image" src="{e(image, quote=True)}" alt="{e(story["title"], quote=True)}" decoding="async"><figcaption>Görsel: {e(story["source_name"])}</figcaption></figure>'
    return f'''<a class="back" href="{back}">← Günün gündemi</a>
    <div class="detail-meta">{date} · Sayı {data['issue']:03d} · {e(story['category'])}</div>
    <h1>{e(story['title'])}</h1><article class="story">{figure}
    <p>{e(story['summary'])}</p><div class="why"><strong>NEDEN ÖNEMLİ?</strong><p>{e(story['why'])}</p></div>
    <a class="source-link" href="{e(story['source_url'], quote=True)}" target="_blank" rel="noopener noreferrer">{e(story['source_name'])} · Kaynağı oku →</a></article>'''


def build_details(output, release):
    output, release = Path(output), Path(release)
    for section in SECTIONS:
        data = read_json(release / f'{section}.json')
        template = (output / section / 'index.html').read_text()
        for story in data['stories']:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', story['id']):
                raise ValueError('Unsafe article identity')
            title = html.escape(story['title'])
            page = re.sub(r'<main id="main">.*?</main>', '<main id="main" class="detail-main">' + article_body(data, story) + '</main>', template, flags=re.S)
            page = re.sub(r'<title>.*?</title>', f'<title>{title} · PULSE</title>', page)
            page = re.sub(r'<script src="[^\"]*site.js[^\"]*" defer></script>', '', page)
            page = page.replace('../assets/', '../../../assets/')
            page = page.replace('href="../"', 'href="../../../"').replace('href="../teknoloji/"', 'href="../../../teknoloji/"').replace('href="../oyun/"', 'href="../../../oyun/"')
            url = 'https://yasargny.github.io/' + article_path(section, story).removesuffix('index.html')
            page = re.sub(r'(<link rel="canonical" href=")[^"]+', lambda m: m[1] + url, page)
            page = re.sub(r'(<meta property="og:url" content=")[^"]+', lambda m: m[1] + url, page)
            page = re.sub(r'(<meta\s+(?:name="description"|property="og:description")\s+content=")[^"]+', lambda m: m[1] + html.escape(story.get('brief') or story['summary'], quote=True), page)
            page = re.sub(r'(<meta\s+property="og:title"\s+content=")[^"]+', lambda m: m[1] + title, page)
            path = output / article_path(section, story)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page)
