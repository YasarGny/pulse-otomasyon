"""Static editorial views shared by live Pages and the portable daily archive."""

import html
import json
import re
from pathlib import Path
from urllib.parse import quote

from pulse.details import article_path, display_date
from pulse.publication import SECTIONS, read_json

DESIGN = "editor-desk-v1"
LABELS = {"teknoloji": "Teknoloji", "oyun": "Oyun"}
NAMES = {"teknoloji": "Yeni Sekme", "oyun": "Moradon FM"}


def e(value):
    return html.escape(str(value), quote=True)


def symbol(kind="external"):
    paths = {
        "external": "M6 18 18 6M6 6h12v12",
        "right": "M4 12h16m-6-6 6 6-6 6",
        "back": "M20 12H4m6-6-6 6 6 6",
        "down": "M12 4v16m-6-6 6 6 6-6",
    }
    return f'<svg class="inline-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="{paths[kind]}"/></svg>'


def symbols(markup):
    def replace(match):
        text = match[0]
        for char, kind in [
            ("↗", "external"),
            ("→", "right"),
            ("←", "back"),
            ("↓", "down"),
        ]:
            text = text.replace(char, symbol(kind))
        return text

    return re.sub(r"(?<=>)[^<]+(?=<)", replace, markup)


def arrow():
    return '<span class="read-arrow" aria-hidden="true">' + symbol("right") + "</span>"


def picture(story, *, eager=False, detail=False):
    url = story.get("image_url", "")
    if not url:
        return '<figure class="news-figure image-missing"><div class="image-fallback">Görsel bulunamadı</div></figure>'
    credit = story.get("image_credit", "")
    credit = credit.strip() if isinstance(credit, str) else ""
    # A publisher link is provenance, not an invented photo copyright attribution.
    caption = (
        e(credit)
        if credit
        else f'<a href="{e(story["source_url"])}" target="_blank" rel="noopener noreferrer">Görsel kaynağı ↗</a>'
    )
    return f"""<figure class="news-figure{' detail-figure' if detail else ''}"><div class="image-frame"><img class="story-image" src="{e(url)}" alt="{e(story['title'])}" loading="{'eager' if eager else 'lazy'}" decoding="async" referrerpolicy="no-referrer" width="900" height="600" {'fetchpriority="high"' if eager else ''}><div class="image-fallback" hidden><span>Görsel yüklenemedi</span><button type="button" class="image-retry">Yeniden dene</button></div></div><figcaption>{caption}</figcaption></figure>"""


def story_card(section, story, root, *, lead=False, eager=False, level=3):
    path = root + article_path(section, story)
    heading = "h2" if lead or level == 2 else "h3"
    return f"""<article class="story{' lead-story' if lead else ''}" data-section="{section}" data-category="{e(story['category'])}" data-story="{e(story['id'])}">
{picture(story, eager=eager)}<div class="story-copy"><div class="category">{LABELS[section]} <span aria-hidden="true">·</span> {e(story['category'])}</div><{heading}><a class="story-detail-link" href="{e(path)}">{e(story['title'])}</a></{heading}><p class="story-brief">{e(story.get('brief') or story['summary'].split('. ')[0])}</p><div class="story-links"><a class="source-link" href="{e(story['source_url'])}" target="_blank" rel="noopener noreferrer">{e(story['source_name'])} ↗</a>{arrow()}</div></div></article>"""


def duration(value):
    seconds = int(value)
    return f"{seconds // 60}:{seconds % 60:02d}"


def podcast_art(section, root, *, large=False):
    name = "yeni-sekme" if section == "teknoloji" else "moradon-fm"
    sizes = (
        "(max-width: 640px) calc(100vw - 72px), 400px"
        if large
        else "(max-width: 640px) 88px, 120px"
    )
    return f'<img class="program-art" src="{root}assets/covers/{name}-192.webp" srcset="{root}assets/covers/{name}-192.webp 192w, {root}assets/covers/{name}-768.webp 768w" sizes="{sizes}" width="192" height="192" alt="" decoding="async">'


