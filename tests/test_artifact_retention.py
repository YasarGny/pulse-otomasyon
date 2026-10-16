import unittest
from scripts.cleanup_artifacts import obsolete

class ArtifactRetentionTests(unittest.TestCase):
    def test_current_site_latest_two_day_states_and_two_browser_proofs_remain(self):
        names=['unrelated-backup','pulse-site-9','pulse-site-8','pulse-state-2026-10-16-9-1','pulse-state-2026-10-16-8-1','pulse-state-2026-10-15-7-1','pulse-state-2026-10-14-6-1','pulse-browser-results','pulse-browser-results','pulse-browser-results','pulse-state-2026-10-17-10-1']
        artifacts=[dict(id=i,name=name,created_at=f'{100-i:03d}',expired=False) for i,name in enumerate(names)]
        self.assertEqual(set(obsolete(artifacts,'2026-10-16',9)),{2,4,6,9})

    def test_unrecognized_or_expired_artifact_is_never_deleted(self):
        artifacts=[dict(id=1,name='pulse-site-secret',created_at='1'),dict(id=2,name='pulse-site-1',created_at='2',expired=True)]
        self.assertEqual(obsolete(artifacts,'2026-10-16',9),[])
