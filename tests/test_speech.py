"""Pronunciation is a copy for synthesis, not an editorial rewrite."""

import copy
import unittest
from pulse.speech import cardinal, pronunciation, spoken_turns, LEXICON_SHA256
from pulse.editorial import summary_script
from fixtures import edition


class SpeechTests(unittest.TestCase):
    def test_brand_and_common_technology_game_names_have_reviewable_spoken_forms(self):
        self.assertEqual(
            pronunciation("PULSE, OpenAI ve NVIDIA; Steam Deck, Xbox, Knight Online."),
            "Pals, Oupın Ey Ay ve Envidya; Stim Dek, Eks Boks, Nayt Onlayn.",
        )
        self.assertEqual(pronunciation("GOG Preservation Program"), "Gog Preservation Program")
        self.assertEqual(len(LEXICON_SHA256), 64)

    def test_longest_match_word_boundaries_and_apostrophes(self):
        self.assertEqual(pronunciation("Pulse pulse PULSE"), "Pals Pals Pals")
        self.assertEqual(
            pronunciation("OpenAI'ın ChatGPT'si; STEAM DECK. PULSE'ta."),
            "Oupın Ey Ay'ın Çet Ci Pi Ti'si; Stim Dek. Pals'ta.",
        )
        self.assertEqual(
            pronunciation("Impulsea OpenAIs Steamship"), "Impulsea OpenAIs Steamship"
        )

    def test_unknown_names_identifiers_source_facts_and_product_versions_are_preserved(
        self,
    ):
        text = "YeniFirma QTX-003, GPT-5 ve 3,5 milyon kullanıcı. https://example.com/PULSE/AI?name=Steam test@pulse.ai `OpenAI API`"
        result = pronunciation(text)
        self.assertIn("YeniFirma QTX-003", result)
        self.assertIn("Ci Pi Ti-5 ve 3,5 milyon", result)
        for token in [
            "https://example.com/PULSE/AI?name=Steam",
            "test@pulse.ai",
            "`OpenAI API`",
        ]:
            self.assertIn(token, result)

    def test_zero_padding_fallback_is_limited_to_spoken_issue_labels(self):
        self.assertEqual(
            pronunciation("Sayı 003, bölüm 012. Model 003, 001 adet."),
            "Sayı üç, bölüm on iki. Model 003, 001 adet.",
        )
        for number, words in [
            (1, "bir"),
            (103, "yüz üç"),
            (1000, "bin"),
            (2026, "iki bin yirmi altı"),
        ]:
            self.assertEqual(cardinal(number), words)

    def test_reviewed_turns_and_speaker_identity_are_not_mutated(self):
        original = [
            {"speaker": "Yaşar", "text": "PULSE ve OpenAI konuşalım."},
            {"speaker": "Necdet", "text": "Steam Deck hakkında kaynak ne diyor?"},
        ]
        before = copy.deepcopy(original)
        result = spoken_turns(original)
        self.assertEqual(original, before)
        self.assertEqual(
            [t["speaker"] for t in result], [t["speaker"] for t in original]
        )
        self.assertNotEqual(result, original)
        self.assertIn("Pals", result[0]["text"])

    def test_summary_uses_date_identity_and_never_reads_issue_numbers_or_analysis(self):
        data = edition("teknoloji")
        data["issue"] = 3
        text = summary_script(data)
        self.assertIn(data["date"], text)
        self.assertNotIn("003", text)
        self.assertNotIn("sayı", text.lower())
        for story in data["stories"]:
            self.assertNotIn(story["why"], text)
