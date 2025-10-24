import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties 
from config import BOT_TOKEN, CURATOR_ROLE, DATABASE_URL, DIRECTOR_ROLE
from database.models import Base, engine # Импортируем для создания таблиц
from handlers.middlewares.error_middleware import CriticalErrorMiddleware
from scheduler.tasks import setup_scheduler
from sheets.service import GoogleSheetsService # Сервис для GSheets
from handlers.common import router as common_router # Общие хендлеры
from handlers.curator import router as curator_router # Хендлеры кураторов
from handlers.director import router as director_router # Хендлеры директора
from handlers.middlewares.middleware import RoleAccessMiddleware
# Инициализируем Сервис Google Sheets
gs_service = GoogleSheetsService()

async def main():
    # 1. Инициализация БД
    print("-> Инициализация БД...")
    Base.metadata.create_all(bind=engine)
    
    # 2. Инициализация Бота и Диспетчера
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # --- Регистрация Аварийного Мидлвара на уровне Диспетчера ---
    # Он должен быть зарегистрирован первым, чтобы обернуть все остальные
    dp.update.middleware(CriticalErrorMiddleware())
    # -----------------------------------------------------------

    # 3. Применение Мидлваров для контроля доступа и регистрация Роутеров
    dp.include_router(common_router)
    
    curator_router.message.middleware(RoleAccessMiddleware(allowed_roles=[CURATOR_ROLE]))
    dp.include_router(curator_router)
    
    director_router.message.middleware(RoleAccessMiddleware(allowed_roles=[DIRECTOR_ROLE]))
    dp.include_router(director_router)
    
    # 4. Настройка и запуск планировщика
    setup_scheduler(bot, gs_service) 
    
    print("-> Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, gs_service=gs_service) 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("-> Бот остановлен.")