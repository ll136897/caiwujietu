import base64
import time
import requests
from .config import (
    BAIDU_API_KEY,
    BAIDU_SECRET_KEY,
    BAIDU_TOKEN_URL,
    BAIDU_OCR_URL,
    BAIDU_OCR_URLS,
)

_token_cache = {"token": None, "expire": 0}


def _get_token():
    if not (BAIDU_API_KEY and BAIDU_SECRET_KEY):
        return None
    if _token_cache["token"] and time.time() < _token_cache["expire"]:
        return _token_cache["token"]
    try:
        r = requests.get(
            BAIDU_TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": BAIDU_API_KEY,
                "client_secret": BAIDU_SECRET_KEY,
            },
            timeout=10,
        )
        data = r.json()
        tok = data.get("access_token")
        _token_cache["token"] = tok
        _token_cache["expire"] = time.time() + 2500000
        return tok
    except Exception:
        return None


def ocr_image_bytes(image_bytes: bytes) -> str:
    """返回 OCR 识别出的原始文本（换行分隔）。无 Key / 调用失败时回退 mock。"""
    token = _get_token()
    if not token:
        return _mock_text()
    b64 = base64.b64encode(image_bytes).decode()
    # 高精度版 -> 标准版 依次尝试；哪个有权限用哪个
    for url in BAIDU_OCR_URLS:
        try:
            r = requests.post(
                url,
                data={"access_token": token, "image": b64},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            data = r.json()
            if data.get("error_code"):
                # 如 6=无权限（未领取该接口免费额度），换下一个接口再试
                continue
            words = [w["words"] for w in data.get("words_result", [])]
            if words:
                return "\n".join(words)
        except Exception:
            continue
    return _mock_text()


def _mock_text():
    # 本地无百度 Key 时的样例文本，用于跑通全链路；真实环境会被云端 OCR 覆盖
    return (
        "微信支付 收款通知\n"
        "收款金额 ¥328.00\n"
        "付款方 青龙湖游客王先生\n"
        "2026-09-08 18:42\n"
        "刘和牛户外烤肉 2-3人套餐"
    )
