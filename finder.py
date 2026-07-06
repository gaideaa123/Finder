"""
CaptionAI - İçerik Üretici Bulucu (TikTok) - çekirdek mantık
===========================================================

Hem CLI (python finder.py) hem de web GUI (app.py) bu dosyayı kullanır.
Ana fonksiyon: find_creators(cfg, on_progress) -> list[dict]
"""

import asyncio
import csv
import json
import os
import sys
from typing import Callable, Dict, List, Optional

try:
    from TikTokApi import TikTokApi
except ImportError:
    TikTokApi = None  # app.py kendi hata mesajını gösterir


def load_config(path: Optional[str] = None) -> dict:
    if path is None:
        path = "config.json" if os.path.exists("config.json") else "config.example.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def engagement_rate(stats: Dict, followers: int) -> float:
    """Basit etkileşim oranı: (begeni + yorum) / takipci."""
    if not followers:
        return 0.0
    likes = stats.get("diggCount", 0) or 0
    comments = stats.get("commentCount", 0) or 0
    return (likes + comments) / followers


async def find_creators(
    cfg: dict,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> List[dict]:
    """
    Hashtag'lerden içerik üreticilerini bulur, filtreler ve liste döner.

    on_progress(callback) her yeni üretici bulunduğunda çağrılır; GUI'de
    canlı ilerleme göstermek için kullanılır.
    """
    if TikTokApi is None:
        raise RuntimeError(
            "TikTokApi kurulu degil. Once: pip install -r requirements.txt"
        )

    hashtags = cfg["hashtags"]
    per_tag = int(cfg.get("videos_per_hashtag", 60))
    min_f = int(cfg.get("min_followers", 5000))
    max_f = int(cfg.get("max_followers", 50000))
    min_er = float(cfg.get("min_engagement_rate", 0.05))
    target = int(cfg.get("target_count", 100))
    ms_token = cfg.get("ms_token", "")

    if not ms_token or "YAPISTIR" in ms_token:
        raise RuntimeError(
            "Gecerli bir ms_token yok. README'deki adimlarla tarayicidan al ve config'e yapistir."
        )

    found: Dict[str, dict] = {}

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

                    nickname = author.get("nickname") or username
                    record = {
                        "username": username,
                        "nickname": nickname,
                        "followers": followers,
                        "engagement_rate": round(er, 4),
                        "profile": f"https://www.tiktok.com/@{username}",
                        "hashtag": tag_name,
                    }
                    found[username] = record

                    if on_progress:
                        on_progress({**record, "count": len(found), "target": target})

                    if len(found) >= target:
                        break
            except Exception as e:  # noqa: BLE001
                if on_progress:
                    on_progress({"error": f"'{tag_name}' taranirken hata: {e}"})
                continue

            await asyncio.sleep(2)  # nazik ol: hashtag'ler arasi bekleme

    return sorted(found.values(), key=lambda r: r["engagement_rate"], reverse=True)


def save_csv(rows: List[dict], out_csv: str) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["username", "nickname", "followers", "engagement_rate", "profile", "hashtag"],
        )
        writer.writeheader()
        writer.writerows(rows)


async def _cli() -> None:
    cfg = load_config()

    def _print(ev: dict) -> None:
        if "error" in ev:
            print(f"  ! {ev['error']}")
        else:
            print(
                f"  + @{ev['username']}  ({ev['followers']} takipci, "
                f"ER {ev['engagement_rate']:.1%})  [{ev['count']}/{ev['target']}]"
            )

    print("Taraniyor...")
    rows = await find_creators(cfg, on_progress=_print)
    out_csv = cfg.get("output_csv", "creators.csv")
    save_csv(rows, out_csv)
    print(f"\n=== BITTI ===\n{len(rows)} uretici bulundu -> {out_csv}")


if __name__ == "__main__":
    if TikTokApi is None:
        print("HATA: TikTokApi kurulu degil. Once: pip install -r requirements.txt")
        sys.exit(1)
    asyncio.run(_cli())
