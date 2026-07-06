"""
CaptionAI Finder - Otomatik Email Gönderici
===========================================

Email'i olan creator'lara insan hızında (rastgele gecikme), günlük limitli,
otomatik mail atar. TikTok DM'in aksine bu kanal yasal ve bansızdır.

Gmail için: normal şifre DEĞİL, 'uygulama şifresi' (app password) kullan.
  1) Google Hesabı -> Güvenlik -> 2 Adımlı Doğrulama açık olmalı
  2) 'Uygulama şifreleri' -> yeni oluştur -> 16 haneli kodu buraya gir
Bu kod iptal edilebilir; normal şifreni asla girme.

Arka planda bir thread'de çalışır (start_email_campaign). Durum get_status ile
sorgulanır. Kota/oturum sorununda güvenli durur.
"""

import random
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Dict, List, Optional

import crm


SMTP_PRESETS = {
    "gmail": ("smtp.gmail.com", 587),
    "outlook": ("smtp-mail.outlook.com", 587),
    "yahoo": ("smtp.mail.yahoo.com", 587),
}

# Kampanya durumu (tek kampanya aynı anda)
_state = {
    "running": False,
    "sent": 0,
    "failed": 0,
    "total": 0,
    "last": "",
    "error": "",
    "stopped": False,
}
_lock = threading.Lock()


def get_status() -> dict:
    with _lock:
        return dict(_state)


def stop_campaign() -> None:
    with _lock:
        _state["stopped"] = True


def _send_one(server, from_addr: str, from_name: str, to_addr: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    server.sendmail(from_addr, [to_addr], msg.as_string())


def _run_campaign(cfg: dict) -> None:
    provider = cfg.get("provider", "gmail")
    host, port = SMTP_PRESETS.get(provider, SMTP_PRESETS["gmail"])
    user = cfg["email_user"]
    app_password = cfg["email_password"]
    from_name = cfg.get("from_name", "")
    subject = cfg.get("subject", "Senin için ufak bir şey")
    daily_limit = int(cfg.get("daily_limit", 30))
    min_delay = float(cfg.get("min_delay", 25))   # saniye (insani)
    max_delay = float(cfg.get("max_delay", 90))
    build_body: Callable[[dict], str] = cfg["build_body"]

    # Günlük limitten kalan
    already = crm.sent_today(channel="email")
    remaining = max(0, daily_limit - already)

    queue = [c for c in crm.get_queue(channel="email", limit=500) if c.get("email")]
    queue = queue[:remaining]

    with _lock:
        _state.update({"running": True, "sent": 0, "failed": 0,
                       "total": len(queue), "last": "", "error": "", "stopped": False})

    if not queue:
        with _lock:
            _state["running"] = False
            _state["error"] = "Gonderilecek email'li kisi yok (ya da gunluk limit dolu)."
        return

    try:
        server = smtplib.SMTP(host, port, timeout=30)
        server.starttls()
        server.login(user, app_password)
    except Exception as e:  # noqa: BLE001
        with _lock:
            _state["running"] = False
            _state["error"] = f"SMTP giris hatasi: {e}"
        return

    try:
        for c in queue:
            with _lock:
                if _state["stopped"]:
                    break
            body = build_body(c)
            try:
                _send_one(server, user, from_name, c["email"], subject, body)
                crm.set_message(c["username"], body)
                crm.mark_sent(c["username"], channel="email")
                with _lock:
                    _state["sent"] += 1
                    _state["last"] = c["email"]
            except Exception as e:  # noqa: BLE001
                with _lock:
                    _state["failed"] += 1
                    _state["error"] = str(e)[:200]
            # İnsani gecikme
            time.sleep(random.uniform(min_delay, max_delay))
    finally:
        try:
            server.quit()
        except Exception:
            pass
        with _lock:
            _state["running"] = False


def start_email_campaign(cfg: dict) -> dict:
    """Kampanyayı arka planda başlatır. cfg:
    email_user, email_password(app pw), from_name, subject, daily_limit,
    min_delay, max_delay, provider, build_body(callable).
    """
    with _lock:
        if _state["running"]:
            return {"ok": False, "error": "Zaten bir kampanya calisiyor."}
    for req in ("email_user", "email_password", "build_body"):
        if not cfg.get(req):
            return {"ok": False, "error": f"Eksik alan: {req}"}
    t = threading.Thread(target=_run_campaign, args=(cfg,), daemon=True)
    t.start()
    return {"ok": True}
