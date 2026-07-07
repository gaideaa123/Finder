"""CaptionAI Finder - Headless email-only AUTOPILOT (DM YOK).

Surekli calisir:
 1) TikTok ve/veya Instagram'da YENI icerik ureticisi bul (Apify VEYA ScrapeCreators)
 2) email'ini cikar
 3) Groq (Llama 3.3 70B) ile hiper-ozel email yaz
 4) gonder (coklu hesap, gunluk limit, insani gecikme)
 5) bekle, tekrar

DM ATILMAZ. Tum ayarlar environment variable'dan gelir.
Ucretsiz server (Fly.io / Oracle) icin tasarlandi; kalici DB sayesinde
restart'ta ayni kisileri tekrar getirmez.

Hangi platform(lar)da aranacagi PLATFORMS env ile secilir:
  PLATFORMS=tiktok            (varsayilan)
  PLATFORMS=instagram
  PLATFORMS=tiktok,instagram  (ikisi birden)

Hangi scraper kullanilacagi SCRAPER env ile secilir:
  SCRAPER=apify           (varsayilan)
  SCRAPER=scrapecreators  (SCRAPECREATORS_KEYS gerekli)
"""

import json
import logging
import os
import sys
import time

import crm
from finder import find_creators
from emailer import start_email_campaign, get_status as email_status

try:
    from ai import AIBrain
except Exception:
    AIBrain = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("autopilot")


def _split(v):
    return [x.strip() for x in (v or "").replace("\n", ",").split(",") if x.strip()]


SITE_URL = os.environ.get("SITE_URL", "thecaptionai.com")

CFG = {
    "apify_tokens": _split(os.environ.get("APIFY_TOKENS")),
    "groq_keys": _split(os.environ.get("GROQ_KEYS")),
    "hashtags": _split(os.environ.get("HASHTAGS")),
    "countries": _split(os.environ.get("COUNTRIES")),
    "platforms": _split(os.environ.get("PLATFORMS")) or ["tiktok"],
    "scraper": (os.environ.get("SCRAPER", "apify") or "apify").strip().lower(),
    "scrapecreators_keys": _split(os.environ.get("SCRAPECREATORS_KEYS")),
    "apify_actor_tiktok": os.environ.get("APIFY_ACTOR_TIKTOK", "paxiq~tiktok-influencer-scraper"),
    "apify_actor_instagram": os.environ.get("APIFY_ACTOR_INSTAGRAM", "apify~instagram-scraper"),
    "min_followers": int(os.environ.get("MIN_FOLLOWERS", "3000")),
    "max_followers": int(os.environ.get("MAX_FOLLOWERS", "80000")),
    "target_per_round": int(os.environ.get("TARGET_PER_ROUND", "40")),
    "hashtags_per_round": int(os.environ.get("HASHTAGS_PER_ROUND", "3")),
    "daily_limit": int(os.environ.get("DAILY_LIMIT_PER_ACCOUNT", "30")),
    "subject": os.environ.get("EMAIL_SUBJECT", "videolarin icin ufak bir sey"),
    "round_interval": int(os.environ.get("ROUND_INTERVAL_SECONDS", "900")),
    "idle_interval": int(os.environ.get("IDLE_INTERVAL_SECONDS", "3600")),
}

try:
    ACCOUNTS = json.loads(os.environ.get("EMAIL_ACCOUNTS", "[]"))
    if not isinstance(ACCOUNTS, list):
        ACCOUNTS = []
except Exception:
    log.error("EMAIL_ACCOUNTS gecerli JSON degil. Ornek: [{\"email\":\"..\",\"password\":\"app-pw\",\"from_name\":\"Ad\"}]")
    ACCOUNTS = []

PRODUCT_PITCH = (
    "CaptionAI: type your video topic and in 3 seconds get 4 viral-formula captions "
    "with strong hooks + ready hashtags, in 6 languages. Built solo by a 16-year-old."
)

