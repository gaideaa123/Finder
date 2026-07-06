"""
CaptionAI - İçerik Üretici Bulucu (Apify tabanlı)
=================================================

Neden Apify? TikTok kazımayı bilerek engelliyor (msToken saniyede değişiyor).
Apify bu savaşı bizim yerimize veriyor: sabit API token'ı ile hashtag'den
creator listesi çekiyoruz. Native derleme (C++/greenlet) gerektirmez.

Hem CLI (python finder.py) hem web GUI (app.py) bu dosyayı kullanır.
Ana fonksiyon: find_creators(cfg) -> list[dict]

HIZ / TIMEOUT NOTU
------------------
Apify'ın 'run-sync-get-dataset-items' endpoint'i 300 saniyede (408) kesiliyordu.
Bunun yerine actor'ı asenkron başlatıp (POST /runs) durumunu yokluyoruz. Actor
çalışırken dataset'e düşen item'ları da okuyoruz; istenen sayıya ulaşınca run'ı
erkenden durdurup sonucu dönüyoruz (early stop = hız). Böylece 300s limiti yok.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional

import requests

APIFY_BASE = "https://api.apify.com/v2"

SUPPORTED_LANGS = ["tr", "en", "es", "de", "fr", "ar"]

# --- Ülke -> dil eşlemesi ------------------------------------------------
COUNTRY_LANG = {
    "TR": "tr",
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "IE": "en", "NZ": "en",
    "DE": "de", "AT": "de", "CH": "de",
    "FR": "fr", "BE": "fr",
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es", "PE": "es",
    "SA": "ar", "AE": "ar", "EG": "ar", "IQ": "ar", "JO": "ar", "MA": "ar", "DZ": "ar",
    "IT": "it", "PT": "pt", "BR": "pt", "NL": "nl", "RU": "ru",
}

LANG_MAIN_COUNTRY = {"tr": "TR", "en": "US", "es": "ES", "de": "DE", "fr": "FR", "ar": "SA"}

COUNTRY_NAME_TO_ISO = {
    "turkiye": "TR", "türkiye": "TR", "turkey": "TR", "tr": "TR",
    "amerika": "US", "abd": "US", "usa": "US", "united states": "US", "us": "US", "ingilizce": "US", "english": "US",
    "ingiltere": "GB", "uk": "GB", "united kingdom": "GB", "gb": "GB",
    "almanya": "DE", "germany": "DE", "de": "DE", "almanca": "DE", "deutsch": "DE",
    "fransa": "FR", "france": "FR", "fr": "FR", "fransızca": "FR", "francais": "FR",
    "ispanya": "ES", "spain": "ES", "es": "ES", "ispanyolca": "ES", "espanol": "ES", "español": "ES",
    "arabistan": "SA", "suudi arabistan": "SA", "saudi arabia": "SA", "sa": "SA", "arapça": "SA", "arabic": "SA", "arab": "SA",
    "italya": "IT", "italy": "IT", "it": "IT",
    "hollanda": "NL", "netherlands": "NL", "nl": "NL",
    "kanada": "CA", "canada": "CA", "ca": "CA",
    "meksika": "MX", "mexico": "MX", "mx": "MX",
    "brezilya": "BR", "brazil": "BR", "br": "BR",
    "bae": "AE", "uae": "AE", "ae": "AE",
    "misir": "EG", "mısır": "EG", "egypt": "EG", "eg": "EG",
}

# --- Dil sinyalleri (metinden çıkarım) -----------------------------------
TURKISH_CHARS = set("ışğüöçİ")
GERMAN_CHARS = set("äöüß")
SPANISH_CHARS = set("ñ¿¡")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

LANG_WORDS = {
    "tr": {"ve", "bir", "için", "ile", "çok", "video", "takip", "içerik", "tarif",
           "yemek", "moda", "gezi", "seyahat", "spor", "eğlence", "kanal", "abone",
           "merhaba", "selam", "türkiye", "türk", "hayat", "günlük"},
    "es": {"el", "la", "los", "las", "para", "con", "por", "vida", "amor", "videos",
           "hola", "gracias", "contenido", "receta", "comida", "viaje", "moda", "belleza"},
    "de": {"und", "der", "die", "das", "für", "mit", "ich", "leben", "video", "kanal",
           "hallo", "essen", "reise", "mode", "rezept", "täglich"},
    "fr": {"le", "la", "les", "pour", "avec", "et", "vie", "vidéo", "bonjour", "merci",
           "recette", "cuisine", "voyage", "mode", "beauté", "quotidien"},
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


def detect_lang_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    if ARABIC_RE.search(text):
        return "ar"
    if any(ch in TURKISH_CHARS for ch in text):
        return "tr"
    if any(ch in GERMAN_CHARS for ch in text):
        return "de"
    if any(ch in SPANISH_CHARS for ch in text):
        return "es"
    low = text.lower()
    tokens = set(re.findall(r"[a-zàâäçéèêëîïôöùûüñ]+", low))
    best_lang, best_hits = None, 0
    for lang, words in LANG_WORDS.items():
        hits = len(tokens & words)
        if hits > best_hits:
            best_lang, best_hits = lang, hits
    return best_lang if best_hits >= 1 else None


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

    country_raw = _first(
        item,
        ["country", "region", "countryCode", "authorMeta.region", "author.region", "location"],
        default="",
    )
    iso = country_to_iso(country_raw)

    lang_raw = _first(item, ["language", "lang", "authorMeta.language"], default="")
    lang = str(lang_raw).lower()[:2] if lang_raw else ""
    if lang not in SUPPORTED_LANGS:
        lang = ""

    text_blob = f"{nickname} {bio}"
    detected = detect_lang_from_text(text_blob)

    if not iso and detected:
        iso = LANG_MAIN_COUNTRY.get(detected)
    if not lang:
        lang = lang_for_country(iso) if iso else (detected or "en")
    if lang not in SUPPORTED_LANGS:
        lang = "en"

    return {
        "username": username,
        "nickname": nickname or username,
        "followers": followers,
        "bio": bio or "",
        "email": email or "",
        "country": iso or "",
        "lang": lang,
        "detected_lang": detected or "",
        "profile": f"https://www.tiktok.com/@{username}",
    }


def _passes_filters(rec: dict, min_f: int, max_f: int, wanted: set, wanted_langs: set) -> bool:
    f = rec["followers"]
    if f and (f < min_f or f > max_f):
        return False
    if wanted:
        country_ok = rec["country"] in wanted if rec["country"] else False
        lang_ok = rec["detected_lang"] in wanted_langs if rec["detected_lang"] else False
        if not (country_ok or lang_ok):
            # Hiç sinyal yoksa dahil et; sinyal var ama eşleşmiyorsa ele.
            if rec["country"] or rec["detected_lang"]:
                return False
    return True


def find_creators(cfg: dict) -> List[dict]:
    """
    Apify actor'ını ASENKRON başlatır, çalışırken dataset'i yoklar, hedefe
    ulaşınca run'ı durdurup sonucu döner. 300s senkron limitine takılmaz.
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

    min_f = int(cfg.get("min_followers", 3000))
    max_f = int(cfg.get("max_followers", 80000))
    target = int(cfg.get("target_count", 100))

    wanted = set()
    for c in cfg.get("countries", []) or []:
        iso = country_to_iso(c)
        if iso:
            wanted.add(iso)
    wanted_langs = {lang_for_country(iso) for iso in wanted}

    # HIZ: hedefin ~1.5 katı kadar aday çek (eskiden 4x idi, çok yavaştı).
    max_items = max(int(target * 1.5), target + 20)
    actor_input = cfg.get("apify_input") or {
        "hashtags": hashtags,
        "minFollowers": min_f,
        "maxFollowers": max_f,
        "maxItems": max_items,
    }
    if wanted:
        actor_input.setdefault("countries", sorted(wanted))

    poll_interval = float(cfg.get("poll_interval", 3))
    overall_timeout = float(cfg.get("overall_timeout", 240))  # toplam bekleme tavanı

    # 1) Actor'ı ASENKRON başlat
    run_url = f"{APIFY_BASE}/acts/{actor}/runs"
    r = requests.post(run_url, params={"token": token}, json=actor_input, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Apify baslatma hatasi ({r.status_code}): {r.text[:300]}")
    run = r.json().get("data", {})
    run_id = run.get("id")
    dataset_id = run.get("defaultDatasetId")
    if not run_id or not dataset_id:
        raise RuntimeError("Apify run baslatilamadi (id yok).")

    seen: Dict[str, dict] = {}
    start = time.time()

    def collect_dataset() -> None:
        """Dataset'teki mevcut item'ları oku ve filtreden geçenleri ekle."""
        ds_url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
        resp = requests.get(ds_url, params={"token": token, "clean": "true", "limit": max_items}, timeout=60)
        if resp.status_code >= 400:
            return
        items = resp.json()
        if not isinstance(items, list):
            return
        for raw in items:
            rec = normalize_item(raw)
            if not rec or rec["username"] in seen:
                continue
            if _passes_filters(rec, min_f, max_f, wanted, wanted_langs):
                seen[rec["username"]] = rec

    # 2) Çalışırken yokla; hedefe ulaşınca ya da bitince dur
    status = run.get("status", "RUNNING")
    while True:
        time.sleep(poll_interval)
        collect_dataset()

        if len(seen) >= target:
            # Yeterince bulduk: run'ı durdur (kredi + zaman tasarrufu) ve çık.
            try:
                requests.post(f"{APIFY_BASE}/actor-runs/{run_id}/abort", params={"token": token}, timeout=15)
            except Exception:
                pass
            break

        # Run durumunu kontrol et
        try:
            sr = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": token}, timeout=15)
            status = sr.json().get("data", {}).get("status", status)
        except Exception:
            pass

        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            collect_dataset()  # son bir kez topla
            break

        if time.time() - start > overall_timeout:
            try:
                requests.post(f"{APIFY_BASE}/actor-runs/{run_id}/abort", params={"token": token}, timeout=15)
            except Exception:
                pass
            collect_dataset()
            break

    rows = sorted(seen.values(), key=lambda r: r["followers"], reverse=True)
    return rows[:target]


def save_csv(rows: List[dict], out_csv: str) -> None:
    import csv
    fields = ["username", "nickname", "followers", "country", "lang", "email", "bio", "profile"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})


def _cli() -> None:
    cfg = load_config()
    print("Apify uzerinden araniyor... (asenkron, erken durur)")
    rows = find_creators(cfg)
    out_csv = cfg.get("output_csv", "creators.csv")
    save_csv(rows, out_csv)
    print(f"\n=== BITTI ===\n{len(rows)} uretici bulundu -> {out_csv}")
    for r in rows[:10]:
        print(f"  @{r['username']}  {r['followers']} takipci  [{r['country'] or '?'} / {r['lang']}]")


if __name__ == "__main__":
    _cli()
