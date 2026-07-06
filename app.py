"""
CaptionAI İçerik Üretici Bulucu - Web GUI sunucusu (Apify tabanlı, 6 dilli)
==========================================================================

Calistir:
    python app.py
Sonra tarayicida ac: http://127.0.0.1:5000

NOT: TikTok DM'de acik link (URL) gondermeyi spam sayip engelliyor. Bu yuzden
sablonlar URL yazmaz; kullaniciyi 'profilimdeki/biomdaki linke bak' diye kendi
biosundaki linke yonlendirir.
"""

import os
import random

from flask import Flask, jsonify, render_template, request

from finder import find_creators, load_config, save_csv, SUPPORTED_LANGS

app = Flask(__name__)


# --- Dil başına 3 DM varyantı (URL YOK, biodaki linke yönlendirir) -------
TEMPLATES = {
    "tr": [
        ("Selam {name} \U0001F44B\n\n16 ya\u015f\u0131nday\u0131m ve senin de ya\u015fad\u0131\u011f\u0131n bir "
         "\u015feyden b\u0131kt\u0131\u011f\u0131m i\u00e7in bunu yapt\u0131m: video haz\u0131r ama caption'da "
         "20 dakika tak\u0131l\u0131yorsun, sonra 'eh i\u015fte' deyip ge\u00e7iyorsun. CaptionAI'yi kodlad\u0131m: "
         "konunu yaz, 3 saniyede hook'u g\u00fc\u00e7l\u00fc, hashtag'i haz\u0131r 4 caption \u00e7\u0131ks\u0131n. "
         "Denemek istersen profilimdeki linkten ula\u015fabilirsin, geri bildirimin \u00e7ok k\u0131ymetli \U0001F680"),
        ("Merhaba {name} \u2728\nSenin gibi d\u00fczenli payla\u015fan birine sormak istedim: caption yazmak "
         "en sevmedi\u011fin k\u0131s\u0131m de\u011fil mi? 16 ya\u015f\u0131nday\u0131m, tam bunun i\u00e7in bir ara\u00e7 yapt\u0131m. "
         "Konunu giriyorsun, viral form\u00fcl\u00fcyle 4 caption + hashtag \u00e7\u0131kar\u0131yor. "
         "Merak edersen biomdaki linke bakabilirsin, ne d\u00fc\u015f\u00fcnd\u00fc\u011f\u00fcn\u00fc \u00e7ok merak ediyorum"),
        ("Selam {name}! \U0001F525\nH\u0131zl\u0131 olaca\u011f\u0131m: videolar\u0131n\u0131 g\u00f6rd\u00fcm, i\u00e7erik g\u00fczel ama "
         "caption'lar biraz daha vurucu olsa izlenmen artar. 16'l\u0131k biri olarak tam bunun i\u00e7in "
         "CaptionAI'yi yapt\u0131m: 3 saniyede hook'lu caption + hashtag. Profilimde linki var, bir dene, "
         "geri bildirimin benim i\u00e7in \u00e7ok de\u011ferli"),
    ],
    "en": [
        ("Hey {name} \U0001F44B\nI'm 16 and built this because of something you've probably felt: the "
         "video's ready but you get stuck on the caption for 20 min, then post something generic. "
         "CaptionAI fixes that: type your topic, get 4 captions with strong hooks + hashtags in 3s. "
         "If you wanna try it the link's in my profile, your honest feedback would mean a lot \U0001F680"),
        ("Hi {name} \u2728\nQuick one for someone who posts consistently: isn't writing captions the worst "
         "part? I'm 16 and made a tool exactly for that. Type your topic, it spits out 4 viral-formula "
         "captions + hashtags. Check the link in my bio if you're curious, I'd love your honest take"),
        ("Hey {name}! \U0001F525\nStraight up: your content is good but punchier captions would get you more "
         "views. I'm 16 and built CaptionAI for exactly this: hook-driven captions + hashtags in 3 seconds. "
         "The link's in my profile, give it a try, your feedback means a lot"),
    ],
    "es": [
        ("Hola {name} \U0001F44B\nTengo 16 a\u00f1os y cre\u00e9 esto por algo que seguro te pasa: el video est\u00e1 "
         "listo pero te atascas 20 min en el t\u00edtulo. CaptionAI lo soluciona: escribe tu tema y en 3s "
         "tienes 4 captions con ganchos fuertes + hashtags. Si quieres probarlo el enlace est\u00e1 en mi "
         "perfil, tu opini\u00f3n honesta significar\u00eda mucho \U0001F680"),
        ("Hola {name} \u2728\nUna pregunta r\u00e1pida para alguien que publica seguido: \u00bfno odias escribir los "
         "captions? Tengo 16 y hice una herramienta justo para eso. Escribes el tema y salen 4 captions "
         "con f\u00f3rmula viral + hashtags. Mira el enlace en mi bio si te interesa, me encantar\u00eda tu opini\u00f3n"),
        ("\u00a1Hola {name}! \U0001F525\nDirecto: tu contenido es bueno pero captions m\u00e1s potentes te dar\u00edan m\u00e1s "
         "vistas. Con 16 a\u00f1os cre\u00e9 CaptionAI para esto: captions con gancho + hashtags en 3 segundos. "
         "El enlace est\u00e1 en mi perfil, pru\u00e9balo, tu feedback vale mucho"),
    ],
    "de": [
        ("Hey {name} \U0001F44B\nIch bin 16 und habe das gebaut, weil du es sicher kennst: Video fertig, aber "
         "du h\u00e4ngst 20 Min an der Caption. CaptionAI l\u00f6st das: Thema eingeben, in 3s bekommst du 4 "
         "Captions mit starken Hooks + Hashtags. Wenn du's testen willst, der Link ist in meinem Profil, "
         "dein ehrliches Feedback w\u00fcrde mir viel bedeuten \U0001F680"),
        ("Hallo {name} \u2728\nKurze Frage an jemanden, der regelm\u00e4\u00dfig postet: Captions schreiben ist das "
         "Nervigste, oder? Ich bin 16 und habe genau daf\u00fcr ein Tool gemacht. Thema rein, 4 Captions mit "
         "viraler Formel + Hashtags raus. Schau in die Bio f\u00fcr den Link, ich w\u00fcrde mich \u00fcber dein Feedback freuen"),
        ("Hey {name}! \U0001F525\nGanz direkt: dein Content ist gut, aber st\u00e4rkere Captions br\u00e4chten dir mehr "
         "Views. Mit 16 habe ich CaptionAI genau daf\u00fcr gebaut: Hook-Captions + Hashtags in 3 Sekunden. "
         "Der Link ist in meinem Profil, probier's, dein Feedback bedeutet mir viel"),
    ],
    "fr": [
        ("Salut {name} \U0001F44B\nJ'ai 16 ans et j'ai cr\u00e9\u00e9 \u00e7a pour un truc que tu vis s\u00fbrement: la vid\u00e9o "
         "est pr\u00eate mais tu bloques 20 min sur la l\u00e9gende. CaptionAI r\u00e8gle \u00e7a: tu tapes ton sujet et en "
         "3s t'as 4 l\u00e9gendes avec des hooks forts + hashtags. Si tu veux l'essayer le lien est dans mon "
         "profil, ton avis honn\u00eate compterait beaucoup \U0001F680"),
        ("Bonjour {name} \u2728\nPetite question pour quelqu'un qui poste r\u00e9guli\u00e8rement: \u00e9crire les l\u00e9gendes "
         "c'est pas le pire? J'ai 16 ans et j'ai fait un outil pile pour \u00e7a. Tu entres ton sujet, \u00e7a sort "
         "4 l\u00e9gendes formule virale + hashtags. Le lien est dans ma bio si \u00e7a t'int\u00e9resse, ton avis compte"),
        ("Salut {name}! \U0001F525\nCash: ton contenu est bon mais des l\u00e9gendes plus percutantes te donneraient "
         "plus de vues. \u00c0 16 ans j'ai cr\u00e9\u00e9 CaptionAI pour \u00e7a: l\u00e9gendes avec hook + hashtags en 3 secondes. "
         "Le lien est dans mon profil, essaie, ton retour compte beaucoup"),
    ],
    "ar": [
        ("\u0645\u0631\u062d\u0628\u0627 {name} \U0001F44B\n\u0639\u0645\u0631\u064a 16 \u0648\u0635\u0646\u0639\u062a \u0647\u0630\u0627 \u0644\u0623\u0646\u0643 \u0628\u0627\u0644\u062a\u0623\u0643\u064a\u062f \u062a\u0648\u0627\u062c\u0647 \u0647\u0630\u0627: "
         "\u0627\u0644\u0641\u064a\u062f\u064a\u0648 \u062c\u0627\u0647\u0632 \u0644\u0643\u0646 \u062a\u0639\u0644\u0642 20 \u062f\u0642\u064a\u0642\u0629 \u0641\u064a \u0627\u0644\u062a\u0639\u0644\u064a\u0642. CaptionAI \u064a\u062d\u0644 \u0630\u0644\u0643: "
         "\u0627\u0643\u062a\u0628 \u0645\u0648\u0636\u0648\u0639\u0643 \u0648\u0641\u064a 3 \u062b\u0648\u0627\u0646\u064a \u062a\u062d\u0635\u0644 \u0639\u0644\u0649 4 \u062a\u0639\u0644\u064a\u0642\u0627\u062a \u0642\u0648\u064a\u0629 + \u0647\u0627\u0634\u062a\u0627\u063a. "
         "\u0625\u0630\u0627 \u0623\u0631\u062f\u062a \u062a\u062c\u0631\u0628\u062a\u0647 \u0627\u0644\u0631\u0627\u0628\u0637 \u0641\u064a \u0645\u0644\u0641\u064a \u0627\u0644\u0634\u062e\u0635\u064a\u060c \u0631\u0623\u064a\u0643 \u064a\u0647\u0645\u0646\u064a \U0001F680"),
        ("\u0623\u0647\u0644\u0627 {name} \u2728\n\u0633\u0624\u0627\u0644 \u0633\u0631\u064a\u0639 \u0644\u0634\u062e\u0635 \u064a\u0646\u0634\u0631 \u0628\u0627\u0633\u062a\u0645\u0631\u0627\u0631: \u0623\u0644\u064a\u0633 \u0643\u062a\u0627\u0628\u0629 "
         "\u0627\u0644\u062a\u0639\u0644\u064a\u0642 \u0623\u0633\u0648\u0623 \u062c\u0632\u0621\u061f \u0639\u0645\u0631\u064a 16 \u0648\u0635\u0646\u0639\u062a \u0623\u062f\u0627\u0629 \u0644\u0647\u0630\u0627 \u0628\u0627\u0644\u0636\u0628\u0637. "
         "\u0627\u0644\u0631\u0627\u0628\u0637 \u0641\u064a \u0627\u0644\u0628\u0627\u064a\u0648 \u0625\u0630\u0627 \u0623\u0631\u062f\u062a \u0627\u0644\u062a\u062c\u0631\u0628\u0629"),
        ("\u0645\u0631\u062d\u0628\u0627 {name}! \U0001F525\n\u0628\u0635\u0631\u0627\u062d\u0629: \u0645\u062d\u062a\u0648\u0627\u0643 \u062c\u064a\u062f \u0644\u0643\u0646 \u062a\u0639\u0644\u064a\u0642\u0627\u062a \u0623\u0642\u0648\u0649 "
         "\u0633\u062a\u0632\u064a\u062f \u0645\u0634\u0627\u0647\u062f\u0627\u062a\u0643. \u0635\u0646\u0639\u062a CaptionAI \u0644\u0647\u0630\u0627: \u062a\u0639\u0644\u064a\u0642\u0627\u062a + \u0647\u0627\u0634\u062a\u0627\u063a \u0641\u064a 3 \u062b\u0648\u0627\u0646\u064a. "
         "\u0627\u0644\u0631\u0627\u0628\u0637 \u0641\u064a \u0645\u0644\u0641\u064a \u0627\u0644\u0634\u062e\u0635\u064a\u060c \u062c\u0631\u0628\u0647"),
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder GUI -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
