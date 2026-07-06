"""CaptionAI Finder - CRM (SQLite, kalici)."""

import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

DB_FILE = "finder_crm.db"


def _conn():
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
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
        # Eski DB'ye sent_account kolonu ekle (varsa gec)
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


def upsert_contacts(creators: List[dict]) -> int:
    added = 0
    with _conn() as c:
        for cr in creators:
            u = (cr.get("username") or "").strip()
            if not u:
                continue
            if c.execute("SELECT 1 FROM contacts WHERE username=?", (u,)).fetchone():
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
            added += 1
        c.commit()
    return added


def get_queue(channel: Optional[str] = None, limit: int = 200) -> List[dict]:
    q = "SELECT * FROM contacts WHERE status='queued'"
    args: list = []
    if channel == "email":
        q += " AND email IS NOT NULL AND email<>''"
    elif channel == "dm":
        pass  # DM kuyrugu: herkes (email olsa da DM atilabilir)
    q += " ORDER BY followers DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def set_message(username: str, message: str) -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET message=? WHERE username=?", (message, username))
        c.commit()


def mark_sent(username: str, channel: str = "dm", account: str = "") -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='sent', channel=?, sent_account=?, sent_at=? WHERE username=?",
                  (channel, account, _now(), username))
        c.commit()


def is_emailed(username: str) -> bool:
    with _conn() as c:
        r = c.execute("SELECT status, channel FROM contacts WHERE username=?", (username,)).fetchone()
    return bool(r and r["status"] in ("sent", "replied") and r["channel"] == "email")


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


def sent_today_by_account(account: str) -> int:
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
        emailed = c.execute("SELECT COUNT(*) n FROM contacts WHERE channel='email' AND status IN ('sent','replied')").fetchone()["n"]
        with_email = c.execute("SELECT COUNT(*) n FROM contacts WHERE email IS NOT NULL AND email<>''").fetchone()["n"]
    reply_rate = round((replied / sent) * 100, 1) if sent else 0.0
    return {"total": total, "sent": sent, "replied": replied, "queued": queued,
            "emailed": emailed, "with_email": with_email, "reply_rate": reply_rate}


def all_contacts(status: Optional[str] = None) -> List[dict]:
    q = "SELECT * FROM contacts"
    args: list = []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY followers DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]
