"""
CaptionAI Finder - Cok Hesapli Otomatik Email Gonderici
=======================================================

Her hesap gunde daily_limit kadar atar; dolunca sonrakine gecer. Ayni email'e
iki kez atmaz. Konu KISIYE OZEL (build_subject). Govde kayitliysa tekrar
uretilmez. send_one: panelden tek kisiye manuel gonderim.
"""

import random
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, List, Optional

import crm

SMTP_PRESETS = {
    "gmail": ("smtp.gmail.com", 587),
    "outlook": ("smtp-mail.outlook.com", 587),
    "yahoo": ("smtp.mail.yahoo.com", 587),
}

_state = {"running": False, "sent": 0, "failed": 0, "total": 0,
          "last": "", "error": "", "stopped": False, "active_account": ""}
_lock = threading.Lock()

def get_status() -> dict:
    with _lock:
        return dict(_state)

def stop_campaign() -> None:
    with _lock:
        _state["stopped"] = True

def _smtp_login(provider: str, user: str, pw: str):
    host, port = SMTP_PRESETS.get(provider, SMTP_PRESETS["gmail"])
    server = smtplib.SMTP(host, port, timeout=30)
    server.starttls()
    server.login(user, pw)
    return server

def _send(server, from_addr, from_name, to_addr, subject, body) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    server.sendmail(from_addr, [to_addr], msg.as_string())

def _subject_for(cfg, c) -> str:
    bs: Optional[Callable[[dict], str]] = cfg.get("build_subject")
    if bs:
        try:
            s = (bs(c) or "").strip()
            if s:
                return s
        except Exception:
            pass
    return cfg.get("subject", "videolarin icin ufak bir sey")

def _run(cfg: dict) -> None:
    provider = cfg.get("provider", "gmail")
    accounts: List[dict] = cfg.get("accounts", [])
    daily_limit = int(cfg.get("daily_limit", 30))
    min_delay = float(cfg.get("min_delay", 25))
    max_delay = float(cfg.get("max_delay", 90))
    build_body: Callable[[dict], str] = cfg["build_body"]

    seen_emails = set()
    queue = []
    for c in crm.email_queue(limit=5000):
        em = (c.get("email") or "").strip().lower()
        if not em or em in seen_emails:
            continue
        seen_emails.add(em)
        queue.append(c)

    with _lock:
        _state.update({"running": True, "sent": 0, "failed": 0, "total": len(queue),
                       "last": "", "error": "", "stopped": False, "active_account": ""})

    if not queue:
        with _lock:
            _state["running"] = False; _state["error"] = "Gonderilecek email'li kisi yok."
        return
    if not accounts:
        with _lock:
            _state["running"] = False; _state["error"] = "Hic email hesabi eklenmemis."
        return

    qi = 0
    for acc in accounts:
        with _lock:
            if _state["stopped"]:
                break
        user = (acc.get("email") or "").strip()
        pw = (acc.get("password") or "").strip()
        from_name = acc.get("from_name", "")
        if not user or not pw:
            continue
        remaining = max(0, daily_limit - crm.sent_today_account(user))
        if remaining <= 0:
            continue
        with _lock:
            _state["active_account"] = user
        try:
            server = _smtp_login(provider, user, pw)
        except Exception as e:  # noqa: BLE001
            with _lock:
                _state["error"] = f"{user} giris hatasi: {e}"
            continue
        try:
            sent_this_acc = 0
            while qi < len(queue) and sent_this_acc < remaining:
                with _lock:
                    if _state["stopped"]:
                        break
                c = queue[qi]; qi += 1
                body = (c.get("message") or "").strip() or build_body(c)
                subject = _subject_for(cfg, c)
                try:
                    _send(server, user, from_name, c["email"], subject, body)
                    crm.set_message(c["username"], body)
                    crm.mark_sent(c["username"], channel="email", account=user)
                    sent_this_acc += 1
                    with _lock:
                        _state["sent"] += 1; _state["last"] = c["email"]
                except Exception as e:  # noqa: BLE001
                    with _lock:
                        _state["failed"] += 1; _state["error"] = str(e)[:200]
                time.sleep(random.uniform(min_delay, max_delay))
        finally:
            try:
                server.quit()
            except Exception:
                pass
        if qi >= len(queue):
            break

    with _lock:
        _state["running"] = False

def send_one(cfg: dict, contact: dict) -> dict:
    accounts = cfg.get("accounts") or []
    to = (contact.get("email") or "").strip()
    if not to:
        return {"ok": False, "error": "Bu kisinin email'i yok."}
    if not accounts:
        return {"ok": False, "error": "Email hesabi yok."}
    provider = cfg.get("provider", "gmail")
    build_body = cfg.get("build_body")
    body = (contact.get("message") or "").strip() or (build_body(contact) if build_body else "")
    subject = _subject_for(cfg, contact)
    daily_limit = int(cfg.get("daily_limit", 30))
    for acc in accounts:
        user = (acc.get("email") or "").strip()
        pw = (acc.get("password") or "").strip()
        if not user or not pw:
            continue
        if crm.sent_today_account(user) >= daily_limit:
            continue
        try:
            server = _smtp_login(provider, user, pw)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{user} giris hatasi: {str(e)[:120]}"}
        try:
            _send(server, user, acc.get("from_name", ""), to, subject, body)
            crm.set_message(contact["username"], body)
            crm.mark_sent(contact["username"], channel="email", account=user)
            return {"ok": True, "account": user}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)[:160]}
        finally:
            try:
                server.quit()
            except Exception:
                pass
    return {"ok": False, "error": "Tum hesaplarin gunluk limiti dolu."}

def start_email_campaign(cfg: dict) -> dict:
    with _lock:
        if _state["running"]:
            return {"ok": False, "error": "Zaten bir kampanya calisiyor."}
    if not cfg.get("accounts"):
        return {"ok": False, "error": "En az bir email hesabi ekle."}
    if not cfg.get("build_body"):
        return {"ok": False, "error": "build_body eksik."}
    threading.Thread(target=_run, args=(cfg,), daemon=True).start()
    return {"ok": True}
