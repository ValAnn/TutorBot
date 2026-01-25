# Файл: handlers/curator.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio

# Используем CRUD для получения БД-сессии
from database.crud import get_db 
from database.models import User # Типизация для User
from sheets.service import GoogleSheetsService, TaskData # Сервис и модель задач
from config import TASK_STATUS_DONE

router = Router()

# --- Команда для просмотра задач ---
@router.message(Command("tasks"))
@router.message(F.text == "📋 Мои задачи") # Обработка осмысленной кнопки
async def command_tasks(message: types.Message): # User приходит через RoleAccessMiddleware
     # Логика остается прежней (вывод инлайн-меню)
    await message.answer(
        "Выберите, какие задачи вы хотите посмотреть:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Мои задачи на неделю", callback_data="tasks_weekly")],
            [InlineKeyboardButton(text="Мои задачи на месяц", callback_data="tasks_monthly")],
        ])
    )

async def _generate_task_report(
    user: User, 
    gs_service: GoogleSheetsService, 
    start_date: date, 
    end_date: date, 
    period_title: str,
    target_message: Message | types.CallbackQuery
):
    """
    Получает задачи и форматирует сообщение с кнопками.
    Отправляет или редактирует сообщение в зависимости от типа target_message.
    """
    
    tasks: list[TaskData] = await asyncio.to_thread(
        gs_service.get_curator_tasks_for_period, 
        user.sheet_name, 
        start_date, 
        end_date
    )

    if not tasks:
        await target_message.answer(f"{period_title}: У вас нет активных задач в этот период.")
        return

    message_text = f"📋 **{period_title}** (Обновлено):\n\n"
    tasks.sort(key=lambda t: (t.status == TASK_STATUS_DONE.upper(), t.end_date))
    
    keyboard_buttons = []
    
    for task in tasks:
        status_icon = "✅" if task.status.upper() == TASK_STATUS_DONE else "🔴"
        
        message_text += (
            f"{status_icon} **{task.title}**\n"
            f"   Сроки: {task.start_date.strftime('%d.%m')} - {task.end_date.strftime('%d.%m')}\n"
        )
        
        if task.status.upper() != TASK_STATUS_DONE:
            # Создаем кнопку для выполнения задачи
            button_text = f"✅ Отметить: {task.title}"
            callback_data = f"done:{task.id}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data=callback_data)
            ])
            
        message_text += "\n"
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправка нового сообщения с актуальным списком
    await target_message.answer(
        message_text, 
        parse_mode='Markdown', 
        reply_markup=reply_markup if keyboard_buttons else None
    )


@router.callback_query(F.data.in_({"tasks_weekly", "tasks_monthly"}))
async def show_period_tasks(callback: types.CallbackQuery, user: User, gs_service: GoogleSheetsService):
    await callback.answer(cache_time=1)
    
    is_weekly = (callback.data == "tasks_weekly")
    today = date.today()

    # Определение периода
    if is_weekly:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_title = f"Задачи на неделю (с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')})"
    else:
        start_date = today.replace(day=1) 
        try:
            # Следующий месяц минус один день
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
        except ValueError:
            # Если это декабрь
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
            
        period_title = f"Задачи на месяц ({start_date.strftime('%B %Y')})"
        
    tasks: list[TaskData] = await asyncio.to_thread(
        gs_service.get_curator_tasks_for_period, 
        user.sheet_name, 
        start_date, 
        end_date
    )

    if not tasks:
        await callback.message.answer(f"{period_title}: У вас нет активных задач в этот период.")
        return

    message_text = f"📋 **{period_title}**:\n\n"
    tasks.sort(key=lambda t: (t.status == TASK_STATUS_DONE, t.end_date))
    
    # Инициализация для кнопок
    keyboard_buttons = []

    for task in tasks:
        status_icon = "✅" if task.status.upper() == TASK_STATUS_DONE else "🔴"
        
        message_text += (
            f"{status_icon} **{task.title}**\n"
            f"   Сроки: {task.start_date.strftime('%d.%m')} - {task.end_date.strftime('%d.%m')}\n"
        )
        
        if task.status.upper() != TASK_STATUS_DONE:
            # 📌 Создаем кнопку для выполнения задачи
            button_text = f"✅ Отметить: {task.title}"
            # Callback data: 'done:TASK_ID'
            callback_data = f"done:{task.id}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data=callback_data)
            ])
            
        message_text += "\n"
    
    # Создаем финальный объект клавиатуры
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Отправляем сообщение с кнопками, если есть невыполненные задачи
    if keyboard_buttons:
        await callback.message.answer(message_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        # Если все выполнено
        await callback.message.answer(message_text, parse_mode='Markdown')


# --- НОВЫЙ CALLBACK HANDLER: Отметить задачу как выполненную ---
@router.callback_query(F.data.startswith("done:"))
async def mark_task_done_callback(callback: types.CallbackQuery, user: User, gs_service: GoogleSheetsService):
    
    # 1. Извлекаем task_id
    try:
        # 'done:123' -> 123
        task_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID задачи.")
        return

    await callback.answer(f"Обрабатываю задачу ID {task_id}...", cache_time=1)
    
    # 2. Обновление статуса в Google Sheets
    success = await asyncio.to_thread(
        gs_service.update_status_in_sheet, 
        task_id, 
        user.sheet_name, 
        TASK_STATUS_DONE
    )

    if success:
        # 3. Редактируем сообщение: удаляем клавиатуру и отправляем подтверждение
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id
            )
        except Exception as e:
            # Игнорируем ошибку, если бот не смог удалить сообщение 
            # (например, если оно слишком старое или нет прав).
            print(f"Не удалось удалить сообщение: {e}")
            pass 
        # Удаляем клавиатуру из сообщения, по которому было нажатие
        
            
        today = date.today()
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_title = f"Задачи на неделю (с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')})"

        await callback.message.answer(
            f"✅ Задача ID **{task_id}** отмечена как выполненная!\n"
            "Данные успешно синхронизированы с Google Sheets.",
            parse_mode='Markdown'
        )

        await _generate_task_report(
            user, 
            gs_service, 
            start_date, 
            end_date, 
            period_title, 
            callback.message # Используем callback.message для отправки нового сообщения
        )
    else:
        await callback.message.answer(
            f"⚠️ **ВНИМАНИЕ!** Не удалось найти или обновить задачу ID **{task_id}** в Google Sheets.",
            parse_mode='Markdown'
        )