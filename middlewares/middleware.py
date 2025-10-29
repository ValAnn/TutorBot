import asyncio
from typing import Callable, Any, Awaitable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from sqlalchemy.orm import Session

from database.crud import get_user_by_telegram_id, get_db
from config import DIRECTOR_ROLE, CURATOR_ROLE

class RoleAccessMiddleware(BaseMiddleware):
    """
    Мидлвар для проверки наличия пользователя в БД и его роли.
    Требует, чтобы роль была передана в фильтрах роутера.
    """
    def __init__(self, allowed_roles: list[str] | None = None):
        super().__init__()
        self.allowed_roles = allowed_roles
        
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # 1. Получаем сессию БД асинхронно
        db: Session = await asyncio.to_thread(get_db)
        
        # 2. Получаем пользователя
        user = await asyncio.to_thread(get_user_by_telegram_id, db, event.from_user.id)
        
        # Если пользователь не зарегистрирован или не подтвержден
        if not user or not user.is_confirmed:
            await event.answer("🚫 Вы не зарегистрированы или ожидаете подтверждения Директором. Используйте /start.")
            return

        # 3. Добавляем объект пользователя в `data` для удобства
        data['user'] = user
        
        # 4. Проверка роли, если она указана в мидлваре
        if self.allowed_roles:
            if user.role not in self.allowed_roles:
                role_name = "Директор" if self.allowed_roles == [DIRECTOR_ROLE] else "Куратор"
                await event.answer(f"🚫 У вас нет прав. Эта команда доступна только для {role_name}.")
                return
        
        # Если все проверки пройдены, передаем управление дальше
        return await handler(event, data)