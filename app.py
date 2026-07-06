"""CaptionAI Finder - Auto bul + email (AI yok, coklu key/hesap)."""

import os
import random

from flask import Flask, jsonify, render_template, request

import crm
from finder import find_creators, load_config, SUPPORTED_LANGS, lang_for_country, country_to_iso
from emailer import start_email_campaign, get_status as email_status, stop_campaign

app = Flask(__name__)
crm.init_db()

SITE_URL = "thecaptionai.com"

# Runtime: coklu apify token + coklu email hesabi
STATE = {
    "apify_tokens": [],   # [str]
    "accounts": [],       # [{email, password, provider, from_name}]
}

# --- DM sablonlari (linksiz, dogru dil) dile gore 3 varyant ---
DM = {
    "tr": [
        "selam {name}, videolarini bir suredir takip ediyorum, tarzin cok iyi. caption yazmak beni hep zorluyordu, 16 yasindayim bunun icin kucuk bir arac yaptim: konuyu yaziyorsun saniyeler icinde 4 hazir caption veriyor. bir denersen fikrini merak ederim, link biomda",
        "merhaba {name}, icerigin gercekten iyi ama daha vurucu caption'larla cok daha fazla izlenirsin bence. 16 yasindayim, tam bunun icin bir arac yaptim: konu yaz, hook'u guclu 4 caption cikiyor. istersen biomdaki linkten dene, geri bildirimin cok kiymetli",
        "selam {name}, senin gibi duzenli paylasan birine sormak istedim: caption yazmak en sevmedigin kisim degil mi? bunun icin bir arac kodladim, 3 saniyede caption + hashtag veriyor. biomda link var, bir bakarsan cok sevinirim",
    ],
    "en": [
        "hey {name}, been following your stuff for a bit and your style is great. writing captions always slowed me down, so at 16 i built a little tool: type the topic, get 4 ready captions in seconds. would love your take if you try it, link's in my bio",
        "hi {name}, your content's genuinely good but punchier captions would get you way more views imo. i'm 16 and made a tool exactly for that, hook-driven captions + hashtags in 3s. link's in my bio if you wanna try, your feedback means a lot",
        "hey {name}, quick one for someone who posts a lot: isn't writing captions the worst part? built a tool for it, type your topic and it gives you 4 captions. link in my bio, would love your honest take",
    ],
    "es": [
        "hola {name}, sigo tu contenido hace un tiempo y tu estilo me encanta. escribir captions siempre me costaba, asi que con 16 anos hice una herramienta: escribes el tema y te da 4 captions en segundos. me encantaria tu opinion, link en mi bio",
        "hola {name}, tu contenido es muy bueno pero con captions mas potentes tendrias muchas mas vistas. hice una herramienta justo para eso, captions + hashtags en 3s. link en mi bio si quieres probar",
        "hey {name}, una pregunta rapida: escribir captions no es lo peor? hice una herramienta para eso, escribes el tema y salen 4 captions. link en mi bio, me encantaria tu opinion",
    ],
    "de": [
        "hey {name}, verfolge deinen content schon eine weile, dein stil ist top. captions schreiben hat mich immer aufgehalten, also hab ich mit 16 ein kleines tool gebaut: thema eingeben, in sekunden 4 fertige captions. link in meiner bio, wenn du magst",
        "hallo {name}, dein content ist echt gut, aber staerkere captions wuerden dir mehr views bringen. hab ein tool dafuer gebaut, captions + hashtags in 3s. link in bio, dein feedback wuerde mir viel bedeuten",
        "hey {name}, kurze frage: captions schreiben ist das nervigste, oder? hab ein tool dafuer gemacht, thema rein, 4 captions raus. link in meiner bio, schau gern mal",
    ],
    "fr": [
        "hey {name}, je suis ton contenu depuis un moment, ton style est top. ecrire les legendes me ralentissait toujours, alors a 16 ans j'ai fait un petit outil: tu tapes le sujet, 4 legendes pretes en secondes. lien dans ma bio",
        "salut {name}, ton contenu est vraiment bien mais des legendes plus percutantes te donneraient plus de vues. j'ai fait un outil pour ca, legendes + hashtags en 3s. lien dans ma bio si tu veux tester",
        "hey {name}, petite question: ecrire les legendes c'est pas le pire? j'ai fait un outil pour ca, tu tapes le sujet et t'as 4 legendes. lien dans ma bio, ton avis m'interesse",
    ],
    "ar": [
        "مرحبا {name}، أتابع محتواك من فترة وأسلوبك رائع. كتابة الكابشن كانت دائما تبطئني، فصنعت أداة صغيرة وعمري 16: تكتب الموضوع وتعطيك 4 كابشنات جاهزة بثواني. الرابط بالبايو",
        "أهلا {name}، محتواك قوي بس كابشنات أقوى رح تجيب لك مشاهدات أكثر. سويت أداة لهذا، كابشنات + هاشتاق بـ3 ثواني. الرابط بالبايو لو حبيت تجرب",
        "هاي {name}، سؤال سريع: كتابة الكابشن أسوأ جزء صح؟ سويت أداة لهذا، تكتب الموضوع وتطلع 4 كابشنات. الرابط بالبايو، يهمني رأيك",
    ],
}

