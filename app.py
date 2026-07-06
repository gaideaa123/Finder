"""
CaptionAI Finder - Tam Sistem (Apify + Gemini/Vertex + CRM + Email)
==================================================================

Calistir:  python app.py   ->  http://127.0.0.1:5000

AI backend iki turlu:
  - apikey  : aistudio.google.com/apikey (hizli, ucretsiz kota)
  - vertex  : project + location + model (kota bitince gec). Vertex icin
              `gcloud auth application-default login` ya da service-account json.

TikTok DM gonderimi KULLANICIDA (insani, bansiz, linksiz). Email tam otomatik
ve linkli (thecaptionai.com).
"""

import os

from flask import Flask, jsonify, render_template, request

import crm
from finder import find_creators, load_config, SUPPORTED_LANGS
from emailer import start_email_campaign, get_status as email_status, stop_campaign

try:
    from ai import AIBrain, QuotaError
except Exception:
    AIBrain, QuotaError = None, Exception

app = Flask(__name__)
crm.init_db()

SITE_URL = "thecaptionai.com"

# Runtime yapılandırma (panelden güncellenir)
KEYS = {
    "apify": "",
    "ai_backend": "apikey",   # 'apikey' | 'vertex'
    "gemini": "",
    "vertex_project": "",
    "vertex_location": "",
    "vertex_model": "",
}

PRODUCT_PITCH = (
    "CaptionAI: type your video topic and in 3 seconds get 4 viral-formula captions "
    "with strong hooks + ready hashtags, in 6 languages. Built solo by a 16-year-old."
)

# AI yoksa kullanılacak insansı yedek DM (linksiz, bio'ya yönlendirir)
FALLBACK = {
    "tr": "selam {name}, videolarını takılıyorum \U0001F440 caption yazmak seni de sıkıyo mu? 16 yaşındayım tam bunun için bi araç yaptım, denersen bi söyle, link biomda",
    "en": "hey {name}, been loving your stuff \U0001F440 does writing captions annoy you too? i'm 16 and built a lil tool for exactly that, lmk if you try it, link's in my bio",
    "es": "hey {name}, me encanta tu contenido \U0001F440 ¿escribir captions también te aburre? tengo 16 e hice una herramienta para eso, dime si la pruebas, link en mi bio",
    "de": "hey {name}, feier deinen content \U0001F440 nervt dich captions schreiben auch? bin 16 und hab ein tool gebaut, sag bescheid wenn du's testest, link in bio",
    "fr": "hey {name}, j'adore ton contenu \U0001F440 écrire les légendes te saoule aussi? j'ai 16 ans et j'ai fait un outil pour ça, dis-moi si tu testes, lien dans ma bio",
    "ar": "هاي {name}، أحب محتواك \U0001F440 كتابة الكابشن تزعجك؟ عمري 16 وسويت أداة لهذا، جربها وقلي، الرابط بالبايو",
}


def _fallback_dm(creator: dict, channel: str = "dm") -> str:
    lang = creator.get("lang", "en")
    tpl = FALLBACK.get(lang, FALLBACK["en"])
    msg = tpl.replace("{name}", creator.get("nickname") or creator.get("username", ""))
    if channel == "email":
        # Email'de link olur
        msg = msg.replace("link biomda", SITE_URL).replace("link's in my bio", SITE_URL) \
                 .replace("link en mi bio", SITE_URL).replace("link in bio", SITE_URL) \
                 .replace("lien dans ma bio", SITE_URL).replace("الرابط بالبايو", SITE_URL)
    return msg


def _brain():
    if AIBrain is None:
        return None
    try:
        if KEYS.get("ai_backend") == "vertex" and KEYS.get("vertex_project"):
            return AIBrain(backend="vertex", project=KEYS["vertex_project"],
                           location=KEYS.get("vertex_location", ""),
                           model=KEYS.get("vertex_model", ""))
        if KEYS.get("gemini"):
            return AIBrain(backend="apikey", api_key=KEYS["gemini"])
    except Exception:
        return None
    return None


def _email_body(creator: dict) -> str:
    brain = _brain()
    if brain:
        try:
            return brain.generate_dm(creator, creator.get("lang", "en"), PRODUCT_PITCH,
                                     link_url=SITE_URL, channel="email")
        except Exception:
            pass
    return _fallback_dm(creator, channel="email")


@app.route("/")
def index():
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    return render_template("index.html", cfg=cfg, langs=SUPPORTED_LANGS)


