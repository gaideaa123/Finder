"""CaptionAI Finder - AI'siz. Bul + coklu Apify key + coklu hesap email otomasyonu."""

import os
import random

from flask import Flask, jsonify, render_template, request

import crm
from finder import find_creators, load_config, SUPPORTED_LANGS, lang_for_country, country_to_iso
from emailer import start_email_campaign, get_status as email_status, stop_campaign

app = Flask(__name__)
crm.init_db()

SITE_URL = "thecaptionai.com"

# Runtime durum
STATE = {
    "apify_tokens": [],   # birden cok token; sirayla denenir
    "accounts": [],       # email hesaplari [{email, password, from_name}]
}

# --- DM sablonlari (dil basi 3 varyant, duzgun native dil, DM'de LINK YOK) ---
DM = {
    "tr": [
        "selam {name}, videolarini bir suredir takip ediyorum, tarzin cok iyi. caption yazmak beni hep zorluyordu, 16 yasindayim bunun icin kucuk bir arac yaptim: konuyu yaziyorsun saniyeler icinde 4 hazir caption veriyor. denersen fikrini cok merak ederim, link biomda",
        "merhaba {name}, icerikelerin gercekten guzel. senin gibi duzenli paylasan birine sormak istedim: caption kismi en sikici yer degil mi? tam bunun icin bir arac yaptim, konuyu yaz 4 caption ciksin. biomdaki linke bakabilirsin, ne dusundugunu merak ediyorum",
        "selam {name}! icerigin iyi ama bence caption'lar biraz daha vurucu olsa izlenmen artar. onun icin ucretsiz bir arac yaptim, denemesi kolay. link biomda, geri donusun benim icin cok kiymetli",
    ],
    "en": [
        "hey {name}, been following your stuff for a bit and your style is great. writing captions always slowed me down, so at 16 i built a little tool for it: type the topic, get 4 ready captions in seconds. would love your honest take, link's in my bio",
        "hi {name}, your content is genuinely good. quick q for someone who posts consistently: isn't the caption the most annoying part? made a tool exactly for that. link's in my bio if you're curious",
        "hey {name}! your content's good but punchier captions would get you more views imo. built a free tool for that, easy to try. link's in my bio, your feedback means a lot",
    ],
    "es": [
        "hola {name}, sigo tu contenido hace un tiempo y tu estilo me encanta. escribir captions siempre me costaba, asi que con 16 anos hice una herramienta: escribes el tema y salen 4 captions en segundos. me encantaria tu opinion, link en mi bio",
        "hola {name}, tu contenido es muy bueno. una pregunta rapida: escribir captions no es lo mas pesado? hice una herramienta justo para eso. mira el link en mi bio si te interesa",
        "hola {name}! tu contenido es bueno pero captions mas potentes te darian mas vistas. hice una herramienta gratis para eso. link en mi bio, tu opinion vale mucho",
    ],
    "de": [
        "hey {name}, verfolge deinen content schon eine weile, dein stil ist top. captions schreiben hat mich immer aufgehalten, also hab ich mit 16 ein kleines tool gebaut: thema eingeben, in sekunden 4 fertige captions. wurde mich uber dein feedback freuen, link in bio",
        "hallo {name}, dein content ist echt gut. kurze frage: captions schreiben ist das nervigste, oder? hab genau dafur ein tool gemacht. link ist in meiner bio, falls du neugierig bist",
        "hey {name}! dein content ist gut, aber starkere captions wurden dir mehr views bringen. hab ein kostenloses tool dafur gebaut. link in bio, dein feedback bedeutet mir viel",
    ],
    "fr": [
        "hey {name}, je suis ton contenu depuis un moment, ton style est top. ecrire les legendes me ralentissait toujours, alors a 16 ans j'ai fait un petit outil: tu tapes le sujet, 4 legendes pretes en secondes. ton avis m'interesse, lien dans ma bio",
        "salut {name}, ton contenu est vraiment bien. petite question: ecrire les legendes c'est pas le pire? j'ai fait un outil pile pour ca. le lien est dans ma bio si ca t'interesse",
        "hey {name}! ton contenu est bon mais des legendes plus percutantes te donneraient plus de vues. j'ai fait un outil gratuit pour ca. lien dans ma bio, ton retour compte beaucoup",
    ],
    "ar": [
        "مرحبا {name}، أتابع محتواك من فترة وأسلوبك رائع. كتابة الكابشن كانت دائما تبطئني، فصنعت أداة صغيرة وعمري 16: تكتب الموضوع وتعطيك 4 كابشنات جاهزة بثواني. يهمني رأيك، الرابط بالبايو",
        "أهلا {name}، محتواك ممتاز. سؤال سريع: أليست كتابة الكابشن أصعب جزء؟ صنعت أداة لهذا بالضبط. الرابط بالبايو لو حابب",
        "{name} مرحبا! محتواك جيد لكن كابشنات أقوى ستزيد مشاهداتك. صنعت أداة مجانية لهذا. الرابط بالبايو، رأيك يهمني كثيرا",
    ],
}


def _dm_text(creator, channel="dm"):
    lang = creator.get("lang", "en")
    variants = DM.get(lang, DM["en"])
    msg = random.choice(variants).replace("{name}", creator.get("nickname") or creator.get("username", ""))
    if channel == "email":
        for tag in ["link biomda", "link's in my bio", "link en mi bio", "link in bio", "lien dans ma bio", "الرابط بالبايو"]:
            msg = msg.replace(tag, SITE_URL)
    return msg


def _email_body(creator):
    return _dm_text(creator, channel="email")


