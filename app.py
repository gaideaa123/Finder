"""
CaptionAI Finder - Tam Sistem Sunucusu (Apify + Gemini + CRM + Email)
====================================================================

Calistir:  python app.py   ->  http://127.0.0.1:5000

Mimari:
  finder.py  -> Apify ile creator bulma
  ai.py      -> Gemini: insansi DM, goren profil analizi, yanit analizi, ogrenme
  crm.py     -> SQLite: kuyruk, durum, yanit orani, tekrar bulmama
  emailer.py -> otomatik email (insan hizinda, gunluk limit) - yasal/bansiz

TikTok DM gonderimi bilerek KULLANICIDA: kuyruk + tek tik profil ac, sen gonder
(insani, ban riski dusuk). Email kanali tam otomatik.

Anahtar bitince: /api/search ve AI uclari ok=false + need_key/need_gemini_key
doner; panel yeni anahtar ister, girince kaldigi yerden devam.
"""

import os
import random

from flask import Flask, jsonify, render_template, request

import crm
from finder import find_creators, load_config, SUPPORTED_LANGS
from emailer import start_email_campaign, get_status as email_status, stop_campaign

try:
    from ai import AIBrain, QuotaError
except Exception:  # google-generativeai yoksa AI uçları kapalı olur
    AIBrain, QuotaError = None, Exception

app = Flask(__name__)
crm.init_db()

# Runtime anahtar deposu (panelden güncellenebilir)
KEYS = {"apify": "", "gemini": ""}

# Ürün tanıtımı (AI DM üretiminde kullanılır) + varsayılan email gövdesi
PRODUCT_PITCH = (
    "CaptionAI: type your video topic and in 3 seconds get 4 viral-formula captions "
    "with strong hooks + ready hashtags, in 6 languages. Built solo by a 16-year-old. "
    "Link is in the bio."
)


# --- Fallback DM (AI yoksa) : dil başına insansı varyantlar ---
FALLBACK = {
    "tr": "selam {name}, videolarını takılıyorum \U0001F440 caption yazmak seni de sıkıyo mu? 16 yaşındayım tam bunun için bi araç yaptım, denersen bi söyle, link biomda",
    "en": "hey {name}, been loving your stuff \U0001F440 does writing captions annoy you too? i'm 16 and built a lil tool for exactly that, lmk if you try it, link's in my bio",
    "es": "hey {name}, me encanta tu contenido \U0001F440 ¿escribir captions también te aburre? tengo 16 e hice una herramienta para eso, dime si la pruebas, link en mi bio",
    "de": "hey {name}, feier deinen content \U0001F440 nervt dich captions schreiben auch? bin 16 und hab ein tool dafür gebaut, sag bescheid wenn du's testest, link in bio",
    "fr": "hey {name}, j'adore ton contenu \U0001F440 écrire les légendes te saoule aussi? j'ai 16 ans et j'ai fait un outil pour ça, dis-moi si tu testes, lien dans ma bio",
    "ar": "هاي {name}، أحب محتواك \U0001F440 كتابة الكابشن تزعجك؟ عمري 16 وسويت أداة لهذا، جربها وقلي، الرابط بالبايو",
}


def _fallback_dm(creator: dict) -> str:
    lang = creator.get("lang", "en")
    tpl = FALLBACK.get(lang, FALLBACK["en"])
    return tpl.replace("{name}", creator.get("nickname") or creator.get("username", ""))


def _email_body(creator: dict) -> str:
    """Email gövdesi: AI varsa ona, yoksa fallback'e düşer. Email uzun olabilir."""
    name = creator.get("nickname") or creator.get("username", "")
    lang = creator.get("lang", "en")
    brain = _brain()
    if brain:
        try:
            return brain.generate_dm(creator, lang, PRODUCT_PITCH)
        except QuotaError:
            pass
        except Exception:
            pass
    return _fallback_dm(creator)


def _brain():
    if AIBrain is None or not KEYS.get("gemini"):
        return None
    try:
        return AIBrain(KEYS["gemini"])
    except Exception:
        return None


@app.route("/")
def index():
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    return render_template("index.html", cfg=cfg, langs=SUPPORTED_LANGS)


# --- Anahtar yönetimi ---
@app.route("/api/keys", methods=["POST"])
def api_keys():
    data = request.get_json(force=True) or {}
    if "apify" in data:
        KEYS["apify"] = (data.get("apify") or "").strip()
    if "gemini" in data:
        KEYS["gemini"] = (data.get("gemini") or "").strip()
    return jsonify({"ok": True, "has_apify": bool(KEYS["apify"]), "has_gemini": bool(KEYS["gemini"])})


