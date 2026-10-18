import hashlib
import unittest
from pulse.source_history import SourceHistory, canonical_url, SIZE


class SourceHistoryTests(unittest.TestCase):
    def test_tracking_aliases_and_fragment_never_bypass_history(self):
        history = SourceHistory()
        history.add('http://www.Example.com/story/?id=42&utm_source=rss#top')
        restored = SourceHistory(history.record())
        self.assertTrue(restored.contains('https://example.com/story?utm_campaign=new&id=42&fbclid=ad'))
        self.assertFalse(restored.contains('https://example.com/story?id=43'))
        self.assertFalse(restored.contains('https://example.com/Story?id=42'))
        self.assertEqual(canonical_url('https://example.com/?b=2&a=1'), 'https://example.com/?a=1&b=2')

    def test_legacy_fingerprints_survive_migration(self):
        url = 'https://example.com/a'
        legacy = {'teknoloji': [hashlib.sha256(url.encode()).hexdigest()], 'oyun': []}
        self.assertTrue(SourceHistory(SourceHistory(legacy).record()).contains(url))

    def test_storage_is_fixed_size_and_contains_no_news_text(self):
        history = SourceHistory()
        for i in range(10000):
            history.add('https://example.com/article/' + str(i))
        record = history.record()
        self.assertLess(len(record['bits']), 700000)
        self.assertNotIn('example.com', str(record))
        restored = SourceHistory(record)
        self.assertEqual(len(restored.data), SIZE)
        for i in (0, 501, 9999):
            self.assertTrue(restored.contains('https://example.com/article/' + str(i)))

    def test_corrupt_or_saturated_history_fails_without_resetting(self):
        record = SourceHistory().record()
        record['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            SourceHistory(record)
        for invalid in ({}, {'teknoloji': [], 'oyun': ['not-a-hash']}):
            with self.assertRaises(ValueError):
                SourceHistory(invalid)
        history = SourceHistory()
        history.data[:] = b'\xff' * SIZE
        with self.assertRaises(ValueError):
            history.record()
