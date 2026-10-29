"""Leichtgewichtige SQLite-Schicht für Job-Metadaten."""
import sqlite3
import time

from . import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    config.ensure_dirs()
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                filename      TEXT NOT NULL,
                status        TEXT NOT NULL,
                created_at    REAL NOT NULL,
                updated_at    REAL NOT NULL,
                language      TEXT,
                num_speakers  INTEGER,
                duration_secs REAL,
                error_message TEXT,
                result_dir    TEXT
            )
            """
        )


def create_job(job_id, filename, language, num_speakers, result_dir):
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, filename, status, created_at, updated_at, "
            "language, num_speakers, result_dir) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, filename, "queued", now, now, language, num_speakers, result_dir),
        )


def update_job(job_id, **fields):
    fields["updated_at"] = time.time()
    assignments = ", ".join(f"{key}=?" for key in fields)
    values = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id=?", values)


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def delete_job(job_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
