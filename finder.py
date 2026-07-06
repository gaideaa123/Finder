"""
CaptionAI - İçerik Üretici Bulucu (TikTok)
==========================================

Verilen hashtag'lerden videolar çeker, o videoları paylaşan üreticileri
toplar, takipçi bandı + etkileşim oranına göre filtreler ve kullanıcı
adlarını (DM atman için) bir CSV'ye yazar.

KULLANIM
--------
1) Bağımlılıklar:
     pip install -r requirements.txt
     python -m playwright install chromium

2) config.example.json'u config.json olarak kopyala ve düzenle.
   ms_token'ı tarayıcıdan almalısın (README'de anlatıldı).

3) Çalıştır:
     python finder.py

Çıktı: creators.csv (username, followers, engagement_rate, profil linki)

NOT: TikTok'un resmi herkese açık API'si bu iş için yok; bu araç TikTok'un
web arayüzünü otomatize eder. Hesabını riske atmamak için makul sayıda
(config'teki target_count) veri çeker ve istekler arasında bekler.
"""

import asyncio
import csv
import json
import os
import sys
from typing import Dict

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("HATA: TikTokApi kurulu degil. Once: pip install -r requirements.txt")
    sys.exit(1)


def load_config() -> dict:
    path = "config.json" if os.path.exists("config.json") else "config.example.json"
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("ms_token") or "YAPISTIR" in cfg["ms_token"]:
        print(
            "HATA: config.json icinde gecerli bir ms_token yok.\n"
            "README'deki adimlarla tarayicidan msToken degerini al ve config.json'a yapistir."
        )
        sys.exit(1)
    return cfg


def engagement_rate(stats: Dict, followers: int) -> float:
    """Basit etkileşim oranı: (begeni + yorum) / takipci."""
    if not followers:
        return 0.0
    likes = stats.get("diggCount", 0) or 0
    comments = stats.get("commentCount", 0) or 0
    return (likes + comments) / followers


async def main() -> None:
    cfg = load_config()

    hashtags = cfg["hashtags"]
    per_tag = int(cfg.get("videos_per_hashtag", 60))
    min_f = int(cfg.get("min_followers", 5000))
    max_f = int(cfg.get("max_followers", 50000))
    min_er = float(cfg.get("min_engagement_rate", 0.05))
    target = int(cfg.get("target_count", 100))
    out_csv = cfg.get("output_csv", "creators.csv")
    ms_token = cfg["ms_token"]

    found: Dict[str, dict] = {}  # username -> kayit (tekrarsiz)

    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[ms_token],
            num_sessions=1,
            sleep_after=3,
            browser="chromium",
        )

        for tag_name in hashtags:
            if len(found) >= target:
                break
            print(f"\n[#] '{tag_name}' taraniyor...")
            try:
                tag = api.hashtag(name=tag_name)
                async for video in tag.videos(count=per_tag):
                    info = video.as_dict
                    author = info.get("author", {}) or {}
                    author_stats = info.get("authorStats", {}) or {}
                    stats = info.get("stats", {}) or {}

                    username = author.get("uniqueId")
                    if not username or username in found:
                        continue

                    followers = author_stats.get("followerCount", 0) or 0
                    if followers < min_f or followers > max_f:
                        continue

                    er = engagement_rate(stats, followers)
                    if er < min_er:
                        continue

                    found[username] = {
                        "username": username,
                        "followers": followers,
                        "engagement_rate": round(er, 4),
                        "profile": f"https://www.tiktok.com/@{username}",
                        "hashtag": tag_name,
                    }
                    print(
                        f"  + @{username}  ({followers} takipci, ER {er:.1%})  "
                        f"[{len(found)}/{target}]"
                    )

                    if len(found) >= target:
                        break
            except Exception as e:  # noqa: BLE001
                print(f"  ! '{tag_name}' taranirken hata: {e}")
                continue

            # Nazik ol: hashtag'ler arasi kisa bekleme
            await asyncio.sleep(2)

    # En yuksek etkilesimden dusuge sirala
    rows = sorted(found.values(), key=lambda r: r["engagement_rate"], reverse=True)

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["username", "followers", "engagement_rate", "profile", "hashtag"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=== BITTI ===")
    print(f"{len(rows)} uretici bulundu -> {out_csv}")
    if rows:
        print("\nIlk 10:")
        for r in rows[:10]:
            print(f"  @{r['username']}  {r['followers']} takipci  ER {r['engagement_rate']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
