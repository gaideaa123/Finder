"""
CaptionAI - İçerik Üretici Bulucu (Apify tabanlı)
=================================================

Neden Apify? TikTok kazımayı bilerek engelliyor (msToken saniyede değişiyor).
Apify bu savaşı bizim yerimize veriyor: sabit API token'ı ile hashtag'den
creator listesi çekiyoruz. Native derleme (C++/greenlet) gerektirmez.

Hem CLI (python finder.py) hem web GUI (app.py) bu dosyayı kullanır.
Ana fonksiyon: find_creators(cfg) -> list[dict]
"""

import json
import os
import re
from typing import Dict, List, Optional

import requests

APIFY_BASE = "https://api.apify.com/v2"


# --- Ülke -> dil eşlemesi ------------------------------------------------
COUNTRY_LANG = {
    "TR": "tr",
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "IE": "en", "NZ": "en",
    "DE": "de", "AT": "de", "CH": "de",
    "FR": "fr", "BE": "fr",
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es", "PE": "es",
    "SA": "ar", "AE": "ar", "EG": "ar", "IQ": "ar", "JO": "ar", "MA": "ar",
    "IT": "it", "PT": "pt", "BR": "pt", "NL": "nl", "RU": "ru",
}

COUNTRY_NAME_TO_ISO = {
    "turkiye": "TR", "türkiye": "TR", "turkey": "TR", "tr": "TR", "turkce": "TR", "türkçe": "TR",
    "amerika": "US", "abd": "US", "usa": "US", "united states": "US", "us": "US",
    "ingiltere": "GB", "uk": "GB", "united kingdom": "GB", "gb": "GB",
    "almanya": "DE", "germany": "DE", "de": "DE",
    "fransa": "FR", "france": "FR", "fr": "FR",
    "ispanya": "ES", "spain": "ES", "es": "ES",
    "italya": "IT", "italy": "IT", "it": "IT",
    "hollanda": "NL", "netherlands": "NL", "nl": "NL",
    "kanada": "CA", "canada": "CA", "ca": "CA",
    "avustralya": "AU", "australia": "AU", "au": "AU",
    "meksika": "MX", "mexico": "MX", "mx": "MX",
    "arjantin": "AR", "argentina": "AR", "ar": "AR",
    "brezilya": "BR", "brazil": "BR", "br": "BR",
    "portekiz": "PT", "portugal": "PT", "pt": "PT",
    "rusya": "RU", "russia": "RU", "ru": "RU",
    "suudi arabistan": "SA", "saudi arabia": "SA", "sa": "SA",
    "bae": "AE", "uae": "AE", "ae": "AE",
    "misir": "EG", "mısır": "EG", "egypt": "EG", "eg": "EG",
}

# Türkçe'ye özgü karakterler ve sık kelimeler (metinden ülke/dil çıkarımı için).
TURKISH_CHARS = set("ışğüöçİ")
TURKISH_WORDS = {
    "ve", "bir", "için", "ile", "çok", "video", "takip", "içerik", "günlük",
    "tarif", "yemek", "moda", "gezi", "seyahat", "spor", "komik", "eğlence",
    "iş", "birlikte", "kanal", "abone", "merhaba", "selam", "türkiye", "türk",
    "öğrenci", "anne", "hayat", "aşk", "sizin", "benim",
}


def country_to_iso(value: str) -> Optional[str]:
    if not value:
        return None
    v = str(value).strip().lower()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return COUNTRY_NAME_TO_ISO.get(v)


def lang_for_country(iso: Optional[str]) -> str:
    if not iso:
        return "en"
    return COUNTRY_LANG.get(iso.upper(), "en")


def looks_turkish(text: str) -> bool:
    """Metinde güçlü Türkçe sinyali var mı? (karakter veya kelime)"""
    if not text:
        return False
    low = text.lower()
    if any(ch in TURKISH_CHARS for ch in text):
        return True
    tokens = set(re.findall(r"[a-zçğıöşü]+", low))
    return len(tokens & TURKISH_WORDS) >= 1


