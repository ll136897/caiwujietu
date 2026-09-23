import sqlite3
from pathlib import Path
from .config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            amount REAL,
            type TEXT,
            category TEXT,
            merchant TEXT,
            project TEXT,
            date TEXT,
            note TEXT,
            unit TEXT,
            quantity TEXT,
            img_hash TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()
