import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла, если он есть
load_dotenv() 

# --- Настройки Telegram ---
# Получи свой токен у BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "7492378721:AAGGwCzItQ7COgp85cqzyfm3TXT8UjKkzIw") 

# --- Настройки Базы Данных ---
# Используем SQLite
DATABASE_URL = "sqlite:///./bot_database.db"

# --- Настройки Google Sheets ---
# Название твоего файла
SPREADSHEET_NAME = "Практика_2025" 
# Имя файла с ключом сервисного аккаунта (создан на шаге 1)
SERVICE_ACCOUNT_KEY_FILE = "service_account.json" 

# --- Константы Системы ---
DIRECTOR_ROLE = "director"
CURATOR_ROLE = "curator"
# Статус задачи по умолчанию
DEFAULT_STATUS = "pending"

# Роли должны быть указаны в БД, а также использоваться в мидлварах для
# ограничения доступа к командам
ROLES = [DIRECTOR_ROLE, CURATOR_ROLE]

# --- Настройки Напоминаний ---
# Дни недели для еженедельных напоминаний (0 - понедельник, 6 - воскресенье)
WEEKLY_REMINDER_DAY = 0 
WEEKLY_REMINDER_HOUR = 9 # Напоминание в 9:00

# День месяца для ежемесячных напоминаний
MONTHLY_REMINDER_DAY = 1 # 1-е число месяца