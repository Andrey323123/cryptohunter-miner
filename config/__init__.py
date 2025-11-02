# config/__init__.py — v2.0: Railway + MySQL + TON Mainnet
from dotenv import load_dotenv
import os

# Загружаем .env (Railway делает это автоматически)
load_dotenv()

# === TELEGRAM ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")

# === АДМИН ===
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# === БАЗА ДАННЫХ (Railway даёт MYSQLURL) ===
# Если есть MYSQLURL — используем его (Railway)
DATABASE_URL = os.getenv("MYSQLURL")

# Если нет — собираем из отдельных переменных (локально)
if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME")
    DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# === TON (MAINNET!) ===
TONKEEPER_MNEMONIC = os.getenv("TONKEEPER_MNEMONIC")
TONKEEPER_API_KEY = os.getenv("TONKEEPER_API_KEY")
TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", TONKEEPER_API_KEY)
TONCENTER_BASE_URL = os.getenv("TONCENTER_BASE_URL", "https://toncenter.com/api/v3")  # MAINNET

# === ВЕБ-ПРИЛОЖЕНИЕ ===
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://cryptohunter-miner.up.railway.app")

# === ОТЛАДКА ===
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
