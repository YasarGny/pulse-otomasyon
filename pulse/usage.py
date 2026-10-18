"""Private, optional usage accounting. Never store prompts, responses or keys."""
import datetime as dt
import json
import os
from pathlib import Path

COUNTERS = ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount',
            'cachedContentTokenCount', 'thoughtsTokenCount')


def record(task, model, response, input_chars):
    target = os.environ.get('PULSE_USAGE_LOG')
    if not target:
        return
    metadata = response.get('usageMetadata') or {}
    if not isinstance(metadata, dict):
        metadata = {}
    counts = {k: metadata[k] for k in COUNTERS if type(metadata.get(k)) is int and metadata[k] >= 0}
    interaction_usage = response.get('usage') or {}
    if isinstance(interaction_usage, dict):
        for key in ('total_input_tokens', 'total_output_tokens', 'total_tokens', 'total_thought_tokens', 'total_cached_tokens'):
            value = interaction_usage.get(key)
            if type(value) is int and value >= 0:
                counts[key] = value
    row = {'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'task': task,
           'model': model, 'input_chars': input_chars, 'tokens': counts}
    # One short append per call; article workers may complete concurrently.
    path = Path(target)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    except OSError:
        # Accounting must never invalidate an already paid, successful response.
        print('Usage accounting unavailable; generation result preserved')
