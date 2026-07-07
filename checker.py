#!/usr/bin/env python3
"""
CaptionAI Finder - Anahtar / Kota Checker
=========================================

Apify token'larin ve Groq key'lerin icin canli durum tarar:

  Apify  -> plan, aylik limit ($), harcanan ($), KALAN ($), fatura donemi.
  Groq   -> bugun kalan istek (RPD) ve dakikada kalan token (TPM).
            NOT: Groq ucretsiz katmanda DOLAR bakiyesi yoktur; kota verir.
            Resmi 'balance' API'si olmadigindan degerler canli rate-limit
            header'larindan (x-ratelimit-*) okunur.

Kullanim
--------
  1) Ortam degiskeninden (onerilen, key'i dosyaya yazma):
       export APIFY_TOKENS="apify_xxx,apify_yyy"
       export GROQ_KEYS="gsk_xxx,gsk_yyy"
       python checker.py

  2) Komut satirindan:
       python checker.py --apify apify_xxx,apify_yyy --groq gsk_xxx,gsk_yyy

  3) Hicbiri yoksa program sana sorar (girdigin key ekranda gizlenmez ama
     hicbir yere KAYDEDILMEZ).

Guvenlik: Bu dosyaya key GOMME. .gitignore zaten config/.env koruyor ama
kaynak dosyaya yazarsan repoya sizabilir.
"""

import argparse
import os
import sys
from typing import List, Optional

import requests

APIFY_BASE = "https://api.apify.com/v2"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Renkler (terminal destekliyorsa)
_C = sys.stdout.isatty()
def c(txt, code):
    return f"\033[{code}m{txt}\033[0m" if _C else txt
def bold(t): return c(t, "1")
def green(t): return c(t, "32")
def red(t): return c(t, "31")
def yellow(t): return c(t, "33")
def dim(t): return c(t, "2")

def _mask(key: str) -> str:
    key = (key or "").strip()
    if len(key) <= 10:
        return key[:3] + "..."
    return f"{key[:6]}...{key[-4:]}"

def _split(v: Optional[str]) -> List[str]:
    return [t.strip() for t in (v or "").replace("\n", ",").split(",") if t.strip()]

# ----------------------------- APIFY -------------------------------------

def check_apify(token: str) -> None:
    label = bold(_mask(token))
    try:
        lim = requests.get(f"{APIFY_BASE}/users/me/limits", params={"token": token}, timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"  {label}  {red('BAGLANTI HATASI')}: {e}")
        return
    if lim.status_code == 401:
        print(f"  {label}  {red('GECERSIZ / yetkisiz token')}")
        return
    if lim.status_code >= 400:
        print(f"  {label}  {red(f'HATA {lim.status_code}')}: {lim.text[:120]}")
        return

    data = (lim.json() or {}).get("data", {}) or {}
    limits = data.get("limits", {}) or {}
    current = data.get("current", {}) or {}
    cycle = data.get("monthlyUsageCycle", {}) or data.get("usageCycle", {}) or {}

    max_usd = limits.get("maxMonthlyUsageUsd")
    used_usd = current.get("monthlyUsageUsd")

    # Plan adi + varsa on-odemeli kredi
    plan_name, credits = "", None
    try:
        me = requests.get(f"{APIFY_BASE}/users/me", params={"token": token}, timeout=30)
        if me.status_code < 400:
            plan = (me.json() or {}).get("data", {}).get("plan", {}) or {}
            plan_name = plan.get("id") or plan.get("description") or ""
            credits = plan.get("monthlyUsageCreditsUsd")
    except Exception:
        pass

    print(f"  {label}  {green('OK')}  {dim(plan_name)}")
    if used_usd is not None and max_usd:
        remaining = max(0.0, float(max_usd) - float(used_usd))
        pct = (float(used_usd) / float(max_usd) * 100) if max_usd else 0
        bar_col = red if pct >= 90 else (yellow if pct >= 60 else green)
        print(f"      Aylik limit : ${float(max_usd):.2f}")
        print(f"      Harcanan    : ${float(used_usd):.2f}  ({bar_col(f'%{pct:.0f}')})")
        print(f"      {bold('KALAN')}       : {bold('$' + format(remaining, '.2f'))}")
    else:
        if used_usd is not None:
            print(f"      Harcanan    : ${float(used_usd):.2f}")
        if credits is not None:
            print(f"      Plan kredisi: ${float(credits):.2f}/ay")
        print(f"      {dim('(limit bilgisi bu planda yok)')}")
    if cycle:
        start = (cycle.get("startAt") or "")[:10]
        end = (cycle.get("endAt") or "")[:10]
        if start or end:
            print(f"      Donem       : {start} -> {end}")

