"""Transient Drive failures must recover without duplicating uploaded archives."""
import unittest
from unittest.mock import Mock, patch

import requests

from pulse.drive_backup import Drive
from pulse.daily_archive import retire_older


class DriveRetryTests(unittest.TestCase):
    def setUp(self):
        self.drive = Drive.__new__(Drive)
        self.drive.session = Mock()
        self.sleep = patch('pulse.drive_backup.time.sleep').start()
        patch('pulse.drive_backup.random.uniform', return_value=0).start()
        self.addCleanup(patch.stopall)

    def response(self, status, headers=None):
        return Mock(ok=200 <= status < 300, status_code=status, headers=headers or {})

    def test_temporary_server_failure_recovers_during_retirement(self):
        current = {'id': 'new', 'appProperties': {'release_id': 'today'}}
        older = {'id': 'old', 'appProperties': {'release_id': 'yesterday'}}
        self.drive.daily_files = Mock(return_value=[current, older])
        success, failure = self.response(200), self.response(500)
        self.drive.session.request.side_effect = [success, failure, success]
        manifest = {'release_id': 'today', 'publish_date': '2026-10-19',
                    'validated_at': '2026-10-19T04:30:00+00:00'}
        receipt = {'file_id': 'new', 'release_id': 'today', 'verified': True}
        self.assertEqual(retire_older(self.drive, 'parent', manifest, receipt), receipt)
        calls = self.drive.session.request.call_args_list
        self.assertEqual(calls[1], calls[2])
        self.assertEqual(calls[2].kwargs['json'], {'trashed': True})
        failure.close.assert_called_once()
        self.sleep.assert_called_once_with(1)

    def test_read_requests_retry_connection_failures_and_rate_limits(self):
        throttled, success = self.response(429, {'Retry-After': '7'}), self.response(200)
        self.drive.session.request.side_effect = [requests.Timeout('private URL'), throttled, success]
        self.assertIs(self.drive.request('GET'), success)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [1, 7])

    def test_retry_budget_is_bounded_and_failure_stays_closed(self):
        self.drive.session.request.return_value = self.response(503)
        with self.assertRaisesRegex(RuntimeError, 'HTTP 503'):
            self.drive.request('PATCH', json={'trashed': True})
        self.assertEqual(self.drive.session.request.call_count, 5)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [1, 2, 4, 8])

    def test_creation_and_upload_are_not_replayed(self):
        for method in ('POST', 'PUT'):
            with self.subTest(method=method):
                self.drive.session.request.reset_mock()
                self.drive.session.request.return_value = self.response(500)
                with self.assertRaisesRegex(RuntimeError, 'HTTP 500'):
                    self.drive.request(method)
                self.drive.session.request.assert_called_once()
        self.sleep.assert_not_called()

    def test_permanent_errors_are_not_retried(self):
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                self.drive.session.request.reset_mock()
                self.drive.session.request.return_value = self.response(status)
                with self.assertRaisesRegex(RuntimeError, 'HTTP ' + str(status)):
                    self.drive.request('GET')
                self.drive.session.request.assert_called_once()
        self.sleep.assert_not_called()

    def test_retry_after_cannot_create_unbounded_waits(self):
        for header in ('999999', '-1', 'invalid', 'NaN', 'Infinity'):
            with self.subTest(header=header):
                self.sleep.reset_mock()
                self.drive.session.request.side_effect = [self.response(503, {'Retry-After': header}), self.response(200)]
                self.drive.request('PATCH', json={'name': 'archive.zip'})
                self.sleep.assert_called_once_with(1)

    def test_exhausted_network_errors_do_not_expose_credentials(self):
        self.drive.session.request.side_effect = requests.ConnectionError('secret-bearing URL')
        with self.assertRaisesRegex(RuntimeError, '^Drive operation failed: connection unavailable$'):
            self.drive.request('GET')
        self.assertEqual(self.drive.session.request.call_count, 5)
