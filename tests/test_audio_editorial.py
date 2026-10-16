"""Editorial safeguards: facts-only briefs and independently approved dialogue."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import edition
from pulse.editorial import summary_script
from pulse.publication import read_json
import pulse_podcast_writer as writer

APPROVED = {"approved": True, "unsupported_claims": [], "misleading_opinions": [], "concerns": []}
REJECTED = {"approved": False, "unsupported_claims": ["A made-up numerical claim"], "misleading_opinions": [], "concerns": []}
TURNS = [{"speaker": "Yaşar" if i % 2 == 0 else "Necdet", "text": "Kaynak notlarındaki gelişmeyi bu açıdan değerlendirebiliriz."} for i in range(12)]


class AudioEditorialTests(unittest.TestCase):
    def test_summary_reads_each_brief_but_no_headline_or_analysis(self):
        data = edition("oyun")
        for i, story in enumerate(data["stories"]):
            story["brief"] = f"Doğrulanmış {i} numaralı gelişme açıklandı."
            story["why"] = "BU ANALİZ SESLENDİRİLMEMELİ."
        text = summary_script(data)
        for story in data["stories"]:
            self.assertIn(story["brief"], text)
            self.assertNotIn(story["title"], text)
            self.assertNotIn(story["why"], text)

    def test_existing_news_falls_back_to_first_factual_sentence_only(self):
        data = edition("teknoloji")
        data["stories"][0]["summary"] = "Yeni sürüm yayımlandı. Sonraki uzun açıklama okunmamalı."
        text = summary_script(data)
        self.assertIn("Yeni sürüm yayımlandı.", text)
        self.assertNotIn("Sonraki uzun açıklama", text)

    def test_rejected_draft_is_repaired_and_checked_again_before_return(self):
        with patch.object(writer, "_request", side_effect=[{"turns": TURNS}, {"turns": TURNS}, REJECTED, {"turns": TURNS}, APPROVED]) as call:
            _, turns = writer.generate([("Haber", "Kaynakta doğrulanmış olgu")])
        self.assertEqual(turns, TURNS)
        self.assertEqual(call.call_count, 5)

    def test_unresolved_fact_problem_blocks_podcast(self):
        with patch.object(writer, "_request", side_effect=[{"turns": TURNS}, {"turns": TURNS}, REJECTED, {"turns": TURNS}, REJECTED]):
            with self.assertRaisesRegex(RuntimeError, "independent evidence"):
                writer.generate([("Haber", "Kaynakta doğrulanmış olgu")])

    def test_editor_failure_never_falls_back_to_unchecked_draft(self):
        with patch.object(writer, "_request", side_effect=[{"turns": TURNS}, RuntimeError("Editor unavailable")]):
            with self.assertRaisesRegex(RuntimeError, "Editor unavailable"):
                writer.generate([("Haber", "Kaynakta doğrulanmış olgu")])

    def test_review_record_binds_exact_final_dialogue(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / "review.json"
            with patch.object(writer, "_request", side_effect=[{"turns": TURNS}, {"turns": TURNS}, APPROVED]):
                writer.generate([("Haber", "Kaynak notu")], audit_path=audit)
            data = read_json(audit)
            self.assertEqual(data["turns_sha256"], writer.dialogue_digest(TURNS))
            changed = copy.deepcopy(TURNS)
            changed[1]["text"] += " Bir ek iddia."
            self.assertNotEqual(data["turns_sha256"], writer.dialogue_digest(changed))

    def test_malformed_approval_is_not_a_pass(self):
        self.assertFalse(writer._approved({"approved": True}))
        self.assertFalse(writer._approved({**APPROVED, "approved": "true"}))
        self.assertFalse(writer._approved({**APPROVED, "concerns": ["It reads headlines"]}))

    def test_yasar_must_open(self):
        turns = copy.deepcopy(TURNS)
        turns[0]["speaker"] = "Necdet"
        with self.assertRaisesRegex(RuntimeError, "Yaşar must open"):
            writer._validate({"turns": turns})
