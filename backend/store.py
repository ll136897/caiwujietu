"""统一存储层：账本存在用户本人 GitHub 仓库的 ledger.json（永久、归用户）。
未配置 GitHub 时退回本地 SQLite（仅调试用，服务重启可能丢）。"""
import base64
import datetime
import json
import os

import requests

from .config import GITHUB_TOKEN, GITHUB_REPO, LEDGER_PATH
from .db import get_conn


def _use_github() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO)


# ---------------- SQLite 兜底 ----------------
def _sqlite_add(entry: dict):
    conn = get_conn()
    conn.execute(
        """INSERT INTO entries (ts, amount, type, category, merchant, project, date, note, unit, quantity, img_hash, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.datetime.now().isoformat(),
            float(entry.get("amount", 0) or 0),
            entry.get("type", "收入"),
            entry.get("category", ""),
            entry.get("merchant", ""),
            entry.get("project", "其他"),
            entry.get("date", ""),
            entry.get("note", ""),
            entry.get("unit", ""),
            entry.get("quantity", ""),
            entry.get("img_hash", ""),
            datetime.datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def _sqlite_list() -> list:
    conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM entries ORDER BY date DESC, id DESC").fetchall()]
    conn.close()
    return rows


# ---------------- GitHub 文件存储 ----------------
def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_get() -> tuple:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LEDGER_PATH}"
    r = requests.get(url, headers=_gh_headers(), timeout=20)
    if r.status_code == 200:
        data = json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        return data.get("entries", []), r.json().get("sha")
    if r.status_code == 404:
        return [], None
    r.raise_for_status()


def _gh_put(entries: list, sha):
    content = base64.b64encode(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    body = {"message": "记账自动同步", "content": content}
    if sha:
        body["sha"] = sha
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LEDGER_PATH}"
    r = requests.put(url, headers=_gh_headers(), json=body, timeout=20)
    r.raise_for_status()


def _github_add(entry: dict) -> dict:
    entries, sha = _gh_get()
    e = dict(entry)
    e["id"] = (entries[-1]["id"] + 1) if entries else 1
    e.setdefault("created_at", datetime.datetime.now().isoformat())
    entries.append(e)
    _gh_put(entries, sha)
    return e


def _github_list() -> list:
    entries, _ = _gh_get()
    return entries


# ---------------- 对外 API ----------------
def add_entry(entry: dict) -> dict:
    if _use_github():
        return _github_add(entry)
    return _sqlite_add(entry)


def list_entries() -> list:
    if _use_github():
        return _github_list()
    return _sqlite_list()
