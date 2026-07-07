"""Setup API - anahtar + email hesabi + SES + hedefleme kaydeder/okur.

GUVENLIK: localhost her zaman; sunucuda ALLOW_SETUP=1 (+ opsiyonel SETUP_PASSWORD).
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

@setup_bp.route("/api/setup/load")
def setup_load():
    d = _read()
    ses = d.get("ses") or {}
    return jsonify({
        "ok": True,
        "has_file": os.path.exists(SECRETS_FILE),
        "apify_masked": [_mask(x) for x in (d.get("apify_tokens") or [])],
        "groq_masked": [_mask(x) for x in (d.get("groq_keys") or [])],
        "scrapecreators_masked": [_mask(x) for x in (d.get("scrapecreators_keys") or [])],
        "accounts": [{"email": a.get("email", ""), "from_name": a.get("from_name", "")}
                     for a in (d.get("email_accounts") or [])],
        "sender": d.get("sender") or "gmail",
        "ses": {"smtp_host": ses.get("smtp_host", ""), "smtp_port": ses.get("smtp_port", 587),
                "smtp_user": ses.get("smtp_user", ""), "smtp_pass_set": bool(ses.get("smtp_pass")),
                "from_email": ses.get("from_email", ""), "from_name": ses.get("from_name", "")},
        "targeting": d.get("targeting") or {},
    })

@setup_bp.route("/api/setup/save", methods=["POST"])
def setup_save():
    data = request.get_json(force=True) or {}
    existing = _read()

    apify = _lines(data.get("apify_tokens", ""))
    groq = _lines(data.get("groq_keys", ""))
    scrape = _lines(data.get("scrapecreators_keys", ""))

    accs = []
    for a in data.get("email_accounts") or []:
        e = (a.get("email") or "").strip()
        p = (a.get("password") or "").strip()
        if e and p:
            accs.append({"email": e, "password": p, "from_name": (a.get("from_name") or "").strip()})

    # SES: bos sifre gelirse eskisini koru
    ses_in = data.get("ses") or {}
    ses_old = existing.get("ses") or {}
    ses = {
        "smtp_host": (ses_in.get("smtp_host") or ses_old.get("smtp_host") or "").strip(),
        "smtp_port": int(ses_in.get("smtp_port") or ses_old.get("smtp_port") or 587),
        "smtp_user": (ses_in.get("smtp_user") or ses_old.get("smtp_user") or "").strip(),
        "smtp_pass": (ses_in.get("smtp_pass") or ses_old.get("smtp_pass") or "").strip(),
        "from_email": (ses_in.get("from_email") or ses_old.get("from_email") or "").strip(),
        "from_name": (ses_in.get("from_name") or ses_old.get("from_name") or "").strip(),
    }

    out = {
        "apify_tokens": apify or existing.get("apify_tokens") or [],
        "groq_keys": groq or existing.get("groq_keys") or [],
        "scrapecreators_keys": scrape or existing.get("scrapecreators_keys") or [],
        "email_accounts": accs or existing.get("email_accounts") or [],
        "ses": ses,
        "sender": data.get("sender") or existing.get("sender") or "gmail",
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
    return jsonify({"ok": True, "apify": len(out["apify_tokens"]), "groq": len(out["groq_keys"]),
                    "scrapecreators": len(out["scrapecreators_keys"]),
                    "accounts": len(out["email_accounts"]), "sender": out["sender"],
                    "ses": bool(out["ses"]["from_email"])})

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
        tags = brain.generate_hashtags(lang=data.get("lang", "tr"), countries=data.get("countries") or [],
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
    return jsonify({"ok": True,
                    "apify": [apify_check(t) for t in (d.get("apify_tokens") or [])],
                    "groq": [groq_check(k) for k in (d.get("groq_keys") or [])]})