# ----------------------------- GROQ --------------------------------------

def check_groq(key: str) -> None:
    label = bold(_mask(key))
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL,
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 1, "temperature": 0},
            timeout=30,
        )
    except Exception as e:  # noqa: BLE001
        print(f"  {label}  {red('BAGLANTI HATASI')}: {e}")
        return

    if r.status_code in (401, 403):
        print(f"  {label}  {red('GECERSIZ / yetkisiz key')}")
        return

    h = r.headers
    lim_req = h.get("x-ratelimit-limit-requests")       # gunluk istek limiti (RPD)
    rem_req = h.get("x-ratelimit-remaining-requests")    # bugun kalan istek
    lim_tok = h.get("x-ratelimit-limit-tokens")          # dakikalik token limiti (TPM)
    rem_tok = h.get("x-ratelimit-remaining-tokens")      # kalan token
    reset_req = h.get("x-ratelimit-reset-requests")
    reset_tok = h.get("x-ratelimit-reset-tokens")

    if r.status_code == 429:
        # Kota dolmus; header'lar yine de gelir.
        print(f"  {label}  {yellow('KOTA DOLU (429)')}  reset: {reset_req or reset_tok or '?'}")
    elif r.status_code >= 400:
        print(f"  {label}  {red(f'HATA {r.status_code}')}: {r.text[:120]}")
        return
    else:
        print(f"  {label}  {green('OK')}")

    def line(name, rem, lim, reset):
        if rem is None and lim is None:
            return
        try:
            rem_i, lim_i = int(float(rem)), int(float(lim))
            pct = (rem_i / lim_i * 100) if lim_i else 0
            col = red if pct <= 10 else (yellow if pct <= 40 else green)
            extra = f"  {dim('reset ' + reset)}" if reset else ""
            print(f"      {name}: {col(f'{rem_i:,}')} / {lim_i:,} kaldi{extra}")
        except (TypeError, ValueError):
            print(f"      {name}: {rem} / {lim}")

    line("Bugun istek (RPD) ", rem_req, lim_req, reset_req)
    line("Dakikada token(TPM)", rem_tok, lim_tok, reset_tok)
    print(f"      {dim('Not: Groq ucretsiz katmanda $ bakiye yoktur; sadece kota.')}")

# ----------------------------- MAIN --------------------------------------

def _gather(cli_val: Optional[str], env_name: str, prompt: str) -> List[str]:
    vals = _split(cli_val) or _split(os.environ.get(env_name))
    if not vals:
        try:
            raw = input(f"{prompt} (virgulle ayir, bos = atla): ").strip()
        except EOFError:
            raw = ""
        vals = _split(raw)
    return vals

def main() -> None:
    ap = argparse.ArgumentParser(description="Apify + Groq kota checker")
    ap.add_argument("--apify", help="Apify token(lar), virgulle ayrilir")
    ap.add_argument("--groq", help="Groq key(ler), virgulle ayrilir")
    args = ap.parse_args()

    apify = _gather(args.apify, "APIFY_TOKENS", "Apify token'lari")
    groq = _gather(args.groq, "GROQ_KEYS", "Groq key'leri")

    if not apify and not groq:
        print(red("Hicbir key girilmedi. --apify / --groq veya env kullan."))
        sys.exit(1)

    print()
    print(bold("=" * 52))
    print(bold(" APIFY ") + dim(f"({len(apify)} token)"))
    print(bold("=" * 52))
    if apify:
        for t in apify:
            check_apify(t)
            print()
    else:
        print(dim("  (atlandi)\n"))

    print(bold("=" * 52))
    print(bold(" GROQ ") + dim(f"({len(groq)} key)"))
    print(bold("=" * 52))
    if groq:
        for k in groq:
            check_groq(k)
            print()
    else:
        print(dim("  (atlandi)\n"))


if __name__ == "__main__":
    main()
