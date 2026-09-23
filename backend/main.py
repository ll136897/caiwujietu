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


@app.get("/")
def index():
    return FileResponse(str(STATIC / "index.html"))


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
    }
    store.add_entry(entry)
    return {"ok": True}


@app.get("/api/entries")
def api_list():
    return store.list_entries()


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
