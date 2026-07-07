"""Setup GUI - anahtarlari yapistir, test et, hashtag uret, BASLAT. Dosya elleme yok.

GUVENLIK:
- Kendi bilgisayarinda (localhost) her zaman acilir.
- Sunucuda: sadece ALLOW_SETUP=1 ise acilir. SETUP_PASSWORD verilirse sifre sorar
  (header 'X-Setup-Password' ya da ?pw=...). install-oracle.sh bunlari otomatik ayarlar.

Acilis: http://<host>:<port>/setup
"""

import json
import os

from flask import Blueprint, jsonify, render_template, request

setup_bp = Blueprint("setup", __name__)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "secrets.local.json")
if not os.path.exists(SECRETS_FILE) and os.path.exists(os.path.join(REPO_ROOT, "secrets.local.json")):
    SECRETS_FILE = os.path.join(REPO_ROOT, "secrets.local.json")

def _is_local() -> bool:
    ra = (request.remote_addr or "").strip()
    return ra in ("127.0.0.1", "::1", "localhost", "")

def _authed() -> bool:
    if _is_local():
        return True
    if os.environ.get("ALLOW_SETUP") != "1":
        return False
    pw = os.environ.get("SETUP_PASSWORD")
    if not pw:
        return True
    given = request.headers.get("X-Setup-Password") or request.args.get("pw")
    return given == pw

@setup_bp.before_request
def _guard():
    # Sayfanin kendisi (HTML) her zaman acilir; sifre kontrolu API'lerde.
    if request.endpoint == "setup.setup_page":
        if _is_local() or os.environ.get("ALLOW_SETUP") == "1":
            return None
        return jsonify({"ok": False, "error": "Setup kapali (ALLOW_SETUP=1 gerekli)."}), 403
    if not _authed():
        return jsonify({"ok": False, "error": "auth", "need_pw": True}), 403
    return None

def _mask(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return (s[:4] + "\u2026" + s[-4:]) if len(s) > 8 else "****"

def _lines(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [t.strip() for t in (v or "").replace("\n", ",").split(",") if t.strip()]

def _read() -> dict:
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

@setup_bp.route("/setup")
def setup_page():
    return render_template("setup.html")

@setup_bp.route("/api/setup/load")
def setup_load():
    d = _read()
    return jsonify({
        "ok": True,
        "has_file": os.path.exists(SECRETS_FILE),
        "path": SECRETS_FILE,
        "apify_masked": [_mask(x) for x in (d.get("apify_tokens") or [])],
        "groq_masked": [_mask(x) for x in (d.get("groq_keys") or [])],
        "accounts": [{"email": a.get("email", ""), "from_name": a.get("from_name", "")}
                     for a in (d.get("email_accounts") or [])],
        "targeting": d.get("targeting") or {},
    })

@setup_bp.route("/api/setup/save", methods=["POST"])
def setup_save():
    data = request.get_json(force=True) or {}
    existing = _read()

    apify = _lines(data.get("apify_tokens", ""))
    groq = _lines(data.get("groq_keys", ""))

    accs = []
    for a in data.get("email_accounts") or []:
        e = (a.get("email") or "").strip()
        p = (a.get("password") or "").strip()
        if e and p:
            accs.append({"email": e, "password": p, "from_name": (a.get("from_name") or "").strip()})

    out = {
        "apify_tokens": apify or existing.get("apify_tokens") or [],
        "groq_keys": groq or existing.get("groq_keys") or [],
        "email_accounts": accs or existing.get("email_accounts") or [],
        "targeting": data.get("targeting") or existing.get("targeting") or {},
    }
    d = os.path.dirname(SECRETS_FILE)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    with open(SECRETS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "apify": len(out["apify_tokens"]),
                    "groq": len(out["groq_keys"]), "accounts": len(out["email_accounts"]),
                    "path": os.path.abspath(SECRETS_FILE)})

def _saved_groq_keys() -> list:
    return _read().get("groq_keys") or []

@setup_bp.route("/api/setup/hashtags", methods=["POST"])
def setup_hashtags():
    keys = _saved_groq_keys()
    if not keys:
        return jsonify({"ok": False, "error": "Once Groq key kaydet."}), 400
    try:
        from ai import AIBrain
        brain = AIBrain(keys)
        data = request.get_json(force=True) or {}
        tags = brain.generate_hashtags(
            lang=data.get("lang", "tr"), countries=data.get("countries") or [],
            niche_hint=data.get("niche", ""), count=int(data.get("count", 12)))
        return jsonify({"ok": True, "hashtags": tags})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)[:150]}), 500

@setup_bp.route("/api/setup/check")
def setup_check():
    try:
        from checker import apify_check, groq_check
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"checker yuklenemedi: {e}"}), 500
    d = _read()
    apify = d.get("apify_tokens") or []
    groq = d.get("groq_keys") or []
    return jsonify({"ok": True,
                    "apify": [apify_check(t) for t in apify],
                    "groq": [groq_check(k) for k in groq]})
