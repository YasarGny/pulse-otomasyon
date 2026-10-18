import tempfile
import unittest
from pathlib import Path
from fixtures import ready_release, tone
from pulse.episode_catalog import catalog
from pulse.publication import read_json


class EpisodeCatalogTests(unittest.TestCase):
    def test_only_two_latest_verified_dates_and_no_broken_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = tone(root / 'tone.mp3')
            previous = root / 'published'
            for date in ('2026-10-16', '2026-10-17'):
                ready_release(previous / 'releases' / date, audio, date=date)
            current = root / 'current'
            ready_release(current, audio, date='2026-10-18')
            data = catalog(current, previous)
            self.assertEqual([e['publish_date'] for e in data['episodes']],
                             ['2026-10-18', '2026-10-18', '2026-10-17', '2026-10-17'])
            for section in ('teknoloji', 'oyun'):
                path = previous / 'releases/2026-10-17' / section / 'podcast.mp3'
                path.write_bytes(b'not an mp3')
            data = catalog(current, previous)
            self.assertNotIn('2026-10-17', [e['publish_date'] for e in data['episodes']])
            self.assertIn('2026-10-18', [e['publish_date'] for e in data['episodes']])
