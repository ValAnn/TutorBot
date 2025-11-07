# Файл: handlers/director.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio

from database.crud import get_all_curators, get_db # CRUD для User
from database.models import User # Типизация для User
from sheets.service import GoogleSheetsService, TaskData # Сервис и модель задач
from config import DIRECTOR_ROLE, TASK_STATUS_DONE

router = Router()

# --- Команда для запроса статистики ---
@router.message(Command("stats") | F.text == "📊 Отчетность")
async def command_stats(message: types.Message):
    # ... (логика вывода инлайн-меню)
    await message.answer(
        "Выберите период, за который хотите получить статистику:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Статистика за неделю", callback_data="stats_weekly")],
            [InlineKeyboardButton(text="Статистика за месяц", callback_data="stats_monthly")],
        ])
    )

# --- Callback: Отправка статистики Директору ---
@router.callback_query(F.data.in_({"stats_weekly", "stats_monthly"}))
async def send_stats_report(callback: types.CallbackQuery, gs_service: GoogleSheetsService):
    await callback.answer(cache_time=1)
    
    # ... (Определение периода)

    await callback.message.answer(f"⏳ Формирую отчет: **{period_title}**...", parse_mode='Markdown')

    # 1. Получение Кураторов из ЛОКАЛЬНОЙ БД
    db: Session = await asyncio.to_thread(get_db)
    curators: list[User] = await asyncio.to_thread(get_all_curators, db) 
    
    report_lines = []
    total_tasks_all = 0
    done_tasks_all = 0

    for curator in curators:
        # 📌 Получение задач: Используем gs_service и curator.sheet_name
        all_tasks: list[TaskData] = await asyncio.to_thread(
            gs_service.get_curator_tasks_for_period, 
            curator.sheet_name, 
            start_date, 
            end_date
        )
        
        # Фильтруем, чтобы посчитать выполненные
        done_tasks = [t for t in all_tasks if t.status == TASK_STATUS_DONE]
        
        total_tasks = len(all_tasks)
        done_count = len(done_tasks)
        
        # ... (Расчет статистики и формирование final_report остается прежним)