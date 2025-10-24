import asyncio
from datetime import date, timedelta
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from database.crud import get_all_curators, get_db, get_curator_tasks_for_period
from sheets.service import GoogleSheetsService
from config import WEEKLY_REMINDER_DAY, WEEKLY_REMINDER_HOUR, MONTHLY_REMINDER_DAY

def setup_scheduler(bot: Bot, gs_service: GoogleSheetsService):
    """Инициализирует и запускает планировщик APScheduler."""
    scheduler = AsyncIOScheduler()
    
    # 1. Задачи синхронизации (запуск каждые 30 минут)
    scheduler.add_job(
        synchronize_tasks, 
        'interval', 
        minutes=30, 
        args=[gs_service],
        id='sync_gsheets'
    )
    
    # 2. Еженедельное напоминание (каждый понедельник в 9:00)
    scheduler.add_job(
        send_weekly_reminders, 
        'cron', 
        day_of_week=WEEKLY_REMINDER_DAY, 
        hour=WEEKLY_REMINDER_HOUR, 
        args=[bot]
    )
    
    # 3. Ежемесячное напоминание (1-е число месяца)
    scheduler.add_job(
        send_monthly_reminders,
        'cron',
        day=MONTHLY_REMINDER_DAY,
        hour=9, # 9 утра
        args=[bot]
    )
    
    scheduler.start()
    print("-> Планировщик запущен.")

# --- Функции Планировщика ---

async def synchronize_tasks(gs_service: GoogleSheetsService):
    """Запускает синхронизацию задач из Google Sheets в БД."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Запуск синхронизации с Google Sheets...")
    
    # Эта функция уже реализована в sheets/service.py
    synced_count = await asyncio.to_thread(gs_service.sync_all_tasks) 
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Синхронизировано {synced_count} задач.")


async def send_weekly_reminders(bot: Bot):
    """Отправляет кураторам список задач на текущую неделю."""
    db: Session = await asyncio.to_thread(get_db)
    curators = await asyncio.to_thread(get_all_curators, db)
    
    today = date.today()
    # Период: текущая неделя (например, с Пн по Вс)
    start_date = today - timedelta(days=today.weekday()) 
    end_date = start_date + timedelta(days=6)
    
    for curator in curators:
        tasks = await asyncio.to_thread(
            get_curator_tasks_for_period, 
            db, 
            curator.id, 
            start_date, 
            end_date, 
            include_done=False # Напоминаем только о незавершенных
        )
        
        if not tasks:
            await bot.send_message(curator.telegram_id, "✨ На этой неделе у вас нет незавершенных задач!")
            continue
            
        message_text = (
            f"🔔 **Еженедельное Напоминание!**\n\n"
            f"Вот ваши <b>незавершенные</b> задачи на текущую неделю ({start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m')}):"
        )
        
        for task in tasks:
            message_text += f"\n🔴 {task.title} (до {task.end_date.strftime('%d.%m')})"
        
        message_text += "\n\nПожалуйста, отметьте выполнение через /tasks."
        
        await bot.send_message(curator.telegram_id, message_text, parse_mode='HTML')


async def send_monthly_reminders(bot: Bot):
    """Отправляет кураторам список задач на текущий месяц."""
    db: Session = await asyncio.to_thread(get_db)
    curators = await asyncio.to_thread(get_all_curators, db)
    
    today = date.today()
    start_date = today.replace(day=1)
    
    # Вычисление конца месяца (аналогично в handlers/curator.py)
    try:
        end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
    except ValueError:
        end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
        
    for curator in curators:
        tasks = await asyncio.to_thread(
            get_curator_tasks_for_period, 
            db, 
            curator.id, 
            start_date, 
            end_date,
            include_done=False
        )

        if not tasks:
            continue
            
        message_text = (
            f"🗓️ **Ежемесячный План ({start_date.strftime('%B %Y')})!**\n\n"
            f"Ваши <b>незавершенные</b> задачи на этот месяц ({len(tasks)} шт.):"
        )
        
        for task in tasks:
            message_text += f"\n🔴 {task.title} (Сроки: {task.start_date.strftime('%d.%m')} - {task.end_date.strftime('%d.%m')})"
        
        message_text += "\n\nПланируйте свою работу! Используйте /tasks для просмотра."
        
        await bot.send_message(curator.telegram_id, message_text, parse_mode='HTML')