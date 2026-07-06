"""
CaptionAI Finder - Coklu Hesap Email Otomasyonu
===============================================

Birden fazla Gmail/Outlook hesabi eklenir. Her hesabin gunluk limiti (varsayilan
30) dolunca otomatik sonraki hesaba gecilir; tum hesaplar dolunca durur.
Daha once email gonderilmis kisiye tekrar gonderilmez (CRM 'sent' garantisi).

Gmail icin: normal sifre DEGIL, 'uygulama sifresi' (app password) kullan.
Arka planda thread'de calisir; durum get_status ile sorgulanir.
"""

import random
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Dict, List

import crm

SMTP_PRESETS = {
    "gmail": ("smtp.gmail.com", 587),
    "outlook": ("smtp-mail.outlook.com", 587),
    "yahoo": ("smtp.mail.yahoo.com", 587),
}

_state = {
    "running": False, "sent": 0, "failed": 0, "total": 0,
    "last": "", "error": "", "stopped": False, "active_account": "",
    "accounts_used": 0,
}
_lock = threading.Lock()


def get_status() -> dict:
    with _lock:
        return dict(_state)


def stop_campaign() -> None:
    with _lock:
        _state["stopped"] = True


def _send_one(server, from_addr, from_name, to_addr, subject, body) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    server.sendmail(from_addr, [to_addr], msg.as_string())


def _login(provider: str, user: str, pw: str):
    host, port = SMTP_PRESETS.get(provider, SMTP_PRESETS["gmail"])
    server = smtplib.SMTP(host, port, timeout=30)
    server.starttls()
    server.login(user, pw)
    return server


def _run(cfg: dict) -> None:
    accounts: List[dict] = cfg["accounts"]          # [{email, password, provider, from_name}]
    per_account_limit = int(cfg.get("daily_limit", 30))
    subject = cfg.get("subject", "videolarin icin ufak bir sey")
    min_delay = float(cfg.get("min_delay", 25))
    max_delay = float(cfg.get("max_delay", 90))
    build_body: Callable[[dict], str] = cfg["build_body"]

    # Gonderilecekler: email'i olan + daha once email gonderilmemis (queued) kisiler
    queue = [c for c in crm.get_queue(channel="email", limit=5000) if c.get("email")]

    with _lock:
        _state.update({"running": True, "sent": 0, "failed": 0, "total": len(queue),
                       "last": "", "error": "", "stopped": False, "active_account": "",
                       "accounts_used": 0})

    if not queue:
        with _lock:
            _state["running"] = False
            _state["error"] = "Gonderilecek email'li kisi yok."
        return
    if not accounts:
        with _lock:
            _state["running"] = False
            _state["error"] = "Hic email hesabi eklenmemis."
        return

    qi = 0  # kuyruk indeksi
    for acc_idx, acc in enumerate(accounts):
        with _lock:
            if _state["stopped"] or qi >= len(queue):
                break
        provider = acc.get("provider", "gmail")
        user = acc.get("email", "")
        pw = acc.get("password", "")
        from_name = acc.get("from_name", "")
        if not user or not pw:
            continue

        # Bu hesabin bugun kalan limiti (ayni hesap birden cok kampanyada kullanildiysa)
        already = crm.sent_today_by_account(user)
        remaining = max(0, per_account_limit - already)
        if remaining <= 0:
            continue

        try:
            server = _login(provider, user, pw)
        except Exception as e:  # noqa: BLE001
            with _lock:
                _state["error"] = f"{user}: giris hatasi ({e})"
            continue

        with _lock:
            _state["active_account"] = user
            _state["accounts_used"] = acc_idx + 1

        sent_this_account = 0
        try:
            while qi < len(queue) and sent_this_account < remaining:
                with _lock:
                    if _state["stopped"]:
                        break
                c = queue[qi]
                qi += 1
                # Guvenlik: bu arada baska kampanya gondermis olabilir
                if crm.is_emailed(c["username"]):
                    continue
                body = build_body(c)
                try:
                    _send_one(server, user, from_name, c["email"], subject, body)
                    crm.set_message(c["username"], body)
                    crm.mark_sent(c["username"], channel="email", account=user)
                    sent_this_account += 1
                    with _lock:
                        _state["sent"] += 1
                        _state["last"] = f"{c['email']} ({user})"
                except Exception as e:  # noqa: BLE001
                    with _lock:
                        _state["failed"] += 1
                        _state["error"] = str(e)[:150]
                time.sleep(random.uniform(min_delay, max_delay))
        finally:
            try:
                server.quit()
            except Exception:
                pass

    with _lock:
        _state["running"] = False
        if qi >= len(queue) and not _state["stopped"]:
            _state["last"] = _state["last"] + "  (kuyruk bitti)"


def start_email_campaign(cfg: dict) -> dict:
    """cfg: accounts(list), daily_limit, subject, min_delay, max_delay, build_body."""
    with _lock:
        if _state["running"]:
            return {"ok": False, "error": "Zaten bir kampanya calisiyor."}
    if not cfg.get("accounts"):
        return {"ok": False, "error": "En az bir email hesabi ekle."}
    if not cfg.get("build_body"):
        return {"ok": False, "error": "build_body eksik."}
    t = threading.Thread(target=_run, args=(cfg,), daemon=True)
    t.start()
    return {"ok": True}
