"""CaptionAI Finder - Groq AI + Apify + coklu hesap Email + CRM + Auto dongu.

Email-only autopilot: TikTok'ta creator bulur -> email'ini bulur -> Groq ile
hiper-ozel EMAIL uretir -> otomatik gonderir. DM GONDERMEZ. Ayni kisiyi tekrar
getirmez (CRM dedup + arama sirasinda eleme). Server'da 7/24 calisabilir (env + AUTOSTART).

Anahtar checker (Apify + Groq bakiye/kullanim) ayri sayfada: /checker
"""

import json
import os
import threading
import time

from flask import Flask, jsonify, render_template, request

import crm
from finder import find_creators, SUPPORTED_LANGS, lang_for_country, country_to_iso
from emailer import start_email_campaign, get_status as email_status, stop_campaign

try:
    from ai import AIBrain, QuotaError
except Exception:
    AIBrain, QuotaError = None, Exception

app = Flask(__name__)
crm.init_db()

# Bakiye/kullanim checker (Apify + Groq) - ayri sayfa: /checker
try:
    from checker import checker_bp
    app.register_blueprint(checker_bp)
except Exception:
    pass

SITE_URL = os.environ.get("SITE_URL", "thecaptionai.com")

STATE = {
    "apify_tokens": [],
    "groq_keys": [],
    "accounts": [],
    "auto": {"running": False, "found": 0, "rounds": 0, "last": "", "stop": False},
}

# Auto dongusunu ayni anda iki kez baslatmayi engeller.
_auto_lock = threading.Lock()

PRODUCT_PITCH = os.environ.get("PRODUCT_PITCH") or (
    "CaptionAI: type your video topic and in 3 seconds get 4 viral-formula captions "
    "with strong hooks + ready hashtags, in 6 languages. Built solo by a 16-year-old."
)

FALLBACK = {
    "tr": "selam {name}, videolarini bir suredir takip ediyorum, tarzin cok iyi. caption yazmak beni hep zorluyordu, 16 yasindayim bunun icin kucuk bir arac yaptim: konuyu yaz saniyeler icinde 4 hazir caption. denersen fikrini merak ederim, link biomda",
    "en": "hey {name}, been following your stuff and your style is great. writing captions always slowed me down, so at 16 i built a little tool: type the topic, get 4 ready captions in seconds. would love your honest take, link's in my bio",
    "es": "hola {name}, sigo tu contenido y tu estilo me encanta. escribir captions me costaba, con 16 anos hice una herramienta: escribes el tema y salen 4 captions en segundos. me encantaria tu opinion, link en mi bio",
    "de": "hey {name}, verfolge deinen content, dein stil ist top. captions schreiben hat mich aufgehalten, mit 16 hab ich ein tool gebaut: thema eingeben, 4 fertige captions in sekunden. feedback ware toll, link in bio",
    "fr": "hey {name}, je suis ton contenu, ton style est top. ecrire les legendes me ralentissait, a 16 ans j'ai fait un outil: tu tapes le sujet, 4 legendes en secondes. ton avis m'interesse, lien dans ma bio",
    "ar": "\u0645\u0631\u062d\u0628\u0627 {name}\u060c \u0623\u062a\u0627\u0628\u0639 \u0645\u062d\u062a\u0648\u0627\u0643 \u0648\u0623\u0633\u0644\u0648\u0628\u0643 \u0631\u0627\u0626\u0639. \u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0643\u0627\u0628\u0634\u0646 \u0643\u0627\u0646\u062a \u062a\u0628\u0637\u0626\u0646\u064a\u060c \u0648\u0639\u0645\u0631\u064a 16 \u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629: \u062a\u0643\u062a\u0628 \u0627\u0644\u0645\u0648\u0636\u0648\u0639 \u0648\u062a\u0639\u0637\u064a\u0643 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u0628\u062b\u0648\u0627\u0646\u064a. \u064a\u0647\u0645\u0646\u064a \u0631\u0623\u064a\u0643\u060c \u0627\u0644\u0631\u0627\u0628\u0637 \u0628\u0627\u0644\u0628\u0627\u064a\u0648",
}

def _fallback(creator, channel="email"):
    lang = creator.get("lang", "en")
    msg = FALLBACK.get(lang, FALLBACK["en"]).replace("{name}", creator.get("nickname") or creator.get("username", ""))
    if channel == "email":
        for t in ["link biomda", "link's in my bio", "link en mi bio", "link in bio", "lien dans ma bio", "\u0627\u0644\u0631\u0627\u0628\u0637 \u0628\u0627\u0644\u0628\u0627\u064a\u0648"]:
            msg = msg.replace(t, SITE_URL)
    return msg

