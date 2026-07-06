"""
CaptionAI İçerik Üretici Bulucu - Web GUI sunucusu (Apify tabanlı)
=================================================================

Calistir:
    python app.py
Sonra tarayicida ac: http://127.0.0.1:5000
"""

import os

from flask import Flask, jsonify, render_template, request

from finder import find_creators, load_config, save_csv

app = Flask(__name__)


# Türk creator'lara gidecek varsayılan Türkçe şablon.
DEFAULT_TEMPLATE_TR = (
    "Selam {name} \U0001F44B\n\n"
    "16 ya\u015f\u0131nday\u0131m ve muhtemelen senin de ya\u015fad\u0131\u011f\u0131n bir "
    "\u015feyden b\u0131kt\u0131\u011f\u0131m i\u00e7in bunu yapt\u0131m: video haz\u0131r, montaj "
    "bitmi\u015f, payla\u015fmaya haz\u0131rs\u0131n... ve caption'da 20 dakika tak\u0131l\u0131p "
    "kal\u0131yorsun. Sonra \"eh i\u015fte\" deyip s\u0131radan bir \u015fey yaz\u0131p ge\u00e7iyorsun. "
    "O caption y\u00fcz\u00fcnden ka\u00e7 video hak etti\u011fi izlenmeyi almad\u0131, kim bilir.\n\n"
    "Ben de oturdum, tek ba\u015f\u0131ma bir ara\u00e7 kodlad\u0131m: CaptionAI. Konunu yaz\u0131yorsun, "
    "3 saniyede sana viral form\u00fcl\u00fcyle yaz\u0131lm\u0131\u015f, hook'u g\u00fc\u00e7l\u00fc, hashtag'i "
    "haz\u0131r 4 caption \u00e7\u0131kar\u0131yor. Bo\u015f bir ChatGPT kutusuna prompt yazmaya "
    "u\u011fra\u015fm\u0131yorsun, direkt i\u015fe yarayan\u0131 al\u0131yorsun.\n\n"
    "Senden tek istedi\u011fim: bir dene, ger\u00e7ekten i\u015fine yarad\u0131 m\u0131 yaramad\u0131 m\u0131 "
    "bana s\u00f6yle. \u0130yisiyle k\u00f6t\u00fcs\u00fcyle d\u00fcr\u00fcst ol, \u00e7\u00fcnk\u00fc bunu sizin gibi "
    "insanlar i\u00e7in daha iyi yapmak istiyorum.\n\n"
    "Link: thecaptionai.com \U0001F680"
)

# Yabancı creator'lara gidecek varsayılan İngilizce şablon.
DEFAULT_TEMPLATE_EN = (
    "Hey {name} \U0001F44B\n\n"
    "I'm 16 and I built this because of something you've probably felt too: the "
    "video's ready, the edit's done, you're about to post... and then you get "
    "stuck on the caption for 20 minutes. You end up typing something generic "
    "and moving on. How many videos never got the views they deserved because "
    "of a weak caption?\n\n"
    "So I sat down and coded a tool by myself: CaptionAI. You type your topic "
    "and in 3 seconds it gives you 4 captions written with a viral formula, "
    "strong hook, hashtags ready. No wrestling with a blank ChatGPT box, you "
    "just grab the one that works.\n\n"
    "All I'm asking: give it a try and tell me if it actually helped or not. Be "
    "honest, good or bad, because I want to make it better for people like you.\n\n"
    "Link: thecaptionai.com \U0001F680"
)


def personalize(template: str, record: dict) -> str:
    """{name}/{username}/{bio} yer tutucularini kisiye ozel doldur."""
    name = record.get("nickname") or record.get("username", "")
    return (
        template
        .replace("{name}", name)
        .replace("{username}", record.get("username", ""))
        .replace("{bio}", record.get("bio", ""))
    )


@app.route("/")
def index():
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    return render_template(
        "index.html",
        default_template_tr=DEFAULT_TEMPLATE_TR,
        default_template_en=DEFAULT_TEMPLATE_EN,
        cfg=cfg,
    )


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
        "min_followers": data.get("min_followers", base.get("min_followers", 5000)),
        "max_followers": data.get("max_followers", base.get("max_followers", 50000)),
        "target_count": data.get("target_count", base.get("target_count", 100)),
    }

    template_tr = data.get("template_tr") or DEFAULT_TEMPLATE_TR
    template_en = data.get("template_en") or DEFAULT_TEMPLATE_EN

    try:
        rows = find_creators(cfg)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400

    # Her creator icin diline gore sablon sec (tr -> Turkce, digerleri -> Ingilizce)
    for r in rows:
        tpl = template_tr if r.get("lang") == "tr" else template_en
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
