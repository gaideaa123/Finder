"""
CaptionAI - Icerik Uretici Bulucu (Apify tabanli)
=================================================

Cok platformlu: TikTok ve/veya Instagram. Her creator'in GERCEK dili kendi
metninden (bio+isim) tespit edilir; boylece yabancilara kendi dilinde mail gider.
Coklu token, kalici gecmis, dedup.

Platform secimi:
  - cfg["platforms"] = ["tiktok", "instagram"]  (liste), ya da
  - cfg["platform"]  = "instagram"              (tekil), ya da
  - PLATFORMS env    = "tiktok,instagram"
  Hicbiri yoksa varsayilan: ["tiktok"] (eski davranis birebir korunur).

Actor secimi:
  - TikTok:    cfg["apify_actor"]     | PLATFORM_ACTORS["tiktok"]
  - Instagram: cfg["ig_apify_actor"]  | IG_APIFY_ACTOR env | PLATFORM_ACTORS["instagram"]
  Instagram icin farkli bir Apify actor'u kullanacaksan input sekli degisebilir;
  cfg["ig_apify_input"] (ya da cfg["apify_input"]) ile tam override edebilirsin.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional, Set

import requests

APIFY_BASE = "https://api.apify.com/v2"
HISTORY_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "seen_history.json")

SUPPORTED_LANGS = ["tr", "en", "es", "de", "fr", "ar"]

# Desteklenen platformlar -> varsayilan Apify actor'leri.
# Instagram actor'u swappable; kendi influencer-tarzi actor'unu kullanmak icin
# cfg["ig_apify_actor"] veya IG_APIFY_ACTOR env kullan.
PLATFORM_ACTORS = {
 "tiktok": "paxiq~tiktok-influencer-scraper",
 "instagram": "apify~instagram-scraper",
}

# Platform basina profil URL sablonu ({u} = username).
PLATFORM_PROFILE = {
 "tiktok": "https://www.tiktok.com/@{u}",
 "instagram": "https://www.instagram.com/{u}/",
}

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
 "turkiye": "TR", "t\u00fcrkiye": "TR", "turkey": "TR", "tr": "TR",
 "amerika": "US", "abd": "US", "usa": "US", "united states": "US", "us": "US", "ingilizce": "US", "english": "US",
 "ingiltere": "GB", "uk": "GB", "united kingdom": "GB", "gb": "GB",
 "almanya": "DE", "germany": "DE", "de": "DE", "almanca": "DE", "deutsch": "DE",
 "fransa": "FR", "france": "FR", "fr": "FR", "frans\u0131zca": "FR", "francais": "FR",
 "ispanya": "ES", "spain": "ES", "es": "ES", "ispanyolca": "ES", "espanol": "ES", "espa\u00f1ol": "ES",
 "arabistan": "SA", "suudi arabistan": "SA", "saudi arabia": "SA", "sa": "SA", "arap\u00e7a": "SA", "arabic": "SA", "arab": "SA",
 "italya": "IT", "italy": "IT", "it": "IT",
 "hollanda": "NL", "netherlands": "NL", "nl": "NL",
 "kanada": "CA", "canada": "CA", "ca": "CA",
 "meksika": "MX", "mexico": "MX", "mx": "MX",
 "brezilya": "BR", "brazil": "BR", "br": "BR",
 "bae": "AE", "uae": "AE", "ae": "AE",
 "misir": "EG", "m\u0131s\u0131r": "EG", "egypt": "EG", "eg": "EG",
}

TURKISH_CHARS = set("\u0131\u015f\u011f\u00fc\u00f6\u00e7\u0130")
GERMAN_CHARS = set("\u00e4\u00f6\u00fc\u00df")
SPANISH_CHARS = set("\u00f1\u00bf\u00a1")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Kelime tabanli tespit (ozel harf yoksa). Her dil icin ayirt edici kelimeler.
LANG_WORDS = {
 "tr": {"ve", "bir", "icin", "ile", "cok", "video", "takip", "icerik", "tarif",
 "yemek", "moda", "gezi", "seyahat", "spor", "eglence", "kanal", "abone",
 "merhaba", "selam", "turkiye", "turk", "hayat", "gunluk", "ogrenci", "anne", "is", "isbirligi"},
 "en": {"the", "and", "for", "with", "your", "my", "life", "daily", "content", "creator",
 "business", "inquiries", "email", "contact", "follow", "love", "official", "tips",
 "recipes", "food", "travel", "fashion", "beauty", "fitness", "vlog", "mom", "dad", "lifestyle"},
 "es": {"el", "la", "los", "las", "para", "con", "por", "vida", "amor", "videos",
 "hola", "gracias", "contenido", "receta", "comida", "viaje", "moda", "belleza", "mi"},
 "de": {"und", "der", "die", "das", "fur", "mit", "ich", "leben", "video", "kanal",
 "hallo", "essen", "reise", "mode", "rezept", "taglich", "mein"},
 "fr": {"le", "la", "les", "pour", "avec", "et", "vie", "video", "bonjour", "merci",
 "recette", "cuisine", "voyage", "mode", "beaute", "quotidien", "ma", "mon"},
}

def load_history() -> Set[str]:
 try:
 with open(HISTORY_FILE, "r", encoding="utf-8") as f:
 return set(json.load(f).get("seen", []))
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

def _norm(text: str) -> str:
 """Turkce/aksanli harfleri sadelestir ki kelime eslesmesi calissin."""
 tbl = str.maketrans("\u0131\u015f\u011f\u00fc\u00f6\u00e7\u0130\u00e2\u00e4\u00e0\u00e9\u00e8\u00ea\u00ee\u00ef\u00f4\u00fb\u00f1",
 "isguociaaaeeeiioun")
 return text.lower().translate(tbl)

def detect_lang_from_text(text: str) -> Optional[str]:
 """Creator'in kendi metninden GERCEK dilini tahmin eder. Bulamazsa None."""
 if not text:
 return None
 # 1) Ozel alfabe/harf sinyalleri (en guclu)
 if ARABIC_RE.search(text):
 return "ar"
 if any(ch in TURKISH_CHARS for ch in text):
 return "tr"
 if any(ch in GERMAN_CHARS for ch in text):
 return "de"
 if any(ch in SPANISH_CHARS for ch in text):
 return "es"
 # 2) Kelime skoru (Ingilizce dahil). En cok eslesen dil kazanir.
 low = _norm(text)
 tokens = set(re.findall(r"[a-z]+", low))
 best_lang, best_hits = None, 0
 for lang, words in LANG_WORDS.items():
 hits = len(tokens & words)
 if hits > best_hits:
 best_lang, best_hits = lang, hits
 return best_lang if best_hits >= 1 else None

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

