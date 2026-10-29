import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from pulse.chapters import CHAPTER_RULES, ChapterValidationError, validate_chapters
from scripts.prepare_chapters import (ChapterProposalInvalid, ChapterReviewRejected,
                                     cached_editor, correction_feedback, propose)


class ChapterContractTests(unittest.TestCase):
    def test_shared_browser_server_vectors(self):
        fixture = json.loads(Path('tests/chapter-contract.json').read_text())
        for case in fixture['cases']:
            asset = {**fixture['asset'], **case.get('asset', {})}
            data = {'schema_version': 1, 'reviewed': True, 'audio_sha256': asset['sha256'], 'chapters': case['chapters']}
            with self.subTest(case=case['name']):
                if case['valid']:
                    self.assertIs(validate_chapters(data, asset), data)
                else:
                    with self.assertRaises(ValueError):
                        validate_chapters(data, asset)
        browser_rules = json.loads(subprocess.check_output(['node', '-e',
            "console.log(JSON.stringify(require('./site/assets/listening.js').rules))"], text=True))
        self.assertEqual(browser_rules, CHAPTER_RULES)

    def test_failure_identifies_the_row_and_rule_without_repeating_title_text(self):
        asset = {'sha256': 'a' * 64, 'duration': 30}
        data = {'schema_version': 1, 'reviewed': True, 'audio_sha256': asset['sha256'],
                'chapters': [{'start': 0, 'title': 'Açılış'}, {'start': 0, 'title': 'private-title'}]}
        with self.assertRaises(ChapterValidationError) as caught:
            validate_chapters(data, asset)
        self.assertEqual((caught.exception.index, caught.exception.code), (1, 'start_order'))
        self.assertNotIn('private-title', str(caught.exception))


class ChapterRepairTests(unittest.TestCase):
    def setUp(self):
        self.asset = {'sha256': 'a' * 64, 'duration': 100}
        self.transcript = {'audio_sha256': self.asset['sha256'], 'segments': [
            {'start': 0, 'end': 3.9, 'text': 'Merhaba.'},
            {'start': 4, 'end': 20, 'text': 'İlk haber.'}]}
        self.good = {'chapters': [{'segment_id': 0, 'title': 'Açılış'}, {'segment_id': 1, 'title': 'İlk haber'}]}
        self.bad = copy.deepcopy(self.good)
        self.bad['chapters'][1]['segment_id'] = 0

    def test_short_opening_keeps_both_measured_starts_and_independent_review(self):
        generate = Mock(side_effect=[self.good, {'approved': True}])
        data = propose(self.transcript, self.asset, generate)
        self.assertEqual([r['start'] for r in data['chapters']], [0, 4])
        self.assertEqual(generate.call_count, 2)

    def test_structural_repair_consumes_one_attempt_and_still_requires_review(self):
        generate = Mock(side_effect=[self.bad, self.good, {'approved': True}])
        self.assertTrue(propose(self.transcript, self.asset, generate)['reviewed'])
        self.assertEqual(generate.call_count, 3)
        self.assertIn('previous start', generate.call_args_list[1].args[0])
        self.assertIn('bağımsız denetle', generate.call_args_list[2].args[0])
        repeated = Mock(side_effect=[self.bad, self.bad])
        with self.assertRaises(ChapterProposalInvalid):
            propose(self.transcript, self.asset, repeated)
        self.assertEqual(repeated.call_count, 2)

    def test_semantic_and_structural_failures_share_the_same_repair_budget(self):
        generate = Mock(side_effect=[self.good, {'approved': False, 'reason': 'Wrong topic'}, self.bad])
        with self.assertRaises(ChapterProposalInvalid):
            propose(self.transcript, self.asset, generate)
        self.assertEqual(generate.call_count, 3)
        denied = Mock(side_effect=[self.bad, self.good, {'approved': False, 'reason': 'Wrong topic'}])
        with self.assertRaises(ChapterReviewRejected):
            propose(self.transcript, self.asset, denied)
        self.assertEqual(denied.call_count, 3)

    def test_interrupted_review_reuses_corrected_proposal_after_checkpoint_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[self.bad, self.good, RuntimeError('offline'), {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            saved = []
            generate.on_correction = lambda reason, proposal: saved.append((reason, proposal))
            with self.assertRaisesRegex(RuntimeError, 'offline'):
                propose(self.transcript, self.asset, generate)
            restored = {**self.transcript, 'review_feedback': correction_feedback(*saved[-1])}
            data = propose(restored, self.asset, cached_editor(tmp, provider, 'fixture-model'))
            self.assertTrue(data['reviewed'])
            self.assertEqual(provider.call_count, 4)

    def test_malformed_review_keeps_valid_proposal_for_rechecking(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Mock(side_effect=[self.good, {'approved': 'yes'}, {'approved': True}])
            generate = cached_editor(tmp, provider, 'fixture-model')
            with self.assertRaises(ChapterProposalInvalid):
                propose(self.transcript, self.asset, generate)
            self.assertTrue(propose(self.transcript, self.asset, generate)['reviewed'])
            self.assertEqual(provider.call_count, 3)
