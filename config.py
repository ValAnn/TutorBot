# Файл: config.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv() 

# --- Настройки Telegram ---
# Читаем из .env
BOT_TOKEN = os.getenv("BOT_TOKEN") 

# --- Настройки Базы Данных ---
# Читаем из .env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot_database.db") # Дефолт, если в .env нет

# --- Настройки Google Sheets ---
# Читаем из .env
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Практика") 
SERVICE_ACCOUNT_KEY_FILE = os.getenv("SERVICE_ACCOUNT_KEY_FILE", "service_account.json") 

# --- Настройки Разработчика/Админа ---
# Читаем из .env (нужно преобразовать в int)
DEVELOPER_TELEGRAM_ID = int(os.getenv("DEVELOPER_TELEGRAM_ID", 0))

# --- Константы Системы (остаются прежними) ---
DIRECTOR_ROLE = "director"
CURATOR_ROLE = "curator"
# ... (остальной код config.py)