# --- Arama (bul + CRM'e ekle) ---
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

    # CRM'deki bilinenleri de finder'ın geçmişine ekleyerek tekrarı garanti et
    try:
        rows = find_creators(cfg)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        need = any(k in msg.lower() for k in ["401", "403", "token", "unauthorized", "payment", "quota", "insufficient"])
        return jsonify({"ok": False, "error": msg, "need_key": need}), 400

    # CRM'de zaten olanları çıkar (tekrar bulma yok)
    known = crm.known_usernames()
    fresh = [r for r in rows if r["username"].lower() not in known]

    # DM taslağı üret (AI varsa insansı, yoksa fallback)
    brain = _brain()
    learned = ""
    if brain:
        try:
            learned = brain.learn_from_stats(crm.learning_samples())
        except QuotaError:
            return jsonify({"ok": False, "error": "Gemini kotasi bitti", "need_gemini_key": True}), 400
        except Exception:
            learned = ""

    for r in fresh:
        if brain:
            try:
                r["message"] = brain.generate_dm(r, r.get("lang", "en"), PRODUCT_PITCH, learned)
            except QuotaError:
                return jsonify({"ok": False, "error": "Gemini kotasi bitti", "need_gemini_key": True,
                                "partial": True}), 400
            except Exception:
                r["message"] = _fallback_dm(r)
        else:
            r["message"] = _fallback_dm(r)

    crm.upsert_contacts(fresh)
    return jsonify({"ok": True, "count": len(fresh), "creators": fresh})


# --- AI: tek creator için DM yeniden üret ---
@app.route("/api/ai/dm", methods=["POST"])
def api_ai_dm():
    data = request.get_json(force=True) or {}
    creator = data.get("creator") or {}
    brain = _brain()
    if not brain:
        return jsonify({"ok": False, "error": "Gemini key yok", "need_gemini_key": True}), 400
    try:
        msg = brain.generate_dm(creator, creator.get("lang", "en"), PRODUCT_PITCH,
                                brain.learn_from_stats(crm.learning_samples()))
        if creator.get("username"):
            crm.set_message(creator["username"], msg)
        return jsonify({"ok": True, "message": msg})
    except QuotaError:
        return jsonify({"ok": False, "error": "Gemini kotasi bitti", "need_gemini_key": True}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


# --- AI: gören profil analizi (ekran görüntüsü) ---
@app.route("/api/ai/analyze-profile", methods=["POST"])
def api_ai_analyze():
    brain = _brain()
    if not brain:
        return jsonify({"ok": False, "error": "Gemini key yok", "need_gemini_key": True}), 400
    f = request.files.get("image")
    if not f:
        return jsonify({"ok": False, "error": "Gorsel yok"}), 400
    try:
        result = brain.analyze_profile(f.read(), f.mimetype or "image/png")
        return jsonify({"ok": True, "analysis": result})
    except QuotaError:
        return jsonify({"ok": False, "error": "Gemini kotasi bitti", "need_gemini_key": True}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


# --- Gönderildi işaretle (DM elle gönderilince) ---
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


# --- Yanıt kaydet + AI analiz ---
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
        except QuotaError:
            pass
        except Exception:
            pass
    crm.mark_replied(u, reply, sentiment, category)
    return jsonify({"ok": True, "sentiment": sentiment, "category": category, "suggested_reply": suggested})


# --- İstatistik / analiz ---
@app.route("/api/stats")
def api_stats():
    s = crm.stats()
    s["sent_today_dm"] = crm.sent_today("dm")
    s["sent_today_email"] = crm.sent_today("email")
    return jsonify({"ok": True, "stats": s})


@app.route("/api/queue")
def api_queue():
    channel = request.args.get("channel")
    return jsonify({"ok": True, "queue": crm.get_queue(channel=channel, limit=300)})


# --- Email kampanyası ---
@app.route("/api/email/start", methods=["POST"])
def api_email_start():
    data = request.get_json(force=True) or {}
    cfg = {
        "provider": data.get("provider", "gmail"),
        "email_user": data.get("email_user", ""),
        "email_password": data.get("email_password", ""),
        "from_name": data.get("from_name", ""),
        "subject": data.get("subject", "Senin icin ufak bir sey"),
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
