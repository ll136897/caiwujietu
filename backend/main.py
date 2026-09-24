import datetime
import json

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import WRITE_TOKEN, BASE_DIR, HOST, PORT
from .db import init_db
from . import store
from .ocr import ocr_image_bytes
from .parse import parse_text
from .reports import daily, weekly, monthly, all_summary, categories, pnl_by_project
from .export import export_excel, export_pdf

app = FastAPI(title="烤肉店截屏记账")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

STATIC = BASE_DIR / "static"
STATIC.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _check_token(req: Request):
    tok = req.headers.get("X-Token") or req.query_params.get("token")
    if tok != WRITE_TOKEN:
        raise HTTPException(status_code=403, detail="token 无效")


@app.get("/api/config")
def api_config():
    return {"write_token": WRITE_TOKEN}


@app.get("/api/health")
def api_health(write: int = 0):
    """自检：账本存储通不通 + 识别引擎配没配（看板顶部状态条用）。
    ?write=1 会真的往 GitHub 写一次再删掉，用来确认令牌有没有写入权限。"""
    from .config import BAIDU_API_KEY, BAIDU_SECRET_KEY, GITHUB_REPO
    st = store.storage_check(write=bool(write))
    return {
        "storage": st,
        "ocr_configured": bool(BAIDU_API_KEY and BAIDU_SECRET_KEY),
        "repo": GITHUB_REPO,
    }


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))


@app.get("/upload")
def upload_page():
    """手机上传页：拍照 / 从相册选图 → 识别支出渠道·时间·类别·名称·数量 → 入账，结果可改"""
    return FileResponse(str(STATIC / "upload.html"))


@app.post("/api/ocr")
async def api_ocr(req: Request, file: UploadFile = File(None)):
    _check_token(req)
    data = None
    ct = req.headers.get("content-type", "")
    if "multipart" in ct or "form" in ct:
        form = await req.form()
        src = file if file else next((v for v in form.values() if hasattr(v, "read")), None)
        if src is not None:
            data = await src.read()
    if not data:
        raw = await req.body()
        if raw:
            try:
                j = json.loads(raw)
                if j.get("image_base64"):
                    import base64
                    data = base64.b64decode(j["image_base64"])
            except Exception:
                pass
    if not data:
        raise HTTPException(status_code=400, detail="需要图片")
    text = ocr_image_bytes(data)
    suggestion = parse_text(text)
    return {"text": text, "suggestion": suggestion}


@app.post("/api/entries")
async def api_add_entry(req: Request):
    _check_token(req)
    body = await req.json()
    entry = {
        "amount": float(body.get("amount", 0) or 0),
        "type": body.get("type", "收入"),
        "category": body.get("category", ""),
        "merchant": body.get("merchant", ""),
        "project": body.get("project", "其他"),
        "date": body.get("date", ""),
        "unit": body.get("unit", ""),
        "quantity": body.get("quantity", ""),
        "note": body.get("note", ""),
        "img_hash": body.get("img_hash", ""),
        "channel": body.get("channel", ""),
        "item": body.get("item", ""),
        "time": body.get("time", ""),
    }
    store.add_entry(entry)
    return {"ok": True}


@app.get("/api/entries")
def api_list():
    return store.list_entries()


@app.patch("/api/entries/{eid}")
async def api_update(eid: int, req: Request):
    _check_token(req)
    body = await req.json()
    return store.update_entry(eid, body)


@app.delete("/api/entries/{eid}")
async def api_delete(eid: int, req: Request):
    _check_token(req)
    ok = store.delete_entry(eid)
    return {"ok": ok}


@app.post("/api/capture")
async def api_capture(req: Request, file: UploadFile = File(None)):
    """快捷指令 / 手机上传页专用：图片 → 识别 → 自动进账，一次请求完成。"""
    _check_token(req)
    try:
        return await _capture_impl(req, file)
    except HTTPException:
        raise
    except Exception as e:
        # 用户看不到服务器日志，所以把原因原样回给页面显示
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


async def _capture_impl(req: Request, file):
    data = None
    ct = req.headers.get("content-type", "")
    if "multipart" in ct or "form" in ct:
        form = await req.form()
        src = file if file else next((v for v in form.values() if hasattr(v, "read")), None)
        if src is not None:
            data = await src.read()
    if not data:
        raw = await req.body()
        if raw:
            try:
                j = json.loads(raw)
                if j.get("image_base64"):
                    import base64
                    data = base64.b64decode(j["image_base64"])
            except Exception:
                pass
    if not data:
        raise HTTPException(status_code=400, detail="需要图片")
    text = ocr_image_bytes(data)
    suggestion = parse_text(text)
    entry = {
        "amount": float(suggestion.get("amount", 0) or 0),
        "type": suggestion.get("type", "收入"),
        "category": suggestion.get("category", ""),
        "merchant": suggestion.get("merchant", ""),
        # 项目靠截图文字猜不准，允许上传时显式指定（?project=烤肉店）
        "project": (req.query_params.get("project") or "").strip() or suggestion.get("project", "其他"),
        "date": suggestion.get("date", "") or datetime.date.today().isoformat(),
        "unit": suggestion.get("unit", ""),
        "quantity": suggestion.get("quantity", ""),
        "note": suggestion.get("note", ""),
        "img_hash": suggestion.get("img_hash", ""),
        "channel": suggestion.get("channel", ""),
        "item": suggestion.get("item", ""),
        "time": suggestion.get("time", ""),
    }
    saved = store.add_entry(entry)
    # 把 OCR 原文一并返回，手机上传页可展开核对"它到底看到了什么"
    return {"ok": True, "entry": saved, "suggestion": suggestion, "text": text}


@app.get("/api/reports/daily")
def api_daily():
    return daily()


@app.get("/api/reports/weekly")
def api_weekly():
    return weekly()


@app.get("/api/reports/monthly")
def api_monthly():
    return monthly()


@app.get("/api/reports/all")
def api_all():
    return all_summary()


@app.get("/api/reports/categories")
def api_cat(month: str = None):
    return categories(month)


@app.get("/api/reports/pnl")
def api_pnl():
    return pnl_by_project()


@app.get("/api/reports/compare")
def api_compare():
    return pnl_by_project()


@app.get("/api/export/excel")
def api_excel(req: Request):
    _check_token(req)
    path = export_excel()
    return FileResponse(
        path,
        filename="烤肉店财务报表.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/export/pdf")
def api_pdf(req: Request):
    _check_token(req)
    path = export_pdf()
    return FileResponse(path, filename="烤肉店财务报表.pdf", media_type="application/pdf")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
