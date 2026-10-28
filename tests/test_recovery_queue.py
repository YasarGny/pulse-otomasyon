"""A skipped completion event must not occupy the single pending publisher slot."""
from pathlib import Path
import unittest


class RecoveryQueueTests(unittest.TestCase):
    def test_conditional_recovery_jobs_join_queue_only_after_eligibility_check(self):
        for name, job in [('complete-chapters.yml', 'complete'), ('publish-ready.yml', 'publish')]:
            with self.subTest(workflow=name):
                text = (Path('.github/workflows') / name).read_text()
                header, jobs = text.split('\njobs:\n', 1)
                self.assertNotIn('\nconcurrency:', header)
                self.assertIn(f'  {job}:\n', jobs)
                self.assertIn('    if:', jobs)
                self.assertIn('    concurrency:\n      group: pulse-github-daily\n      cancel-in-progress: false', jobs)
                self.assertIn('github.event.workflow_run.head_repository.full_name == github.repository', jobs)

    def test_failed_daily_run_has_an_audio_preserving_recovery_route(self):
        text = Path('.github/workflows/publish-ready.yml').read_text()
        self.assertIn("workflows: ['PULSE GitHub daily publication']", text)
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", text)
        self.assertIn('from pulse.ready_recovery import restore_ready', text)
        self.assertIn("allowed_events=('workflow_dispatch', 'workflow_run')", text)
        self.assertIn("COMPLETE_CHAPTERS: ${{ inputs.complete_chapters == true || github.event_name == 'workflow_run' }}", text)
        self.assertNotIn('python -m pulse.pipeline', text)
        self.assertIn("needs.inspect_failure.outputs.recoverable == 'true'", text)
