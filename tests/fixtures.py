"""Explicitly synthetic news/audio used only inside isolated tests."""

import shutil
import subprocess
from pathlib import Path

from pulse.publication import (
    audio_info,
    issue_number,
    seal_release,
    turkish_date,
    write_json,
)

DATE = "2026-10-16"
GAME_START = DATE


def tone(path):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:sample_rate=44100",
            "-t",
            "42",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def edition(section, date=DATE, game_start=GAME_START):
    labels = (
        [
            "Yeni bir açık kaynak aracı geliştiricilerle buluştu",
            "Uzay araştırmasında yeni veriler paylaşıldı",
            "Dijital güvenlik için yeni bir yaklaşım",
        ]
        if section == "teknoloji"
        else [
            "Bağımsız bir oyundan ilk oynanış görüntüleri",
            "Yeni güncelleme takım oyununu değiştiriyor",
            "Oyun dünyasında erişilebilirlik üzerine yeni adımlar",
        ]
    )
    return {
        "schema_version": 1,
        "section": section,
        "publish_date": date,
        "date": turkish_date(date),
        "issue": issue_number(date, section, game_start),
        "ready": False,
        "stories": [
            {
                "id": section + str(i),
                "category": "YAZILIM" if section == "teknoloji" else "OYUN KÜLTÜRÜ",
                "title": title,
                "summary": "Bu, PULSE otomasyonunu sınamak için hazırlanmış sentetik bir haber örneğidir. Güncel bir haber ya da gerçek bir şirket duyurusu olarak yayımlanmaz.",
                "why": "Gelişmenin günlük kullanım üzerindeki etkilerini ve açık kalan soruları birlikte değerlendirmek gerekiyor.",
                "source_name": "Test kaynağı",
                "source_url": f"https://example.com/{section}/{i}",
                "source_published_at": date + "T05:00:00+03:00",
                "image_url": "https://images.example.test/article.jpg"
                if i == 0
                else "",
            }
            for i, title in enumerate(labels)
        ],
    }


def ready_release(root, audio, date=DATE, game_start=GAME_START):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for section in ("teknoloji", "oyun"):
        data = edition(section, date, game_start)
        (root / section).mkdir(exist_ok=True)
        for kind in ("summary", "podcast"):
            path = root / section / (kind + ".mp3")
            shutil.copyfile(audio, path)
            data[kind] = {
                "file": f"{section}/{kind}.mp3",
                "title": "Günün sesli özeti"
                if kind == "summary"
                else ("Yeni Sekme" if section == "teknoloji" else "Moradon FM"),
                "episode": data["issue"],
                **audio_info(path, 20 if kind == "summary" else 40),
            }
            if kind == "podcast":
                data[kind]["hosts"] = ["Yaşar", "Necdet"]
        data["ready"] = True
        write_json(root / (section + ".json"), data)
    return seal_release(root, date, game_start)
