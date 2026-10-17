import base64
import copy
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from fixtures import DATE, edition, ready_release, tone

from pulse.build import assert_public_tree, build
from pulse.editorial import create_edition, parse_feed, summary_script
from pulse.history import exclude_published
from pulse.pipeline import AUDIO_REVISION, generate_audio, run
from pulse.publication import (
    expected_date,
    game_start_from_site,
    issue_number,
    not_before,
    read_json,
    turkish_date,
    validate_content,
    validate_release,
    verify_manifest,
    write_json,
)
from pulse.verify_site import check_site
from scripts.state import unpack
from scripts.sync_site import sync

ROOT = Path(__file__).resolve().parents[1]


class CalendarTests(unittest.TestCase):
    def test_tech_initial_issue(self):
        self.assertEqual(issue_number(DATE, "teknoloji", DATE), 1)

    def test_tech_next_day(self):
        self.assertEqual(issue_number("2026-10-17", "teknoloji", DATE), 2)

    def test_game_starts_on_its_own_launch_date(self):
        self.assertEqual(issue_number("2026-11-01", "oyun", "2026-11-01"), 1)

    def test_game_rerun_cannot_increment_issue(self):
        self.assertEqual(
            issue_number(DATE, "oyun", DATE), issue_number(DATE, "oyun", DATE)
        )

    def test_before_start_rejected(self):
        with self.assertRaises(ValueError):
            issue_number("2026-10-15", "teknoloji", DATE)

    def test_turkish_date(self):
        self.assertEqual(turkish_date(DATE), "16 Ekim 2026")

    def test_0600_changes_required_date(self):
        self.assertEqual(
            expected_date(dt.datetime.fromisoformat("2026-10-17T02:59:59+00:00")), DATE
        )
        self.assertEqual(
            expected_date(dt.datetime.fromisoformat("2026-10-17T03:00:00+00:00")),
            "2026-10-17",
        )

    def test_midnight_keeps_previous_edition(self):
        self.assertEqual(
            expected_date(dt.datetime.fromisoformat("2026-10-17T00:00:00+03:00")), DATE
        )

    def test_release_time(self):
        self.assertEqual(not_before(DATE).astimezone(dt.timezone.utc).hour, 4)


