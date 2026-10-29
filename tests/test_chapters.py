import copy
import json
import tempfile
import unittest
from pathlib import Path
from pulse.chapters import load_chapters, validate_chapters


class ChapterValidationTests(unittest.TestCase):
    def setUp(self):
        self.asset = {'sha256': 'a' * 64, 'duration': 120}
        self.data = {'schema_version': 1, 'reviewed': True,
                     'audio_sha256': 'a' * 64,
                     'chapters': [{'start': 0, 'title': 'Açılış'},
                                  {'start': 12.4, 'title': 'Uzun bir konu başlığı'}]}

    def test_valid_final_audio_sidecar(self):
        self.assertEqual(validate_chapters(self.data, self.asset), self.data)

    def test_rejects_changed_audio_and_unreviewed_data(self):
        for update in ({'reviewed': False}, {'audio_sha256': 'b' * 64}):
            with self.assertRaises(ValueError):
                validate_chapters({**self.data, **update}, self.asset)

    def test_rejects_invalid_chapter_times_titles_and_order(self):
        for value in (-1, 120, float('nan'), float('inf'), True, '12', 0):
            data = copy.deepcopy(self.data)
            data['chapters'][1]['start'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_chapters(data, self.asset)
        for title in ('', ' ', 'a' * 241, 'bad\ntext'):
            data = copy.deepcopy(self.data)
            data['chapters'][1]['title'] = title
            with self.assertRaises(ValueError):
                validate_chapters(data, self.asset)

    def test_optional_missing_corrupt_stale_or_oversize_files_do_not_block_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(load_chapters(folder, self.asset))
            path = Path(folder) / ('a' * 64 + '.json')
            for body in ('{bad', 'x' * 65537, json.dumps({**self.data, 'reviewed': False})):
                path.write_text(body)
                self.assertIsNone(load_chapters(folder, self.asset))
            path.write_text(json.dumps(self.data))
            self.assertEqual(load_chapters(folder, self.asset), self.data)
            self.assertIsNone(load_chapters(folder, {'sha256': '../../bad'}))
