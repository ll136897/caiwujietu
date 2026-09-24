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
    cur = conn.execute(
        """INSERT INTO entries (ts, amount, type, category, merchant, project, date, note, unit, quantity, img_hash, created_at, channel, item, time)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
            entry.get("channel", ""),
            entry.get("item", ""),
            entry.get("time", ""),
        ),
    )
    row = dict(conn.execute("SELECT * FROM entries WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.commit()
    conn.close()
    return row


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
    if not r.ok:
        hint = ""
        if r.status_code in (401, 403):
            hint = "｜GITHUB_TOKEN 没有写入权限：到 GitHub 令牌设置把 Contents 改成 Read and write"
        elif r.status_code == 404:
            hint = "｜仓库名或 LEDGER_PATH 不对，或令牌没给这个仓库权限"
        elif r.status_code == 409:
            hint = "｜账本刚被改过，重试一次即可"
        raise RuntimeError(f"写账本到 GitHub 失败 {r.status_code}{hint}：{r.text[:140]}")


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


def _github_update(eid, fields: dict) -> dict:
    entries, sha = _gh_get()
    for e in entries:
        if e.get("id") == eid:
            for k in ("amount", "type", "category", "merchant", "project", "date", "unit", "quantity", "note", "channel", "item", "time"):
                if k in fields:
                    e[k] = fields[k]
            _gh_put(entries, sha)
            return e
    raise KeyError("not found")


def _github_delete(eid) -> bool:
    entries, sha = _gh_get()
    new = [e for e in entries if e.get("id") != eid]
    if len(new) == len(entries):
        return False
    _gh_put(new, sha)
    return True


def _sqlite_update(eid, fields: dict) -> dict:
    cols = []
    vals = []
    for k in ("amount", "type", "category", "merchant", "project", "date", "unit", "quantity", "note", "channel", "item", "time"):
        if k in fields:
            cols.append(f"{k}=?")
            val = fields[k]
            if k == "amount":
                val = float(val or 0)
            vals.append(val)
    conn = get_conn()
    conn.execute("UPDATE entries SET " + ", ".join(cols) + " WHERE id=?", vals + [eid])
    conn.commit()
    row = dict(conn.execute("SELECT * FROM entries WHERE id=?", (eid,)).fetchone())
    conn.close()
    return row


def _sqlite_delete(eid) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM entries WHERE id=?", (eid,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


# ---------------- 对外 API ----------------
def add_entry(entry: dict) -> dict:
    if _use_github():
        return _github_add(entry)
    return _sqlite_add(entry)


def list_entries() -> list:
    if _use_github():
        return _github_list()
    return _sqlite_list()


def update_entry(eid, fields: dict) -> dict:
    if _use_github():
        return _github_update(eid, fields)
    return _sqlite_update(eid, fields)


def delete_entry(eid) -> bool:
    if _use_github():
        return _github_delete(eid)
    return _sqlite_delete(eid)


def write_probe() -> dict:
    """真正写一次 GitHub（写一个探针文件再删掉），用来确认令牌有没有写入权限。
    读取成功不代表能写——这是"拍照报错"最常见的根因。"""
    if not _use_github():
        return {"ok": False, "detail": "没接 GitHub，当前写的是服务器本地（重启会丢）"}
    path = "data/.write_probe.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    try:
        content = base64.b64encode(b'{"probe": true}').decode("ascii")
        r = requests.put(url, headers=_gh_headers(),
                         json={"message": "写入自检（可忽略）", "content": content}, timeout=20)
        if r.status_code not in (200, 201):
            hint = "令牌没有写入权限：到 GitHub → 令牌设置，把 Contents 改成 Read and write" if r.status_code in (401, 403) else r.text[:120]
            return {"ok": False, "detail": f"写入失败 {r.status_code}：{hint}"}
        sha = r.json().get("content", {}).get("sha")
        if sha:
            requests.delete(url, headers=_gh_headers(),
                            json={"message": "清理自检文件", "sha": sha}, timeout=20)
        return {"ok": True, "detail": "写入正常：账本能存进你的 GitHub 仓库"}
    except Exception as e:
        return {"ok": False, "detail": f"连不上 GitHub：{type(e).__name__}: {e}"}


def storage_check(write=False) -> dict:
    """自检：账本存哪、通不通（给非技术用户看"填对了没"）。
    write=True 时额外真写一次，验证是否有写入权限。"""
    if not _use_github():
        return {
            "mode": "sqlite",
            "ok": False,
            "detail": "还没接上你的 GitHub：账本暂存在服务器上，重启会丢。请填 GITHUB_REPO 和 GITHUB_TOKEN。",
        }
    try:
        entries, _ = _gh_get()
        st = {
            "mode": "github",
            "ok": True,
            "detail": f"账本已永久存入 {GITHUB_REPO}/{LEDGER_PATH}，当前 {len(entries)} 笔。",
        }
        if write:
            st["write"] = write_probe()
            if not st["write"]["ok"]:
                st["ok"] = False
                st["detail"] = st["write"]["detail"]
        return st
    except Exception as e:
        return {
            "mode": "github",
            "ok": False,
            "detail": f"连不上 GitHub（检查仓库名格式 用户名/仓库名、令牌权限）：{e}",
        }
