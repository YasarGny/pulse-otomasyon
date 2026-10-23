"""A deterministic pronunciation copy; never edit the published or reviewed text."""

import hashlib
import json
from pathlib import Path
import re

LEXICON_PATH = Path(__file__).with_name("pronunciations.json")
LEXICON = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
if not all(
    isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
    for k, v in LEXICON.items()
):
    raise ValueError("Invalid pronunciation lexicon")
LEXICON_SHA256 = hashlib.sha256(LEXICON_PATH.read_bytes()).hexdigest()
LOOKUP = {key.casefold(): value for key, value in LEXICON.items()}
NAMES = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(name) for name in sorted(LEXICON, key=len, reverse=True))
    + r")(?!\w)",
    re.I,
)
# Web addresses, mail addresses and code are identifiers, not brand mentions.
PROTECTED = re.compile(
    r"https?://[^\s<>]+|www\.[^\s<>]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|`[^`]*`", re.I
)


def cardinal(number):
    """Natural spoken issue labels, without touching model names or product digits."""
    number = int(number)
    if not 0 <= number < 1000000:
        raise ValueError("Spoken number out of range")
    ones = ("", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
    tens = (
        "",
        "on",
        "yirmi",
        "otuz",
        "kırk",
        "elli",
        "altmış",
        "yetmiş",
        "seksen",
        "doksan",
    )
    if number == 0:
        return "sıfır"
    parts = []
    if number >= 1000:
        thousands, number = divmod(number, 1000)
        parts.append((cardinal(thousands) + " " if thousands > 1 else "") + "bin")
    hundreds, number = divmod(number, 100)
    if hundreds:
        parts.append((ones[hundreds] + " " if hundreds > 1 else "") + "yüz")
    decade, unit = divmod(number, 10)
    parts.extend(word for word in (tens[decade], ones[unit]) if word)
    return " ".join(parts)


def pronunciation(text):
    def speak(part):
        part = NAMES.sub(lambda m: LOOKUP.get(m[0].casefold(), m[0]), part)
        # Defensive fallback for an existing script: 003 is 'üç', never 'sıfır sıfır üç'.
        return re.sub(
            r"\b(sayı|bölüm)(\s+(?:numarası\s*)?[:#]?\s*)(0[0-9]{1,5})(?!\w)",
            lambda m: m[1] + m[2] + cardinal(m[3]),
            part,
            flags=re.I,
        )

    result, end = [], 0
    for match in PROTECTED.finditer(text):
        result.extend((speak(text[end : match.start()]), match[0]))
        end = match.end()
    result.append(speak(text[end:]))
    return "".join(result)


def spoken_turns(turns):
    return [{**turn, "text": pronunciation(turn["text"])} for turn in turns]


def pronunciation_review(text):
    """Offline review hints, not a claim to detect every foreign name correctly."""
    clean = PROTECTED.sub(lambda m: " " * len(m[0]), text)
    matches = list(NAMES.finditer(clean))
    replacements = {}
    for match in matches:
        name = match[0].casefold()
        replacements[name] = replacements.get(name, 0) + 1
    unknown = NAMES.sub(lambda m: " " * len(m[0]), clean)
    common = set("Bu Bir Ve Ya Ama Yeni Bugün Günün Özet Özeti Teknoloji Oyun Haber Haberler Kaynak Kaynaklar Evet Hayır Şimdi Sonra Ayrıca Daha Tamam Ana İlk Son Türkçe Türkiye Yaşar Necdet Yeni Sekme Moradon Peki Ancak Yani Her Çok Biz Ben Sen Siz Bunun Bunu Böyle Olan Önemli Tarih Sayı Bölüm Günlük Merhaba Ekim Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Kasım Aralık Pazartesi Salı Çarşamba Perşembe Cuma Cumartesi Pazar".casefold().split())
    candidates = {}
    for match in re.finditer(r"(?<!\w)(?:[A-Z][A-Za-z0-9-]+|[a-z]+[A-Z][A-Za-z0-9-]*)(?!\w)", unknown):
        name = match[0]
        if name.casefold() in common:
            continue
        if name.casefold() not in candidates:
            candidates[name.casefold()] = {
                "name": name,
                "context": clean[max(0, match.start()-45):match.end()+45].strip(),
            }
    return {
        "schema_version": 1,
        "lexicon_sha256": LEXICON_SHA256,
        "note": "Candidates are review hints, not verified foreign names. Unknown names are not rewritten automatically.",
        "replacements": [
            {"name": name, "spoken": LOOKUP[name], "count": count}
            for name, count in sorted(replacements.items())
        ],
        "candidates": list(candidates.values())[:100],
        "candidate_count": len(candidates),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Offline pronunciation review; no API or audio generation")
    parser.add_argument("--input", type=Path, required=True, help="UTF-8 speech script")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(pronunciation_review(args.input.read_text(encoding="utf-8")), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)
