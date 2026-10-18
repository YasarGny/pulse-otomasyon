"""Static reading, route safety and archive coverage of the editor desk."""

import tempfile
import json
import struct
import shutil
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

from fixtures import DATE, ready_release, tone
from pulse.build import build
from pulse.details import article_path
from pulse.pages import picture, story_card, build_views
from pulse.publication import not_before


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.links = []
        self.scripts = 0
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "script" and not attrs.get("src"):
            self.scripts += 1


class EditorViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        release = cls.root / "release"
        ready_release(release, tone(cls.root / "tone.mp3"))
        cls.site = cls.root / "site"
        build("site", cls.site, release=release, at=not_before(DATE))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_public_identity_is_date_based_even_when_internal_issue_numbers_differ(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            shutil.copytree(self.site, site)
            manifest = json.loads((site / "data/publication.json").read_text())
            game = site / "releases" / manifest["release_id"] / "oyun.json"
            data = json.loads(game.read_text())
            data["issue"] = 7
            game.write_text(json.dumps(data))
            build_views(site, manifest)
            for route in (
                "oyun/index.html",
                "teknoloji/index.html",
                "index.html",
                "teknoloji/dinle/index.html",
            ):
                text = (site / route).read_text()
                self.assertNotIn("Sayı 007", text)
                self.assertNotIn("Sayı 001", text)
                self.assertIn("16.10.2026", text)

    def test_navigation_exposes_both_categories_and_category_audio_is_not_mixed(self):
        for section in ("teknoloji", "oyun"):
            text = (self.site / section / "index.html").read_text()
            from pulse.pages import navigation

            self.assertIn(navigation("../", "news", section), text)
            self.assertEqual(text.count('data-audio-section="' + section + '"'), 2)
            self.assertNotIn(
                'data-audio-section="'
                + ("oyun" if section == "teknoloji" else "teknoloji")
                + '"',
                text,
            )
        podcasts = (self.site / "podcastler/index.html").read_text()
        self.assertEqual(podcasts.count('class="program-card"'), 2)
        self.assertEqual(podcasts.count('class="program-cover-link"'), 2)
        self.assertIn("400px", podcasts)
        self.assertIn("Moradon FM", podcasts)

    def test_install_manifest_and_icons_are_public_and_reachable_from_deep_routes(self):
        from urllib.parse import urljoin

        manifest = json.loads((self.site / "manifest.webmanifest").read_text())
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["id"], "./")
        self.assertEqual(manifest["scope"], "./")
        self.assertEqual(
            urljoin("https://example.test/manifest.webmanifest", manifest["start_url"]),
            "https://example.test/",
        )
        for size in (180, 192, 512):
            body = (self.site / f"assets/app-{size}.png").read_bytes()
            self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", body[16:24]), (size, size))
        self.assertTrue((self.site / "sw.js").is_file())
        for path in self.site.rglob("*.html"):
            if path.name == "404.html":
                continue
            import re

            html = path.read_text()
            href = re.search(r'<link rel="manifest" href="([^"]+)"', html).group(1)
            self.assertEqual(
                (path.parent / href).resolve(),
                (self.site / "manifest.webmanifest").resolve(),
            )
            self.assertIn("install.js?v=3", html)

    def test_every_internal_article_and_navigation_link_has_a_real_destination(self):
        for page in self.site.rglob("*.html"):
            if page.name == "404.html":
                continue
            for href in Links(page.read_text()).links:
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = (
                    (self.site / url.path.lstrip("/"))
                    if url.path.startswith("/")
                    else page.parent / unquote(url.path)
                )
                self.assertTrue(
                    target.resolve().is_relative_to(self.site.resolve()), (page, href)
                )
                self.assertTrue(
                    target.is_file() or (target / "index.html").is_file(), (page, href)
                )

    def test_distinct_section_news_and_listening_routes_exist(self):
        for route in ["haberler", "podcastler", "teknoloji/dinle", "oyun/dinle"]:
            text = (self.site / route / "index.html").read_text()
            self.assertIn('data-design="editor-desk-v1"', text)
            self.assertIn(
                'data-release="' + next((self.site / "releases").iterdir()).name + '"',
                text,
            )
        self.assertIn(
            "Yeni Sekme", (self.site / "teknoloji/dinle/index.html").read_text()
        )
        self.assertIn("Moradon FM", (self.site / "oyun/dinle/index.html").read_text())

    def test_section_switching_links_to_the_other_publication_instead_of_an_empty_filter(
        self,
    ):
        text = (self.site / "teknoloji/index.html").read_text()
        self.assertIn('href="../oyun/index.html"', text)
        self.assertNotIn('data-filter="oyun"', text)

    def test_home_is_static_and_does_not_auto_select_audio(self):
        home = (self.site / "index.html").read_text()
        self.assertEqual(home.count('class="story lead-story"'), 3)
        self.assertIn("Günün Özeti", home)
        self.assertNotIn("autoplay", home)
        self.assertNotIn('aria-pressed="true"', home)

    def test_article_source_and_complete_body_are_in_html_without_a_fetch(self):
        article = (self.site / "teknoloji/haber/teknoloji0/index.html").read_text()
        self.assertIn("article-text", article)
        self.assertEqual(article.count('class="source-link"'), 1)
        self.assertNotIn('class="article-source"', article)
        self.assertIn("https://example.com/teknoloji/0", article)
        self.assertIn("Görsel kaynağı", article)
        self.assertIn('property="og:type" content="article"', article)
        self.assertIn("https://images.example.test/article.jpg", article)

    def test_source_text_cannot_inject_markup_or_inline_script(self):
        story = {
            "id": "safe",
            "title": "<script>alert(1)</script>",
            "source_name": "<img src=x onerror=alert(1)>",
            "source_url": 'https://example.com/a?x="bad"',
            "category": "<b>bad</b>",
            "image_url": "https://example.com/a.jpg",
            "summary": "A <script> tag",
        }
        text = story_card("teknoloji", story, "../", lead=True)
        self.assertEqual(Links(text).scripts, 0)
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<img src=x", text)

    def test_publisher_provenance_is_not_an_invented_photo_credit(self):
        story = {
            "title": "Title",
            "image_url": "https://example.com/a.jpg",
            "source_url": "https://example.com/source",
            "source_name": "Publisher",
        }
        text = picture(story)
        self.assertIn("Görsel kaynağı", text)
        self.assertNotIn("Fotoğraf: Publisher", text)
        self.assertIn('loading="lazy"', text)

    def test_path_traversal_ids_cannot_overwrite_another_page(self):
        for identity in [
            "..",
            "../else",
            "/absolute",
            "x/y",
            "a%2fb",
            "a.html",
            'x"onload',
        ]:
            with self.assertRaisesRegex(ValueError, "Unsafe article"):
                article_path("teknoloji", {"id": identity})
