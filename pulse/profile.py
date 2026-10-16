"""Versioned publishing targets; old sealed issues remain verifiable."""
PROFILE = 'expanded-v1'
TARGETS = {'teknoloji': (15, 20), 'oyun': (12, 18)}
MIN_STORIES = {'teknoloji': 10, 'oyun': 8}
WORDS = {'teknoloji': (2100, 2900), 'oyun': (1700, 2500)}
PODCAST_SECONDS = {'teknoloji': (900, 1500), 'oyun': (720, 1320)}


def expanded(data):
    return data.get('publication_profile') == PROFILE


def podcast_minimum(data):
    return PODCAST_SECONDS[data['section']][0] if expanded(data) else 40
