"""
CaptionAI - İçerik Üretici Bulucu (Apify tabanlı)
=================================================

Actor: paxiq/tiktok-influencer-scraper
Gerçek input alanları: hashtags, min_followers, max_followers (0=limitsiz),
max_results, extract_emails, follow_bio_links, require_email, country_hint.
Gerçek çıktı alanları: handle, display_name, first_name, followers, bio,
email, bio_link, profile_url, hashtag_source.

Neden Apify? TikTok kazımayı bilerek engelliyor (msToken saniyede değişiyor).
Asenkron çalıştırıp yokluyoruz -> 300s senkron limitine (408) takılmaz.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional

import requests

APIFY_BASE = "https://api.apify.com/v2"

SUPPORTED_LANGS = ["tr", "en", "es", "de", "fr", "ar"]

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

TURKISH_CHARS = set("ışğüöçİ")
GERMAN_CHARS = set("äöüß")
SPANISH_CHARS = set("ñ¿¡")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")

LANG_WORDS = {
    "tr": {"ve", "bir", "için", "ile", "çok", "video", "takip", "içerik", "tarif",
           "yemek", "moda", "gezi", "seyahat", "spor", "eğlence", "kanal", "abone",
           "merhaba", "selam", "türkiye", "türk", "hayat", "günlük", "öğrenci", "anne"},
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
    # Actor çıktısı: handle, display_name, first_name, followers, bio, email,
    # bio_link, profile_url, hashtag_source. (Diğer actor'lar için de esnek.)
    username = _first(
        item,
        ["handle", "username", "uniqueId", "userName", "authorMeta.name", "author.uniqueId"],
    )
    if not username:
        return None
    username = str(username).lstrip("@")

    nickname = _first(
        item,
        ["display_name", "first_name", "nickname", "name", "fullName", "authorMeta.nickName"],
        default=username,
    )
    followers = _first(
        item,
        ["followers", "followerCount", "fans", "authorMeta.fans", "authorStats.followerCount"],
        default=0,
    )
    try:
        followers = int(followers)
    except (TypeError, ValueError):
        followers = 0

    bio = _first(item, ["bio", "signature", "authorMeta.signature", "description"], default="")
    email = _first(item, ["email", "authorMeta.email"], default="")
    profile = _first(item, ["profile_url", "profileUrl"], default=f"https://www.tiktok.com/@{username}")

    # country_hint input'tan pass-through (güvenilir değil), yine de oku.
    country_raw = _first(
        item, ["country_hint", "country", "region", "countryCode", "authorMeta.region"], default=""
    )
    iso = country_to_iso(country_raw)

    # Dil: metin bazlı çıkarım (bio + isim)
    text_blob = f"{nickname} {bio}"
    detected = detect_lang_from_text(text_blob)

    if not iso and detected:
        iso = LANG_MAIN_COUNTRY.get(detected)
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
        "profile": profile,
    }


def _fetch_dataset(dataset_id: str, token: str, limit: int) -> List[dict]:
    ds_url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
    resp = requests.get(ds_url, params={"token": token, "limit": limit}, timeout=60)
    if resp.status_code >= 400:
        return []
    data = resp.json()
    return data if isinstance(data, list) else []


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

    min_f = int(cfg.get("min_followers", 3000))
    max_f = int(cfg.get("max_followers", 80000))
    target = int(cfg.get("target_count", 100))

    wanted = set()
    for c in cfg.get("countries", []) or []:
        iso = country_to_iso(c)
        if iso:
            wanted.add(iso)
    wanted_langs = {lang_for_country(iso) for iso in wanted}

    # Actor'ın GERÇEK input alanları (şemadan).
    max_results = max(int(target * 1.5), target + 20)
    actor_input = cfg.get("apify_input") or {
        "hashtags": hashtags,
        "min_followers": min_f,
        "max_followers": max_f,  # 0 = limitsiz
        "max_results": max_results,
        "extract_emails": True,
        "follow_bio_links": False,  # hız için kapalı (bio link takibi yavaş)
    }
    # country_hint tek string, kesin filtre değil; sadece ilk ülkeyi ipucu ver.
    if wanted and "country_hint" not in actor_input:
        actor_input["country_hint"] = sorted(wanted)[0]

    poll_interval = float(cfg.get("poll_interval", 3))
    overall_timeout = float(cfg.get("overall_timeout", 240))

    # 1) ASENKRON başlat
    run_url = f"{APIFY_BASE}/acts/{actor}/runs"
    r = requests.post(run_url, params={"token": token}, json=actor_input, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Apify baslatma hatasi ({r.status_code}): {r.text[:300]}")
    run = r.json().get("data", {})
    run_id = run.get("id")
    dataset_id = run.get("defaultDatasetId")
    if not run_id or not dataset_id:
        raise RuntimeError("Apify run baslatilamadi (id yok).")

    all_norm: Dict[str, dict] = {}   # tüm normalize kayıtlar (filtresiz yedek)
    matched: Dict[str, dict] = {}    # ülke/dil filtresinden geçenler
    start = time.time()

    def collect() -> None:
        for raw in _fetch_dataset(dataset_id, token, max_results):
            rec = normalize_item(raw)
            if not rec or rec["username"] in all_norm:
                continue
            f = rec["followers"]
            if f and (f < min_f or f > max_f):
                continue
            all_norm[rec["username"]] = rec
            # Ülke/dil eşleşmesi
            if wanted:
                lang_ok = rec["detected_lang"] in wanted_langs if rec["detected_lang"] else False
                country_ok = rec["country"] in wanted if rec["country"] else False
                if lang_ok or country_ok:
                    matched[rec["username"]] = rec
            else:
                matched[rec["username"]] = rec

    status = run.get("status", "RUNNING")
    while True:
        time.sleep(poll_interval)
        collect()

        if len(matched) >= target:
            try:
                requests.post(f"{APIFY_BASE}/actor-runs/{run_id}/abort", params={"token": token}, timeout=15)
            except Exception:
                pass
            break

        try:
            sr = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": token}, timeout=15)
            status = sr.json().get("data", {}).get("status", status)
        except Exception:
            pass

        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            collect()
            break

        if time.time() - start > overall_timeout:
            try:
                requests.post(f"{APIFY_BASE}/actor-runs/{run_id}/abort", params={"token": token}, timeout=15)
            except Exception:
                pass
            collect()
            break

    # Ülke filtresi seçiliydi ama hiç eşleşme yoksa: kullanıcıya boş ekran
    # göstermek yerine filtresiz sonucu dön (dil tespiti actor verisine bağlı,
    # her zaman tutmayabilir). Eşleşme varsa onları önceler.
    pool = matched if matched else all_norm
    rows = sorted(pool.values(), key=lambda r: r["followers"], reverse=True)
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
