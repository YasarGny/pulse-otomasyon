"""Versioned publishing targets; old sealed issues remain verifiable."""
PROFILE = 'expanded-v1'
DAILY_PROFILE = 'daily-v2'
POLICY_START = '2026-10-22'
PODCAST_PLAN_START = '2026-10-23'
DAILY_TARGET = (15, 20)
DAILY_WORDS = (2500, 3100)
DAILY_PODCAST_SECONDS = (900, 1500)
TARGETS = {'teknoloji': (15, 20), 'oyun': (12, 18)}
MIN_STORIES = {'teknoloji': 12, 'oyun': 10}
WORDS = {'teknoloji': (2500, 3100), 'oyun': (2000, 2700)}
# Planning estimate, not a substitute for independent review or real duration.
SCRIPT_ESTIMATED_WORDS_PER_MINUTE = (120, 180)
PODCAST_SECONDS = {'teknoloji': (900, 1500), 'oyun': (720, 1320)}


def expanded(data):
    return data.get('publication_profile') in (PROFILE, DAILY_PROFILE)


def shared_policy(data):
    return data.get('publication_profile') == DAILY_PROFILE


def planned_podcast(data):
    return shared_policy(data) and data.get('publish_date', '') >= PODCAST_PLAN_START


def profile_for(date):
    return DAILY_PROFILE if date >= POLICY_START else PROFILE


def minimum_stories(data):
    # A real non-empty edition is required; the editorial target is not a quota.
    return 1 if shared_policy(data) else MIN_STORIES[data['section']] if expanded(data) else 3


def podcast_maximum(data):
    return PODCAST_SECONDS[data['section']][1] if data.get('publication_profile') == PROFILE else None


def podcast_minimum(data):
    # Keep old sealed contracts intact. New duration targets are guidance;
    # decoding, factual/conversation review, silence and chapters remain gates.
    return PODCAST_SECONDS[data['section']][0] if data.get('publication_profile') == PROFILE else 40


def summary_minimum(data):
    if not shared_policy(data):
        return 20
    from pulse.editorial import summary_script
    # A conservative 240 words/minute bound catches grossly short output.
    # It is a file sanity check, not a target speaking rate or completeness proof.
    words = len(summary_script(data).split())
    return min(20, max(5, words / 4))
