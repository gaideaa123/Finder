"""Setup GUI - tek sayfadan kur: anahtarlari yapistir, test et, TEK TUSLA Fly'a deploy et.

GUVENLIK: Bu sayfa anahtar yazar/okur ve deploy komutu calistirir. Bu yuzden
SADECE kendi bilgisayarindan (localhost) acilir; server'da (Fly) kapalidir.
Gercekten uzaktan acmak istersen ALLOW_SETUP=1 ver (onerilmez).

Acilis: `python app.py` -> http://127.0.0.1:5000/setup
"""

import json
import os
import subprocess

from flask import Blueprint, Response, jsonify, render_template, request

setup_bp = Blueprint("setup", __name__)
SECRETS_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "secrets.local.json")
if not os.path.exists(SECRETS_FILE) and os.path.exists("secrets.local.json"):
    SECRETS_FILE = "secrets.local.json"

def _is_local() -> bool:
    ra = (request.remote_addr or "").strip()
    return ra in ("127.0.0.1", "::1", "localhost", "")

@setup_bp.before_request
def _guard():
    if os.environ.get("ALLOW_SETUP") == "1":
        return None
    if not _is_local():
        return jsonify({"ok": False, "error": "Setup yalnizca kendi bilgisayarinda acilir."}), 403
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
        # bos birakildiysa eskisini koru (maskeliyi geri yazmaya calisma)
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
                    "groq": len(out["groq_keys"]), "accounts": len(out["email_accounts"])})

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

@setup_bp.route("/api/setup/deploy")
def setup_deploy():
    """deploy.sh'i calistirir, ciktisini canli (SSE) akitir."""
    app_name = (request.args.get("app") or "captionai-finder").strip()
    # basit isim dogrulamasi (komut enjeksiyonu olmasin)
    safe = "".join(ch for ch in app_name if ch.isalnum() or ch in "-_") or "captionai-finder"

    def gen():
        yield "data: Deploy basliyor...\n\n"
        try:
            proc = subprocess.Popen(
                ["bash", "deploy.sh", safe],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except Exception as e:  # noqa: BLE001
            yield f"data: HATA: {e}\n\n"
            yield "data: [DONE]\n\n"
            return
        try:
            for line in iter(proc.stdout.readline, ""):
                yield f"data: {line.rstrip()}\n\n"
        finally:
            proc.wait()
        yield f"data: [EXIT {proc.returncode}]\n\n"
        yield "data: [DONE]\n\n"

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