class ContentTests(unittest.TestCase):
    def test_valid_content(self):
        validate_content(edition("teknoloji"), "teknoloji", DATE, DATE)

    def test_missing_source_blocks(self):
        d = edition("teknoloji")
        d["stories"][0]["source_url"] = ""
        with self.assertRaises(ValueError):
            validate_content(d, "teknoloji", DATE, DATE)

    def test_empty_edition_blocks(self):
        d = edition("oyun")
        d["stories"] = []
        with self.assertRaises(ValueError):
            validate_content(d, "oyun", DATE, DATE)

    def test_cross_section_blocks(self):
        with self.assertRaises(ValueError):
            validate_content(edition("oyun"), "teknoloji", DATE, DATE)

    def test_duplicate_story_blocks(self):
        d = edition("oyun")
        d["stories"][1] = d["stories"][0]
        with self.assertRaises(ValueError):
            validate_content(d, "oyun", DATE, DATE)

    def test_stale_source_blocks(self):
        d = edition("oyun")
        d["stories"][0]["source_published_at"] = "2026-10-01T05:00:00+03:00"
        with self.assertRaises(ValueError):
            validate_content(d, "oyun", DATE, DATE)

    def test_narration_covers_every_story(self):
        d = edition("teknoloji")
        script = summary_script(d)
        self.assertTrue(
            all(
                s["summary"].split(". ")[0] in script and s["why"] not in script
                for s in d["stories"]
            )
        )

    def test_model_cannot_invent_source(self):
        source = {"publish_date": DATE, "sections": {"teknoloji": [{"id": "known"}]}}
        with patch(
            "pulse.editorial.gemini", return_value={"stories": [{"id": "invented"}]}
        ):
            with self.assertRaises(KeyError):
                create_edition(source, "teknoloji", DATE, 1, DATE)

    def test_feed_filters_stale_and_foreign_links(self):
        def item(url, stamp):
            return f"<item><title>Test article headline</title><link>{url}</link><description>{'Source facts. ' * 20}</description><pubDate>{stamp}</pubDate></item>"

        raw = (
            "<rss><channel>"
            + item("https://example.com/a", "Fri, 16 Oct 2026 02:00:00 GMT")
            + item("https://evil.test/b", "Fri, 16 Oct 2026 02:00:00 GMT")
            + item("https://example.com/c", "Thu, 01 Oct 2026 02:00:00 GMT")
            + "</channel></rss>"
        ).encode()
        found = parse_feed(raw, {"hosts": ["example.com"], "name": "Test"}, DATE)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["source_url"], "https://example.com/a")


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.audio = tone(Path(cls.shared.name) / "tone.mp3")
        cls.base = Path(cls.shared.name) / "release"
        cls.manifest = ready_release(cls.base, cls.audio)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.release = self.root / "release"
        shutil.copytree(self.base, self.release)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_four_audio_files_fully_decode(self):
        validate_release(self.release, DATE, DATE)

    def test_missing_game_podcast_blocks_everything(self):
        (self.release / "oyun/podcast.mp3").unlink()
        with self.assertRaises(ValueError):
            validate_release(self.release, DATE, DATE)

    def test_truncated_audio_blocks_everything(self):
        p = self.release / "teknoloji/summary.mp3"
        p.write_bytes(p.read_bytes()[:1000])
        with self.assertRaises(ValueError):
            validate_release(self.release, DATE, DATE)

    def test_hash_detects_changed_asset(self):
        p = self.release / "teknoloji/summary.mp3"
        p.write_bytes(p.read_bytes() + b"corruption")
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            validate_release(self.release, DATE, DATE)

    def test_wrong_episode_blocks(self):
        p = self.release / "oyun.json"
        d = read_json(p)
        d["podcast"]["episode"] = 2
        write_json(p, d)
        with self.assertRaises(ValueError):
            validate_release(self.release, DATE, DATE)

    def test_manifest_tampering_blocks(self):
        m = copy.deepcopy(self.manifest)
        m["editions"]["oyun"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_manifest(self.release, m)

    def test_public_build_excludes_legacy_unsourced_json_and_prompts(self):
        (self.release / "research.json").write_text('{"private_research":true}')
        output = self.root / "dist"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        self.assertFalse((output / "data/teknoloji.json").exists())
        self.assertFalse(any(p.name == "research.json" for p in output.rglob("*")))
        self.assertEqual(read_json(output / "data/publication.json")["status"], "ready")

    def test_early_build_rejected(self):
        with self.assertRaises(ValueError):
            build(
                ROOT / "site",
                self.root / "dist",
                release=self.release,
                at=not_before(DATE) - dt.timedelta(seconds=1),
            )

    def test_overnight_revision_retains_its_real_date_until_six(self):
        at = not_before(DATE).replace(hour=5, minute=59) + dt.timedelta(days=1)
        output = self.root / "overnight"
        build(ROOT / "site", output, release=self.release, at=at)
        sync(output, self.root / "overnight-published", at=at)
        self.assertEqual(
            read_json(output / "data/publication.json")["publish_date"], DATE
        )
        with patch("pulse.pipeline.now", return_value=at):
            from pulse.pipeline import wait_for

            wait_for(DATE, "07:30")

    def test_exact_next_six_blocks_build_sync_and_pipeline_wait(self):
        at = not_before(DATE).replace(hour=6, minute=0) + dt.timedelta(days=1)
        output = self.root / "morning"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        with self.assertRaises(ValueError):
            build(ROOT / "site", self.root / "blocked", release=self.release, at=at)
        with self.assertRaises(ValueError):
            sync(output, self.root / "blocked-sync", at=at)
        with patch("pulse.pipeline.now", return_value=at):
            from pulse.pipeline import wait_for

            with self.assertRaisesRegex(RuntimeError, "expired"):
                wait_for(DATE, "07:30")

    def test_expired_build_rejected(self):
        with self.assertRaises(ValueError):
            build(
                ROOT / "site",
                self.root / "dist",
                release=self.release,
                at=not_before(DATE) + dt.timedelta(days=1),
            )

    def test_prepare_cannot_close_already_ready_today(self):
        output = self.root / "dist"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        other = self.root / "prepare"
        m = build(ROOT / "site", other, preparing=DATE, previous=output)
        self.assertEqual(m["status"], "ready")

    def test_next_morning_prepare_closes(self):
        output = self.root / "dist"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        m = build(
            ROOT / "site", self.root / "next", preparing="2026-10-17", previous=output
        )
        self.assertEqual(m["status"], "preparing")
        self.assertEqual(m["publish_date"], "2026-10-17")

    def test_pipeline_rerun_reuses_sealed_issue_without_api_calls(self):
        work = self.root / "work"
        shutil.copytree(self.release, work / DATE)
        parts = work / DATE / "teknoloji" / "tts-parts" / "finished"
        parts.mkdir(parents=True)
        (parts / "part_000.wav").write_bytes(b"finished intermediate")
        with (
            patch(
                "pulse.pipeline.research",
                side_effect=AssertionError("Must not research again"),
            ),
            patch(
                "pulse.pipeline.generate_audio",
                side_effect=AssertionError("Must not synthesize again"),
            ),
        ):
            one = run(work, DATE, DATE)
            two = run(work, DATE, DATE)
        self.assertEqual(one, two)
        self.assertFalse(parts.parent.exists())
        verify_manifest(work / DATE, one)

    def test_unverified_release_keeps_all_render_parts_for_recovery(self):
        from pulse.pipeline import verified_checkpoint

        root = self.root / "invalid-checkpoint"
        shutil.copytree(self.release, root)
        parts = root / "teknoloji" / "tts-parts"
        parts.mkdir()
        (parts / "part_000.wav").write_bytes(b"recoverable partial stage")
        (root / "teknoloji" / "podcast.mp3").write_bytes(b"broken")
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            verified_checkpoint(root)
        self.assertTrue((parts / "part_000.wav").exists())

    def test_audio_revision_preserves_news_numbering_and_cannot_be_rolled_back_by_rerun(
        self,
    ):
        published = self.root / "published-for-refresh"
        build(ROOT / "site", published, release=self.release, at=not_before(DATE))
        original = read_json(published / "data/publication.json")
        work = self.root / "revision-work"

        def generate(root, data):
            source = read_json(self.release / (data["section"] + ".json"))
            for kind in ("summary", "podcast"):
                dest = root / source[kind]["file"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.release / source[kind]["file"], dest)
                data[kind] = source[kind]
            data["audio_revision"] = AUDIO_REVISION
            data["ready"] = True
            return data

        with (
            patch("pulse.pipeline.now", return_value=not_before(DATE)),
            patch("pulse.pipeline.generate_audio", side_effect=generate) as synth,
        ):
            revised = run(work, DATE, DATE, previous=published, refresh_audio=True)
            again = run(work, DATE, DATE, previous=published, refresh_audio=True)
            normal = run(work, DATE, DATE, previous=published)
        self.assertEqual(synth.call_count, 2)
        self.assertEqual(revised, again)
        self.assertEqual(normal["release_id"], revised["release_id"])
        self.assertNotEqual(original["release_id"], revised["release_id"])
        self.assertEqual(read_json(published / "data/publication.json"), original)
        for section in ("teknoloji", "oyun"):
            result = read_json(work / DATE / (section + ".json"))
            self.assertEqual(result["issue"], 1)
            self.assertEqual(
                result["stories"],
                read_json(self.release / (section + ".json"))["stories"],
            )

    def test_generation_resume_and_preserve_existing_voice_method(self):
        root = self.root / "audio"
        root.mkdir()
        data = edition("teknoloji")

        async def save(path):
            shutil.copyfile(self.audio, path)

        turns = [
            {
                "speaker": "Yaşar" if i % 2 == 0 else "Necdet",
                "text": "Doğrulanmış notlar üzerine bir test sohbeti.",
            }
            for i in range(12)
        ]

        def render(dialogue, target, *, strict_audio=False):
            shutil.copyfile(self.audio, target)

        def reviewed_writer(*args, **kwargs):
            write_json(
                kwargs["audit_path"],
                {
                    "turns_sha256": __import__("pulse_podcast_writer").dialogue_digest(
                        turns
                    ),
                    "review": {
                        "approved": True,
                        "unsupported_claims": [],
                        "misleading_opinions": [],
                        "concerns": [],
                    },
                },
            )
            return "", turns

        with (
            patch("edge_tts.Communicate") as edge,
            patch(
                "pulse_podcast_writer.generate", side_effect=reviewed_writer
            ) as writer,
            patch("pulse_podcast_audio.render", side_effect=render) as tts,
        ):
            edge.return_value.save = save
            one = generate_audio(root, data)
            two = generate_audio(root, one)
            self.assertEqual(writer.call_count, 1)
            self.assertEqual(tts.call_count, 1)
            self.assertTrue(tts.call_args.kwargs["strict_audio"])
            self.assertEqual(edge.call_count, 1)
            self.assertEqual(edge.call_args.kwargs["voice"], "tr-TR-EmelNeural")
            self.assertEqual(two["podcast"]["title"], "Yeni Sekme")
        data["stories"][0]["title"] = "Changed after synthesis"
        with self.assertRaises(ValueError):
            generate_audio(root, data)

    def test_deploy_atomic_commit_and_repeatability_in_local_git(self):
        output = self.root / "dist"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        target = self.root / "target"
        target.mkdir()
        (target / "keep.txt").write_text("preserve existing files")
        (target / "data").mkdir()
        (target / "data/teknoloji.json").write_text('{"pilot": true}')
        (target / "data/oyun.json").write_text('{"pilot": true}')

        def git(*args):
            return subprocess.run(
                ["git", "-C", str(target), *args],
                check=True,
                capture_output=True,
                text=True,
            ).stdout

        git("init", "-b", "main")
        git("config", "user.name", "PULSE test")
        git("config", "user.email", "test@example.com")
        sync(output, target, at=not_before(DATE))
        self.assertFalse((target / "data/teknoloji.json").exists())
        self.assertFalse((target / "data/oyun.json").exists())
        git("add", ".")
        git("commit", "-m", "atomic release")
        sync(output, target, at=not_before(DATE))
        self.assertEqual(git("status", "--porcelain"), "")
        self.assertEqual(
            read_json(target / "data/publication.json")["release_id"],
            self.manifest["release_id"],
        )
        self.assertEqual((target / "keep.txt").read_text(), "preserve existing files")
        remote = self.root / "pages.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)], check=True, capture_output=True
        )
        git("remote", "add", "origin", str(remote))
        git("push", "origin", "HEAD:main")
        restored = self.root / "restored-pages"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(remote), str(restored)],
            check=True,
            capture_output=True,
        )
        published = read_json(restored / "data/publication.json")
        verify_manifest(restored / "releases" / published["release_id"], published)

    def test_secret_not_allowed_in_public_tree(self):
        p = self.root / "public"
        p.mkdir()
        (p / "config.json").write_text(json.dumps({"key": "AIza" + "a" * 35}))
        with self.assertRaises(ValueError):
            assert_public_tree(p)

    def test_no_source_files_allowed_in_public_tree(self):
        p = self.root / "public"
        p.mkdir()
        (p / "script.py").write_text("pass")
        with self.assertRaises(ValueError):
            assert_public_tree(p)

    def test_first_failed_game_attempt_does_not_consume_issue_one(self):
        output = self.root / "dist"
        build(ROOT / "site", output, preparing=DATE)
        start = game_start_from_site(output, "2026-10-17")
        self.assertEqual(start, "2026-10-17")
        self.assertEqual(issue_number("2026-10-17", "oyun", start), 1)

    def test_game_start_survives_preparation_manifest(self):
        output = self.root / "dist"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        next_site = self.root / "next"
        build(ROOT / "site", next_site, preparing="2026-10-17", previous=output)
        self.assertEqual(game_start_from_site(next_site, "2026-10-17"), DATE)
        self.assertEqual(issue_number("2026-10-17", "oyun", DATE), 2)

    def test_existing_gemini_payload_retains_both_custom_voices(self):
        import pulse_podcast_audio as engine

        wav = self.root / "provider.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(self.audio),
                "-t",
                "3",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            check=True,
            capture_output=True,
        )
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "steps": [
                {
                    "content": [
                        {
                            "type": "audio",
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(wav.read_bytes()).decode(),
                        }
                    ]
                }
            ]
        }
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-only-key"}),
            patch(
                "pulse_podcast_audio.requests.post", return_value=response
            ) as request,
        ):
            engine.synthesize(
                [
                    {"speaker": "Yaşar", "text": "Günaydın."},
                    {"speaker": "Necdet", "text": "Günaydın Yaşar."},
                ],
                self.root / "part.wav",
                0,
                strict_audio=True,
            )
        payload = request.call_args.kwargs["json"]
        self.assertEqual(
            payload["generation_config"]["speech_config"]["speakers"],
            [
                {"speaker": "Yaşar", "voice": "voice_glt4mz1jtaeh"},
                {"speaker": "Necdet", "voice": "voice_8nqcoox86z5q"},
            ],
        )
        self.assertGreaterEqual(engine.duration(self.root / "part.wav"), 2.9)

    def test_legacy_untyped_audio_response_remains_compatible(self):
        import pulse_podcast_audio as engine

        wav = self.root / "legacy-provider.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(self.audio),
                "-t",
                "3",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            check=True,
            capture_output=True,
        )
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "steps": [
                {"content": [{"data": base64.b64encode(wav.read_bytes()).decode()}]}
            ]
        }
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-only-key"}),
            patch("pulse_podcast_audio.requests.post", return_value=response),
        ):
            engine.synthesize(
                [{"speaker": "Yaşar", "text": "Test."}], self.root / "part.wav", 0
            )
        self.assertGreaterEqual(engine.duration(self.root / "part.wav"), 2.9)

    def test_non_audio_provider_data_is_rejected_without_decoding_it_as_pcm(self):
        import pulse_podcast_audio as engine

        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "steps": [
                {
                    "content": [
                        {
                            "type": "image",
                            "data": base64.b64encode(b"not-audio").decode(),
                        }
                    ]
                }
            ]
        }
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-only-key"}),
            patch("pulse_podcast_audio.requests.post", return_value=response),
            patch("pulse_podcast_audio.run") as decode,
        ):
            with self.assertRaisesRegex(RuntimeError, "No audio returned"):
                engine.synthesize(
                    [{"speaker": "Yaşar", "text": "Test."}],
                    self.root / "part.wav",
                    0,
                    strict_audio=True,
                )
            decode.assert_not_called()

    def test_legacy_writer_default_remains_new_tab(self):
        import pulse_podcast_writer as writer

        turns = [
            {
                "speaker": "Yaşar" if i % 2 == 0 else "Necdet",
                "text": "A source-grounded fixture dialogue.",
            }
            for i in range(12)
        ]
        with patch(
            "pulse_podcast_writer._request",
            side_effect=[
                {"turns": turns},
                {"turns": turns},
                {
                    "approved": True,
                    "unsupported_claims": [],
                    "misleading_opinions": [],
                    "concerns": [],
                },
            ],
        ) as request:
            writer.generate([("Fixture headline", "Fixture source facts")])
        self.assertEqual(
            request.call_args_list[0].args[0]["system_instruction"]["parts"][0]["text"],
            writer.SYSTEM,
        )

    def test_game_writer_uses_distinct_station_and_issue(self):
        import pulse_podcast_writer as writer

        turns = [
            {
                "speaker": "Yaşar" if i % 2 == 0 else "Necdet",
                "text": "A source-grounded fixture dialogue.",
            }
            for i in range(12)
        ]
        with patch(
            "pulse_podcast_writer._request",
            side_effect=[
                {"turns": turns},
                {"turns": turns},
                {
                    "approved": True,
                    "unsupported_claims": [],
                    "misleading_opinions": [],
                    "concerns": [],
                },
            ],
        ) as request:
            writer.generate(
                [("Oyun haberi", "Kaynak notları")],
                section="oyun",
                date="16 Ekim 2026",
                issue=1,
            )
        system = request.call_args_list[0].args[0]["system_instruction"]["parts"][0][
            "text"
        ]
        self.assertIn("Moradon FM", system)
        self.assertNotIn("Yeni Sekme", system)
        self.assertIn("001", system)

    def test_published_site_restores_day_after_artifact_deletion(self):
        site = self.root / "published"
        build(ROOT / "site", site, release=self.release, at=not_before(DATE))
        with (
            patch(
                "pulse.pipeline.research",
                side_effect=AssertionError("Already published"),
            ),
            patch(
                "pulse.pipeline.generate_audio",
                side_effect=AssertionError("Already published"),
            ),
        ):
            m = run(self.root / "fresh-work", DATE, DATE, previous=site)
        self.assertEqual(m["release_id"], self.manifest["release_id"])
        verify_manifest(self.root / "fresh-work" / DATE, m)

    def test_prior_day_source_urls_are_not_republished(self):
        site = self.root / "published"
        build(ROOT / "site", site, release=self.release, at=not_before(DATE))
        raw = {
            "sections": {
                s: [{"source_url": f"https://example.com/{s}/0"}]
                + [{"source_url": f"https://example.com/{s}/new-{i}"} for i in range(3)]
                for s in ("teknoloji", "oyun")
            }
        }
        filtered = exclude_published(raw, site, "2026-10-17")
        self.assertTrue(all(len(items) == 3 for items in filtered["sections"].values()))
        self.assertTrue(
            all(
                "/new-" in s["source_url"]
                for items in filtered["sections"].values()
                for s in items
            )
        )

    def test_insufficient_new_stories_blocks_instead_of_reusing_old_news(self):
        site = self.root / "published"
        build(ROOT / "site", site, release=self.release, at=not_before(DATE))
        raw = {
            "sections": {
                s: [{"source_url": f"https://example.com/{s}/{i}"} for i in range(3)]
                for s in ("teknoloji", "oyun")
            }
        }
        with self.assertRaisesRegex(ValueError, "Insufficient fresh"):
            exclude_published(raw, site, "2026-10-17")

    def public_session(self, folder):
        from urllib.parse import urlparse

        import requests

        def get(url, **kwargs):
            file = folder / (urlparse(url).path.strip("/") or "index.html")
            if file.is_dir():
                file = file / "index.html"
            response = requests.Response()
            response.url = url
            response.status_code = 200 if file.is_file() else 404
            response._content = file.read_bytes() if file.is_file() else b"missing"
            response._content_consumed = True
            response.headers["Date"] = "Fri, 16 Oct 2026 05:30:00 GMT"
            import mimetypes

            response.headers["Content-Type"] = (
                mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            )
            return response

        return Mock(get=Mock(side_effect=get))

    def test_actual_pages_ready_bytes_are_verified_not_just_the_commit(self):
        output = self.root / "site"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        check_site(self.public_session(output), "https://example.test/", self.manifest)

    def test_pages_mp3_corruption_is_detected_after_deployment(self):
        output = self.root / "site"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        mp3 = output / "releases" / self.manifest["release_id"] / "oyun/podcast.mp3"
        raw = bytearray(mp3.read_bytes())
        raw[len(raw) // 2] ^= 255
        mp3.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "Deployed MP3"):
            check_site(
                self.public_session(output), "https://example.test/", self.manifest
            )

    def test_pages_old_html_cannot_count_as_a_complete_deployment(self):
        output = self.root / "site"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        (output / "index.html").write_text("<h1>Old site</h1>")
        with self.assertRaisesRegex(ValueError, "HTML has not updated"):
            check_site(
                self.public_session(output), "https://example.test/", self.manifest
            )

    def test_pages_same_design_with_stale_release_html_cannot_open(self):
        output = self.root / "site"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        page = output / "haberler/index.html"
        page.write_text(
            page.read_text().replace(self.manifest["release_id"], "old-release")
        )
        with self.assertRaisesRegex(ValueError, "another release"):
            check_site(
                self.public_session(output), "https://example.test/", self.manifest
            )

    def test_pages_missing_new_listening_route_is_not_a_complete_deployment(self):
        import requests

        output = self.root / "site"
        build(ROOT / "site", output, release=self.release, at=not_before(DATE))
        (output / "oyun/dinle/index.html").unlink()
        with self.assertRaises(requests.HTTPError):
            check_site(
                self.public_session(output), "https://example.test/", self.manifest
            )

    def test_pages_preparation_mode_is_verified_without_requiring_future_audio(self):
        output = self.root / "site"
        manifest = build(ROOT / "site", output, preparing=DATE)
        check_site(self.public_session(output), "https://example.test/", manifest)

    def test_zip_traversal_rejected(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as z:
            z.writestr("../outside.json", "{}")
        with self.assertRaises(ValueError):
            unpack(raw.getvalue(), self.root / "state", DATE)

    def test_zip_wrong_day_rejected(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w") as z:
            z.writestr("2026-10-15/state.json", "{}")
        with self.assertRaises(ValueError):
            unpack(raw.getvalue(), self.root / "state", DATE)


if __name__ == "__main__":
    unittest.main()
