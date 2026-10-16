import datetime as dt
import unittest
from pulse.schedule import build_available, phase
from pulse.publication import not_before
from fixtures import DATE

class ScheduledStagesTests(unittest.TestCase):
    def test_six_only_prepares_and_other_runs_produce(self):
        self.assertEqual(phase('schedule','0 3 * * *'),'prepare')
        self.assertEqual(phase('schedule','15 3 * * *'),'produce')
        self.assertEqual(phase('workflow_dispatch','0 3 * * *'),'produce')

    def test_ready_checkpoint_waits_without_building_early(self):
        self.assertFalse(build_available(DATE,not_before(DATE)-dt.timedelta(minutes=45)))
        self.assertTrue(build_available(DATE,not_before(DATE)))

    def test_overnight_window_still_ends_at_exact_next_six(self):
        self.assertTrue(build_available(DATE,not_before(DATE)+dt.timedelta(hours=22,minutes=29)))
        with self.assertRaises(ValueError):build_available(DATE,not_before(DATE)+dt.timedelta(hours=22,minutes=30))
