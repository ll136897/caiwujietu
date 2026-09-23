import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

# 百度智能云 OCR（通用文字识别高精度版）
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"

# 持久化存储：默认存进用户本人 GitHub 仓库里的账本文件（永久在、归用户、可导出）
# 不填则退回本地 SQLite（仅本机、会随服务清空，仅用于本地调试）
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")        # 格式：你的用户名/仓库名
LEDGER_PATH = os.getenv("LEDGER_PATH", "data/ledger.json")

# 写入令牌：快捷指令与看板导出时携带，防误刷
WRITE_TOKEN = os.getenv("WRITE_TOKEN", "changer-secret-token")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