def _run_search(data):
    """Coklu Apify token ile arama; biri bitince sonrakine gecer. (rows, error, need_key) doner."""
    tokens = STATE["apify_tokens"] or ([data.get("apify_token")] if data.get("apify_token") else [])
    tokens = [t for t in tokens if t]
    if not tokens:
        return None, "Apify token yok", True

    countries = data.get("countries") or []
    base_cfg = {
        "apify_actor": "paxiq~tiktok-influencer-scraper",
        "hashtags": data.get("hashtags") or [],
        "countries": countries,
        "min_followers": data.get("min_followers", 3000),
        "max_followers": data.get("max_followers", 80000),
        "target_count": data.get("target_count", 60),
        "require_email": bool(data.get("require_email", False)),
        "strict_country": bool(data.get("strict_country", True)),
        "skip_seen": True,
    }

    last_err = ""
    for tok in tokens:
        cfg = dict(base_cfg, apify_token=tok)
        try:
            rows = find_creators(cfg)
            return rows, "", False
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            low = last_err.lower()
            # Token bitti/gecersiz -> sonraki token'i dene
            if any(k in low for k in ["401", "402", "403", "quota", "payment", "insufficient", "unauthorized", "token"]):
                continue
            # Baska hata -> dur
            break
    return None, last_err or "Tum Apify token'lar tukendi", True


def _finalize(rows, countries):
    """Dil override + dedup + DM mesaji + CRM'e ekle. Eklenen listeyi doner."""
    isos = {country_to_iso(c) for c in countries if country_to_iso(c)}
    forced = lang_for_country(list(isos)[0]) if len(isos) == 1 else ""
    if forced:
        for r in rows:
            if not r.get("detected_lang"):
                r["lang"] = forced

    known_u = crm.known_usernames()
    known_e = crm.known_emails()
    fresh = []
    seen_e = set()
    for r in rows:
        if r["username"].lower() in known_u:
            continue
        em = (r.get("email") or "").strip().lower()
        if em and (em in known_e or em in seen_e):
            continue  # ayni email tekrar yok
        if em:
            seen_e.add(em)
        r["message"] = _dm_text(r, channel="dm")
        fresh.append(r)

    crm.upsert_contacts(fresh)
    return fresh


@app.route("/")
def index():
    return render_template("index.html", langs=SUPPORTED_LANGS)


@app.route("/api/keys", methods=["POST"])
def api_keys():
    data = request.get_json(force=True) or {}
    toks = data.get("apify_tokens")
    if isinstance(toks, str):
        toks = [t.strip() for t in toks.replace("\n", ",").split(",") if t.strip()]
    if isinstance(toks, list):
        STATE["apify_tokens"] = [t.strip() for t in toks if t and t.strip()]
    return jsonify({"ok": True, "apify_count": len(STATE["apify_tokens"])})


@app.route("/api/email/accounts", methods=["POST"])
def api_accounts():
    data = request.get_json(force=True) or {}
    accs = data.get("accounts") or []
    clean = []
    for a in accs:
        e = (a.get("email") or "").strip()
        p = (a.get("password") or "").strip()
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


@app.route("/api/auto", methods=["POST"])
def api_auto():
    """Auto-bul + email: bul, CRM'e ekle, sonra email kampanyasini otomatik baslat."""
    data = request.get_json(force=True) or {}
    rows, err, need = _run_search(data)
    if rows is None:
        return jsonify({"ok": False, "error": err, "need_key": need}), 400
    fresh = _finalize(rows, data.get("countries") or [])

    with_email = sum(1 for r in fresh if r.get("email"))
    started = False
    email_err = ""
    if STATE["accounts"]:
        res = start_email_campaign({
            "provider": data.get("provider", "gmail"),
            "accounts": STATE["accounts"],
            "subject": data.get("subject", "videolarin icin ufak bir sey"),
            "daily_limit": int(data.get("daily_limit", 30)),
            "build_body": _email_body,
        })
        started = res.get("ok", False)
        email_err = res.get("error", "")
    else:
        email_err = "Once email hesabi ekle (Email sekmesi)."

    return jsonify({"ok": True, "count": len(fresh), "with_email": with_email,
                    "email_started": started, "email_error": email_err, "creators": fresh})


@app.route("/api/queue")
def api_queue():
    return jsonify({"ok": True, "queue": crm.get_queue(channel=request.args.get("channel", "dm"), limit=500)})


@app.route("/api/sent", methods=["POST"])
def api_sent():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    if not u:
        return jsonify({"ok": False}), 400
    if data.get("message"):
        crm.set_message(u, data["message"])
    crm.mark_sent(u, channel=data.get("channel", "dm"))
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
    u = data.get("username")
    reply = data.get("reply", "")
    if not u or not reply:
        return jsonify({"ok": False, "error": "username + reply gerekli"}), 400
    crm.mark_replied(u, reply)
    return jsonify({"ok": True})


@app.route("/api/stats")
def api_stats():
    s = crm.stats()
    s["sent_today_dm"] = crm.sent_today("dm")
    s["sent_today_email"] = crm.sent_today("email")
    return jsonify({"ok": True, "stats": s})


@app.route("/api/email/start", methods=["POST"])
def api_email_start():
    data = request.get_json(force=True) or {}
    if not STATE["accounts"]:
        return jsonify({"ok": False, "error": "Once email hesabi ekle."}), 400
    res = start_email_campaign({
        "provider": data.get("provider", "gmail"),
        "accounts": STATE["accounts"],
        "subject": data.get("subject", "videolarin icin ufak bir sey"),
        "daily_limit": int(data.get("daily_limit", 30)),
        "build_body": _email_body,
    })
    return jsonify(res)


@app.route("/api/email/status")
def api_email_status():
    return jsonify({"ok": True, "status": email_status()})


@app.route("/api/email/stop", methods=["POST"])
def api_email_stop():
    stop_campaign()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
