"""Independent website, automation and podcast controls; default on."""
import os

PODCAST_VARIABLES = {'teknoloji': 'PULSE_TECH_PODCAST_ENABLED',
                     'oyun': 'PULSE_GAME_PODCAST_ENABLED'}


def flag(name):
    value = os.environ.get(name, '').strip().lower()
    if value not in ('', 'true', 'false'):
        raise ValueError('Control must be true or false: ' + name)
    return value != 'false'


def settings():
    return {'schema_version': 1, 'enabled': flag('PULSE_SITE_ENABLED'),
            'automation_enabled': flag('PULSE_AUTOMATION_ENABLED'),
            'podcasts': {s: flag(name) for s, name in PODCAST_VARIABLES.items()}}


def require_running():
    if not flag('PULSE_AUTOMATION_ENABLED'):
        raise RuntimeError('PULSE is paused by its owner')


def podcast_enabled(section):
    return flag('PULSE_AUTOMATION_ENABLED') and flag(PODCAST_VARIABLES[section])


def podcast_present(edition):
    value = edition.get('podcast_enabled', True)
    if type(value) is not bool:
        raise ValueError('Invalid podcast enabled state')
    if not value and ('podcast' not in edition or edition['podcast'] is not None):
        raise ValueError('Disabled podcast must not contain a playable asset')
    return value


def audio_kinds(edition):
    return ('summary', 'podcast') if podcast_present(edition) else ('summary',)
