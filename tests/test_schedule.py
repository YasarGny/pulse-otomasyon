import datetime as dt
import unittest
from pulse.schedule import build_available, phase
from pulse.publication import not_before
from fixtures import DATE

class ScheduledStagesTests(unittest.TestCase):
    def test_first_and_backup_runs_produce_without_a_second_cron_dependency(self):
        self.assertEqual(phase('schedule','0 3 * * *'),'produce')
        self.assertEqual(phase('schedule','15 3 * * *'),'produce')
        self.assertEqual(phase('workflow_dispatch','0 3 * * *'),'produce')

    def test_ready_checkpoint_waits_without_building_early(self):
        self.assertFalse(build_available(DATE,not_before(DATE)-dt.timedelta(minutes=45)))
        self.assertTrue(build_available(DATE,not_before(DATE)))

    def test_overnight_window_still_ends_at_exact_next_six(self):
        self.assertTrue(build_available(DATE,not_before(DATE)+dt.timedelta(hours=22,minutes=29)))
        with self.assertRaises(ValueError):build_available(DATE,not_before(DATE)+dt.timedelta(hours=22,minutes=30))

    def test_late_recovery_does_not_generate_an_already_ready_issue(self):
        ready={'status':'ready','publish_date':DATE}
        for cron in ('15 3 * * *','30 5 * * *','0 6 * * *'):
            self.assertEqual(phase('schedule',cron,ready,DATE),'complete')
        self.assertEqual(phase('workflow_dispatch','',ready,DATE),'produce')
        self.assertEqual(phase('schedule','30 5 * * *',{'status':'preparing','publish_date':DATE},DATE),'produce')
        self.assertEqual(phase('schedule','30 5 * * *',{'status':'ready','publish_date':'2000-01-01'},DATE),'produce')
