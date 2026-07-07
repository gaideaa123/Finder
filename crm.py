"""CaptionAI Finder - CRM (SQLite). Kuyruk, durum, email dedup, hesap takibi, DB yonetimi."""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

DB_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "finder_crm.db")

def _conn():
    c = sqlite3.connect(DB_FILE, timeout=30)
    c.row_factory = sqlite3.Row
    return c

def init_db() -> None:
    d = os.path.dirname(DB_FILE)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS contacts (
                username TEXT PRIMARY KEY,
                nickname TEXT, followers INTEGER, lang TEXT, country TEXT,
                email TEXT, bio TEXT, bio_link TEXT, profile TEXT,
                channel TEXT DEFAULT 'dm',
                status TEXT DEFAULT 'queued',
                message TEXT, reply_text TEXT, sentiment TEXT, category TEXT,
                sent_account TEXT,
                created_at TEXT, sent_at TEXT, replied_at TEXT
            )"""
        )
        try:
            c.execute("ALTER TABLE contacts ADD COLUMN sent_account TEXT")
        except Exception:
            pass
        c.commit()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def known_usernames() -> set:
    with _conn() as c:
        rows = c.execute("SELECT username FROM contacts").fetchall()
    return {r["username"].lower() for r in rows}

def known_emails() -> set:
    with _conn() as c:
        rows = c.execute("SELECT email FROM contacts WHERE email IS NOT NULL AND email<>''").fetchall()
    return {r["email"].strip().lower() for r in rows}

def upsert_contacts(creators: List[dict]) -> int:
    added = 0
    with _conn() as c:
        existing_emails = {
            r["email"].strip().lower()
            for r in c.execute("SELECT email FROM contacts WHERE email IS NOT NULL AND email<>''").fetchall()
        }
        for cr in creators:
            u = (cr.get("username") or "").strip()
            if not u:
                continue
            if c.execute("SELECT 1 FROM contacts WHERE username=?", (u,)).fetchone():
                continue
            em = (cr.get("email") or "").strip().lower()
            if em and em in existing_emails:
                continue
            c.execute(
                """INSERT INTO contacts
                   (username, nickname, followers, lang, country, email, bio, bio_link,
                    profile, channel, status, message, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (u, cr.get("nickname", ""), int(cr.get("followers", 0) or 0),
                 cr.get("lang", ""), cr.get("country", ""), cr.get("email", ""),
                 cr.get("bio", ""), cr.get("bio_link", ""), cr.get("profile", ""),
                 "email" if cr.get("email") else "dm", "queued",
                 cr.get("message", ""), _now()),
            )
            if em:
                existing_emails.add(em)
            added += 1
        c.commit()
    return added

def get_contact(username: str) -> Optional[dict]:
    with _conn() as c:
        r = c.execute("SELECT * FROM contacts WHERE username=?", (username,)).fetchone()
    return dict(r) if r else None

def get_queue(channel: Optional[str] = None, limit: int = 300) -> List[dict]:
    q = "SELECT * FROM contacts WHERE status='queued'"
    args: list = []
    if channel:
        q += " AND channel=?"
        args.append(channel)
    q += " ORDER BY followers DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]

def email_queue(limit: int = 5000) -> List[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM contacts WHERE status='queued' AND email IS NOT NULL AND email<>'' ORDER BY followers DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def set_message(username: str, message: str) -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET message=? WHERE username=?", (message, username))
        c.commit()

def mark_sent(username: str, channel: str = "dm", account: str = "") -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='sent', channel=?, sent_account=?, sent_at=? WHERE username=?",
                  (channel, account, _now(), username))
        c.commit()

def mark_replied(username: str, reply_text: str, sentiment: str = "", category: str = "") -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='replied', reply_text=?, sentiment=?, category=?, replied_at=? WHERE username=?",
                  (reply_text, sentiment, category, _now(), username))
        c.commit()

def mark_skipped(username: str) -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='skipped' WHERE username=?", (username,))
        c.commit()

def sent_today(channel: Optional[str] = None) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    q = "SELECT COUNT(*) n FROM contacts WHERE sent_at LIKE ?"
    args = [today + "%"]
    if channel:
        q += " AND channel=?"
        args.append(channel)
    with _conn() as c:
        return c.execute(q, args).fetchone()["n"]

def sent_today_account(account: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) n FROM contacts WHERE channel='email' AND sent_account=? AND sent_at LIKE ?",
            (account, today + "%"),
        ).fetchone()["n"]

def stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM contacts").fetchone()["n"]
        sent = c.execute("SELECT COUNT(*) n FROM contacts WHERE status IN ('sent','replied')").fetchone()["n"]
        replied = c.execute("SELECT COUNT(*) n FROM contacts WHERE status='replied'").fetchone()["n"]
        queued = c.execute("SELECT COUNT(*) n FROM contacts WHERE status='queued'").fetchone()["n"]
        with_email = c.execute("SELECT COUNT(*) n FROM contacts WHERE email IS NOT NULL AND email<>''").fetchone()["n"]
    reply_rate = round((replied / sent) * 100, 1) if sent else 0.0
    return {"total": total, "sent": sent, "replied": replied, "queued": queued,
            "with_email": with_email, "reply_rate": reply_rate}

def list_contacts(status: Optional[str] = None, channel: Optional[str] = None,
                  search: str = "", limit: int = 500) -> List[dict]:
    q = "SELECT * FROM contacts WHERE 1=1"
    args: list = []
    if status:
        q += " AND status=?"
        args.append(status)
    if channel:
        q += " AND channel=?"
        args.append(channel)
    if search:
        q += " AND (LOWER(username) LIKE ? OR LOWER(nickname) LIKE ? OR LOWER(email) LIKE ?)"
        s = f"%{search.lower()}%"
        args += [s, s, s]
    q += " ORDER BY (sent_at IS NOT NULL) DESC, followers DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]

def sent_emails(limit: int = 500) -> List[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT username, nickname, email, sent_account, sent_at, message FROM contacts "
            "WHERE channel='email' AND status IN ('sent','replied') ORDER BY sent_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

def requeue(username: str) -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='queued', sent_at=NULL, sent_account=NULL, replied_at=NULL WHERE username=?", (username,))
        c.commit()

def delete_contact(username: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM contacts WHERE username=?", (username,))
        c.commit()

def delete_all(status: Optional[str] = None) -> int:
    """Toplu sil. status verilirse sadece o durumdakileri, yoksa HEPSINI siler."""
    with _conn() as c:
        if status:
            cur = c.execute("DELETE FROM contacts WHERE status=?", (status,))
        else:
            cur = c.execute("DELETE FROM contacts")
        c.commit()
        return cur.rowcount if cur.rowcount is not None else 0

def update_contact(username: str, fields: dict) -> None:
    allowed = {"email", "message", "lang", "country", "nickname", "status", "channel"}
    sets, args = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(v)
    if not sets:
        return
    args.append(username)
    with _conn() as c:
        c.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE username=?", args)
        c.commit()