def load_config(path: Optional[str] = None) -> dict:
    if path is None:
        path = "config.json" if os.path.exists("config.json") else "config.example.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _first(d: dict, keys: List[str], default=None):
    for k in keys:
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
        elif k in d and d[k] not in (None, ""):
            return d[k]
    return default


def normalize_item(item: dict) -> Optional[dict]:
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

    # 1) Actor'un döndürdüğü ülke (varsa)
    country_raw = _first(
        item,
        ["country", "region", "countryCode", "authorMeta.region", "author.region", "location"],
        default="",
    )
    iso = country_to_iso(country_raw)

    # 2) Actor'un döndürdüğü dil (varsa)
    lang_raw = _first(item, ["language", "lang", "authorMeta.language"], default="")
    lang = str(lang_raw).lower()[:2] if lang_raw else ""

    # 3) Metin bazlı çıkarım (ülke/dil bilinmiyorsa): bio + nickname
    text_blob = f"{nickname} {bio}"
    turkish_signal = looks_turkish(text_blob)

    if not iso and turkish_signal:
        iso = "TR"
    if not lang:
        lang = lang_for_country(iso) if iso else ("tr" if turkish_signal else "en")

    return {
        "username": username,
        "nickname": nickname or username,
        "followers": followers,
        "bio": bio or "",
        "email": email or "",
        "country": iso or "",
        "lang": lang or "en",
        "turkish_signal": turkish_signal,
        "profile": f"https://www.tiktok.com/@{username}",
    }


def find_creators(cfg: dict) -> List[dict]:
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

    wanted = set()
    for c in cfg.get("countries", []) or []:
        iso = country_to_iso(c)
        if iso:
            wanted.add(iso)
    only_turkey = wanted == {"TR"}

    actor_input = cfg.get("apify_input") or {
        "hashtags": hashtags,
        "minFollowers": min_f,
        "maxFollowers": max_f,
        "maxItems": target * 4,  # filtre sonrası hedefe ulaşmak için bolca çek
    }
    if wanted:
        actor_input.setdefault("countries", sorted(wanted))

    url = f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items"
    resp = requests.post(url, params={"token": token}, json=actor_input, timeout=600)
    if resp.status_code >= 400:
        raise RuntimeError(f"Apify hatasi ({resp.status_code}): {resp.text[:300]}")

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
        f = rec["followers"]
        if f and (f < min_f or f > max_f):
            continue

        # --- Ülke filtresi (artık gerçekten eliyor) ---
        if wanted:
            if only_turkey:
                # Sadece Türkiye: ülke TR olmalı YA DA güçlü Türkçe sinyali olmalı.
                # (Actor ülke döndürmese bile metinden Türk creator'ı yakalar,
                #  yabancıları eler.)
                if rec["country"] != "TR" and not rec["turkish_signal"]:
                    continue
            else:
                # Belirli ülke(ler): ülke biliniyorsa listede olmalı.
                # Bilinmiyorsa dahil et (actor ülke vermeyince her şey elenmesin).
                if rec["country"] and rec["country"] not in wanted:
                    continue

        seen[rec["username"]] = rec
        if len(seen) >= target:
            break

    return sorted(seen.values(), key=lambda r: r["followers"], reverse=True)


def save_csv(rows: List[dict], out_csv: str) -> None:
    import csv
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["username", "nickname", "followers", "country", "lang", "email", "bio", "profile"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in
                             ["username", "nickname", "followers", "country", "lang", "email", "bio", "profile"]})


def _cli() -> None:
    cfg = load_config()
    print("Apify uzerinden araniyor... (birkac dakika surebilir)")
    rows = find_creators(cfg)
    out_csv = cfg.get("output_csv", "creators.csv")
    save_csv(rows, out_csv)
    print(f"\n=== BITTI ===\n{len(rows)} uretici bulundu -> {out_csv}")
    for r in rows[:10]:
        print(f"  @{r['username']}  {r['followers']} takipci  [{r['country'] or '?'} / {r['lang']}]")


if __name__ == "__main__":
    _cli()
