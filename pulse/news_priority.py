"""Source-grounded editorial judgements; never an objective importance claim."""

DIMENSIONS = ('impact', 'development', 'timeliness', 'evidence')


def validate_priority(story):
    priority = story.get('editorial_priority')
    if not isinstance(priority, dict) or any(
        type(priority.get(key)) is not int or not 0 <= priority[key] <= 4
        for key in DIMENSIONS
    ):
        raise ValueError('Missing/invalid editorial priority dimensions')
    if priority['evidence'] == 0 or priority['development'] == 0:
        raise ValueError('A selected story needs source evidence and a concrete new development')
    reason = priority.get('reason')
    if not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 500:
        raise ValueError('Source-grounded editorial priority reason is required')
    return priority


def rank_key(story):
    priority = validate_priority(story)
    # Stable tie-breaks never prefer a category or an attractive illustration.
    return (-sum(priority[key] for key in DIMENSIONS), story['id'])


def ranked(items):
    return sorted(items, key=lambda item: rank_key(item[1]))
