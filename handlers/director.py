from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio

from database.crud import get_db, get_all_curators, get_curator_tasks_for_period
from config import DIRECTOR_ROLE # Роль уже проверена мидлваром

router = Router()

# --- Команда для запроса статистики ---
@router.message(Command("stats") | F.text == "📊 Отчетность")
async def command_stats(message: types.Message):
    await message.answer(
        "Выберите период, за который хотите получить статистику:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Статистика за неделю", callback_data="stats_weekly")],
            [InlineKeyboardButton(text="Статистика за месяц", callback_data="stats_monthly")],
        ])
    )

# --- Callback: Отправка статистики Директору ---
@router.callback_query(F.data.in_({"stats_weekly", "stats_monthly"}))
async def send_stats_report(callback: types.CallbackQuery):
    await callback.answer(cache_time=1)
    
    is_weekly = (callback.data == "stats_weekly")
    today = date.today()
    
    # 1. Определение периода
    if is_weekly:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_title = f"НЕДЕЛЬНЫЙ ОТЧЕТ (с {start_date} по {end_date})"
    else:
        start_date = today.replace(day=1)
        try:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
        except ValueError:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        period_title = f"МЕСЯЧНЫЙ ОТЧЕТ ({start_date.strftime('%B %Y')})"
        
    await callback.message.answer(f"⏳ Формирую отчет: **{period_title}**...", parse_mode='Markdown')

    # 2. Получение данных и расчет
    db: Session = await asyncio.to_thread(get_db)
    curators = await asyncio.to_thread(get_all_curators, db)
    
    report_lines = []
    total_tasks_all = 0
    done_tasks_all = 0

    for curator in curators:
        # Получаем ВСЕ задачи, которые попадают в период (включая выполненные)
        all_tasks = await asyncio.to_thread(
            get_curator_tasks_for_period, 
            db, 
            curator.id, 
            start_date, 
            end_date, 
            include_done=True
        )
        
        # Фильтруем, чтобы посчитать выполненные
        done_tasks = [t for t in all_tasks if t.status == 'done']
        
        total_tasks = len(all_tasks)
        done_count = len(done_tasks)
        
        total_tasks_all += total_tasks
        done_tasks_all += done_count

        if total_tasks == 0:
            progress = "Нет задач"
        else:
            percent = (done_count / total_tasks) * 100
            progress = f"{done_count}/{total_tasks} ({percent:.1f}%)"
            
        report_lines.append(f"👤 **{curator.name}**: {progress}")
        
    # 3. Формирование итогового отчета
    final_report = f"📊 **ОБЩИЙ {period_title}**\n\n"
    
    if total_tasks_all > 0:
        total_percent = (done_tasks_all / total_tasks_all) * 100
        final_report += (
            f"**Общий Прогресс:** {done_tasks_all}/{total_tasks_all} задач выполнено ({total_percent:.1f}%)\n\n"
        )
    else:
        final_report += "В этот период нет зарегистрированных задач ни у одного куратора.\n\n"

    final_report += "--- Прогресс по Кураторам ---\n"
    final_report += "\n".join(report_lines)
    
    final_report += "\n\n<i>Полная аналитика доступна в Google Sheets.</i>"

    await callback.message.answer(final_report, parse_mode='Markdown')