import asyncio
import traceback
from typing import Callable, Any, Awaitable, Dict
from aiogram import BaseMiddleware, Bot
from aiogram.types import Update
from sqlalchemy.orm import Session
from datetime import datetime

from database.crud import get_director, get_db
from config import DIRECTOR_ROLE # Убедись, что DIRECTOR_ROLE импортирован в config.py

# ID Разработчика/Админа, которому отправляются критические ошибки
# В реальном проекте это должно быть в config.py или .env
# Замени на свой Telegram ID (его можно узнать через бота @userinfobot)
DEVELOPER_TELEGRAM_ID = 0000000000 # <-- ЗАМЕНИ ЭТОТ ID!

class CriticalErrorMiddleware(BaseMiddleware):
    """
    Мидлвар для перехвата критических ошибок и отправки уведомлений
    Директору и Разработчику.
    """
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        bot: Bot = data['bot']
        
        try:
            # Пытаемся выполнить основной хендлер
            return await handler(event, data)
        
        except Exception as e:
            # --- Логирование и Уведомление об ошибке ---
            
            error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_type = type(e).__name__
            error_message = str(e)
            
            # Получаем полный стек вызовов
            full_traceback = traceback.format_exc()

            # Формируем отчет
            report_message = (
                f"🚨 **КРИТИЧЕСКАЯ ОШИБКА В БОТЕ!** 🚨\n"
                f"**Время:** `{error_time}`\n"
                f"**Тип:** `{error_type}`\n"
                f"**Сообщение:** `{error_message}`\n\n"
                f"**Обновление (Update):**\n`{event.model_dump_json(indent=2, exclude_none=True)}`\n\n"
                f"**Трассировка (Traceback):**\n```python\n{full_traceback[:1000]}... (см. логи)\n```"
            )
            
            # 1. Уведомление Разработчика (для немедленного исправления)
            if DEVELOPER_TELEGRAM_ID:
                try:
                    await bot.send_message(
                        chat_id=DEVELOPER_TELEGRAM_ID, 
                        text=report_message, 
                        parse_mode='Markdown'
                    )
                except Exception as e_dev:
                    print(f"Не удалось отправить ошибку разработчику: {e_dev}")
            
            # 2. Уведомление Директора (для информирования)
            # Поскольку это синхронная операция, запускаем ее в отдельном потоке
            db: Session = await asyncio.to_thread(get_db)
            director = await asyncio.to_thread(get_director, db)
            
            if director and director.is_confirmed and director.telegram_id != DEVELOPER_TELEGRAM_ID:
                try:
                    await bot.send_message(
                        chat_id=director.telegram_id, 
                        text=f"⚠️ **ВНИМАНИЕ!** В системе произошла внутренняя ошибка ({error_type}). Разработчик уже уведомлен и занимается устранением."
                    )
                except Exception as e_dir:
                    print(f"Не удалось отправить ошибку директору: {e_dir}")


            # 3. Отправка сообщения пользователю, у которого произошла ошибка
            user_message = "Произошла внутренняя ошибка системы. Пожалуйста, попробуйте позже. Разработчик уже уведомлен."
            if event.message:
                await event.message.answer(user_message)
            elif event.callback_query:
                await event.callback_query.answer(user_message, show_alert=True)

            # Выбрасываем исключение снова, чтобы оно было зафиксировано в консольных логах
            raise e