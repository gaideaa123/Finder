"""CaptionAI Finder - Apify tabanli creator bulma (16GB, asenkron, 6 dil)."""

import json
import os
import re
import time
from typing import Dict, List, Optional, Set

import requests

APIFY_BASE = "https://api.apify.com/v2"
HISTORY_FILE = "seen_history.json"

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
    "turkiye": "TR", "turkey": "TR", "tr": "TR",
    "amerika": "US", "abd": "US", "usa": "US", "united states": "US", "us": "US", "ingilizce": "US", "english": "US",
    "ingiltere": "GB", "uk": "GB", "united kingdom": "GB", "gb": "GB",
    "almanya": "DE", "germany": "DE", "de": "DE", "almanca": "DE", "deutsch": "DE",
    "fransa": "FR", "france": "FR", "fr": "FR", "francais": "FR",
    "ispanya": "ES", "spain": "ES", "es": "ES", "ispanyolca": "ES", "espanol": "ES",
    "arabistan": "SA", "saudi arabia": "SA", "sa": "SA", "arabic": "SA", "arab": "SA",
    "italya": "IT", "italy": "IT", "it": "IT",
    "hollanda": "NL", "netherlands": "NL", "nl": "NL",
    "kanada": "CA", "canada": "CA", "ca": "CA",
    "meksika": "MX", "mexico": "MX", "mx": "MX",
    "brezilya": "BR", "brazil": "BR", "br": "BR",
    "bae": "AE", "uae": "AE", "ae": "AE",
    "misir": "EG", "egypt": "EG", "eg": "EG",
}

TURKISH_CHARS = set("\u0131\u015f\u011f\u00fc\u00f6\u00e7\u0130")
GERMAN_CHARS = set("\u00e4\u00f6\u00fc\u00df")
SPANISH_CHARS = set("\u00f1\u00bf\u00a1")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

LANG_WORDS = {
    "tr": {"ve", "bir", "video", "takip", "icerik", "tarif", "yemek", "moda", "gezi",
           "spor", "kanal", "abone", "merhaba", "selam", "turkiye", "turk", "hayat", "gunluk"},
    "es": {"el", "la", "los", "las", "para", "con", "por", "vida", "hola", "gracias",
           "contenido", "receta", "comida", "viaje", "moda", "belleza"},
    "de": {"und", "der", "die", "das", "mit", "ich", "leben", "video", "kanal", "hallo",
           "essen", "reise", "mode", "rezept"},
    "fr": {"le", "la", "les", "pour", "avec", "et", "vie", "bonjour", "merci",
           "recette", "cuisine", "voyage", "mode"},
}


def load_history() -> Set[str]:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("seen", []))
    except Exception:
        return set()