FALLBACK = {
    "tr": "selam {name}, videolarini bir suredir takip ediyorum, tarzin cok iyi. caption yazmak beni hep zorluyordu, 16 yasindayim bunun icin kucuk bir arac yaptim: konuyu yaz saniyeler icinde 4 hazir caption. denersen fikrini merak ederim: {site}",
    "en": "hey {name}, been following your stuff and your style is great. writing captions always slowed me down, so at 16 i built a little tool: type the topic, get 4 ready captions in seconds. would love your honest take: {site}",
    "es": "hola {name}, sigo tu contenido y tu estilo me encanta. escribir captions me costaba, con 16 anos hice una herramienta: escribes el tema y salen 4 captions en segundos. me encantaria tu opinion: {site}",
    "de": "hey {name}, verfolge deinen content, dein stil ist top. captions schreiben hat mich aufgehalten, mit 16 hab ich ein tool gebaut: thema eingeben, 4 fertige captions in sekunden. feedback ware toll: {site}",
    "fr": "hey {name}, je suis ton contenu, ton style est top. ecrire les legendes me ralentissait, a 16 ans j'ai fait un outil: tu tapes le sujet, 4 legendes en secondes. ton avis m'interesse: {site}",
    "ar": "\u0645\u0631\u062d\u0628\u0627 {name}\u060c \u0623\u062a\u0627\u0628\u0639 \u0645\u062d\u062a\u0648\u0627\u0643 \u0648\u0623\u0633\u0644\u0648\u0628\u0643 \u0631\u0627\u0626\u0639. \u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0643\u0627\u0628\u0634\u0646 \u0643\u0627\u0646\u062a \u062a\u0628\u0637\u0626\u0646\u064a\u060c \u0648\u0639\u0645\u0631\u064a 16 \u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629: \u062a\u0643\u062a\u0628 \u0627\u0644\u0645\u0648\u0636\u0648\u0639 \u0648\u062a\u0639\u0637\u064a\u0643 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u0628\u062b\u0648\u0627\u0646\u064a. \u064a\u0647\u0645\u0646\u064a \u0631\u0623\u064a\u0643: {site}",
}

_BRAIN = None


def _brain():
    global _BRAIN
    if _BRAIN is not None:
        return _BRAIN
    if AIBrain is None or not CFG["groq_keys"]:
        return None
    try:
        _BRAIN = AIBrain(CFG["groq_keys"])
    except Exception as e:  # noqa: BLE001
        log.warning("Groq baslatilamadi: %s", e)
        _BRAIN = None
    return _BRAIN


def _fallback_email(creator):
    lang = creator.get("lang", "en")
    name = creator.get("nickname") or creator.get("username", "")
    return FALLBACK.get(lang, FALLBACK["en"]).replace("{name}", name).replace("{site}", SITE_URL)


