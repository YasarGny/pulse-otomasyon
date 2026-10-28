"""Build sentence-aligned review units using only measured ASR timestamps."""
import math
import re

VERSION = 1
ABBREVIATIONS = {'dr.', 'prof.', 'doç.', 'sn.', 'örn.', 'vb.', 'vs.', 'ltd.', 'inc.', 'a.ş.'}


def sentence_end(text):
    text = text.rstrip().rstrip('\"\u201d\u2019\u00bb)]}').rstrip()
    return bool(re.search(r'[.!?\u2026]$', text)) and text.split()[-1].casefold() not in ABBREVIATIONS


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def atoms(segment):
    """Use words only when their text and times faithfully cover the ASR row."""
    words = segment.get('words')
    if isinstance(words, list) and words:
        previous = segment['start']
        valid = True
        for word in words:
            if (not isinstance(word, dict) or not isinstance(word.get('word'), str) or not word['word'].strip()
                    or not number(word.get('start')) or not number(word.get('end'))
                    or not previous <= word['start'] <= word['end']
                    or (number(segment.get('end')) and word['end'] > segment['end'] + 0.02)):
                valid = False
                break
            previous = word['end']
        if valid and re.sub(r'\s+', '', ''.join(w['word'] for w in words)) == re.sub(r'\s+', '', segment['text']):
            return [{'start': w['start'], 'end': w['end'], 'text': w['word']} for w in words]
    return [segment]


def sentence_units(transcript):
    """Legacy rows are merged, never split with guessed/interpolated timings."""
    units, pending = [], []
    previous = -1
    for segment in transcript['segments']:
        if (not number(segment.get('start')) or segment['start'] < 0 or segment['start'] < previous
                or not isinstance(segment.get('text'), str)
                or (segment.get('end') is not None and
                    (not number(segment['end']) or segment['end'] < segment['start']))):
            raise ValueError('Invalid measured transcript segment')
        previous = segment['start']
        for atom in atoms(segment):
            pending.append(atom)
            if sentence_end(atom['text']):
                units.append(unit(pending, True))
                pending = []
    if pending:
        units.append(unit(pending, False))
    return {**transcript, 'segments': units, 'sentence_units_version': VERSION}


def unit(rows, complete):
    return {'start': rows[0]['start'], 'end': rows[-1].get('end'),
            'text': ' '.join(row['text'].strip() for row in rows).strip(),
            'complete_start': True, 'complete_end': complete}