def audio_card(section, kind, data, root, *, origin=None):
    asset = data[kind]
    name = NAMES[section] if kind == "podcast" else LABELS[section]
    title = f'{name} — {LABELS[section]} {"podcast’i" if kind == "podcast" else "Günün Özeti"}'
    route = root + f"{section}/dinle/index.html"
    origin = origin or ("secki" if root == "./" else section)
    route += ("?ses=ozet&" if kind == "summary" else "?") + "from=" + origin
    artwork = (
        podcast_art(section, root)
        if kind == "podcast"
        else '<span class="summary-mark" aria-hidden="true">≡</span>'
    )
    return f"""<section class="audio-box {kind}-box" data-audio-section="{section}" data-audio-kind="{kind}">{artwork}<div class="audio-copy"><h3><a href="{e(route)}">{e(name)}</a></h3><p>{LABELS[section] + ' podcast’i · ' if kind == 'podcast' else ''}{duration(asset['duration'])}</p></div><button type="button" class="audio-start" data-section="{section}" data-kind="{kind}" aria-label="{e(title)}: Oynat"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 12 7-12 7Z" fill="currentColor"/></svg></button></section>"""


def listening(editions, root, *, only=None):
    sections = [only] if only else SECTIONS
    return (
        '<aside class="listening" id="podcastler" aria-labelledby="listening-title"><h2 id="listening-title">Bugünün podcast’leri</h2><div class="podcast-cards">'
        + "".join(audio_card(s, "podcast", editions[s], root) for s in sections)
        + '</div><h2 class="summary-heading">Günün Özeti</h2><div class="summary-cards">'
        + "".join(audio_card(s, "summary", editions[s], root) for s in sections)
        + "</div></aside>"
    )


def category_audio(section, data, root):
    return f'<section class="section-audio" aria-label="{LABELS[section]} sesleri"><div><h2>Podcast</h2>{audio_card(section, "podcast", data, root)}</div><div><h2>Günün Özeti</h2>{audio_card(section, "summary", data, root)}</div></section>'


def program_card(section, data, root):
    title = NAMES[section]
    route = root + section + "/dinle/index.html?from=podcastler"
    return f"""<section class="program-card" aria-labelledby="program-{section}"><a class="program-cover-link" href="{e(route)}" aria-label="{title}: Bölüm ayrıntıları">{podcast_art(section, root, large=True)}</a><div class="program-body"><p class="eyebrow">{LABELS[section]} podcast’i</p><div class="program-title-row"><h2 id="program-{section}"><a href="{e(route)}">{title}</a></h2><button type="button" class="audio-start" data-section="{section}" data-kind="podcast" aria-label="{title}: Oynat"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 12 7-12 7Z" fill="currentColor" stroke="none"/></svg></button></div><p>Yaşar ve Necdet</p><p class="program-meta">{display_date(data['publish_date'])} · {duration(data['podcast']['duration'])}</p><a class="program-detail" href="{e(route)}">Bölümü incele →</a></div></section>"""


def navigation(root, page="", section=""):
    active = (
        "podcasts"
        if page in ("podcasts", "listen")
        else (section or ("home" if page == "home" else ""))
    )
    entries = [
        ("home", "index.html", "Günün seçkisi"),
        ("teknoloji", "teknoloji/index.html", "Teknoloji"),
        ("oyun", "oyun/index.html", "Oyun"),
        ("podcasts", "podcastler/index.html", "Podcast’ler"),
    ]
    return (
        '<nav aria-label="Ana menü">'
        + "".join(
            f'<a href="{root}{route}"'
            + (' aria-current="page"' if key == active else "")
            + f"><span>{label}</span></a>"
            for key, route, label in entries
        )
        + "</nav>"
    )


def selection(editions):
    # Preserve each edition's verified editorial order. Represent both publications;
    # do not invent importance scores or a new AI news ranking in the web layer.
    tech, game = editions["teknoloji"]["stories"], editions["oyun"]["stories"]
    return [("teknoloji", tech[0]), ("oyun", game[0]), ("teknoloji", tech[1])]