def normalize_item(item: dict, platform: str = "tiktok") -> Optional[dict]:
 # username: TikTok + Instagram alanlarini birlikte tara
 username = _first(item, [
 "handle", "username", "uniqueId", "userName", "ownerUsername", "instagramUsername",
 "authorMeta.name", "author.uniqueId", "owner.username",
 ])
 if not username:
 return None
 username = str(username).lstrip("@")

 nickname = _first(item, [
 "display_name", "first_name", "nickname", "name", "fullName", "ownerFullName",
 "authorMeta.nickName", "owner.full_name",
 ], default=username)

 followers = _first(item, [
 "followers", "followerCount", "followersCount", "fans",
 "authorMeta.fans", "authorStats.followerCount", "edge_followed_by.count",
 ], default=0)
 try:
 followers = int(followers)
 except (TypeError, ValueError):
 followers = 0

 bio = _first(item, [
 "bio", "signature", "biography", "authorMeta.signature", "description",
 ], default="")
 bio_link = _first(item, [
 "bio_link", "bioLink", "bioLink.link", "external_url", "externalUrl",
 ], default="")

 email = _first(item, [
 "email", "public_email", "publicEmail", "businessEmail", "business_email",
 "authorMeta.email",
 ], default="")
 if not email and bio:
 m = EMAIL_RE.search(bio)
 if m:
 email = m.group(0)

 # Profil URL: platforma gore dogru sablon.
 url_tmpl = PLATFORM_PROFILE.get(platform, PLATFORM_PROFILE["tiktok"])
 profile = _first(item, ["profile_url", "profileUrl", "url"], default=url_tmpl.format(u=username))

 country_raw = _first(item, [
 "country_hint", "country", "region", "countryCode", "authorMeta.region",
 ], default="")
 iso = country_to_iso(country_raw)

 detected = detect_lang_from_text(f"{nickname} {bio}")

 # GERCEK DIL onceligi: 1) kisinin kendi metninden tespit, 2) kendi ulkesi, 3) en.
 # Arama ulkesi burada dayatilmaz (yabanci creator'a yanlis dil gitmesin).
 if detected:
 lang = detected
 elif iso:
 lang = lang_for_country(iso)
 else:
 lang = "en"
 if lang not in SUPPORTED_LANGS:
 lang = "en"

 return {
 "platform": platform,
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

def _start_run(actor: str, tokens: List[str], actor_input: dict):
 run_url = f"{APIFY_BASE}/acts/{actor}/runs"
 last_err = ""
 for tok in tokens:
 tok = tok.strip()
 if not tok:
 continue
 try:
 r = requests.post(run_url, params={"token": tok}, json=actor_input, timeout=30)
 except Exception as e: # noqa: BLE001
 last_err = str(e); continue
 if r.status_code < 400:
 return r.json().get("data", {}), tok
 last_err = f"{r.status_code}: {r.text[:150]}"
 if any(k in last_err.lower() for k in ["401", "402", "403", "quota", "payment", "insufficient", "limit", "unauthorized"]):
 continue
 break
 raise RuntimeError(f"Tum Apify token'lari basarisiz. Son hata -> {last_err}")

def _platforms_from(cfg: dict) -> List[str]:
 """cfg['platforms'] > cfg['platform'] > PLATFORMS env > ['tiktok']."""
 raw = cfg.get("platforms") or cfg.get("platform") or os.environ.get("PLATFORMS") or "tiktok"
 if isinstance(raw, str):
 raw = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
 out = []
 for p in raw:
 p = str(p).strip().lower()
 if p in PLATFORM_ACTORS and p not in out:
 out.append(p)
 return out or ["tiktok"]

def _actor_for(platform: str, cfg: dict) -> str:
 if platform == "instagram":
 return (cfg.get("ig_apify_actor") or os.environ.get("IG_APIFY_ACTOR")
 or PLATFORM_ACTORS["instagram"])
 # tiktok (varsayilan): eski cfg["apify_actor"] uyumlulugu korunur
 return cfg.get("apify_actor") or PLATFORM_ACTORS.get(platform, PLATFORM_ACTORS["tiktok"])

def _actor_input_for(platform: str, cfg: dict, hashtags: List[str],
 min_f: int, max_f: int, max_results: int,
 require_email: bool, wanted: Set[str]) -> dict:
 """Platform basina Apify actor input'u. Tam override:
  - Instagram: cfg['ig_apify_input']
  - TikTok:    cfg['apify_input']
 """
 if platform == "instagram" and cfg.get("ig_apify_input"):
 return dict(cfg["ig_apify_input"])
 if platform == "tiktok" and cfg.get("apify_input"):
 return dict(cfg["apify_input"])

 # Ortak/varsayilan sekil. Influencer-tarzi actor'ler bu alanlari anlar.
 actor_input = {
 "hashtags": hashtags,
 "min_followers": min_f,
 "max_followers": max_f,
 "max_results": max_results,
 "extract_emails": True,
 "follow_bio_links": True,
 }
 if platform == "instagram":
 # apify~instagram-scraper gibi actor'ler icin hashtag arama ipuclari.
 # Farkli actor kullanacaksan ig_apify_input ile override et.
 actor_input.setdefault("search", " ".join(f"#{h}" for h in hashtags))
 actor_input.setdefault("searchType", "hashtag")
 actor_input.setdefault("resultsType", "details")
 actor_input.setdefault("resultsLimit", max_results)
 actor_input.setdefault(
 "directUrls",
 [f"https://www.instagram.com/explore/tags/{h}/" for h in hashtags],
 )
 if require_email:
 actor_input["require_email"] = True
 if wanted and "country_hint" not in actor_input:
 actor_input["country_hint"] = sorted(wanted)[0]
 return actor_input

def find_creators(cfg: dict) -> List[dict]:
 tokens = cfg.get("apify_tokens") or ([cfg.get("apify_token")] if cfg.get("apify_token") else [])
 tokens = [t for t in tokens if t and "YAPISTIR" not in t]
 if not tokens:
 raise RuntimeError("Gecerli bir Apify API token yok.")

 hashtags = [h.lstrip("#") for h in cfg.get("hashtags", []) if h.strip()]
 if not hashtags:
 raise RuntimeError("En az bir hashtag gerekli.")

 platforms = _platforms_from(cfg)

 min_f = int(cfg.get("min_followers", 3000))
 max_f = int(cfg.get("max_followers", 80000))
 target = int(cfg.get("target_count", 100))
 require_email = bool(cfg.get("require_email", False))
 strict_country = bool(cfg.get("strict_country", True))
 skip_seen = bool(cfg.get("skip_seen", True))

 exclude_users = {str(u).lower() for u in (cfg.get("exclude_usernames") or set())}
 exclude_emails = {str(e).strip().lower() for e in (cfg.get("exclude_emails") or set()) if e}

 wanted = set()
 for c in cfg.get("countries", []) or []:
 iso = country_to_iso(c)
 if iso:
 wanted.add(iso)
 wanted_langs = {lang_for_country(iso) for iso in wanted}

 history = load_history() if skip_seen else set()
 max_results = max(int(target * 12) + len(exclude_users), target + 400)

 poll_interval = float(cfg.get("poll_interval", 3))
 overall_timeout = float(cfg.get("overall_timeout", 360))

 # Platformlar arasi ortak sonuc havuzu. Anahtar platform:username (cakisma olmaz).
 matched: Dict[str, dict] = {}

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

 def collect(dataset_id: str, token: str, platform: str) -> None:
 for raw in _fetch_dataset(dataset_id, token, max_results):
 rec = normalize_item(raw, platform=platform)
 if not rec:
 continue
 key = f"{platform}:{rec['username'].lower()}"
 if key in matched:
 continue
 uname = rec["username"].lower()
 if uname in exclude_users:
 continue
 if skip_seen and uname in history:
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
 matched[key] = rec

 def run_platform(platform: str) -> None:
 actor = _actor_for(platform, cfg)
 actor_input = _actor_input_for(platform, cfg, hashtags, min_f, max_f,
 max_results, require_email, wanted)
 run, token = _start_run(actor, tokens, actor_input)
 run_id = run.get("id")
 dataset_id = run.get("defaultDatasetId")
 if not run_id or not dataset_id:
 raise RuntimeError(f"Apify run baslatilamadi ({platform}, id yok).")

 start = time.time()
 status = run.get("status", "RUNNING")
 while True:
 time.sleep(poll_interval)
 collect(dataset_id, token, platform)
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
 collect(dataset_id, token, platform)
 break
 if time.time() - start > overall_timeout:
 try:
 requests.post(f"{APIFY_BASE}/actor-runs/{run_id}/abort", params={"token": token}, timeout=15)
 except Exception:
 pass
 collect(dataset_id, token, platform)
 break

 last_err = ""
 for platform in platforms:
 if len(matched) >= target:
 break
 try:
 run_platform(platform)
 except Exception as e: # noqa: BLE001
 # Bir platform patlarsa digerine devam et; hepsi patlarsa en sonda raise.
 last_err = f"{platform}: {str(e)[:150]}"
 continue

 if not matched and last_err:
 raise RuntimeError(f"Hicbir platformdan sonuc alinamadi. Son hata -> {last_err}")

 rows = sorted(matched.values(), key=lambda r: r["followers"], reverse=True)[:target]
 if skip_seen and rows:
 add_to_history([r["username"] for r in rows])
 return rows

def save_csv(rows: List[dict], out_csv: str) -> None:
 import csv
 fields = ["platform", "username", "nickname", "followers", "country", "lang", "email", "bio_link", "bio", "profile"]
 with open(out_csv, "w", newline="", encoding="utf-8") as f:
 writer = csv.DictWriter(f, fieldnames=fields)
 writer.writeheader()
 for r in rows:
 writer.writerow({k: r.get(k, "") for k in fields})