def _brain():
    if AIBrain is None or not STATE["groq_keys"]:
        return None
    try:
        return AIBrain(STATE["groq_keys"])
    except Exception:
        return None

def _dm_for(creator, channel="email", brain=None, learned=""):
    b = brain or _brain()
    if b:
        try:
            return b.generate_dm(creator, creator.get("lang", "en"), PRODUCT_PITCH, learned,
                                 link_url=SITE_URL, channel=channel)
        except Exception:
            pass
    return _fallback(creator, channel)

def _email_body(creator):
    # Emailer once STATE'teki hazir mesaji kullanir; yoksa burdan uretir.
    return _dm_for(creator, channel="email")

def _run_search(data):
    tokens = STATE["apify_tokens"] or ([data.get("apify_token")] if data.get("apify_token") else [])
    tokens = [t for t in tokens if t]
    if not tokens:
        return None, "Apify token yok", True
    countries = data.get("countries") or []
    base = {
        "apify_actor": "paxiq~tiktok-influencer-scraper",
        "hashtags": data.get("hashtags") or [],
        "countries": countries,
        "min_followers": data.get("min_followers", 3000),
        "max_followers": data.get("max_followers", 80000),
        "target_count": data.get("target_count", 60),
        # Email-only: varsayilan olarak sadece email'i olanlar.
        "require_email": bool(data.get("require_email", True)),
        "strict_country": bool(data.get("strict_country", True)),
        # TEK HAFIZA: dedup CRM'de. Boylece Database'den 'Sil'/'Tekrar Bul' gercekten etki eder.
        "skip_seen": False,
        # TEKRAR BUG FIX: CRM'de olanlari arama sirasinda ele -> her tur yeni kisi.
        "exclude_usernames": crm.known_usernames(),
        "exclude_emails": crm.known_emails(),
    }
    last = ""
    for tok in tokens:
        try:
            return find_creators(dict(base, apify_token=tok)), "", False
        except Exception as e:  # noqa: BLE001
            last = str(e)
            if any(k in last.lower() for k in ["401", "402", "403", "quota", "payment", "insufficient", "unauthorized", "token"]):
                continue
            break
    return None, last or "Tum Apify token'lar tukendi", True

def _finalize(rows, countries):
    isos = {country_to_iso(c) for c in countries if country_to_iso(c)}
    forced = lang_for_country(list(isos)[0]) if len(isos) == 1 else ""
    if forced:
        for r in rows:
            if not r.get("detected_lang"):
                r["lang"] = forced
    known_u, known_e = crm.known_usernames(), crm.known_emails()
    brain = _brain()
    learned = ""
    if brain:
        try:
            learned = brain.learn_from_stats(crm.list_contacts(status="sent", limit=40))
        except Exception:
            learned = ""
    fresh, seen_e = [], set()
    for r in rows:
        if r["username"].lower() in known_u:
            continue
        em = (r.get("email") or "").strip().lower()
        if em and (em in known_e or em in seen_e):
            continue
        if em:
            seen_e.add(em)
        # Email-only: dogrudan EMAIL govdesi uret (emailer bunu yeniden uretmeden kullanir).
        r["message"] = _dm_for(r, channel="email", brain=brain, learned=learned)
        fresh.append(r)
    crm.upsert_contacts(fresh)
    return fresh

@app.route("/")
def index():
    return render_template("index.html", langs=SUPPORTED_LANGS)

@app.route("/health")
def health():
    return jsonify({"ok": True, "auto": STATE["auto"]["running"], "email": email_status().get("running", False)})

@app.route("/api/keys", methods=["POST"])
def api_keys():
    data = request.get_json(force=True) or {}
    for field, key in (("apify_tokens", "apify_tokens"), ("groq_keys", "groq_keys")):
        val = data.get(field)
        if isinstance(val, str):
            val = [t.strip() for t in val.replace("\n", ",").split(",") if t.strip()]
        if isinstance(val, list):
            STATE[key] = [t.strip() for t in val if t and t.strip()]
    ai_ok, ai_err = False, ""
    b = _brain()
    if b:
        try:
            ai_ok = b.ping()
            if not ai_ok:
                ai_err = "AI yanit vermedi (key/model?)."
        except QuotaError:
            ai_err = "Kota bitti."
        except Exception as e:  # noqa: BLE001
            ai_err = str(e)[:150]
    return jsonify({"ok": True, "apify_count": len(STATE["apify_tokens"]),
                    "groq_count": len(STATE["groq_keys"]), "ai_ok": ai_ok, "ai_error": ai_err})

@app.route("/api/email/accounts", methods=["POST"])
def api_accounts():
    data = request.get_json(force=True) or {}
    clean = []
    for a in data.get("accounts") or []:
        e, p = (a.get("email") or "").strip(), (a.get("password") or "").strip()
        if e and p:
            clean.append({"email": e, "password": p, "from_name": (a.get("from_name") or "").strip()})
    STATE["accounts"] = clean
    return jsonify({"ok": True, "count": len(clean), "emails": [a["email"] for a in clean]})