def email_body(creator):
    """emailer bunu her alici icin cagirir: Groq ile hiper-ozel email, olmazsa fallback."""
    b = _brain()
    if b:
        try:
            return b.generate_dm(
                creator, creator.get("lang", "en"), PRODUCT_PITCH,
                learned_tips="", link_url=SITE_URL, channel="email",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Groq email uretemedi (%s), fallback kullaniliyor", str(e)[:80])
    return _fallback_email(creator)


def _rotate(tags, k, i):
    """Her tur farkli hashtag dilimi -> havuz degisir -> yeni kisiler."""
    if not tags:
        return []
    if len(tags) <= k:
        return tags
    start = (i * k) % len(tags)
    return [tags[(start + j) % len(tags)] for j in range(k)]


def _search(tags):
    scraper = CFG["scraper"]
    if scraper in ("scrapecreators", "scrape_creators", "sc"):
        if not CFG["scrapecreators_keys"]:
            raise RuntimeError("SCRAPECREATORS_KEYS bos")
    else:
        if not CFG["apify_tokens"]:
            raise RuntimeError("APIFY_TOKENS bos")
    base = {
        "scraper": scraper,
        "scrapecreators_keys": CFG["scrapecreators_keys"],
        "platforms": CFG["platforms"],
        "apify_actor": CFG["apify_actor_tiktok"],
        "apify_actor_tiktok": CFG["apify_actor_tiktok"],
        "apify_actor_instagram": CFG["apify_actor_instagram"],
        "hashtags": tags,
        "countries": CFG["countries"],
        "min_followers": CFG["min_followers"],
        "max_followers": CFG["max_followers"],
        "target_count": CFG["target_per_round"],
        "require_email": True,  # sadece email'i olanlar (email-only)
        "strict_country": True,
        "skip_seen": False,  # dedup CRM'de
        "exclude_usernames": list(crm.known_usernames()),  # AYNI KISILERI GETIRME
    }
    # ScrapeCreators tek key listesi kullanir; Apify coklu token'i iceride dener.
    if scraper in ("scrapecreators", "scrape_creators", "sc"):
        return find_creators(base)
    last = ""
    for tok in CFG["apify_tokens"]:
        try:
            return find_creators(dict(base, apify_token=tok))
        except Exception as e:  # noqa: BLE001
            last = str(e)
            if any(k in last.lower() for k in ["401", "402", "403", "quota", "payment", "insufficient", "unauthorized", "token"]):
                continue
            raise
    raise RuntimeError(last or "Tum Apify token'lari tukendi")


def _send_batch():
    if not ACCOUNTS:
        log.warning("EMAIL_ACCOUNTS bos, email gonderilemez")
        return
    if not crm.email_queue(limit=1):
        return
    res = start_email_campaign({
        "provider": "gmail",
        "accounts": ACCOUNTS,
        "subject": CFG["subject"],
        "daily_limit": CFG["daily_limit"],
        "build_body": email_body,
    })
    if not res.get("ok"):
        log.warning("Email kampanyasi baslamadi: %s", res.get("error"))
        return
    while email_status().get("running"):
        time.sleep(3)
    st = email_status()
    log.info("Email turu bitti: gonderilen=%s hatali=%s", st.get("sent"), st.get("failed"))


def run_forever():
    crm.init_db()
    log.info("Autopilot basladi | scraper=%s platform=%s hashtag=%s ulke=%s hesap=%s",
             CFG["scraper"], CFG["platforms"], CFG["hashtags"], CFG["countries"], len(ACCOUNTS))
    is_sc = CFG["scraper"] in ("scrapecreators", "scrape_creators", "sc")
    if is_sc and not CFG["scrapecreators_keys"]:
        log.error("SCRAPECREATORS_KEYS yok, cikiliyor"); return
    if not is_sc and not CFG["apify_tokens"]:
        log.error("APIFY_TOKENS yok, cikiliyor"); return
    if not CFG["hashtags"]:
        log.error("HASHTAGS yok, cikiliyor"); return

    round_i = 0
    while True:
        tags = _rotate(CFG["hashtags"], CFG["hashtags_per_round"], round_i)
        found = 0
        try:
            rows = _search(tags)
            found = crm.upsert_contacts(rows)  # sadece gercekten yeni + email'li
            log.info("Tur %s | hashtag=%s | %s aday, %s YENI kayit", round_i, tags, len(rows), found)
        except Exception as e:  # noqa: BLE001
            log.error("Arama hatasi: %s", str(e)[:200])

        try:
            _send_batch()
        except Exception as e:  # noqa: BLE001
            log.error("Email hatasi: %s", str(e)[:200])

        wait = CFG["round_interval"] if found else CFG["idle_interval"]
        log.info("Bekleniyor %ss (yeni kalmadiysa daha uzun)", wait)
        time.sleep(wait)
        round_i += 1


if __name__ == "__main__":
    try:
        run_forever()
    except KeyboardInterrupt:
        log.info("Durduruldu")
