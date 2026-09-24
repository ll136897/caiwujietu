import sqlite3
from pathlib import Path
from .config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


EXTRA_COLS = {"channel": "TEXT", "item": "TEXT", "time": "TEXT"}


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
            created_at TEXT,
            channel TEXT,
            item TEXT,
            time TEXT
        )
        """
    )
    # 老库升级：缺哪列补哪列（线上主用 GitHub 存储，这里只是本地兜底，但保持字段一致）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()}
    for c, t in EXTRA_COLS.items():
        if c not in cols:
            conn.execute(f"ALTER TABLE entries ADD COLUMN {c} {t}")
    conn.commit()
    conn.close()