def add_to_history(usernames: List[str]) -> None:
    seen = load_history()
    seen.update(u.lower() for u in usernames if u)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"seen": sorted(seen)}, f, ensure_ascii=False)
    except Exception:
        pass


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
    tokens = set(re.findall(r"[a-z\u00e0\u00e2\u00e4\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f6\u00f9\u00fb\u00fc\u00f1]+", low))
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
    username = _first(item, ["handle", "username", "uniqueId", "userName", "authorMeta.name", "author.uniqueId"])
    if not username:
        return None
    username = str(username).lstrip("@")

    nickname = _first(item, ["display_name", "first_name", "nickname", "name", "fullName", "authorMeta.nickName"], default=username)
    followers = _first(item, ["followers", "followerCount", "fans", "authorMeta.fans", "authorStats.followerCount"], default=0)
    try:
        followers = int(followers)
    except (TypeError, ValueError):
        followers = 0

    bio = _first(item, ["bio", "signature", "authorMeta.signature", "description"], default="")
    bio_link = _first(item, ["bio_link", "bioLink"], default="")

    email = _first(item, ["email", "authorMeta.email"], default="")
    if not email and bio:
        m = EMAIL_RE.search(bio)
        if m:
            email = m.group(0)

    profile = _first(item, ["profile_url", "profileUrl"], default=f"https://www.tiktok.com/@{username}")

    country_raw = _first(item, ["country_hint", "country", "region", "countryCode", "authorMeta.region"], default="")
    iso = country_to_iso(country_raw)

    detected = detect_lang_from_text(f"{nickname} {bio}")
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
        "bio_link": bio_link or "",
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
        raise RuntimeError("Gecerli bir Apify API token yok. apify.com'dan al ve panele yapistir.")

    actor = cfg.get("apify_actor", "paxiq~tiktok-influencer-scraper")
    hashtags = [h.lstrip("#") for h in cfg.get("hashtags", []) if h.strip()]
    if not hashtags:
        raise RuntimeError("En az bir hashtag gerekli.")

    min_f = int(cfg.get("min_followers", 3000))
    max_f = int(cfg.get("max_followers", 80000))
    target = int(cfg.get("target_count", 100))
    require_email = bool(cfg.get("require_email", False))
    strict_country = bool(cfg.get("strict_country", True))
    skip_seen = bool(cfg.get("skip_seen", True))
    apify_memory = int(cfg.get("apify_memory", 16384))

    wanted = set()
    for c in cfg.get("countries", []) or []:
        iso = country_to_iso(c)
        if iso:
            wanted.add(iso)
    wanted_langs = {lang_for_country(iso) for iso in wanted}

    history = load_history() if skip_seen else set()

    # Filtre (ulke/dil) + gecmis + email cok aday eler. Hedefe ulasmak icin
    # bolca aday cek: 6x + genis taban.
    max_results = max(int(target * 6), target + 120)
    actor_input = cfg.get("apify_input") or {
        "hashtags": hashtags,
        "min_followers": min_f,
        "max_followers": max_f,
        "max_results": max_results,
        "extract_emails": True,
        "follow_bio_links": True,  # email icin HER ZAMAN bio-linkleri de tara
    }
    if require_email:
        actor_input["require_email"] = True
    if wanted and "country_hint" not in actor_input:
        actor_input["country_hint"] = sorted(wanted)[0]

    poll_interval = float(cfg.get("poll_interval", 3))
    overall_timeout = float(cfg.get("overall_timeout", 360))

    run_url = f"{APIFY_BASE}/acts/{actor}/runs"
    r = requests.post(run_url, params={"token": token, "memory": apify_memory}, json=actor_input, timeout=30)
    if r.status_code >= 400:
        r = requests.post(run_url, params={"token": token}, json=actor_input, timeout=30)
        if r.status_code >= 400:
            raise RuntimeError(f"Apify baslatma hatasi ({r.status_code}): {r.text[:300]}")
    run = r.json().get("data", {})
    run_id = run.get("id")
    dataset_id = run.get("defaultDatasetId")
    if not run_id or not dataset_id:
        raise RuntimeError("Apify run baslatilamadi (id yok).")

    matched: Dict[str, dict] = {}
    start = time.time()

    def matches_country(rec: dict) -> bool:
        if not wanted:
            return True
        lang_ok = rec["detected_lang"] in wanted_langs if rec["detected_lang"] else False
        country_ok = rec["country"] in wanted if rec["country"] else False
        if strict_country:
            return lang_ok or country_ok
        if lang_ok or country_ok:
            return True
        return not (rec["country"] or rec["detected_lang"])

    def collect() -> None:
        for raw in _fetch_dataset(dataset_id, token, max_results):
            rec = normalize_item(raw)
            if not rec or rec["username"] in matched:
                continue
            if skip_seen and rec["username"].lower() in history:
                continue
            f = rec["followers"]
            if f and (f < min_f or f > max_f):
                continue
            if require_email and not rec["email"]:
                continue
            if not matches_country(rec):
                continue
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

    rows = sorted(matched.values(), key=lambda r: r["followers"], reverse=True)[:target]
    if skip_seen and rows:
        add_to_history([r["username"] for r in rows])
    return rows


def save_csv(rows: List[dict], out_csv: str) -> None:
    import csv
    fields = ["username", "nickname", "followers", "country", "lang", "email", "bio_link", "bio", "profile"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fields})


def _cli() -> None:
    cfg = load_config()
    print("Apify uzerinden araniyor... (asenkron, 16GB, erken durur)")
    rows = find_creators(cfg)
    out_csv = cfg.get("output_csv", "creators.csv")
    save_csv(rows, out_csv)
    print(f"BITTI: {len(rows)} uretici bulundu -> {out_csv}")
    for r in rows[:10]:
        print(f"  @{r['username']}  {r['followers']}  [{r['country'] or '?'}/{r['lang']}]  {r['email'] or '-'}")


if __name__ == "__main__":
    _cli()
