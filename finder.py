"""
CaptionAI - İçerik Üretici Bulucu (Apify tabanlı)
=================================================

Neden Apify? TikTok'un kendi kazımayı engelleme sistemi (msToken saniyede
değişiyor, Playwright kırılıyor) yüzünden doğrudan kazıma güvenilmez. Apify
bu savaşı bizim yerimize veriyor: sabit bir API token'ı ile hashtag'den
creator listesi çekiyoruz. Native derleme (C++/greenlet) gerektirmez.

Hem CLI (python finder.py) hem web GUI (app.py) bu dosyayı kullanır.
Ana fonksiyon: find_creators(cfg) -> list[dict]
"""

import json
import os
import time
from typing import Dict, List, Optional

import requests

APIFY_BASE = "https://api.apify.com/v2"


def load_config(path: Optional[str] = None) -> dict:
    if path is None:
        path = "config.json" if os.path.exists("config.json") else "config.example.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Esnek alan çözümleyiciler ------------------------------------------
# Farklı Apify actor'ları farklı alan isimleri döndürür. Hepsini tek bir
# normalize edilmiş kayıta indirger.

def _first(d: dict, keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
        # nested: authorMeta.name gibi
        if "." in k:
            cur = d
            ok = True
            for part in k.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    ok = False
                    break
            if ok and cur not in (None, ""):
                return cur
    return default


def normalize_item(item: dict) -> Optional[dict]:
    """Bir Apify sonucunu {username, nickname, followers, bio, profile} yap."""
    username = _first(
        item,
        ["username", "handle", "uniqueId", "authorMeta.name", "author.uniqueId", "userName"],
    )
    if not username:
        return None
    username = str(username).lstrip("@")

    nickname = _first(
        item,
        ["nickname", "name", "fullName", "authorMeta.nickName", "author.nickname", "displayName"],
        default=username,
    )
    followers = _first(
        item,
        ["followers", "followerCount", "fans", "authorMeta.fans", "authorStats.followerCount", "followersCount"],
        default=0,
    )
    try:
        followers = int(followers)
    except (TypeError, ValueError):
        followers = 0

    bio = _first(item, ["bio", "signature", "authorMeta.signature", "description"], default="")
    email = _first(item, ["email", "authorMeta.email"], default="")

    return {
        "username": username,
        "nickname": nickname or username,
        "followers": followers,
        "bio": bio or "",
        "email": email or "",
        "profile": f"https://www.tiktok.com/@{username}",
    }


def find_creators(cfg: dict) -> List[dict]:
    """
    Apify actor'ını çalıştırıp normalize edilmiş creator listesi döner.
    Takipçi bandına göre filtreler, hedef sayıda keser, tekrarları atar.
    """
    token = cfg.get("apify_token", "")
    if not token or "YAPISTIR" in token:
        raise RuntimeError(
            "Gecerli bir Apify API token yok. apify.com'dan ucretsiz al ve config'e/GUI'ye yapistir."
        )

    actor = cfg.get("apify_actor", "paxiq~tiktok-influencer-scraper")
    hashtags = [h.lstrip("#") for h in cfg.get("hashtags", []) if h.strip()]
    if not hashtags:
        raise RuntimeError("En az bir hashtag gerekli.")

    min_f = int(cfg.get("min_followers", 5000))
    max_f = int(cfg.get("max_followers", 50000))
    target = int(cfg.get("target_count", 100))

    # Actor input'u. paxiq/tiktok-influencer-scraper bu alanları kullanır;
    # başka actor seçilirse config.apify_input ile override edilebilir.
    actor_input = cfg.get("apify_input") or {
        "hashtags": hashtags,
        "minFollowers": min_f,
        "maxFollowers": max_f,
        "maxItems": target * 2,  # filtreden sonra hedefe ulaşmak için fazladan çek
    }

    # Actor'ı senkron çalıştır ve dataset item'larını al (tek çağrı).
    url = f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items"
    resp = requests.post(
        url,
        params={"token": token},
        json=actor_input,
        timeout=600,
    )

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Apify hatasi ({resp.status_code}): {resp.text[:300]}"
        )

    items = resp.json()
    if not isinstance(items, list):
        items = items.get("items", []) if isinstance(items, dict) else []

    seen: Dict[str, dict] = {}
    for raw in items:
        rec = normalize_item(raw)
        if not rec:
            continue
        if rec["username"] in seen:
            continue
        # Takipçi bandı filtresi (actor zaten filtrelese de garantiye al)
        f = rec["followers"]
        if f and (f < min_f or f > max_f):
            continue
        seen[rec["username"]] = rec
        if len(seen) >= target:
            break

    # Takipçiye göre büyükten küçüğe sırala
    return sorted(seen.values(), key=lambda r: r["followers"], reverse=True)


def save_csv(rows: List[dict], out_csv: str) -> None:
    import csv
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["username", "nickname", "followers", "email", "bio", "profile"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _cli() -> None:
    cfg = load_config()
    print("Apify uzerinden araniyor... (birkac dakika surebilir)")
    rows = find_creators(cfg)
    out_csv = cfg.get("output_csv", "creators.csv")
    save_csv(rows, out_csv)
    print(f"\n=== BITTI ===\n{len(rows)} uretici bulundu -> {out_csv}")
    for r in rows[:10]:
        print(f"  @{r['username']}  {r['followers']} takipci")


if __name__ == "__main__":
    _cli()
