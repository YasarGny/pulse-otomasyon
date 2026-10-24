"""Verify actual turn/source coverage without a hard duration quota or real API."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pulse_podcast_writer as writer
from pulse import podcast_depth as depth
from pulse.podcast_plan import catalogue, verify_audit, digest
from pulse.profile import DAILY_PROFILE
from pulse.publication import read_json, write_json, turkish_date
from test_podcast_plans import STORIES, META, PLAN, TURNS, RESULT, APPROVED


def approval():
    review = copy.deepcopy(APPROVED)
    review['discussion_review'] = {'schema_version': 1, 'topics': [{
        'topic_index': 0, 'covered_story_ids': ['a', 'b'], 'turn_ids': [0, 1, 2, 3],
        'treatment': 'discussion', 'exchange': [0, 1, 2],
        'finding': 'Yaşar kararın etkisini soruyor; Necdet tercihin gerekçesini açıklıyor ve belirsizlik ele alınıyor.'}],
        'budget': {'appropriate': True,
                   'reason': 'Üç haberli sakin gündemde aynı açıklamanın etkisi ve kaynak sınırları birlikte değerlendirildi.',
                   'short_reason': 'İki haber aynı sınırlı resmi duyurudan geliyor; üçüncü haber yalnız küçük bir güncelleme açıklıyor.',
                   'limited_story_ids': ['a', 'b', 'c']}}
    return review


def generate(**kwargs):
    kwargs.setdefault('date', '25 Ekim 2026')
    kwargs.setdefault('publish_date', '2026-10-25')
    return writer.generate(STORIES, section=kwargs.pop('section', 'oyun'),
                           publication_profile=DAILY_PROFILE, require_plan=True,
                           story_catalogue=META, long_form=True, **kwargs)


class PodcastDepthTests(unittest.TestCase):
    def test_policy_uses_canonical_and_turkish_dates_without_changing_sealed_issues(self):
        for date, expected in [('2026-10-24', False), ('24 Ekim 2026', False),
                               ('2026-10-25', True), ('25 Ekim 2026', True),
                               ('25.10.2026', True), ('01.11.2026', True)]:
            self.assertEqual(depth.enabled(date), expected)
        with self.assertRaises(ValueError):
            depth.enabled('2026-02-31')

    def test_short_source_bound_conversation_is_allowed_without_word_padding(self):
        result = depth.validate_review(approval(), PLAN, TURNS, catalogue(STORIES, META))
        self.assertEqual(result['topics'][0]['exchange'], [0, 1, 2])
        self.assertTrue(depth.metrics(TURNS)['short_review_required'])

    def test_short_check_is_review_guidance_not_measured_audio_or_minimum_length(self):
        for words, needed in [(1799, True), (1800, False), (2500, False)]:
            metric = depth.metrics([{'text': 'x ' * words}])
            self.assertEqual(metric['short_review_required'], needed)
            self.assertEqual(metric['words'], words)
            self.assertTrue(metric['duration_is_estimate'])
        turns = copy.deepcopy(TURNS)
        for turn in turns:
            turn['text'] = 'x ' * 500  # Structural fixture only, no audio or semantic approval.
        review = approval()
        review['discussion_review']['budget'].update(short_reason=None, limited_story_ids=[])
        depth.validate_review(review, PLAN, turns, catalogue(STORIES, META))

    def test_review_cannot_approve_a_short_dialogue_without_source_justification(self):
        for change in ({'short_reason': None}, {'limited_story_ids': []},
                       {'limited_story_ids': ['unknown']}, {'short_reason': 'Yeterli.'},
                       {'limited_story_ids': ['a', 'a']}):
            review = approval()
            review['discussion_review']['budget'].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, 'source-bound editorial justification'):
                depth.validate_review(review, PLAN, TURNS, catalogue(STORIES, META))
        review = approval()
        review['discussion_review']['budget']['appropriate'] = False
        with self.assertRaisesRegex(RuntimeError, 'scope/depth budget assessment'):
            depth.validate_review(review, PLAN, TURNS, catalogue(STORIES, META))

    def test_independent_review_must_reference_actual_turns_and_actual_coverage(self):
        cases = [
            {'covered_story_ids': ['a']}, {'covered_story_ids': ['a', 'unknown']},
            {'covered_story_ids': ['a', 'a']}, {'turn_ids': [0, 999]},
            {'turn_ids': [True, 3]}, {'turn_ids': [2, 1, 0]}, {'exchange': [0, 0, 2]},
            {'exchange': [0, 1, 999]}, {'exchange': [True, 1, 2]},
            {'treatment': 'brief', 'exchange': None}, {'finding': ''}, {'topic_index': 2}]
        for change in cases:
            review = approval()
            review['discussion_review']['topics'][0].update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                depth.validate_review(review, PLAN, TURNS, catalogue(STORIES, META))
        turns = copy.deepcopy(TURNS)
        turns[1]['speaker'] = 'Yaşar'
        with self.assertRaisesRegex(RuntimeError, 'two-host response'):
            depth.validate_review(approval(), PLAN, turns, catalogue(STORIES, META))

    def test_briefs_and_returning_to_a_topic_do_not_require_a_linear_news_order(self):
        plan = copy.deepcopy(PLAN)
        plan['omitted'] = []
        plan['topics'].append({'story_ids': ['c'], 'title': 'Küçük güncelleme',
                               'reason': 'Kaynağın sınırlı yeni ayrıntısı.', 'questions': ['Ne değişti?']})
        turns = copy.deepcopy(TURNS) + [{'speaker': 'Yaşar', 'text': 'Küçük güncelleme açıklandı.'},
                                       {'speaker': 'Necdet', 'text': 'Önceki konuya dönersek kaynak sınırı tercih açısından önemli.'}]
        review = approval()
        review['discussion_review']['topics'][0]['turn_ids'].append(5)
        review['discussion_review']['topics'].append({'topic_index': 1, 'covered_story_ids': ['c'],
            'turn_ids': [4], 'treatment': 'brief', 'exchange': None,
            'finding': 'Kaynak yalnız küçük değişikliği açıklıyor, yeni bir iddia veya yapay tartışma eklenmiyor.'})
        depth.validate_review(review, plan, turns, catalogue(STORIES, META))
        for change in ({'turn_ids': [3, 4]}, {'topic_index': 0}):
            bad = copy.deepcopy(review)
            bad['discussion_review']['topics'][1].update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                depth.validate_review(bad, plan, turns, catalogue(STORIES, META))

    def test_both_programs_keep_the_existing_three_calls_and_exact_approval_reuse(self):
        for section in ('teknoloji', 'oyun'):
            with self.subTest(section=section), tempfile.TemporaryDirectory() as tmp:
                audit = Path(tmp) / 'podcast-review.json'
                with patch.object(writer, '_request', side_effect=copy.deepcopy([RESULT, RESULT, approval()])) as request:
                    generate(section=section, audit_path=audit)
                self.assertEqual(request.call_count, 3)
                for call in request.call_args_list:
                    system = call.args[0]['system_instruction']['parts'][0]['text']
                    self.assertNotIn('iki-üç güçlü konu yeter', system)
                    self.assertIn('15–20', system)
                editor = request.call_args_list[1].args[0]['contents'][0]['parts'][0]['text']
                self.assertIn('Taslak yerel ölçümü', editor)
                reviewer = request.call_args_list[2].args[0]
                self.assertIn('discussion_review', reviewer['system_instruction']['parts'][0]['text'])
                self.assertIn('short_review_required', reviewer['contents'][0]['parts'][0]['text'])
                saved = read_json(audit)
                verify_audit(saved, catalogue(STORIES, META), date='2026-10-25', turns=TURNS)
                self.assertTrue(saved['discussion_metrics']['short_review_required'])
                with patch.object(writer, '_request') as repeat:
                    generate(section=section, audit_path=audit)
                repeat.assert_not_called()

    def test_boolean_only_approval_cannot_bypass_new_review_and_repair_is_bounded(self):
        with patch.object(writer, '_request', side_effect=copy.deepcopy([RESULT, RESULT, APPROVED, RESULT, APPROVED])) as request:
            with self.assertRaisesRegex(RuntimeError, 'source/turn-bound assessment'):
                generate()
        self.assertEqual(request.call_count, 5)

    def test_specific_missing_depth_is_repaired_once_inside_the_existing_cycle(self):
        bad = approval()
        bad['discussion_review']['budget']['short_reason'] = None
        with patch.object(writer, '_request', side_effect=copy.deepcopy([RESULT, RESULT, bad, RESULT, approval()])) as request:
            generate()
        self.assertEqual(request.call_count, 5)
        repair = request.call_args_list[3].args[0]['contents'][0]['parts'][0]['text']
        self.assertIn('source-bound editorial justification', repair)

    def test_audit_cannot_rebind_report_to_another_dialogue_or_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / 'podcast-review.json'
            with patch.object(writer, '_request', side_effect=copy.deepcopy([RESULT, RESULT, approval()])):
                generate(audit_path=audit)
            saved = read_json(audit)
            changed = copy.deepcopy(TURNS)
            changed[0]['text'] = 'Başka diyalog.'
            with self.assertRaisesRegex(RuntimeError, 'final dialogue'):
                verify_audit(saved, catalogue(STORIES, META), date='2026-10-25', turns=changed)
            saved['review']['discussion_review']['topics'][0]['exchange'] = [0, 2, 3]
            with self.assertRaisesRegex(RuntimeError, 'final dialogue'):
                verify_audit(saved, catalogue(STORIES, META), date='2026-10-25', turns=TURNS)

    def test_pipeline_checks_new_review_before_any_paid_audio_for_both_programs(self):
        from pulse.pipeline import generate_audio
        for section in ('teknoloji', 'oyun'):
            data = {'section': section, 'publication_profile': DAILY_PROFILE, 'publish_date': '2026-10-25',
                    'issue': 10, 'date': turkish_date('2026-10-25'), 'stories': [
                        {**row, 'summary': summary, 'brief': 'Kaynağın doğruladığı gelişme.',
                         'source_url': 'https://example.test/' + row['id']}
                        for row, (_, summary) in zip(META, STORIES)]}
            with self.subTest(section=section), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with patch('pulse.pipeline.valid_audio', return_value=True), \
                     patch('pulse.pipeline.audio_info', return_value={'duration': 60, 'bytes': 40000, 'sha256': 'f' * 64}), \
                     patch('edge_tts.Communicate') as edge, patch('pulse_podcast_audio.render') as voice, \
                     patch.object(writer, '_request', side_effect=copy.deepcopy([RESULT, RESULT, approval()])) as request:
                    self.assertTrue(generate_audio(root, copy.deepcopy(data))['ready'])
                    self.assertEqual(request.call_count, 3)
                    audit = root / section / 'podcast-review.json'
                    saved = read_json(audit)
                    saved['review'].pop('discussion_review')
                    saved['review_sha256'] = digest(saved['review'])
                    write_json(audit, saved)
                    with patch('pulse.pipeline.valid_audio', side_effect=lambda path, _: path.name == 'summary.mp3'):
                        with self.assertRaisesRegex(RuntimeError, 'source/turn-bound assessment'):
                            generate_audio(root, copy.deepcopy(data))
                    edge.assert_not_called()
                    voice.assert_not_called()