# Email govdesi (linkli)
EMAIL_BODY = {
    "tr": "Selam {name},\n\nVideolarini bir suredir takip ediyorum, tarzin gercekten iyi. Caption yazmanin ne kadar vakit aldigini bildigim icin (16 yasindayim, kendim yasadim) kucuk bir arac yaptim: CaptionAI. Konunu yaziyorsun, 3 saniyede hook'u guclu, hashtag'i hazir 4 caption veriyor, hem de 6 dilde.\n\nBir denersen ve dursut geri bildirim verirsen benim icin cok kiymetli olur: {url}\n\nSevgiler",
    "en": "Hi {name},\n\nI've been following your content for a bit and your style is genuinely great. I know how much time captions eat up (I'm 16 and lived it), so I built a little tool: CaptionAI. You type your topic and in 3 seconds it gives you 4 captions with strong hooks and ready hashtags, in 6 languages.\n\nIf you try it and share honest feedback it would mean a lot: {url}\n\nThanks!",
    "es": "Hola {name},\n\nSigo tu contenido hace un tiempo y tu estilo me encanta. Se cuanto tiempo quitan los captions (tengo 16 y lo vivi), asi que hice una herramienta: CaptionAI. Escribes el tema y en 3 segundos te da 4 captions con ganchos fuertes y hashtags listos, en 6 idiomas.\n\nSi la pruebas y me das tu opinion honesta significaria mucho: {url}\n\nGracias!",
    "de": "Hallo {name},\n\nich verfolge deinen content schon eine weile und dein stil ist wirklich gut. Ich weiss, wie viel zeit captions kosten (ich bin 16 und hab's erlebt), also hab ich ein tool gebaut: CaptionAI. Thema eingeben, in 3 sekunden 4 captions mit starken hooks und fertigen hashtags, in 6 sprachen.\n\nWenn du's testest und ehrliches feedback gibst, wuerde es mir viel bedeuten: {url}\n\nDanke!",
    "fr": "Salut {name},\n\nJe suis ton contenu depuis un moment et ton style est vraiment top. Je sais combien de temps prennent les legendes (j'ai 16 ans et je l'ai vecu), alors j'ai fait un outil: CaptionAI. Tu tapes ton sujet et en 3 secondes tu as 4 legendes avec des hooks forts et des hashtags prets, en 6 langues.\n\nSi tu l'essaies et donnes un retour honnete, ca compterait beaucoup: {url}\n\nMerci!",
    "ar": "مرحبا {name}،\n\nأتابع محتواك من فترة وأسلوبك رائع فعلا. أعرف كم يأخذ الكابشن من وقت (عمري 16 وعشت هذا)، فصنعت أداة: CaptionAI. تكتب الموضوع وبـ3 ثواني تعطيك 4 كابشنات بهوك قوي وهاشتاق جاهز، بـ6 لغات.\n\nلو جربتها وأعطيتني رأيك الصادق رح يعني لي الكثير: {url}\n\nشكرا!",
}


def _dm_for(creator):
    lang = creator.get("lang", "en")
    tpl = random.choice(DM.get(lang, DM["en"]))
    return tpl.replace("{name}", creator.get("nickname") or creator.get("username", ""))


def _email_body(creator):
    lang = creator.get("lang", "en")
    tpl = EMAIL_BODY.get(lang, EMAIL_BODY["en"])
    return tpl.replace("{name}", creator.get("nickname") or creator.get("username", "")).replace("{url}", SITE_URL)


