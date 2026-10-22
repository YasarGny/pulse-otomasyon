import copy
import unittest
from unittest.mock import patch

from pulse.editorial import checked_selection, create_edition, enrich_selection_sources


class SelectionGateTests(unittest.TestCase):
    def setUp(self):
        self.sources = {
            str(i): {'id': str(i), 'original_title': 'Verified source headline',
                     'source_name': 'NASA', 'source_published_at': '2026-10-19T02:00:00Z',
                     'source_excerpt': 'Source evidence. ' * 100,
                     'source_url': f'https://www.nasa.gov/news/{i}', 'image_url': ''}
            for i in range(15)
        }
        self.rows = [{'id': str(i), 'event_key': f'event-{i}', 'category': 'BİLİM',
                      'title': 'Doğrulanmış haber', 'summary': 'Kaynak özeti.',
                      'brief': 'Kaynağa dayanan olgusal kısa haber özeti.', 'why': 'Önem açıklaması.'}
                     for i in range(15)]

    def test_floor_is_not_lowered_and_diagnostic_is_actionable(self):
        with self.assertRaisesRegex(ValueError, 'teknoloji: selected 11.*12–24'):
            checked_selection({'stories': self.rows[:11]}, self.sources, 'teknoloji')
        self.assertEqual(len(checked_selection({'stories': self.rows[:12]}, self.sources, 'teknoloji')), 12)
        self.assertEqual(len(checked_selection({'stories': self.rows[:10]}, self.sources, 'oyun')), 10)

    def test_short_source_is_enriched_before_selection_without_overwriting_feed(self):
        source = copy.deepcopy(self.sources['0']); source['source_excerpt'] = 'Short factual RSS excerpt.'
        with patch('pulse.source_media.article_text', return_value='Complete publisher evidence. ' * 80) as fetch:
            enrich_selection_sources({'0': source})
        fetch.assert_called_once_with(source['source_url'])
        self.assertEqual(source['source_excerpt'], 'Short factual RSS excerpt.')
        self.assertTrue(source['source_full_text'].startswith('Complete publisher'))

    def test_failed_source_fetch_keeps_original_evidence(self):
        source = copy.deepcopy(self.sources['0']); source['source_excerpt'] = 'Original RSS evidence.'
        with patch('pulse.source_media.article_text', side_effect=ValueError('Not a trusted public source')):
            enrich_selection_sources({'0': source})
        self.assertEqual(source['source_excerpt'], 'Original RSS evidence.')
        self.assertNotIn('source_full_text', source)

    def test_duplicates_cannot_fill_the_quota(self):
        for field, value in [('id', '0'), ('event_key', 'EVENT-0')]:
            rows = copy.deepcopy(self.rows)
            rows[1][field] = value
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                checked_selection({'stories': rows}, self.sources, 'teknoloji')

    def test_wrong_category_does_not_count_and_unknown_source_fails(self):
        rows = copy.deepcopy(self.rows[:12]); rows[0]['category'] = 'OYUN'
        with self.assertRaisesRegex(ValueError, 'selected 11'):
            checked_selection({'stories': rows}, self.sources, 'teknoloji')
        rows[0]['id'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'source identity'):
            checked_selection({'stories': rows}, self.sources, 'teknoloji')

    def test_failed_repair_never_pays_for_articles(self):
        research = {'publish_date': '2026-10-19', 'sections': {'teknoloji': list(self.sources.values())}}
        with patch('pulse.editorial.gemini', return_value={'stories': self.rows[:5]}) as generate, \
             patch('pulse.articles.full_articles') as articles:
            with self.assertRaisesRegex(ValueError, 'selected 5'):
                create_edition(research, 'teknoloji', '2026-10-19', 4, '2026-10-16')
            self.assertEqual(generate.call_count, 2)
            articles.assert_not_called()

    def test_repaired_selection_still_goes_through_articles_and_final_validation(self):
        research = {'publish_date': '2026-10-19', 'sections': {'teknoloji': list(self.sources.values())}}
        with patch('pulse.editorial.gemini', side_effect=[{'stories': self.rows[:5]}, {'stories': self.rows}]) as generate, \
             patch('pulse.articles.full_articles', return_value=[]) as articles, \
             patch('pulse.editorial.validate_content', side_effect=ValueError('Final gate preserved')):
            with self.assertRaisesRegex(ValueError, 'Final gate preserved'):
                create_edition(research, 'teknoloji', '2026-10-19', 4, '2026-10-16')
            self.assertEqual(generate.call_count, 2)
            self.assertEqual(len(articles.call_args.args[0]), 15)


    def test_previous_events_reach_existing_selection_without_an_extra_call(self):
        prior = {'date': '2026-10-18', 'section': 'teknoloji', 'event_key': 'older-launch',
                 'title': 'Previously published launch', 'brief': 'Already reported facts'}
        research = {'publish_date': '2026-10-19',
                    'sections': {'teknoloji': list(self.sources.values())},
                    'previous_events': {'teknoloji': [prior]}}
        with patch('pulse.editorial.gemini', return_value={'stories': self.rows}) as generate, \
             patch('pulse.articles.full_articles', return_value=[]), \
             patch('pulse.editorial.validate_content', side_effect=ValueError('Final gate preserved')):
            with self.assertRaisesRegex(ValueError, 'Final gate preserved'):
                create_edition(research, 'teknoloji', '2026-10-19', 4, '2026-10-16')
        self.assertEqual(generate.call_count, 1)
        self.assertIn('Already reported facts', generate.call_args.args[0])
        self.assertIn('somut YENİ gelişme', generate.call_args.args[0])

    def test_missing_why_is_repaired_before_any_article_generation(self):
        research={'publish_date':'2026-10-19','sections':{'teknoloji':list(self.sources.values())}}
        bad=copy.deepcopy(self.rows);bad[0].pop('why')
        with patch('pulse.editorial.gemini',side_effect=[{'stories':bad},{'stories':self.rows}]) as generate, \
             patch('pulse.articles.full_articles',return_value=[]) as articles, \
             patch('pulse.editorial.validate_content',side_effect=ValueError('Final gate preserved')):
            with self.assertRaisesRegex(ValueError,'Final gate preserved'):
                create_edition(research,'teknoloji','2026-10-19',4,'2026-10-16')
        self.assertEqual(generate.call_count,2)
        self.assertIn('why',generate.call_args.args[0])
        self.assertEqual(len(articles.call_args.args[0]),15)

    def test_retry_reuses_valid_selection_but_changed_evidence_invalidates_it(self):
        import tempfile
        research={'publish_date':'2026-10-19','sections':{'teknoloji':list(self.sources.values())}}
        with tempfile.TemporaryDirectory() as tmp, \
             patch('pulse.editorial.gemini',return_value={'stories':self.rows}) as generate, \
             patch('pulse.articles.full_articles',side_effect=ValueError('Article rejected')) as articles:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'Article rejected'):
                    create_edition(research,'teknoloji','2026-10-19',4,'2026-10-16',article_cache=tmp)
            self.assertEqual(generate.call_count,1)
            self.assertEqual(articles.call_count,2)
            research['sections']['teknoloji'][0]['source_excerpt'] += ' New verified facts.'
            with self.assertRaisesRegex(ValueError,'Article rejected'):
                create_edition(research,'teknoloji','2026-10-19',4,'2026-10-16',article_cache=tmp)
            self.assertEqual(generate.call_count,2)
