"""Streaming limits remain enforced even with missing or dishonest HTTP lengths."""
import unittest
from unittest.mock import Mock, patch

from pulse.archive import ARCHIVE_IMAGE_MAX_BYTES, fetch_archive_image
from pulse.source_media import SourceTooLarge, fetch_public


class SourceBoundsTests(unittest.TestCase):
    def response(self, chunks):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.is_redirect = False
        response.headers = {'Content-Type': 'image/png', 'Content-Length': '1'}
        response.iter_content.return_value = iter(chunks)
        return response

    def test_exact_limit_allowed(self):
        response = self.response([b'12', b'34'])
        with patch('pulse.source_media.public_url'), patch('pulse.source_media.requests.get', return_value=response):
            self.assertEqual(fetch_public('https://example.test/x', limit=4)[0], b'1234')

    def test_over_limit_stops_stream_and_closes_response(self):
        response = self.response([b'12', b'345', b'never consumed'])
        with patch('pulse.source_media.public_url'), patch('pulse.source_media.requests.get', return_value=response):
            with self.assertRaises(SourceTooLarge):
                fetch_public('https://example.test/x', limit=4)
        self.assertEqual(next(response.iter_content.return_value), b'never consumed')
        response.__exit__.assert_called_once()

    def test_only_archive_uses_larger_budget(self):
        with patch('pulse.archive.fetch_public', return_value=(b'picture', 'image/png')) as fetch:
            self.assertEqual(fetch_archive_image('https://example.test/x'), (b'picture', 'image/png'))
            fetch.assert_called_once_with('https://example.test/x', limit=ARCHIVE_IMAGE_MAX_BYTES)
        self.assertEqual(fetch_public.__kwdefaults__['limit'], 8_000_000)
