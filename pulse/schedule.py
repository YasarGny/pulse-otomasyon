"""Separate preparation from production; keep completed morning work off live Pages."""
from pulse.publication import expected_date, not_before, now


def phase(event, cron, current=None, date=None):
    if event == 'schedule' and date and current and current.get('status') == 'ready' and current.get('publish_date') == date:
        return 'complete'
    return 'prepare' if event == 'schedule' and cron == '0 3 * * *' else 'produce'


def build_available(date, at=None):
    at = at or now()
    if expected_date(at) != date:
        raise ValueError('Publication is outside its Istanbul publication day')
    return at >= not_before(date)
