"""
CaptionAI Finder - CRM (SQLite, kalıcı)
=======================================

Tüm creator'ları ve outreach durumlarını kalıcı tutar. AI öğrenmesi ve yanıt
oranı analizi bu verinin üstünde çalışır.

Tablolar:
  contacts(username PK, nickname, followers, lang, country, email, bio, bio_link,
           profile, channel, status, message, reply_text, sentiment, category,
           created_at, sent_at, replied_at)

Durumlar (status):
  queued   -> kuyrukta, henüz gönderilmedi
  sent     -> DM/email gönderildi
  replied  -> yanıt geldi
  skipped  -> elle atlandı / silindi
"""

import sqlite3
import time
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
                created_at TEXT, sent_at TEXT, replied_at TEXT
            )"""
        )
        c.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def known_usernames() -> set:
    with _conn() as c:
        rows = c.execute("SELECT username FROM contacts").fetchall()
    return {r["username"].lower() for r in rows}


def upsert_contacts(creators: List[dict]) -> int:
    """Yeni creator'ları kuyruğa ekler (varsa dokunmaz). Eklenen sayıyı döner."""
    added = 0
    with _conn() as c:
        for cr in creators:
            u = (cr.get("username") or "").strip()
            if not u:
                continue
            exists = c.execute("SELECT 1 FROM contacts WHERE username=?", (u,)).fetchone()
            if exists:
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
    if channel:
        q += " AND channel=?"
        args.append(channel)
    q += " ORDER BY followers DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def set_message(username: str, message: str) -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET message=? WHERE username=?", (message, username))
        c.commit()


def mark_sent(username: str, channel: str = "dm") -> None:
    with _conn() as c:
        c.execute("UPDATE contacts SET status='sent', channel=?, sent_at=? WHERE username=?",
                  (channel, _now(), username))
        c.commit()


def mark_replied(username: str, reply_text: str, sentiment: str = "", category: str = "") -> None:
    with _conn() as c:
        c.execute(
            "UPDATE contacts SET status='replied', reply_text=?, sentiment=?, category=?, replied_at=? WHERE username=?",
            (reply_text, sentiment, category, _now(), username),
        )
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


def stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM contacts").fetchone()["n"]
        sent = c.execute("SELECT COUNT(*) n FROM contacts WHERE status IN ('sent','replied')").fetchone()["n"]
        replied = c.execute("SELECT COUNT(*) n FROM contacts WHERE status='replied'").fetchone()["n"]
        queued = c.execute("SELECT COUNT(*) n FROM contacts WHERE status='queued'").fetchone()["n"]
        pos = c.execute("SELECT COUNT(*) n FROM contacts WHERE sentiment='pos'").fetchone()["n"]
        by_lang = c.execute(
            """SELECT lang,
                      SUM(CASE WHEN status IN ('sent','replied') THEN 1 ELSE 0 END) sent,
                      SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END) replied
               FROM contacts GROUP BY lang"""
        ).fetchall()
        repliers = c.execute(
            "SELECT username, nickname, lang, reply_text, sentiment, category FROM contacts WHERE status='replied' ORDER BY replied_at DESC LIMIT 50"
        ).fetchall()
    reply_rate = round((replied / sent) * 100, 1) if sent else 0.0
    return {
        "total": total, "sent": sent, "replied": replied, "queued": queued,
        "positive": pos, "reply_rate": reply_rate,
        "by_lang": [dict(r) for r in by_lang],
        "repliers": [dict(r) for r in repliers],
    }


def learning_samples(limit: int = 60) -> List[dict]:
    """AI öğrenmesi için: gönderilmiş mesaj + yanıt geldi mi + duygu."""
    with _conn() as c:
        rows = c.execute(
            """SELECT message, status, sentiment FROM contacts
               WHERE status IN ('sent','replied') AND message IS NOT NULL AND message<>''
               ORDER BY sent_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {"message": r["message"], "replied": r["status"] == "replied", "sentiment": r["sentiment"] or ""}
        for r in rows
    ]


def all_contacts(status: Optional[str] = None) -> List[dict]:
    q = "SELECT * FROM contacts"
    args: list = []
    if status:
        q += " WHERE status=?"
        args.append(status)
    q += " ORDER BY followers DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]