@app.route("/api/keys", methods=["POST"])
def api_keys():
    data = request.get_json(force=True) or {}
    for k in ("apify", "gemini", "ai_backend", "vertex_project", "vertex_location", "vertex_model"):
        if k in data:
            KEYS[k] = (data.get(k) or "").strip()
    ai_ok = bool(KEYS.get("gemini")) or bool(KEYS.get("vertex_project"))
    return jsonify({"ok": True, "has_apify": bool(KEYS["apify"]), "has_ai": ai_ok,
                    "backend": KEYS.get("ai_backend")})


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True) or {}
    token = (data.get("apify_token") or KEYS.get("apify") or "").strip()
    if token:
        KEYS["apify"] = token

    try:
        base = load_config()
    except Exception:
        base = {}

    cfg = {
        "apify_token": token,
        "apify_actor": data.get("apify_actor") or base.get("apify_actor", "paxiq~tiktok-influencer-scraper"),
        "hashtags": data.get("hashtags") or [],
        "countries": data.get("countries") or [],
        "min_followers": data.get("min_followers", 3000),
        "max_followers": data.get("max_followers", 80000),
        "target_count": data.get("target_count", 100),
        "require_email": bool(data.get("require_email", False)),
        "strict_country": bool(data.get("strict_country", True)),
        "skip_seen": True,
    }

    try:
        rows = find_creators(cfg)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        need = any(k in msg.lower() for k in ["401", "403", "token", "unauthorized", "payment", "quota", "insufficient"])
        return jsonify({"ok": False, "error": msg, "need_key": need}), 400

    known = crm.known_usernames()
    fresh = [r for r in rows if r["username"].lower() not in known]

    brain = _brain()
    learned = ""
    if brain:
        try:
            learned = brain.learn_from_stats(crm.learning_samples())
        except QuotaError:
            return jsonify({"ok": False, "error": "AI kotasi bitti", "need_ai_key": True}), 400
        except Exception:
            learned = ""

    for r in fresh:
        if brain:
            try:
                r["message"] = brain.generate_dm(r, r.get("lang", "en"), PRODUCT_PITCH, learned, channel="dm")
            except QuotaError:
                return jsonify({"ok": False, "error": "AI kotasi bitti", "need_ai_key": True, "partial": True}), 400
            except Exception:
                r["message"] = _fallback_dm(r)
        else:
            r["message"] = _fallback_dm(r)

    crm.upsert_contacts(fresh)
    return jsonify({"ok": True, "count": len(fresh), "creators": fresh})


@app.route("/api/ai/dm", methods=["POST"])
def api_ai_dm():
    data = request.get_json(force=True) or {}
    creator = data.get("creator") or {}
    brain = _brain()
    if not brain:
        return jsonify({"ok": False, "error": "AI yok", "need_ai_key": True}), 400
    try:
        msg = brain.generate_dm(creator, creator.get("lang", "en"), PRODUCT_PITCH,
                                brain.learn_from_stats(crm.learning_samples()), channel="dm")
        if creator.get("username"):
            crm.set_message(creator["username"], msg)
        return jsonify({"ok": True, "message": msg})
    except QuotaError:
        return jsonify({"ok": False, "error": "AI kotasi bitti", "need_ai_key": True}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


# --- Metin bazlı uygunluk (profil görseli GEREKMEZ) ---
@app.route("/api/ai/fit", methods=["POST"])
def api_ai_fit():
    data = request.get_json(force=True) or {}
    creator = data.get("creator") or {}
    brain = _brain()
    if not brain:
        return jsonify({"ok": False, "error": "AI yok", "need_ai_key": True}), 400
    try:
        return jsonify({"ok": True, "fit": brain.analyze_fit(creator)})
    except QuotaError:
        return jsonify({"ok": False, "error": "AI kotasi bitti", "need_ai_key": True}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/ai/analyze-profile", methods=["POST"])
def api_ai_analyze():
    brain = _brain()
    if not brain:
        return jsonify({"ok": False, "error": "AI yok", "need_ai_key": True}), 400
    f = request.files.get("image")
    if not f:
        return jsonify({"ok": False, "error": "Gorsel yok"}), 400
    try:
        return jsonify({"ok": True, "analysis": brain.analyze_profile(f.read(), f.mimetype or "image/png")})
    except QuotaError:
        return jsonify({"ok": False, "error": "AI kotasi bitti", "need_ai_key": True}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/sent", methods=["POST"])
def api_sent():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    if not u:
        return jsonify({"ok": False}), 400
    if data.get("message"):
        crm.set_message(u, data["message"])
    crm.mark_sent(u, channel=data.get("channel", "dm"))
    return jsonify({"ok": True, "sent_today": crm.sent_today()})


@app.route("/api/skip", methods=["POST"])
def api_skip():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    if u:
        crm.mark_skipped(u)
    return jsonify({"ok": True})


@app.route("/api/reply", methods=["POST"])
def api_reply():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    reply = data.get("reply", "")
    if not u or not reply:
        return jsonify({"ok": False, "error": "username + reply gerekli"}), 400
    sentiment, category, suggested = "", "", ""
    brain = _brain()
    if brain:
        try:
            a = brain.analyze_reply(data.get("dm", ""), reply, data.get("lang", "tr"))
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


@app.route("/api/queue")
def api_queue():
    return jsonify({"ok": True, "queue": crm.get_queue(channel=request.args.get("channel"), limit=300)})


@app.route("/api/email/start", methods=["POST"])
def api_email_start():
    data = request.get_json(force=True) or {}
    cfg = {
        "provider": data.get("provider", "gmail"),
        "email_user": data.get("email_user", ""),
        "email_password": data.get("email_password", ""),
        "from_name": data.get("from_name", ""),
        "subject": data.get("subject", "videolarin icin ufak bir sey"),
        "daily_limit": int(data.get("daily_limit", 30)),
        "min_delay": float(data.get("min_delay", 25)),
        "max_delay": float(data.get("max_delay", 90)),
        "build_body": _email_body,
    }
    return jsonify(start_email_campaign(cfg))


@app.route("/api/email/status")
def api_email_status():
    return jsonify({"ok": True, "status": email_status()})


@app.route("/api/email/stop", methods=["POST"])
def api_email_stop():
    stop_campaign()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder (AI) -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