@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True) or {}
    rows, err, need = _run_search(data)
    if rows is None:
        return jsonify({"ok": False, "error": err, "need_key": need}), 400
    fresh = _finalize(rows, data.get("countries") or [])
    return jsonify({"ok": True, "count": len(fresh), "creators": fresh})

def _start_email():
    if not STATE["accounts"]:
        return {"ok": False, "error": "Once email hesabi ekle."}
    return start_email_campaign({
        "provider": os.environ.get("EMAIL_PROVIDER", "gmail"), "accounts": STATE["accounts"],
        "subject": os.environ.get("EMAIL_SUBJECT", "videolarin icin ufak bir sey"),
        "daily_limit": int(os.environ.get("DAILY_LIMIT", 30)),
        "build_body": _email_body,
    })

def _auto_loop(data):
    STATE["auto"] = {"running": True, "found": 0, "rounds": 0, "last": "baslatildi", "stop": False}
    # Server modunda kimse kalmayinca durma; bekle ve tekrar dene (7/24 kesintisiz).
    idle_sleep = int(os.environ.get("IDLE_SLEEP", 0))
    try:
        while not STATE["auto"]["stop"]:
            rows, err, _ = _run_search(data)
            if rows is None:
                STATE["auto"]["last"] = "Apify: " + (err or "hata")
                break
            fresh = _finalize(rows, data.get("countries") or [])
            STATE["auto"]["found"] += len(fresh)
            STATE["auto"]["rounds"] += 1
            STATE["auto"]["last"] = f"{len(fresh)} yeni bulundu, email atiliyor..."
            _start_email()
            while email_status().get("running"):
                if STATE["auto"]["stop"]:
                    break
                time.sleep(3)
            if len(fresh) == 0:
                if idle_sleep > 0 and not STATE["auto"]["stop"]:
                    STATE["auto"]["last"] = f"Yeni kisi yok, {idle_sleep}s sonra tekrar denenecek."
                    slept = 0
                    while slept < idle_sleep and not STATE["auto"]["stop"]:
                        time.sleep(3)
                        slept += 3
                    continue
                STATE["auto"]["last"] = "Yeni kisi kalmadi, durdu."
                break
            time.sleep(2)
    finally:
        STATE["auto"]["running"] = False

def _spawn_auto(data):
    with _auto_lock:
        if STATE["auto"]["running"]:
            return False
        STATE["auto"]["running"] = True
        threading.Thread(target=_auto_loop, args=(data,), daemon=True).start()
        return True

@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.get_json(force=True) or {}
    if STATE["auto"]["running"]:
        return jsonify({"ok": False, "error": "Auto zaten calisiyor."}), 400
    if not (STATE["apify_tokens"] or data.get("apify_token")):
        return jsonify({"ok": False, "error": "Apify token yok", "need_key": True}), 400
    if not _spawn_auto(data):
        return jsonify({"ok": False, "error": "Auto zaten calisiyor."}), 400
    return jsonify({"ok": True, "started": True})

@app.route("/api/auto/status")
def api_auto_status():
    return jsonify({"ok": True, "auto": STATE["auto"], "email": email_status()})

@app.route("/api/auto/stop", methods=["POST"])
def api_auto_stop():
    STATE["auto"]["stop"] = True
    stop_campaign()
    return jsonify({"ok": True})

@app.route("/api/queue")
def api_queue():
    return jsonify({"ok": True, "queue": crm.get_queue(channel=request.args.get("channel") or None, limit=500)})

@app.route("/api/sent", methods=["POST"])
def api_sent():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    if not u:
        return jsonify({"ok": False}), 400
    if data.get("message"):
        crm.set_message(u, data["message"])
    crm.mark_sent(u, channel=data.get("channel", "email"))
    return jsonify({"ok": True})

@app.route("/api/skip", methods=["POST"])
def api_skip():
    data = request.get_json(force=True) or {}
    if data.get("username"):
        crm.mark_skipped(data["username"])
    return jsonify({"ok": True})

@app.route("/api/reply", methods=["POST"])
def api_reply():
    data = request.get_json(force=True) or {}
    u, reply = data.get("username"), data.get("reply", "")
    if not u or not reply:
        return jsonify({"ok": False, "error": "username + reply gerekli"}), 400
    sentiment, category, suggested = "", "", ""
    b = _brain()
    if b:
        try:
            a = b.analyze_reply(data.get("dm", ""), reply, data.get("lang", "tr"))
            sentiment, category, suggested = a.get("sentiment", ""), a.get("category", ""), a.get("suggested_reply", "")
        except Exception:
            pass
    crm.mark_replied(u, reply, sentiment, category)
    return jsonify({"ok": True, "sentiment": sentiment, "category": category, "suggested_reply": suggested})