def list_controls(section=None):
    search = '<button type="button" class="search-toggle" aria-expanded="false" aria-controls="news-search-field">Ara</button><label class="news-search-label" id="news-search-field"><span class="sr-only">Haberlerde ara</span><input class="news-search" type="search" placeholder="Haberlerde ara" maxlength="160" autocomplete="off" aria-controls="stories"></label><button type="button" class="search-clear" hidden>Aramayı temizle</button>'
    sections = '' if section else '<div class="section-filters" role="group" aria-label="Yayın filtresi"><button type="button" data-filter="" aria-pressed="true">Tümü</button><button type="button" data-filter="teknoloji" aria-pressed="false">Teknoloji</button><button type="button" data-filter="oyun" aria-pressed="false">Oyun</button></div>'
    return '<div class="news-tools">' + search + sections + '<button type="button" class="topics-toggle" aria-haspopup="dialog" aria-controls="topics-dialog">Konular</button><span class="story-count" id="story-count" role="status"></span></div><div class="filter-chips" role="group" aria-label="Etkin konu filtreleri"></div><dialog class="topics-dialog" id="topics-dialog" aria-labelledby="topics-title"><form method="dialog"><div class="topics-heading"><h2 id="topics-title">Konular</h2><button type="submit" aria-label="Konu seçimini kapat">×</button></div><div class="topic-options"></div><div class="topic-actions"><button type="button" class="topics-clear">Seçimi temizle</button><button type="submit" class="topics-apply" value="apply">Uygula</button></div></form></dialog>'



def listing(editions, root, *, section=None):
    sections = [section] if section else SECTIONS
    # Interleave for a neutral combined list; section pages retain their own order.
    rows = [
        (s, editions[s]["stories"][i])
        for i in range(max(len(editions[s]["stories"]) for s in sections))
        for s in sections
        if i < len(editions[s]["stories"])
    ]
    cards = "".join(story_card(s, story, root, level=2) for s, story in rows)
    return (
        list_controls(section)
        + f'<div id="stories" class="news-list">{cards}</div><p class="empty-filter" role="status" hidden>Bu seçimde haber bulunamadı. <button type="button" class="reset-filter">Arama ve filtreleri temizle</button></p><button type="button" class="news-more" hidden>Daha fazla haber</button>'
    )


def shell(
    main,
    *,
    title="PULSE. — Günlük gündemimiz",
    description="Teknoloji, oyun ve iyi muhabbet. Günlük haberler, Günün Özeti ve podcast’ler.",
    route="",
    page="home",
    release_id="",
    stamp="",
    section="",
    story_id="",
    share_image="",
):
    depth = route.count("/")
    root = "../" * depth or "./"
    url = "https://yasargny.github.io/" + route
    attrs = f'data-page="{page}" data-section="{section}" data-story="{e(story_id)}"'
    return symbols(
        f"""<!doctype html>
<html lang="tr" class="pulse-loading" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#151618"><meta name="description" content="{e(description)}"><title>{e(title)}</title><link rel="canonical" href="{url}"><meta property="og:type" content="{'article' if page == 'article' else 'website'}"><meta property="og:locale" content="tr_TR"><meta property="og:site_name" content="PULSE"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{e(share_image or "https://yasargny.github.io/assets/og.png?v=3")}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image"><link rel="icon" href="{root}assets/favicon.svg?v=2" type="image/svg+xml"><link rel="manifest" href="{root}manifest.webmanifest"><link rel="apple-touch-icon" href="{root}assets/app-180.png?v=2"><meta name="apple-mobile-web-app-title" content="PULSE"><script src="{root}assets/theme.js?v=1"></script><link rel="stylesheet" href="{root}assets/style.css?v=20"><script src="{root}assets/publication.js?v=4" defer></script><script src="{root}assets/printing.js?v=8" defer></script><script src="{root}assets/listening.js?v=1" defer></script><script src="{root}assets/site.js?v=19" defer></script><script src="{root}assets/install.js?v=3" defer></script></head>
<body data-design="{DESIGN}" {attrs}><noscript><style>.pulse-loading .site-shell{{visibility:visible!important}}.site-shell{{display:block!important}}[data-audio-section],.audio-start,.listen-player,.theme-toggle,.news-tools,.news-more{{display:none!important}}</style><p class="nojs-note">Bu kayıt {e(stamp)} tarihli sayıdır. Güncel yayın durumunu ve sesleri kullanmak için JavaScript’i etkinleştirin.</p></noscript><div class="site-shell"><a class="skip" href="#main">İçeriğe geç</a><header class="nav"><a class="brand" href="{root}index.html" aria-label="PULSE ana sayfa">PULSE<span class="brand-dot">.</span></a><span class="nav-issue">{e(stamp)}</span>{navigation(root, page, section)}<button type="button" class="theme-toggle" aria-label="Açık temaya geç"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></svg></button></header><main id="main" tabindex="-1" data-release="{e(release_id)}">{main}</main><footer class="foot"><a class="brand" href="{root}index.html" aria-label="PULSE ana sayfa">PULSE<span class="brand-dot">.</span></a><div class="foot-actions"><button type="button" class="install-entry" aria-haspopup="dialog" hidden>Uygulamayı yükle <span aria-hidden="true">↗</span></button><a href="{root}gizlilik/index.html">Gizlilik</a></div></footer></div></body></html>"""
    )


