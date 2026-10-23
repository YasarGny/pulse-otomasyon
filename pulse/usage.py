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
    _append({'kind':'response','task':task,'model':model,'input_chars':input_chars,'tokens':counts})


# Scoped labels do not enter provider prompts or change generation settings.
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import threading
import uuid

_stage = ContextVar('pulse_usage_stage', default=None)
_section = ContextVar('pulse_usage_section', default=None)
_lock = threading.Lock()


@contextmanager
def scope(stage, section=None):
    a = _stage.set(stage)
    b = _section.set(section if section is not None else _section.get())
    try:
        yield
    finally:
        _stage.reset(a)
        _section.reset(b)


def invoke(stage, function, *args, section=None, **kwargs):
    with scope(stage, section):
        return function(*args, **kwargs)


def reused(stage=None, section=None):
    with scope(stage or _stage.get() or 'approved-output', section):
        _append({'kind':'reuse', 'tokens':{}})


def _append(row):
    target = os.environ.get('PULSE_USAGE_LOG')
    if not target:
        return
    row = {**row, 'call_id':uuid.uuid4().hex,
           'at':dt.datetime.now(dt.timezone.utc).isoformat(),
           'stage':_stage.get() or row.get('task', 'unknown'),
           'section':_section.get()}
    try:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    except OSError:
        print('Usage accounting unavailable; generation result preserved')


ALIASES = {'input':('promptTokenCount','total_input_tokens'),
           'output':('candidatesTokenCount','total_output_tokens'),
           'total':('totalTokenCount','total_tokens'),
           'cached':('cachedContentTokenCount','total_cached_tokens'),
           'thought':('thoughtsTokenCount','total_thought_tokens')}


def summarize(paths):
    groups, seen = {}, set()
    malformed = 0
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
                if not isinstance(row,dict): raise ValueError('Invalid accounting row')
            except (ValueError,TypeError):
                malformed += 1
                continue
            identity = row.get('call_id') or hashlib.sha256(line.encode()).hexdigest()
            if identity in seen: continue
            seen.add(identity)
            key = (row.get('stage') or row.get('task','unknown'),row.get('model','not-applicable'),row.get('section'))
            group = groups.setdefault(key,{'stage':key[0],'model':key[1],'section':key[2],
                'calls':0,'reuses':0,'tokens':{k:0 for k in ALIASES},'missing':{k:0 for k in ALIASES}})
            if row.get('kind') == 'reuse':
                group['reuses'] += 1
                continue
            group['calls'] += 1
            counts = row.get('tokens',{})
            if not isinstance(counts,dict): counts={}
            for metric,aliases in ALIASES.items():
                value = next((counts[k] for k in aliases if type(counts.get(k)) is int and counts[k]>=0),None)
                if value is None: group['missing'][metric] += 1
                else: group['tokens'][metric] += value
    return {'schema_version':1,'groups':list(groups.values()),'malformed_rows':malformed,
            'note':'Provider-reported response tokens, not an invoice. Missing counters are unknown, not zero; cached/thought counts are not added to total.'}


def main():
    import argparse
    from pulse.publication import write_json
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',required=True)
    args=parser.parse_args()
    root=Path(args.work)
    try:
        result=summarize(sorted(root.rglob('api-usage.jsonl')))
        if root.exists(): write_json(root/'api-usage-summary.json',result)
        lines=['\n### API tüketimi\n','Aşağıdaki sayılar sağlayıcının raporudur; fatura veya TL tahmini değildir. Eksik alanlar bilinmiyor.\n',
               '| Aşama | Model | Yayın | Çağrı | Yeniden kullanım | Girdi | Çıktı | Düşünme | Önbellek | Eksik toplam sayacı |',
               '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for g in result['groups']:
            value=lambda k: str(g['tokens'][k])+(' + bilinmeyen' if g['missing'][k] else '')
            lines.append(f"| {g['stage']} | {g['model']} | {g['section'] or '—'} | {g['calls']} | {g['reuses']} | {value('input')} | {value('output')} | {value('thought')} | {value('cached')} | {g['missing']['total']} |")
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out: out.write('\n'.join(lines)+'\n')
        print('Usage summary:',sum(g['calls'] for g in result['groups']),'recorded responses;',sum(g['reuses'] for g in result['groups']),'local reuses; no prompts or credentials logged.')
    except (OSError,ValueError):
        print('Usage summary unavailable; publication result preserved')


if __name__ == '__main__':
    main()
