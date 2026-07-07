"""
ScrapeCreators saglayicisi (opt-in) - TikTok + Instagram
=======================================================

Apify'a ALTERNATIF. Varsayilan DEGIL: sadece cfg["scraper"] == "scrapecreators"
olunca finder.find_creators buraya yonlendirir. Apify yolu aynen korunur.

DB'ye, emailer'a, crm'e DOKUNMAZ. Sadece creator bulur ve finder ile ayni
semada satir dondurur (username, nickname, followers, bio, email, lang, ...).

Uclar (docs.scrapecreators.com):
  TikTok:    GET /v1/tiktok/search/hashtag    + GET /v1/tiktok/profile
  Instagram: GET /v1/instagram/search/hashtag + GET /v1/instagram/profile
Auth: header x-api-key. Rate limit yok (500 es zamanli altinda kal).
"""

import json
import os
from typing import Dict, List, Optional, Set

import requests

# finder'daki yardimcilari tekrar kullaniyoruz (finder bunu SADECE lazy import
# eder, o yuzden dairesel import olmaz).
from finder import (
    normalize_item,
    country_to_iso,
    lang_for_country,
    load_history,
    add_to_history,
    _resolve_platforms,
    _read_panel_secrets,
    _as_list,
)

BASE = "https://api.scrapecreators.com"
_AUTH_STATUSES = {401, 402, 403, 429}


def _keys(cfg: dict) -> List[str]:
    keys = cfg.get("scrapecreators_keys") or (
        [cfg.get("scrapecreators_key")] if cfg.get("scrapecreators_key") else []
    )
    # Panel/env fallback: secrets.local.json -> SCRAPECREATORS_KEYS
    if not keys:
        sec = _read_panel_secrets()
        keys = sec.get("scrapecreators_keys") or os.environ.get("SCRAPECREATORS_KEYS") or []
        keys = _as_list(keys)
    return [str(k).strip() for k in keys if k and "YAPISTIR" not in str(k)]


def _sc_get(path: str, params: dict, keys: List[str], timeout: int = 45):
    """GET + coklu key rotasyonu. Auth/kota hatasinda sonraki key'e gecer.
    Hicbir key calismaz + auth hatasi varsa RuntimeError; diger durumda None."""
    last_status = ""
    saw_auth = False
    for k in keys:
        try:
            r = requests.get(BASE + path, params=params, headers={"x-api-key": k}, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            last_status = str(e)
            continue
        if r.status_code < 400:
            try:
                return r.json()
            except Exception:  # noqa: BLE001
                return None
        last_status = str(r.status_code)
        if r.status_code in _AUTH_STATUSES:
            saw_auth = True
            continue  # sonraki key'i dene
        return None  # 400/404/500 vb: bu istek bos don
    if saw_auth:
        raise RuntimeError(f"ScrapeCreators: tum key'ler basarisiz (auth/kota, son={last_status}).")
    return None


def _deep_find(obj, keys, _depth: int = 0):
    """Ic ice yapida verilen anahtarlardan ilk bos-olmayani bulur (case-insensitive)."""
    if _depth > 6 or obj is None:
        return None
    keyset = {str(k).lower() for k in keys}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in keyset and v not in (None, "", [], {}):
                return v
        for v in obj.values():
            r = _deep_find(v, keys, _depth + 1)
            if r not in (None, "", [], {}):
                return r
    elif isinstance(obj, list):
        for it in obj:
            r = _deep_find(it, keys, _depth + 1)
            if r not in (None, "", [], {}):
                return r
    return None


def _extract_handles(data, platform: str) -> List[str]:
    """Arama sonucundan (video/post listesi) benzersiz kullanici handle'larini toplar."""
    out: List[str] = []
    username_keys = ("unique_id", "uniqueId", "username", "ownerUsername", "owner_username")

    def walk(o):
        if isinstance(o, dict):
            for k in username_keys:
                v = o.get(k)
                if v:
                    out.append(str(v).lstrip("@"))
                    break
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)

    walk(data)
    return out


def _next_cursor(data):
    has = _deep_find(data, ["has_more", "hasMore", "more_available", "has_next_page"])
    if has is False:
        return None
    return _deep_find(data, ["cursor", "nextCursor", "next_cursor", "max_id", "end_cursor"])


def _discover_handles(platform: str, hashtags: List[str], keys: List[str],
                      need: int, max_pages: int, region: str = "") -> List[str]:
    handles: List[str] = []
    seen: Set[str] = set()
    path = f"/v1/{platform}/search/hashtag"
    for tag in hashtags:
        cursor = None
        for _ in range(max_pages):
            params = {"hashtag": str(tag).lstrip("#")}
            if platform == "tiktok" and region:
                params["region"] = region
            if cursor is not None:
                params["cursor"] = cursor
            data = _sc_get(path, params, keys)
            if not data:
                break
            for h in _extract_handles(data, platform):
                hl = h.lower()
                if hl and hl not in seen:
                    seen.add(hl)
                    handles.append(h)
            cursor = _next_cursor(data)
            if len(handles) >= need or not cursor:
                break
        if len(handles) >= need:
            break
    return handles


