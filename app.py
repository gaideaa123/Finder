"""
CaptionAI İçerik Üretici Bulucu - Web GUI sunucusu (Apify tabanlı, 6 dilli)
==========================================================================

Calistir:
    python app.py
Sonra tarayicida ac: http://127.0.0.1:5000

NOT: TikTok DM'de acik link (URL) gondermeyi spam sayip engelliyor. Sablonlar
URL yazmaz; kullaniciyi 'biomdaki linke bak' diye kendi biosundaki linke
yonlendirir. Mesajlar bilerek kisa, sahici ve gayri-resmi (AI gibi durmasin).
"""

import os
import random

from flask import Flask, jsonify, render_template, request

from finder import find_creators, load_config, save_csv, SUPPORTED_LANGS, HISTORY_FILE

app = Flask(__name__)


# --- Dil başına 3 DM varyantı --------------------------------------------
# Bilerek: kısa, samimi, küçük harf ağırlıklı, fragman cümleler, tek emoji.
# Amaç: gerçek bir 16 yaşındanın elle yazdığı gibi durmak, AI/otomasyon değil.
TEMPLATES = {
    "tr": [
        ("selam {name}, videolar\u0131n\u0131 tak\u0131l\u0131yorum bi ara \U0001F440 "
         "bi \u015fey sorcam: caption yazmak seni de s\u0131k\u0131yo mu? beni \u00e7ok s\u0131k\u0131yodu, "
         "16 ya\u015f\u0131nday\u0131m kendim bi ara\u00e7 yapt\u0131m onun i\u00e7in. konuyu yaz\u0131yosun 4 tane "
         "haz\u0131r caption veriyo. denersen bi s\u00f6yle nas\u0131l, linki biomda"),
        ("ya {name} selam \U0001F44B video haz\u0131r ama caption'da tak\u0131l\u0131p kal\u0131yosun ya hani, "
         "o hissi bildi\u011fim i\u00e7in kendim bi \u015fey kodlad\u0131m (16'y\u0131m). konuyu yaz, 3 saniyede "
         "hook'lu caption + hashtag \u00e7\u0131k\u0131yo. merak edersen biomda link var, fikrini merak ediyorum"),
        ("{name} selam! senin i\u00e7eriklerin ger\u00e7ekten iyi de bence caption'lar biraz daha "
         "vurucu olsa patlars\u0131n. onun i\u00e7in bi ara\u00e7 yapt\u0131m, tamamen bedava deneyebiliyosun. "
         "biomdaki linkten bak istersen, geri d\u00f6n\u00fc\u015f\u00fcn benim i\u00e7in \u00e7ok k\u0131ymetli \U0001F64C"),
    ],
    "en": [
        ("hey {name}, been watching your stuff \U0001F440 quick q: does writing captions annoy "
         "you too? it drove me nuts so i built a lil tool for it (i'm 16). you type the topic, "
         "it gives you 4 ready captions. lmk what you think if you try it, link's in my bio"),
        ("yo {name} \U0001F44B you know that moment when the video's ready but you're stuck on the "
         "caption forever? made something for exactly that. type your topic, get hook-y captions + "
         "hashtags in 3s. link's in my bio if you're curious, would love your honest take"),
        ("{name} hey! your content's genuinely good but punchier captions would blow it up imo. "
         "i built a free tool for that, you can just try it. link's in my bio, your feedback would "
         "mean a lot \U0001F64C"),
    ],
    "es": [
        ("hey {name}, llevo viendo tus videos \U0001F440 pregunta r\u00e1pida: \u00bfescribir captions "
         "tambi\u00e9n te aburre? a m\u00ed me hart\u00f3, as\u00ed que hice una herramienta (tengo 16). escribes "
         "el tema y te da 4 captions listos. dime qu\u00e9 tal si la pruebas, el link est\u00e1 en mi bio"),
        ("ey {name} \U0001F44B \u00bfconoces ese momento en que el video est\u00e1 listo pero te atascas "
         "en el caption? hice algo justo para eso. escribe el tema, salen captions con gancho + "
         "hashtags en 3s. el link est\u00e1 en mi bio, me encantar\u00eda saber tu opini\u00f3n"),
        ("{name} \u00a1hey! tu contenido es muy bueno pero con captions m\u00e1s potentes explotar\u00edas. "
         "hice una herramienta gratis para eso. el link est\u00e1 en mi bio, tu feedback vale much\u00edsimo \U0001F64C"),
    ],
    "de": [
        ("hey {name}, schau deine videos schon 'ne weile \U0001F440 kurze frage: nervt dich captions "
         "schreiben auch? mich hat's genervt, drum hab ich ein tool gebaut (bin 16). du tippst das "
         "thema, kriegst 4 fertige captions. sag mir bescheid wie's ist, link ist in meiner bio"),
        ("yo {name} \U0001F44B kennst du das, video fertig aber du h\u00e4ngst ewig an der caption? hab "
         "genau daf\u00fcr was gemacht. thema eintippen, hook-captions + hashtags in 3s. link ist in "
         "meiner bio falls du neugierig bist, w\u00fcrd mich \u00fcber dein feedback freuen"),
        ("{name} hey! dein content ist echt gut aber st\u00e4rkere captions w\u00fcrden dich pushen. hab "
         "ein kostenloses tool daf\u00fcr gebaut. link ist in meiner bio, dein feedback bedeutet mir viel \U0001F64C"),
    ],
    "fr": [
        ("hey {name}, je regarde tes vid\u00e9os depuis un moment \U0001F440 petite question: \u00e9crire les "
         "l\u00e9gendes \u00e7a te sa\u00f4le aussi? moi \u00e7a me sa\u00f4lait donc j'ai fait un outil (j'ai 16 ans). "
         "tu tapes le sujet, \u00e7a te donne 4 l\u00e9gendes pr\u00eates. dis-moi ce que t'en penses, lien dans ma bio"),
        ("yo {name} \U0001F44B tu connais ce moment o\u00f9 la vid\u00e9o est pr\u00eate mais tu bloques sur la "
         "l\u00e9gende? j'ai fait un truc pile pour \u00e7a. tu tapes le sujet, l\u00e9gendes avec hook + hashtags "
         "en 3s. le lien est dans ma bio si \u00e7a t'int\u00e9resse, ton avis m'int\u00e9resse"),
        ("{name} hey! ton contenu est vraiment bien mais des l\u00e9gendes plus percutantes te feraient "
         "exploser. j'ai fait un outil gratuit pour \u00e7a. le lien est dans ma bio, ton retour compte \u00e9norm\u00e9ment \U0001F64C"),
    ],
    "ar": [
        ("\u0647\u0627\u064a {name}\u060c \u0635\u0631\u0644\u064a \u0641\u062a\u0631\u0629 \u0623\u062a\u0627\u0628\u0639 \u0641\u064a\u062f\u064a\u0648\u0647\u0627\u062a\u0643 \U0001F440 \u0633\u0624\u0627\u0644 \u0633\u0631\u064a\u0639: "
         "\u0643\u062a\u0627\u0628\u0629 \u0627\u0644\u0643\u0627\u0628\u0634\u0646 \u062a\u0632\u0639\u062c\u0643 \u0623\u0646\u062a \u0643\u0645\u0627\u0646\u061f \u0623\u0632\u0639\u062c\u062a\u0646\u064a \u0641\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 (\u0639\u0645\u0631\u064a 16). "
         "\u062a\u0643\u062a\u0628 \u0627\u0644\u0645\u0648\u0636\u0648\u0639 \u0648\u062a\u0639\u0637\u064a\u0643 4 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u062c\u0627\u0647\u0632\u0629. \u062c\u0631\u0628\u0647\u0627 \u0648\u0642\u0644\u064a \u0631\u0623\u064a\u0643\u060c \u0627\u0644\u0631\u0627\u0628\u0637 \u0628\u0627\u0644\u0628\u0627\u064a\u0648"),
        ("\u0647\u0644\u0627 {name} \U0001F44B \u062a\u0639\u0631\u0641 \u0644\u0645\u0627 \u064a\u0643\u0648\u0646 \u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u062c\u0627\u0647\u0632 \u0628\u0633 \u062a\u0639\u0644\u0642 \u0628\u0627\u0644\u0643\u0627\u0628\u0634\u0646\u061f "
         "\u0633\u0648\u064a\u062a \u0634\u064a \u0644\u0647\u0630\u0627 \u0628\u0627\u0644\u0636\u0628\u0637. \u0627\u0643\u062a\u0628 \u0627\u0644\u0645\u0648\u0636\u0648\u0639\u060c \u0643\u0627\u0628\u0634\u0646\u0627\u062a + \u0647\u0627\u0634\u062a\u0627\u063a \u0628\u0640 3 \u062b\u0648\u0627\u0646\u064a. "
         "\u0627\u0644\u0631\u0627\u0628\u0637 \u0628\u0627\u0644\u0628\u0627\u064a\u0648 \u0625\u0630\u0627 \u062d\u0628\u064a\u062a"),
        ("{name} \u0647\u0627\u064a! \u0645\u062d\u062a\u0648\u0627\u0643 \u0642\u0648\u064a \u0628\u0633 \u0643\u0627\u0628\u0634\u0646\u0627\u062a \u0623\u0642\u0648\u0649 \u0631\u062d \u062a\u0641\u062c\u0631\u0643. "
         "\u0633\u0648\u064a\u062a \u0623\u062f\u0627\u0629 \u0645\u062c\u0627\u0646\u064a\u0629 \u0644\u0647\u0630\u0627. \u0627\u0644\u0631\u0627\u0628\u0637 \u0628\u0627\u0644\u0628\u0627\u064a\u0648\u060c \u0631\u0623\u064a\u0643 \u064a\u0647\u0645\u0646\u064a \u0643\u062b\u064a\u0631 \U0001F64C"),
    ],
}


