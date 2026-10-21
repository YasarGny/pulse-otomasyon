"""Versioned publishing targets; old sealed issues remain verifiable."""
PROFILE = 'expanded-v1'
TARGETS = {'teknoloji': (15, 20), 'oyun': (12, 18)}
MIN_STORIES = {'teknoloji': 12, 'oyun': 10}
WORDS = {'teknoloji': (2500, 3100), 'oyun': (2000, 2700)}
# Planning estimate, not a substitute for independent review or real duration.
SCRIPT_WORD_TOLERANCE = 0.05
PODCAST_SECONDS = {'teknoloji': (900, 1500), 'oyun': (720, 1320)}


def expanded(data):
    return data.get('publication_profile') == PROFILE


def podcast_minimum(data):
    return PODCAST_SECONDS[data['section']][0] if expanded(data) else 40
