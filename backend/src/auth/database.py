"""Base de datos SQLite para el sistema de autenticación.

Sigue el patrón de src/persistence/event_store.py.
"""
import sqlite3
import os
import logging
from pathlib import Path

logger = logging.getLogger("vantare.auth.database")

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "vantare_auth.db"


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                user_email TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                google_sub TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_key TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        logger.info("Auth database initialized at %s", DB_PATH)
    finally:
        conn.close()


def log_usage(license_key: str, endpoint: str, tokens_in: int = 0, tokens_out: int = 0) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO usage_logs (license_key, endpoint, tokens_in, tokens_out) VALUES (?, ?, ?, ?)",
            (license_key, endpoint, tokens_in, tokens_out),
        )
        conn.commit()
    finally:
        conn.close()
