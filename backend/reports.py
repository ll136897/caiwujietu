from datetime import datetime, date

from . import store


def _rows():
    return store.list_entries()


def _week_key(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    except Exception:
        return "未知周"


def _agg(rows, key_fn):
    out = {}
    for r in rows:
        k = key_fn(r.get("date") or "")
        if not k:
            continue
        d = out.setdefault(k, {"key": k, "income": 0.0, "expense": 0.0, "count": 0})
        if r.get("type") == "收入":
            d["income"] += r.get("amount") or 0
        else:
            d["expense"] += r.get("amount") or 0
        d["count"] += 1
    for d in out.values():
        d["income"] = round(d["income"], 2)
        d["expense"] = round(d["expense"], 2)
        d["net"] = round(d["income"] - d["expense"], 2)
    return out


def daily():
    return sorted(_agg(_rows(), lambda ds: (ds or "")[:10]).values(), key=lambda x: x["key"])


def weekly():
    return sorted(_agg(_rows(), _week_key).values(), key=lambda x: x["key"])


def monthly():
    return sorted(_agg(_rows(), lambda ds: (ds or "")[:7]).values(), key=lambda x: x["key"])


def all_summary():
    rows = _rows()
    inc = sum(r.get("amount", 0) for r in rows if r.get("type") == "收入")
    exp = sum(r.get("amount", 0) for r in rows if r.get("type") != "收入")
    return {
        "income": round(inc, 2),
        "expense": round(exp, 2),
        "net": round(inc - exp, 2),
        "count": len(rows),
    }


def categories(month=None):
    rows = _rows()
    inc, exp = {}, {}
    for r in rows:
        if month and (r.get("date") or "")[:7] != month:
            continue
        if r.get("type") == "收入":
            inc[r.get("category") or "未分类"] = round(inc.get(r.get("category") or "未分类", 0) + (r.get("amount") or 0), 2)
        else:
            exp[r.get("category") or "未分类"] = round(exp.get(r.get("category") or "未分类", 0) + (r.get("amount") or 0), 2)
    return {"income": inc, "expense": exp}


def pnl_by_project():
    rows = _rows()
    proj = {}
    for r in rows:
        p = r.get("project") or "其他"
        d = proj.setdefault(p, {"project": p, "income": 0.0, "cost": 0.0, "count": 0})
        if r.get("type") == "收入":
            d["income"] += r.get("amount") or 0
        else:
            d["cost"] += r.get("amount") or 0
        d["count"] += 1
    for d in proj.values():
        d["income"] = round(d["income"], 2)
        d["cost"] = round(d["cost"], 2)
        d["profit"] = round(d["income"] - d["cost"], 2)
    return sorted(proj.values(), key=lambda x: -x["profit"])