def personalize(template: str, record: dict) -> str:
    name = record.get("nickname") or record.get("username", "")
    return (
        template
        .replace("{name}", name)
        .replace("{username}", record.get("username", ""))
        .replace("{bio}", record.get("bio", ""))
    )


def pick_template(lang: str, custom: dict) -> str:
    lang = lang if lang in TEMPLATES else "en"
    variants = None
    if custom and custom.get(lang):
        raw = custom[lang]
        parts = [p.strip() for p in raw.split("---") if p.strip()]
        variants = parts or None
    if not variants:
        variants = TEMPLATES[lang]
    return random.choice(variants)


@app.route("/")
def index():
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    joined = {lang: "\n---\n".join(v) for lang, v in TEMPLATES.items()}
    return render_template("index.html", templates=joined, cfg=cfg, langs=SUPPORTED_LANGS)


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True) or {}
    try:
        base = load_config()
    except Exception:
        base = {}

    cfg = {
        "apify_token": data.get("apify_token") or base.get("apify_token", ""),
        "apify_actor": data.get("apify_actor") or base.get("apify_actor", "paxiq~tiktok-influencer-scraper"),
        "hashtags": data.get("hashtags") or base.get("hashtags", []),
        "countries": data.get("countries") or base.get("countries", []),
        "min_followers": data.get("min_followers", base.get("min_followers", 3000)),
        "max_followers": data.get("max_followers", base.get("max_followers", 80000)),
        "target_count": data.get("target_count", base.get("target_count", 100)),
        "require_email": bool(data.get("require_email", False)),
        "strict_country": bool(data.get("strict_country", True)),
        "skip_seen": bool(data.get("skip_seen", True)),
    }

    custom = data.get("templates") or {}

    try:
        rows = find_creators(cfg)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400

    for r in rows:
        tpl = pick_template(r.get("lang", "en"), custom)
        r["message"] = personalize(tpl, r)

    try:
        save_csv(rows, base.get("output_csv", "creators.csv"))
    except Exception:
        pass

    return jsonify({"ok": True, "count": len(rows), "creators": rows})


@app.route("/api/reset-history", methods=["POST"])
def api_reset_history():
    """Bulunan geçmişini sıfırla (istersen baştan taransın)."""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder GUI -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
