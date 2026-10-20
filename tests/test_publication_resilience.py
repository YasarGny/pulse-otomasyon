import unittest
from unittest.mock import Mock, patch
import requests
from pulse.editorial import gemini
from pulse.verify_site import wait_for_site, SiteVerificationError


class PublicationResilienceTests(unittest.TestCase):
    def response(self, text):
        response = Mock(ok=True)
        response.json.return_value = {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':text}]}}]}
        return response

    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.usage.record')
    @patch('pulse.editorial.requests.post')
    def test_malformed_json_retries_once_and_accounts_for_both_responses(self, post, usage):
        post.side_effect = [self.response('{"stories":['),self.response('{"stories":[]}')]
        self.assertEqual(gemini('original evidence',system='grounded facts'), {'stories':[]})
        self.assertEqual(post.call_count,2)
        self.assertEqual(post.call_args_list[0],post.call_args_list[1])
        self.assertEqual(usage.call_count,2)

    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.usage.record')
    @patch('pulse.editorial.requests.post')
    def test_second_malformed_response_still_blocks_publication(self, post, usage):
        post.return_value = self.response('{broken')
        with self.assertRaisesRegex(ValueError,'invalid JSON after two attempts'):
            gemini('evidence')
        self.assertEqual(post.call_count,2)

    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.editorial.requests.post')
    def test_authentication_errors_are_not_retried(self, post):
        post.return_value = Mock(ok=False,status_code=401)
        with self.assertRaisesRegex(RuntimeError,'HTTP 401'):
            gemini('evidence')
        post.assert_called_once()

    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.usage.record')
    @patch('pulse.editorial.requests.post')
    def test_plain_text_does_not_request_a_second_response(self, post, usage):
        post.return_value = self.response('Natural dialogue')
        self.assertEqual(gemini('evidence',json_output=False),'Natural dialogue')
        post.assert_called_once()

    @patch('pulse.verify_site.check_site')
    @patch('pulse.verify_site.check_assets')
    def test_stale_assets_are_reported_before_downloading_all_audio(self, assets, site):
        assets.side_effect = SiteVerificationError('Pages asset has not updated: site.js')
        with self.assertRaisesRegex(RuntimeError,'site.js'):
            wait_for_site({}, timeout=0, tree='synthetic-tree')
        site.assert_not_called()

    @patch('pulse.verify_site.check_site')
    def test_transport_errors_do_not_expose_raw_urls(self, site):
        site.side_effect = requests.ConnectionError('https://private.test/?secret=example')
        with self.assertRaises(RuntimeError) as failure:
            wait_for_site({}, timeout=0)
        self.assertIn('ConnectionError',str(failure.exception))
        self.assertNotIn('secret',str(failure.exception))


    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.editorial.time.sleep')
    @patch('pulse.usage.record')
    @patch('pulse.editorial.requests.post')
    def test_transient_editorial_failure_recovers_without_restarting_the_pipeline(self, post, usage, sleep):
        bad=Mock(ok=False,status_code=503,headers={'Retry-After':'5'})
        post.side_effect=[bad,self.response('{"stories":[]}')]
        self.assertEqual(gemini('evidence'),{'stories':[]})
        self.assertEqual(post.call_count,2);sleep.assert_called_once_with(5)
        self.assertEqual(usage.call_count,1)

    @patch.dict('os.environ', {'GEMINI_API_KEY':'synthetic-test-key'})
    @patch('pulse.editorial.time.sleep')
    @patch('pulse.editorial.requests.post')
    def test_editorial_network_retry_is_bounded_and_sanitized(self, post, sleep):
        post.side_effect=requests.ConnectionError('private credential-bearing URL')
        with self.assertRaisesRegex(RuntimeError,'^Gemini editorial connection unavailable$'):
            gemini('evidence')
        self.assertEqual(post.call_count,3);self.assertEqual(sleep.call_count,2)
