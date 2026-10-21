import unittest
from pulse.event_history import EventHistory, event_key, relevant_events
from pulse.source_history import SourceHistory, fingerprint
from pulse.editorial import checked_selection


class EventHistoryTests(unittest.TestCase):
    def test_bloom_collision_is_never_an_exclusion(self):
        old = SourceHistory()
        old.add_hash(fingerprint('https://example.com/new'))
        record = old.bloom_record()
        restored = SourceHistory(record)
        self.assertTrue(restored.uncertain('https://example.com/new'))
        self.assertFalse(restored.contains('https://example.com/new'))
        restored.add('https://example.com/new')
        self.assertTrue(SourceHistory(restored.record()).contains('https://example.com/new'))

    def test_storage_prunes_old_briefs_but_not_exact_hashes(self):
        history = EventHistory()
        for date in ('2026-01-01', '2026-10-18'):
            history.add('oyun', date, {'event_key': 'steam-demo', 'title': 'Steam demo', 'brief': 'A'*10000})
        record = history.record('2026-10-19')
        self.assertEqual(len(record['events']), 1)
        self.assertEqual(len(record['events'][0]['brief']), 320)
        self.assertEqual(EventHistory(record).record('2026-10-19'), record)

    def test_retrieval_prioritizes_entity_and_event(self):
        rows = [{'date': '2026-10-18', 'event_key': 'steam-demo', 'title': 'Steam demo'},
                {'date': '2026-10-19', 'event_key': 'nasa-launch', 'title': 'NASA launch'}]
        selected = relevant_events(rows, {'x': {'original_title': 'Steam demo cancelled'}}, limit=1)
        self.assertEqual(selected[0]['event_key'], 'steam-demo')

    def test_known_event_from_different_source_is_rejected_but_update_allowed(self):
        sources = {str(i): {'source_url': f'https://example.com/{i}'} for i in range(11)}
        rows = [{'id': str(i), 'category': 'OYUN DÜNYASI', 'title':'Doğrulanmış başlık', 'summary':'Kaynak özeti', 'why':'Önem açıklaması', 'event_key': f'new-event-{i}'} for i in range(11)]
        rows[0]['event_key'] = 'Steam DEMO'
        selected = checked_selection({'stories': rows}, sources, 'oyun', [{'event_key': 'steam-demo'}])
        self.assertEqual(len(selected), 10)
        rows[0]['event_key'] = 'steam-demo-yeni-surum-cikti'
        self.assertEqual(len(checked_selection({'stories': rows}, sources, 'oyun', [{'event_key': 'steam-demo'}])), 11)
        self.assertEqual(event_key('Steam DEMO'), 'steam-demo')
