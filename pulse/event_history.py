"""Bounded recent event briefs, not an article archive or a public history view."""
import datetime as dt
import re
import unicodedata

DAYS = 90
MAX_ROWS = DAYS * 48


def event_key(value):
    text = unicodedata.normalize('NFKC', str(value)).casefold()
    return '-'.join(re.findall(r'[^\W_]+', text, re.UNICODE))


class EventHistory:
    def __init__(self, record=None):
        self.rows = {}
        if record is not None:
            if record.get('schema_version') != 1 or not isinstance(record.get('events'), list):
                raise ValueError('Invalid event history')
            if len(record['events']) > MAX_ROWS:
                raise ValueError('Event history capacity exceeded')
            for row in record['events']:
                self.add(row['section'], row['date'], row)

    def add(self, section, date, story):
        dt.date.fromisoformat(date)
        if section not in ('teknoloji', 'oyun'):
            raise ValueError('Invalid event section')
        key = event_key(story.get('event_key', ''))
        if not key:
            return  # Older sealed editions need not have an event identity.
        if len(key) > 160:
            raise ValueError('Invalid event identity')
        row = {'section': section, 'date': date, 'event_key': key,
               'title': str(story.get('title', ''))[:200],
               'brief': str(story.get('brief') or story.get('summary', ''))[:320]}
        identity = (section, date, key)
        self.rows[identity] = row

    def record(self, date):
        day = dt.date.fromisoformat(date)
        cutoff = (day - dt.timedelta(days=DAYS - 1)).isoformat()
        rows = [r for r in self.rows.values() if cutoff <= r['date'] <= date]
        if len(rows) > MAX_ROWS:
            raise ValueError('Event history capacity exceeded; review before pruning')
        return {'schema_version': 1, 'events': sorted(rows, key=lambda r: (r['date'], r['section'], r['event_key']))}


def relevant_events(rows, sources, limit=80):
    """Retrieve recent + lexical/entity matches without extra model requests.

    Retrieval is not a semantic certainty claim. The selection model compares
    the retrieved actual facts and must distinguish a new development.
    """
    def tokens(text):
        return set(re.findall(r'[^\W_]{3,}', unicodedata.normalize('NFKC', text).casefold()))
    evidence = [tokens(s.get('original_title', '') + ' ' + s.get('source_excerpt', '')[:500]) for s in sources.values()]
    scored = []
    for row in rows:
        words = tokens(row['title'] + ' ' + row['event_key'])
        score = max((len(words & candidate) / max(1, len(words)) for candidate in evidence), default=0)
        scored.append((score, row['date'], row['event_key'], row))
    return [item[-1] for item in sorted(scored, key=lambda x: x[:3], reverse=True)[:limit]]
