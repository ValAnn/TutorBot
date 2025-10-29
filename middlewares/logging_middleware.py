from aiogram import BaseMiddleware
from aiogram.types import Update
from collections.abc import Awaitable, Callable
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, any]], Awaitable[any]],
        event: Update,
        data: dict[str, any]
    ) -> any:

        # Log the event before processing
        ban_status = await self.pre_process(event, data)

        return await handler(event, data) if ban_status else False

    async def pre_process(self, update: Update, data: dict):
        state = data.get('state')
        user_state = f's: {await state.get_state()}' if state else ''
        if update.message:
            obj = update.message
            content = f"m: {obj.text}" if obj.text else f"c: {obj.content_type}"
            chat_id = f"[{obj.chat.id}]" if obj.chat.id != obj.from_user.id else ''
            logger.info(f"U: {obj.from_user.id}{chat_id} {content} {user_state}")
        elif update.callback_query:
            obj = update.callback_query
            chat_id = f"[{obj.message.chat.id}]" if obj.message.chat.id != obj.from_user.id else ''
            logger.info(f"U: {obj.from_user.id}{chat_id} cb: {obj.data} {user_state}")
        else:
            logger.info(f"Unhandled update type: {update}")

        return True