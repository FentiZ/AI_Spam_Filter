import sqlite3
import hashlib
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "spam_filter.db")


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_key TEXT NOT NULL,
                sender TEXT NOT NULL,
                text TEXT NOT NULL,
                date TEXT,
                classification TEXT NOT NULL,
                ai_classification TEXT NOT NULL,
                user_classification TEXT,
                confidence REAL NOT NULL,
                reasons TEXT NOT NULL,
                risk TEXT NOT NULL,
                prompt_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(email_key, prompt_version)
            )
        """)


def make_key(sender, text, date):
    value = sender + "\n" + text + "\n" + date
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_existing(email_key, version):
    with connect() as db:
        return db.execute(
            "SELECT * FROM emails WHERE email_key = ? AND prompt_version = ?",
            (email_key, version)
        ).fetchone()


def save_email(sender, text, date, result, version):
    email_key = make_key(sender, text, date)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reasons = json.dumps(result["reasons"], ensure_ascii=False)

    with connect() as db:
        old = db.execute(
            "SELECT id FROM emails WHERE email_key = ? AND prompt_version = ?",
            (email_key, version)
        ).fetchone()
        label = db.execute(
            "SELECT user_classification FROM emails "
            "WHERE email_key = ? AND user_classification IS NOT NULL LIMIT 1",
            (email_key,)
        ).fetchone()
        user_label = label["user_classification"] if label else None

        if old:
            db.execute("""
                UPDATE emails
                SET classification = ?, ai_classification = ?, confidence = ?,
                    reasons = ?, risk = ?, created_at = ?, user_classification = ?
                WHERE id = ?
            """, (
                result["classification"], result["classification"],
                result["confidence"], reasons, result["risk"], now,
                user_label, old["id"]
            ))
            return old["id"]

        cursor = db.execute("""
            INSERT INTO emails (
                email_key, sender, text, date, classification, ai_classification,
                user_classification, confidence, reasons, risk, prompt_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email_key, sender, text, date,
            result["classification"], result["classification"], user_label,
            result["confidence"], reasons, result["risk"], version, now
        ))
        return cursor.lastrowid


def set_feedback(email_id, user_classification):
    with connect() as db:
        email = db.execute(
            "SELECT email_key FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        if not email:
            return False
        # Исправление относится к письму во ВСЕХ версиях промпта.
        db.execute(
            "UPDATE emails SET user_classification = ? WHERE email_key = ?",
            (user_classification, email["email_key"])
        )
        return True


def get_by_id(email_id):
    with connect() as db:
        return db.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()


def get_history(version, limit=20, offset=0):
    with connect() as db:
        return db.execute(
            "SELECT * FROM emails WHERE prompt_version = ? "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (version, limit, offset)
        ).fetchall()


def get_by_version(version):
    with connect() as db:
        return db.execute(
            "SELECT * FROM emails WHERE prompt_version = ? ORDER BY id",
            (version,)
        ).fetchall()


def get_all():
    with connect() as db:
        return db.execute("SELECT * FROM emails ORDER BY id").fetchall()


def get_errors():
    with connect() as db:
        return db.execute("""
            SELECT * FROM emails
            WHERE user_classification IS NOT NULL
              AND ai_classification != user_classification
            ORDER BY id
        """).fetchall()


def get_labeled_emails():
    # Одно письмо может иметь несколько анализов (V1, V2, V3).
    # Для повторного теста берем его только один раз.
    result = []
    seen = set()
    for row in get_all():
        if row["user_classification"] is not None and row["email_key"] not in seen:
            result.append(row)
            seen.add(row["email_key"])
    return result