def _profile_record(platform: str, handle: str, keys: List[str]) -> Optional[dict]:
    """Profil ucundan zenginlestir, finder.normalize_item ile son kayda cevir."""
    path = f"/v1/{platform}/profile"
    data = _sc_get(path, {"handle": handle}, keys)
    if not data:
        return None

    followers = _deep_find(data, ["followerCount", "follower_count", "followers", "fans", "edge_followed_by"])
    if isinstance(followers, dict):
        followers = followers.get("count") or followers.get("value") or 0

    bio = _deep_find(data, ["signature", "biography", "bio", "desc"]) or ""
    email = _deep_find(data, ["businessEmail", "business_email", "public_email", "publicEmail", "email"]) or ""
    bio_link = _deep_find(data, ["bioLink", "bio_link", "externalUrl", "external_url"]) or ""
    if isinstance(bio_link, dict):
        bio_link = bio_link.get("link") or bio_link.get("url") or ""
    nickname = _deep_find(data, ["nickname", "full_name", "fullName", "display_name", "name"]) or handle
    country = _deep_find(data, ["region", "country", "countryCode", "country_code"]) or ""
    uname = _deep_find(data, ["uniqueId", "unique_id", "username", "handle"]) or handle
    uname = str(uname).lstrip("@")

    profile_url = (
        f"https://www.tiktok.com/@{uname}" if platform == "tiktok"
        else f"https://www.instagram.com/{uname}/"
    )

    raw = {
        "username": uname,
        "handle": uname,
        "nickname": nickname or uname,
        "followers": followers or 0,
        "bio": bio or "",
        "signature": bio or "",
        "email": email or "",
        "bio_link": bio_link or "",
        "country": country or "",
        "profile_url": profile_url,
    }
    return normalize_item(raw, platform)


def find_creators_scrapecreators(cfg: dict) -> List[dict]:
    """finder.find_creators ile ayni sozlesme. ScrapeCreators uzerinden creator bulur."""
    keys = _keys(cfg)
    if not keys:
        raise RuntimeError("ScrapeCreators API key yok (scrapecreators_keys / SCRAPECREATORS_KEYS).")

    platforms = _resolve_platforms(cfg)
    hashtags = [str(h).lstrip("#") for h in cfg.get("hashtags", []) if str(h).strip()]
    if not hashtags:
        raise RuntimeError("En az bir hashtag gerekli.")

    min_f = int(cfg.get("min_followers", 3000))
    max_f = int(cfg.get("max_followers", 80000))
    target = int(cfg.get("target_count", 100))
    require_email = bool(cfg.get("require_email", False))
    strict_country = bool(cfg.get("strict_country", True))
    skip_seen = bool(cfg.get("skip_seen", True))
    max_pages = int(cfg.get("sc_max_pages", 5))
    region = str(cfg.get("sc_region", "") or "")

    exclude_users = {str(u).lower() for u in (cfg.get("exclude_usernames") or set())}
    exclude_emails = {str(e).strip().lower() for e in (cfg.get("exclude_emails") or set()) if e}

    wanted: Set[str] = set()
    for c in cfg.get("countries", []) or []:
        iso = country_to_iso(c)
        if iso:
            wanted.add(iso)
    wanted_langs = {lang_for_country(iso) for iso in wanted}

    history = load_history() if skip_seen else set()

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

    all_matched: Dict[str, dict] = {}
    errors: List[str] = []

    # Hedeften fazla handle topla (filtreler eleyecek).
    need_handles = max(target * 4, target + 40)

    for platform in platforms:
        try:
            handles = _discover_handles(platform, hashtags, keys, need=need_handles,
                                        max_pages=max_pages, region=region)
            for h in handles:
                if len([k for k in all_matched if k.startswith(platform + ":")]) >= target:
                    break
                hl = h.lower()
                if hl in exclude_users or (skip_seen and hl in history):
                    continue
                rec = _profile_record(platform, h, keys)
                if not rec:
                    continue
                em = (rec.get("email") or "").strip().lower()
                if em and em in exclude_emails:
                    continue
                f = rec["followers"]
                if f and (f < min_f or f > max_f):
                    continue
                if require_email and not rec["email"]:
                    continue
                if not matches_country(rec):
                    continue
                all_matched[f"{platform}:{rec['username'].lower()}"] = rec
        except Exception as e:  # noqa: BLE001
            errors.append(f"[{platform}] {e}")
            if len(platforms) == 1:
                raise
            continue

    if not all_matched and errors:
        raise RuntimeError("; ".join(errors))

    rows = sorted(all_matched.values(), key=lambda r: r["followers"], reverse=True)[:target]
    if skip_seen and rows:
        add_to_history([r["username"] for r in rows])
    return rows
