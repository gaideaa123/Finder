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


DEFAULT_TEMPLATE = (
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
    return render_template("index.html", default_template=DEFAULT_TEMPLATE, cfg=cfg)


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
        "min_followers": data.get("min_followers", base.get("min_followers", 5000)),
        "max_followers": data.get("max_followers", base.get("max_followers", 50000)),
        "target_count": data.get("target_count", base.get("target_count", 100)),
    }
    template = data.get("template") or DEFAULT_TEMPLATE

    try:
        rows = find_creators(cfg)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 400

    for r in rows:
        r["message"] = personalize(template, r)

    try:
        save_csv(rows, base.get("output_csv", "creators.csv"))
    except Exception:
        pass

    return jsonify({"ok": True, "count": len(rows), "creators": rows})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  CaptionAI Finder GUI -> http://127.0.0.1:{port}\n")
    app.run(debug=True, port=port)
