"""Source-grounded, independently addressable static article pages."""

import html
import re
from urllib.parse import quote


def display_date(value):
    from datetime import date

    return date.fromisoformat(value).strftime("%d.%m.%Y")


def article_path(section, story):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", story["id"]):
        raise ValueError("Unsafe article identity")
    return f"{section}/haber/{quote(story['id'], safe='')}/index.html"


def article_body(data, story, *, back="../../index.html", image=None):
    from pulse.pages import picture

    e = html.escape
    display_story = dict(story)
    if image is not None:
        display_story["image_url"] = image
    paragraphs = "".join(
        "<p>" + e(p) + "</p>" for p in story.get("body", [story["summary"]])
    )
    source = f'<a class="source-link" href="{e(story["source_url"], quote=True)}" target="_blank" rel="noopener noreferrer">{e(story["source_name"])} ↗</a>'
    return f"""<div class="article-layout"><article class="article-reader"><a class="back" href="{back}">← Haberlere dön</a><header class="article-heading"><p class="eyebrow">{e(story['category'])}</p><h1>{e(story['title'])}</h1><div class="article-meta"><time class="detail-meta" datetime="{data['publish_date']}">{display_date(data['publish_date'])}</time>{source}</div></header>{picture(display_story, eager=True, detail=True)}<div class="article-text">{paragraphs}</div><aside class="why"><h2>Neden önemli?</h2><p>{e(story['why'])}</p></aside></article></div>"""
