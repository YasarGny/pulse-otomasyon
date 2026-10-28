import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse.publication import write_json
from pulse.ready_recovery import restore_ready


class ReadyRecoveryTests(unittest.TestCase):
    def test_missing_checkpoint_defers_automatic_recovery_but_manual_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pulse.ready_recovery.restore', return_value=False):
            self.assertIsNone(restore_ready('owner/repo', '2026-10-28', tmp, automatic=True))
            with self.assertRaisesRegex(ValueError, 'No trusted'):
                restore_ready('owner/repo', '2026-10-28', tmp)

    def test_partial_checkpoint_cannot_be_promoted_to_ready(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pulse.ready_recovery.restore', return_value=True):
            self.assertIsNone(restore_ready('owner/repo', '2026-10-28', tmp, automatic=True))
            write_json(Path(tmp) / '2026-10-28/release.json', {'publish_date': '2026-10-28', 'status': 'preparing'})
            self.assertIsNone(restore_ready('owner/repo', '2026-10-28', tmp, automatic=True))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                restore_ready('owner/repo', '2026-10-28', tmp)

    def test_stale_date_is_rejected_even_during_automatic_recovery(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pulse.ready_recovery.restore', return_value=True):
            write_json(Path(tmp) / '2026-10-28/release.json', {'publish_date': '2026-10-27', 'status': 'ready'})
            with self.assertRaisesRegex(ValueError, 'date mismatch'):
                restore_ready('owner/repo', '2026-10-28', tmp, automatic=True)

    def test_ready_source_is_returned_without_modifying_audio_or_identity(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pulse.ready_recovery.restore', return_value=True) as restore:
            path = Path(tmp) / '2026-10-28/release.json'
            write_json(path, {'publish_date': '2026-10-28', 'status': 'ready', 'release_id': 'immutable-fixture'})
            audio = path.parent / 'existing.mp3'
            audio.write_bytes(b'existing audio fixture')
            before = path.read_bytes(), audio.read_bytes()
            self.assertEqual(restore_ready('owner/repo', '2026-10-28', tmp), path.parent)
            self.assertEqual((path.read_bytes(), audio.read_bytes()), before)
            restore.assert_called_once_with('owner/repo', '2026-10-28', tmp)
