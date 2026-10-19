import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.pipeline import run
from pulse.publication import write_json


class ResearchRefreshTests(unittest.TestCase):
    def check(self, age, completed, expected):
        at = dt.datetime(2026, 10, 19, 5, tzinfo=dt.timezone.utc)
        old = {'publish_date': '2026-10-19', 'researched_at': (at - dt.timedelta(minutes=age)).isoformat(),
               'sections': {'teknoloji': [{'id': 'old-tech'}], 'oyun': [{'id': 'old-game'}]}}
        new = {'publish_date': '2026-10-19', 'researched_at': at.isoformat(),
               'sections': {'teknoloji': [{'id': 'new-tech'}], 'oyun': [{'id': 'new-game'}]}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / '2026-10-19'
            write_json(root / 'research.json', old)
            for section in completed:
                write_json(root / (section + '.json'), {})
            def refresh(date, path):
                write_json(path, new)
                return new
            with patch('pulse.pipeline.now', return_value=at), \
                 patch('pulse.pipeline.research', side_effect=refresh) as fetch, \
                 patch('pulse.pipeline.exclude_published', side_effect=RuntimeError('Stop before paid generation')) as exclude:
                with self.assertRaisesRegex(RuntimeError, 'Stop before paid generation'):
                    run(tmp, '2026-10-19', '2026-10-16')
                self.assertEqual(fetch.call_count, expected)
                data = exclude.call_args.args[0]
                for section in ('teknoloji', 'oyun'):
                    expected_rows = old['sections'][section] if section in completed or not expected else new['sections'][section]
                    self.assertEqual(data['sections'][section], expected_rows)

    def test_old_incomplete_research_is_refreshed(self):
        self.check(45, [], 1)

    def test_completed_category_keeps_its_original_evidence(self):
        self.check(45, ['teknoloji'], 1)

    def test_recent_snapshot_is_not_repeatedly_fetched(self):
        self.check(20, [], 0)

    def test_complete_editions_do_not_refresh_research(self):
        self.check(45, ['teknoloji', 'oyun'], 0)
