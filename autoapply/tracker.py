"""
Application tracker — SQLite backend for auto-apply state.
DB lives at applications.db (gitignored).
"""

import sqlite3
import os
from datetime import datetime, date

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, "applications.db")

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS applications (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  job_title     TEXT NOT NULL,
  company       TEXT NOT NULL,
  url           TEXT NOT NULL,
  source        TEXT,
  job_type      TEXT,
  platform      TEXT,
  status        TEXT DEFAULT 'queued',
  applied_at    DATETIME,
  error_msg     TEXT,
  cover_letter  TEXT,
  notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_url    ON applications(url);
CREATE INDEX IF NOT EXISTS idx_status ON applications(status);

CREATE TABLE IF NOT EXISTS outreach (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  company    TEXT NOT NULL,
  job_title  TEXT,
  to_email   TEXT NOT NULL,
  subject    TEXT,
  body       TEXT,
  sent_at    DATETIME,
  status     TEXT DEFAULT 'draft',
  notes      TEXT
);
CREATE INDEX IF NOT EXISTS idx_outreach_company ON outreach(company);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript(_CREATE_SQL)


def add_job(job: dict) -> int:
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO applications (job_title, company, url, source, job_type, platform, status)
            VALUES (?, ?, ?, ?, ?, ?, 'queued')
            """,
            (
                str(job.get("title", "")),
                str(job.get("company", "")),
                str(job.get("url", "")),
                str(job.get("source", "")),
                str(job.get("job_type", "")),
                str(job.get("source", "")),
            ),
        )
        return cur.lastrowid


def update_status(
    app_id: int,
    status: str,
    error_msg: str | None = None,
    cover_letter: str | None = None,
) -> None:
    applied_at = datetime.utcnow().isoformat() if status == "applied" else None
    with _conn() as c:
        c.execute(
            """
            UPDATE applications
            SET status=?, error_msg=?, cover_letter=COALESCE(?, cover_letter),
                applied_at=COALESCE(?, applied_at)
            WHERE id=?
            """,
            (status, error_msg, cover_letter, applied_at, app_id),
        )


def already_applied(url: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM applications WHERE url=? AND status IN ('applied','queued','applying') LIMIT 1",
            (url,),
        ).fetchone()
        return row is not None


def count_applied_today() -> int:
    today = date.today().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM applications WHERE status='applied' AND applied_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return row[0] if row else 0


def get_all(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM applications ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    with _conn() as c:
        counts = {
            row["status"]: row["cnt"]
            for row in c.execute(
                "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
            ).fetchall()
        }
    return {
        "total":    sum(counts.values()),
        "queued":   counts.get("queued",   0),
        "applied":  counts.get("applied",  0),
        "failed":   counts.get("failed",   0),
        "skipped":  counts.get("skipped",  0),
        "applying": counts.get("applying", 0),
    }


def clear_all() -> None:
    with _conn() as c:
        c.execute("DELETE FROM applications")


# ── Outreach CRUD ──────────────────────────────────────────────────────────────

def add_outreach(company: str, job_title: str, to_email: str, subject: str, body: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO outreach (company, job_title, to_email, subject, body, status) VALUES (?,?,?,?,?,'draft')",
            (company, job_title, to_email, subject, body),
        )
        return cur.lastrowid


def update_outreach_status(outreach_id: int, status: str) -> None:
    sent_at = datetime.utcnow().isoformat() if status == "sent" else None
    with _conn() as c:
        c.execute(
            "UPDATE outreach SET status=?, sent_at=COALESCE(?,sent_at) WHERE id=?",
            (status, sent_at, outreach_id),
        )


def already_emailed(company: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM outreach WHERE company=? AND status='sent' LIMIT 1",
            (company,),
        ).fetchone()
        return row is not None


def get_outreach(outreach_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM outreach WHERE id=?", (outreach_id,)).fetchone()
        return dict(row) if row else None


def get_all_outreach(limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM outreach ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