@app.route("/api/stats")
def api_stats():
    s = crm.stats()
    s["sent_today_dm"] = crm.sent_today("dm")
    s["sent_today_email"] = crm.sent_today("email")
    return jsonify({"ok": True, "stats": s})

@app.route("/api/db")
def api_db():
    return jsonify({"ok": True, "rows": crm.list_contacts(
        status=request.args.get("status") or None,
        channel=request.args.get("channel") or None,
        search=request.args.get("q", ""), limit=800)})

@app.route("/api/sent-emails")
def api_sent_emails():
    return jsonify({"ok": True, "rows": crm.sent_emails(limit=800)})

@app.route("/api/db/requeue", methods=["POST"])
def api_requeue():
    u = (request.get_json(force=True) or {}).get("username")
    if u:
        crm.requeue(u)
    return jsonify({"ok": True})

@app.route("/api/db/delete", methods=["POST"])
def api_delete():
    u = (request.get_json(force=True) or {}).get("username")
    if u:
        crm.delete_contact(u)
    return jsonify({"ok": True})

@app.route("/api/db/update", methods=["POST"])
def api_update():
    d = request.get_json(force=True) or {}
    u = d.get("username")
    if u:
        crm.update_contact(u, d.get("fields", {}))
    return jsonify({"ok": True})

@app.route("/api/email/start", methods=["POST"])
def api_email_start():
    return jsonify(_start_email())

@app.route("/api/email/status")
def api_email_status():
    return jsonify({"ok": True, "status": email_status()})

@app.route("/api/email/stop", methods=["POST"])
def api_email_stop():
    stop_campaign()
    return jsonify({"ok": True})

# ---- Server / env bootstrap (PC'siz 7/24 calisma icin) ------------------

def _split(v):
    return [t.strip() for t in (v or "").replace("\n", ",").split(",") if t.strip()]

def _norm_list(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return _split(v or "")

def _accounts_from(items):
    out = []
    for a in items or []:
        e, p = (a.get("email") or "").strip(), (a.get("password") or "").strip()
        if e and p:
            out.append({"email": e, "password": p, "from_name": (a.get("from_name") or "").strip()})
    return out

def bootstrap_from_env():
    """Anahtarlari + email hesaplarini once env'den, sonra secrets.local.json'dan yukler.
    Gizli dosya .gitignore'dadir; repoya asla gitmez."""
    STATE["apify_tokens"] = _split(os.environ.get("APIFY_TOKENS", ""))
    STATE["groq_keys"] = _split(os.environ.get("GROQ_KEYS", ""))
    raw = os.environ.get("EMAIL_ACCOUNTS", "").strip()
    if raw:
        try:
            STATE["accounts"] = _accounts_from(json.loads(raw))
        except Exception:
            pass
    # env bos ise gizli local dosyadan doldur
    for p in ("secrets.local.json", os.path.join(os.environ.get("DATA_DIR", "."), "secrets.local.json")):
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            break
        if not STATE["apify_tokens"]:
            STATE["apify_tokens"] = _norm_list(d.get("apify_tokens"))
        if not STATE["groq_keys"]:
            STATE["groq_keys"] = _norm_list(d.get("groq_keys"))
        if not STATE["accounts"] and d.get("email_accounts"):
            STATE["accounts"] = _accounts_from(d.get("email_accounts"))
        break

def _env_autostart_config():
    return {
        "hashtags": _split(os.environ.get("HASHTAGS", "")),
        "countries": _split(os.environ.get("COUNTRIES", "")),
        "min_followers": int(os.environ.get("MIN_FOLLOWERS", 3000)),
        "max_followers": int(os.environ.get("MAX_FOLLOWERS", 80000)),
        "target_count": int(os.environ.get("TARGET_COUNT", 60)),
        "require_email": os.environ.get("REQUIRE_EMAIL", "1") == "1",
        "strict_country": os.environ.get("STRICT_COUNTRY", "1") == "1",
    }

bootstrap_from_env()
if os.environ.get("AUTOSTART") == "1":
    cfg = _env_autostart_config()
    if cfg["hashtags"] and STATE["apify_tokens"]:
        _spawn_auto(cfg)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    # debug/reloader varsayilan KAPALI (RCE riski + reloader auto dongusunu iki kez baslatir).
    debug = os.environ.get("FLASK_DEBUG") == "1"
    print(f"\n CaptionAI Finder -> http://{host}:{port}  (checker: /checker)\n")
    app.run(debug=debug, host=host, port=port)
