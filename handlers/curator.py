from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio

from database.crud import get_curator_tasks_for_period, get_db, update_task_status
from database.models import User, Task
from config import CURATOR_ROLE # Используется для наглядности, но роль проверяет мидлвар

router = Router()

# --- Команда для просмотра задач ---
@router.message(Command("stats") | F.text == "📊 Отчетность") 
async def command_tasks(message: types.Message, user: User):
    await message.answer(
        "Выберите, какие задачи вы хотите посмотреть:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Мои задачи на неделю", callback_data="tasks_weekly")],
            [InlineKeyboardButton(text="Мои задачи на месяц", callback_data="tasks_monthly")],
        ])
    )

# --- Callback: Показать задачи на период ---
@router.callback_query(F.data.in_({"tasks_weekly", "tasks_monthly"}))
async def show_period_tasks(callback: types.CallbackQuery, user: User):
    await callback.answer(cache_time=1)
    
    is_weekly = (callback.data == "tasks_weekly")
    
    # Определение периода
    today = date.today()
    if is_weekly:
        # С начала текущей недели (понедельника) до конца
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_title = f"Задачи на неделю (с {start_date} по {end_date})"
    else:
        # С начала текущего месяца до конца
        start_date = today.replace(day=1)
        # Находим последнее число месяца
        try:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
        except ValueError: # Если месяц - декабрь
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        period_title = f"Задачи на месяц ({start_date.strftime('%B %Y')})"
        
    # Получение задач из БД
    db: Session = await asyncio.to_thread(get_db)
    tasks: list[Task] = await asyncio.to_thread(
        get_curator_tasks_for_period, 
        db, 
        user.id, 
        start_date, 
        end_date
    )

    if not tasks:
        await callback.message.answer(f"{period_title}: У вас нет активных задач в этот период.")
        return

    message_text = f"📋 **{period_title}**:\n\n"
    
    # Сортируем: сначала невыполненные, потом выполненные
    tasks.sort(key=lambda t: (t.status == 'done', t.end_date))
    
    for task in tasks:
        status_icon = "✅" if task.status == 'done' else ("⏳" if task.status == 'in_progress' else "🔴")
        
        # Куратор видит ВСЕ задачи, включая выполненные (как ты просила)
        message_text += (
            f"{status_icon} **{task.title}**\n"
            f"   Сроки: {task.start_date.strftime('%d.%m')} - {task.end_date.strftime('%d.%m')}\n"
        )
        # Если задача не выполнена, предлагаем кнопку
        if task.status != 'done':
            message_text += (
                f"   [ ] -> `/done_{task.id}`\n"
            )

    await callback.message.answer(message_text, parse_mode='Markdown')

# --- Команда для отметки выполнения (кнопка "Готово") ---
@router.message(F.text.startswith("/done_"))
async def mark_task_done(message: types.Message, user: User, gs_service):
    # Извлекаем ID задачи из команды
    try:
        task_id = int(message.text.split("_")[1])
    except (IndexError, ValueError):
        await message.answer("Ошибка в формате команды. Пожалуйста, используйте кнопку или команду /tasks.")
        return

    db: Session = await asyncio.to_thread(get_db)
    # Ищем задачу и проверяем, что она принадлежит этому куратору
    task_to_update: Task = await asyncio.to_thread(lambda: db.query(Task).filter(Task.id == task_id, Task.curator_id == user.id).first())

    if not task_to_update:
        await message.answer("Задача не найдена или принадлежит другому куратору.")
        return
        
    if task_to_update.status == 'done':
        await message.answer(f"Задача **{task_to_update.title}** уже была выполнена. ✅", parse_mode='Markdown')
        return

    # 1. Обновление статуса в БД
    updated_task = await asyncio.to_thread(update_task_status, db, task_id, 'done')
    
    # 2. Обновление статуса в Google Sheets
    # Используем gs_service, переданный через DI
    success = await asyncio.to_thread(gs_service.update_status_in_sheet, updated_task, 'DONE')

    if success:
        await message.answer(
            f"✅ Задача **{updated_task.title}** отмечена как выполненная!\n"
            "Данные успешно синхронизированы с Google Sheets.",
            parse_mode='Markdown'
        )
    else:
        # Если GSheet не обновился, но БД обновилась
        await message.answer(
            f"✅ Задача **{updated_task.title}** отмечена как выполненная в системе.\n"
            "⚠️ **ВНИМАНИЕ!** Не удалось обновить Google Sheets. Сообщите Директору.",
            parse_mode='Markdown'
        )