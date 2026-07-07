"""CaptionAI Finder - Apify & Groq bakiye / kullanim checker.

- Apify: hesap plani + bu ay kullanilan USD + aylik limit + kalan kredi
  (endpoint'ler: /users/me ve /users/me/limits).
- Groq: DOLAR BAKIYESI API'de YOK (Groq rate-limit tabanli). Onun yerine
  canli response header'larindan gunluk istek (RPD) ve dakikalik token (TPM)
  limit/kalan degerlerini okur. (x-ratelimit-* header'lari)

Kullanim:
  Web:  /checker           (panelden ayri, self-contained sayfa)
  CLI:  python checker.py   (env APIFY_TOKENS / GROQ_KEYS ya da secrets.local.json)

Anahtarlar ASLA repoya yazilmaz: secrets.local.json .gitignore'dadir; server'da
env/secret olarak verilir; ya da /checker sayfasina elle yapistirilir.
"""

import json
import os

import requests
from flask import Blueprint, jsonify, render_template, request

APIFY_BASE = "https://api.apify.com/v2"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

checker_bp = Blueprint("checker", __name__)

def _mask(k: str) -> str:
    k = (k or "").strip()
    return "****" if len(k) <= 8 else k[:4] + "\u2026" + k[-4:]

def _split(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [t.strip() for t in (v or "").replace("\n", ",").split(",") if t.strip()]

def _load_secrets():
    """env -> secrets.local.json sirasiyla anahtarlari toplar."""
    apify = _split(os.environ.get("APIFY_TOKENS", ""))
    groq = _split(os.environ.get("GROQ_KEYS", ""))
    for p in ("secrets.local.json", os.path.join(os.environ.get("DATA_DIR", "."), "secrets.local.json")):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                apify = apify or _split(d.get("apify_tokens"))
                groq = groq or _split(d.get("groq_keys"))
            except Exception:
                pass
            break
    return apify, groq

def apify_check(token: str) -> dict:
    """Bir Apify token'i icin plan + kullanim + kalan krediyi doner."""
    out = {"token": _mask(token), "ok": False}
    try:
        me = requests.get(f"{APIFY_BASE}/users/me", params={"token": token}, timeout=20)
        if me.status_code in (401, 403):
            out["error"] = "Gecersiz/yetkisiz token"
            return out
        me.raise_for_status()
        mdata = me.json().get("data", {}) or {}
        plan = mdata.get("plan", {}) or {}

        lim = requests.get(f"{APIFY_BASE}/users/me/limits", params={"token": token}, timeout=20)
        lim.raise_for_status()
        ldata = lim.json().get("data", {}) or {}
        limits = ldata.get("limits", {}) or {}
        current = ldata.get("current", {}) or {}
        cycle = ldata.get("monthlyUsageCycle", {}) or {}

        used = float(current.get("monthlyUsageUsd") or 0)
        credits = float(plan.get("monthlyUsageCreditsUsd") or 0)
        max_usd = limits.get("maxMonthlyUsageUsd")

        out.update({
            "ok": True,
            "username": mdata.get("username", ""),
            "plan": plan.get("id") or plan.get("name") or "free",
            "used_usd": round(used, 3),
            "credits_usd": round(credits, 2),
            "credit_left_usd": round(max(credits - used, 0), 3) if credits else None,
            "max_monthly_usd": max_usd,
            "cycle_start": (cycle.get("startAt") or "")[:10],
            "cycle_end": (cycle.get("endAt") or "")[:10],
        })
    except requests.HTTPError as e:
        out["error"] = f"HTTP {getattr(e.response, 'status_code', '?')}"
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:150]
    return out

def groq_check(key: str) -> dict:
    """Bir Groq key'i icin gunluk istek + dakikalik token limit/kalanini doner.
    (Groq dolar bakiyesi API'de sunulmuyor; degerler canli header'lardan.)"""
    out = {"key": _mask(key), "ok": False}
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            timeout=30,
        )
        if r.status_code in (401, 403):
            out["error"] = "Gecersiz key"
            return out
        h = r.headers
        out.update({
            "ok": r.status_code < 400 or r.status_code == 429,
            "status": r.status_code,
            "model": GROQ_MODEL,
            "req_limit_day": h.get("x-ratelimit-limit-requests"),
            "req_remaining_day": h.get("x-ratelimit-remaining-requests"),
            "req_reset": h.get("x-ratelimit-reset-requests"),
            "tok_limit_min": h.get("x-ratelimit-limit-tokens"),
            "tok_remaining_min": h.get("x-ratelimit-remaining-tokens"),
            "tok_reset": h.get("x-ratelimit-reset-tokens"),
        })
        if r.status_code == 429:
            out["note"] = "Su an limit dolu (429). Reset'i bekle."
        elif r.status_code >= 400:
            out["error"] = f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:150]
    return out

# ---- Web (Blueprint) -----------------------------------------------------

@checker_bp.route("/checker")
def checker_page():
    return render_template("checker.html")

@checker_bp.route("/api/check/apify", methods=["POST"])
def api_check_apify():
    tokens = _split((request.get_json(force=True) or {}).get("tokens", ""))
    return jsonify({"ok": True, "results": [apify_check(t) for t in tokens]})

@checker_bp.route("/api/check/groq", methods=["POST"])
def api_check_groq():
    keys = _split((request.get_json(force=True) or {}).get("keys", ""))
    return jsonify({"ok": True, "results": [groq_check(k) for k in keys]})

@checker_bp.route("/api/check/auto")
def api_check_auto():
    """Server'da yuklu anahtarlari (env / secrets.local.json) tarar.
    Anahtarlar taraciya GONDERILMEZ; tarama server tarafinda yapilir."""
    apify, groq = _load_secrets()
    return jsonify({
        "ok": True,
        "apify": [apify_check(t) for t in apify],
        "groq": [groq_check(k) for k in groq],
    })

# ---- CLI -----------------------------------------------------------------

def _print_cli() -> None:
    apify, groq = _load_secrets()
    print("\n== APIFY ==")
    if not apify:
        print("  (token yok - APIFY_TOKENS env ya da secrets.local.json)")
    for t in apify:
        r = apify_check(t)
        if r.get("ok"):
            print(f"  {r['token']}  plan={r['plan']}  kullanildi=${r['used_usd']}  "
                  f"kredi=${r['credits_usd']}  kalan={r.get('credit_left_usd')}  "
                  f"(cycle {r['cycle_start']}..{r['cycle_end']})")
        else:
            print(f"  {r['token']}  HATA: {r.get('error')}")
    print("\n== GROQ ==  (dolar bakiyesi API'de yok; rate-limit gosterilir)")
    if not groq:
        print("  (key yok - GROQ_KEYS env ya da secrets.local.json)")
    for k in groq:
        r = groq_check(k)
        if r.get("ok"):
            print(f"  {r['key']}  istek/gun {r.get('req_remaining_day')}/{r.get('req_limit_day')}  "
                  f"token/dk {r.get('tok_remaining_min')}/{r.get('tok_limit_min')}"
                  + (f"  [{r['note']}]" if r.get('note') else ""))
        else:
            print(f"  {r['key']}  HATA: {r.get('error')}")
    print()

if __name__ == "__main__":
    _print_cli()
