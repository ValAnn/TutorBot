# Файл: main.py
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, SPREADSHEET_NAME, SERVICE_ACCOUNT_KEY_FILE
from database.models import Base, engine # <-- Восстановлено

from sheets.service import GoogleSheetsService
from handlers.common import router as common_router
from handlers.curator import router as curator_router
from handlers.director import router as director_router
#from handlers.middlewares import RoleAccessMiddleware 
from middlewares.error_middleware import CriticalErrorMiddleware 
from middlewares.logging_middleware import LoggingMiddleware 
from middlewares.middleware import RoleAccessMiddleware 
from config import DIRECTOR_ROLE, CURATOR_ROLE

# Функция для инициализации БД (только для пользователей)
def init_db():
    print("-> Создание таблиц БД (только для пользователей)...")
    Base.metadata.create_all(bind=engine)

async def main():
    # 1. Инициализация БД и Sheets Service
    init_db() 
    print("-> Инициализация Google Sheets Service (для задач)...")
    gs_service = GoogleSheetsService(SPREADSHEET_NAME, SERVICE_ACCOUNT_KEY_FILE)
    
    # 2. Инициализация Бота и Диспетчера
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # 3. Применение Мидлваров
    dp.update.middleware(LoggingMiddleware()) 
    dp.update.middleware(CriticalErrorMiddleware())
    # ActionLogMiddleware все еще будет пытаться записать в БД, 
    # если вы не убрали оттуда логику Task/ProgressLog.
    # Если ProgressLog удален, этот мидлвар нужно будет удалить или переписать.
    # dp.update.middleware(ActionLogMiddleware()) 

    # 4. Регистрация Роутеров и RoleAccessMiddleware
    dp.include_router(common_router)

    # --- РОУТЕР КУРАТОРА ---
    # Привязываем мидлвар к сообщениям
    curator_router.message.middleware(RoleAccessMiddleware(allowed_roles=[CURATOR_ROLE]))
    # 📌 ДОБАВЬТЕ ЭТУ СТРОКУ для Callback Queries (нажатий кнопок)
    curator_router.callback_query.middleware(RoleAccessMiddleware(allowed_roles=[CURATOR_ROLE])) 
    dp.include_router(curator_router)

    # --- РОУТЕР ДИРЕКТОРА ---
    # Также расширьте для Директора, если его хендлеры используют колбэки:
    director_router.message.middleware(RoleAccessMiddleware(allowed_roles=[DIRECTOR_ROLE]))
    director_router.callback_query.middleware(RoleAccessMiddleware(allowed_roles=[DIRECTOR_ROLE]))
    dp.include_router(director_router)
    
    print("-> Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    # Передаем gs_service в хендлеры
    await dp.start_polling(bot, gs_service=gs_service) 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен вручную.")