def build_views(output, manifest):
    output = Path(output)
    if manifest.get("status") != "ready":
        return
    release = output / "releases" / manifest["release_id"]
    editions = {s: read_json(release / f"{s}.json") for s in SECTIONS}
    date = display_date(manifest["publish_date"])
    stamp = date

    def save(route, main, **kwargs):
        path = output / route / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        structured = kwargs.pop("structured", None)
        page = shell(
            main,
            route=route,
            release_id=manifest["release_id"],
            stamp=stamp,
            **kwargs,
        )
        if structured:
            encoded = json.dumps(structured, ensure_ascii=False).replace(
                "<", chr(92) + "u003c"
            )
            page = page.replace(
                "</head>",
                '<script type="application/ld+json">' + encoded + "</script></head>",
            )
        if kwargs.get("share_image"):
            page = re.sub(r'<meta property="og:image:(?:width|height)"[^>]*>', "", page)
        path.write_text(page)

    lead = selection(editions)
    selected = {(s, story["id"]) for s, story in lead}
    remaining = [
        (s, story)
        for i in range(max(len(d["stories"]) for d in editions.values()))
        for s, d in editions.items()
        if i < len(d["stories"])
        and (s, (story := d["stories"][i])["id"]) not in selected
    ]
    lead_html = "".join(
        story_card(s, story, "./", lead=True, eager=i == 0)
        for i, (s, story) in enumerate(lead)
    )
    home = f"""<section class="daily-selection" aria-labelledby="selection-title"><div class="sectiontop"><h1 id="selection-title">Günün seçkisi</h1><span class="morning">Her sabah 07:30</span></div><div class="selection-grid">{lead_html}</div></section><a class="mobile-news-jump" href="haberler/index.html">Tüm haberlere git ↓</a><div class="desk-grid"><section class="other-news" aria-labelledby="other-title"><div class="sectiontop"><h2 id="other-title">Diğer haberler</h2><a href="haberler/index.html">Tüm haberler ↗</a></div><div class="home-news">{''.join(story_card(s, story, './') for s, story in remaining[:4])}</div><div class="edition-links"><a href="teknoloji/index.html">Teknoloji yayını ↗</a><a href="oyun/index.html">Oyun yayını ↗</a></div></section>{listening(editions, './')}</div>"""
    save("", home)
    for section in (None, *SECTIONS):
        route = "haberler/" if section is None else section + "/"
        root = "../"
        title = "Günün haberleri" if section is None else LABELS[section]
        count = " · ".join(
            f'{LABELS[s]} {len(editions[s]["stories"])}'
            for s in ([section] if section else SECTIONS)
        )
        audio = category_audio(section, editions[section], root) if section else ""
        main = f'<header class="page-heading"><h1>{title}</h1><p>{count}</p></header>{audio}{listing(editions, root, section=section)}'
        save(route, main, title=f"{title} · PULSE", page="news", section=section or "")
    save(
        "podcastler/",
        '<header class="page-heading"><h1>Podcast’ler</h1></header><div class="program-grid">'
        + "".join(
            program_card(section, editions[section], "../") for section in SECTIONS
        )
        + '</div><section class="podcast-summaries" aria-labelledby="summary-title"><h2 id="summary-title">Günün Özeti</h2><div class="summary-cards">'
        + "".join(
            audio_card(section, "summary", editions[section], "../", origin="podcastler")
            for section in SECTIONS
        )
        + "</div></section>",
        page="podcasts",
        title="Podcast’ler · PULSE",
    )
    for section in SECTIONS:
        data = editions[section]
        main = f"""<a class="back listen-back" href="../../podcastler/index.html">← Podcast’lere dön</a><section class="episode"><div class="episode-heading">{podcast_art(section, "../../")}<div><p class="eyebrow">{LABELS[section]} podcast’i</p><h1>{NAMES[section]}</h1><p class="episode-hosts">Yaşar ve Necdet</p><p class="detail-meta">{date} · {duration(data['podcast']['duration'])}</p></div></div><div class="listen-player" data-listen-section="{section}"><button type="button" class="audio-start" data-section="{section}" data-kind="podcast" aria-label="{NAMES[section]}: Oynat"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 12 7-12 7Z" fill="currentColor" stroke="none"/></svg></button><span>Dinle</span></div></section><section aria-labelledby="episode-news"><h2 id="episode-news">Bölümdeki haberler</h2><div class="episode-stories">{''.join(story_card(section, story, '../../') for story in data['stories'])}</div></section><div class="episode-secondary">{audio_card(section, 'summary', data, '../../')}<a href="../../{('oyun' if section == 'teknoloji' else 'teknoloji')}/dinle/index.html">{NAMES['oyun' if section == 'teknoloji' else 'teknoloji']} ↗</a></div>"""
        save(
            section + "/dinle/",
            main,
            title=NAMES[section] + " · PULSE",
            page="listen",
            section=section,
        )
        for story in data["stories"]:
            from pulse.details import article_body

            content = article_body(data, story)
            save(
                section + "/haber/" + quote(story["id"], safe="") + "/",
                content,
                title=story["title"] + " · PULSE",
                description=story.get("brief") or story["summary"],
                page="article",
                section=section,
                story_id=story["id"],
                share_image=story.get("image_url", ""),
                structured={
                    "@context": "https://schema.org",
                    "@type": "NewsArticle",
                    "headline": story["title"],
                    "datePublished": data["publish_date"] + "T07:30:00+03:00",
                    "author": {"@type": "Organization", "name": "PULSE"},
                    "publisher": {"@type": "Organization", "name": "PULSE"},
                    "mainEntityOfPage": "https://yasargny.github.io/"
                    + article_path(section, story).removesuffix("index.html"),
                    **(
                        {"image": [story["image_url"]]}
                        if story.get("image_url")
                        else {}
                    ),
                },
            )
    # Discovery includes the generated full articles, not only section landing pages.
    routes = [
        "",
        "haberler/",
        "podcastler/",
        "teknoloji/",
        "oyun/",
        "teknoloji/dinle/",
        "oyun/dinle/",
        "gizlilik/",
        "kosullar/",
    ] + [
        article_path(s, story).removesuffix("index.html")
        for s, data in editions.items()
        for story in data["stories"]
    ]
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(
            "<url><loc>https://yasargny.github.io/" + e(route) + "</loc></url>"
            for route in routes
        )
        + "</urlset>"
    )