def _run_find(data):
    """Ortak bulma mantigi: creator bul, dil zorla, DM sablonu ekle, CRM'e koy."""
    tokens = data.get("apify_tokens") or STATE["apify_tokens"]
    tokens = [t.strip() for t in tokens if t and t.strip()]
    if tokens:
        STATE["apify_tokens"] = tokens

    countries = data.get("countries") or []
    cfg = {
        "apify_tokens": tokens,
        "hashtags": data.get("hashtags") or [],
        "countries": countries,
        "min_followers": data.get("min_followers", 3000),
        "max_followers": data.get("max_followers", 80000),
        "target_count": data.get("target_count", 100),
        "require_email": bool(data.get("require_email", False)),
        "strict_country": bool(data.get("strict_country", True)),
        "skip_seen": True,
    }
    rows = find_creators(cfg)

    isos = {country_to_iso(c) for c in countries if country_to_iso(c)}
    forced = lang_for_country(list(isos)[0]) if len(isos) == 1 else ""
    if forced:
        for r in rows:
            if not r.get("detected_lang"):
                r["lang"] = forced

    known = crm.known_usernames()
    fresh = [r for r in rows if r["username"].lower() not in known]
    for r in fresh:
        r["message"] = _dm_for(r)
    crm.upsert_contacts(fresh)
    return fresh


@app.route("/")
def index():
    return render_template("index.html", langs=SUPPORTED_LANGS)


@app.route("/api/config", methods=["POST"])
def api_config():
    """Apify token listesi + email hesaplarini kaydet."""
    data = request.get_json(force=True) or {}
    if "apify_tokens" in data:
        STATE["apify_tokens"] = [t.strip() for t in data["apify_tokens"] if t and t.strip()]
    if "accounts" in data:
        accs = []
        for a in data["accounts"]:
            if a.get("email") and a.get("password"):
                accs.append({"email": a["email"].strip(), "password": a["password"].strip(),
                             "provider": a.get("provider", "gmail"), "from_name": a.get("from_name", "")})
        STATE["accounts"] = accs
    return jsonify({"ok": True, "apify_count": len(STATE["apify_tokens"]), "account_count": len(STATE["accounts"])})


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True) or {}
    if not data.get("hashtags"):
        return jsonify({"ok": False, "error": "En az bir hashtag gir."}), 400
    try:
        fresh = _run_find(data)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "count": len(fresh), "creators": fresh})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    """Auto-bul + email: bul, email'i olanlar kuyruga, coklu hesapla kampanya baslat."""
    data = request.get_json(force=True) or {}
    if not data.get("hashtags"):
        return jsonify({"ok": False, "error": "En az bir hashtag gir."}), 400
    if not STATE["accounts"] and not data.get("accounts"):
        return jsonify({"ok": False, "error": "Once email hesabi ekle (Email sekmesi)."}), 400
    if data.get("accounts"):
        api_config()  # gelen hesaplari kaydet

    try:
        fresh = _run_find(data)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400

    emailli = [f for f in fresh if f.get("email")]
    # Email kampanyasini otomatik baslat
    res = start_email_campaign({
        "accounts": STATE["accounts"],
        "daily_limit": int(data.get("daily_limit", 30)),
        "subject": data.get("subject", "videolarin icin ufak bir sey"),
        "build_body": _email_body,
    })
    return jsonify({"ok": True, "found": len(fresh), "with_email": len(emailli),
                    "email_started": res.get("ok", False), "email_error": res.get("error", "")})


@app.route("/api/queue")
def api_queue():
    return jsonify({"ok": True, "queue": crm.get_queue(channel="dm", limit=500)})


@app.route("/api/sent", methods=["POST"])
def api_sent():
    data = request.get_json(force=True) or {}
    u = data.get("username")
    if not u:
        return jsonify({"ok": False}), 400
    if data.get("message"):
        crm.set_message(u, data["message"])
    crm.mark_sent(u, channel="dm")
    return jsonify({"ok": True})


@app.route("/api/skip", methods=["POST"])
def api_skip():
    data = request.get_json(force=True) or {}
    if data.get("username"):
        crm.mark_skipped(data["username"])
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
    if data.get("accounts"):
        api_config()
    if not STATE["accounts"]:
        return jsonify({"ok": False, "error": "Once email hesabi ekle."}), 400
    res = start_email_campaign({
        "accounts": STATE["accounts"],
        "daily_limit": int(data.get("daily_limit", 30)),
        "subject": data.get("subject", "videolarin icin ufak bir sey"),
        "build_body": _email_body,
    })
    return jsonify(res)


@app.route("/api/email/status")
def api_email_status():
    return jsonify({"ok": True, "status": email_status(), "accounts": len(STATE["accounts"])})


@app.route("/api/email/stop", methods=["POST"])
def api_email_stop():
    stop_campaign()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
