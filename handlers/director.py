from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from datetime import date, timedelta
import asyncio
from aiogram.fsm.context import FSMContext

# Используем CRUD для User
from database.crud import get_all_curators, get_db, get_unconfirmed_users, update_user_confirmation
from database.models import User
# Сервис Google Sheets для работы с задачами
from sheets.service import GoogleSheetsService, TaskData, CuratorSheetInfo 
from config import DIRECTOR_ROLE, TASK_STATUS_DONE, CURATOR_ROLE

router = Router()

# --- Команда для запроса статистики ---
@router.message(F.text == "📊 Отчетность")
async def command_stats(message: types.Message):
    """
    Отправляет инлайн-клавиатуру для выбора периода статистики.
    """
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
    
    is_weekly = (callback.data == "stats_weekly")
    today = date.today()

    # Определение периода
    if is_weekly:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        period_title = f"Неделя (с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')})"
    else:
        start_date = today.replace(day=1)
        try:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(days=1)
        except ValueError:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(days=1)
            
        period_title = f"Месяц ({start_date.strftime('%B %Y')})"
        
    await callback.message.answer(f"⏳ Формирую отчет за **{period_title}**...", parse_mode='Markdown')

    # 1. Получение Кураторов по названиям листов
    # Функция gs_service.get_all_curator_sheets() возвращает список CuratorSheetInfo
    curators: list[CuratorSheetInfo] = await asyncio.to_thread(gs_service.get_all_curator_sheets) 
    
    # Инициализация переменных для сводки
    total_tasks_all = 0
    done_tasks_all = 0
    
    report_details = [] # Список для хранения отчетов по каждому куратору

    # 2. Сбор статистики по каждому куратору/листу
    for curator in curators:
        # sheet_name - это теперь имя куратора
        all_tasks: list[TaskData] = await asyncio.to_thread(
            gs_service.get_curator_tasks_for_period, 
            curator.sheet_name, 
            start_date, 
            end_date
        )
        
        # Расчет статистики
        done_tasks = [t for t in all_tasks if t.status.upper() == TASK_STATUS_DONE]
        
        total_tasks = len(all_tasks)
        done_count = len(done_tasks)
        pending_count = total_tasks - done_count
        
        total_tasks_all += total_tasks
        done_tasks_all += done_count
        
        if total_tasks > 0:
            performance = (done_count / total_tasks) * 100
        else:
            performance = 0
            
        # Формирование блока для одного куратора
        if total_tasks > 0:
            status_line = (
                f"✅ Выполнено: **{done_count}**\n"
                f"❌ Осталось: **{pending_count}**\n"
                f"💯 Прогресс: **{performance:.1f}%**"
            )
        else:
            status_line = "Нет активных задач в этот период."
            
        report_details.append(
            f"👤 **{curator.name}** (Всего задач: {total_tasks})\n"
            f"{status_line}"
        )

    # 3. Формирование итогового отчета
    final_report = f"📈 **Сводный Отчет за {period_title}**\n"
    
    if total_tasks_all > 0:
        performance_overall = (done_tasks_all / total_tasks_all) * 100
        
        # Общая сводка
        final_report += (
            f"\n--- **Общая сводка** ---\n"
            f"💼 Всего Кураторов: **{len(curators)}**\n"
            f"🔢 Общее количество задач: **{total_tasks_all}**\n"
            f"✅ Общее выполнение: **{performance_overall:.1f}%**\n"
            f"---"
        )
        
        # Детализация
        final_report += "\n\n📊 **Детализация по кураторам:**\n\n"
        final_report += "\n---\n".join(report_details)
    
    elif not curators:
        final_report += "\n\nНет рабочих листов кураторов в таблице."
    else:
        final_report += "\n\nВсе кураторы найдены, но у них нет активных задач в этот период."


    await callback.message.answer(final_report, parse_mode='Markdown')


# --- Команда для подтверждения пользователей ---
# Эта логика предполагает, что подтверждение пользователя изменяет поле is_confirmed в ЛОКАЛЬНОЙ БД
@router.message( F.text == "👤 Подтверждение пользователей")
async def command_confirm(message: types.Message, state: FSMContext):
    
    # 1. Получаем список неподтвержденных пользователей из БД
    db: Session = await asyncio.to_thread(get_db)
    unconfirmed_users = await asyncio.to_thread(get_unconfirmed_users, db)

    if not unconfirmed_users:
        await message.answer("Нет пользователей, ожидающих подтверждения.")
        await state.clear()
        return

    # 2. Формируем список и инлайн-клавиатуру
    text = "Пользователи, ожидающие подтверждения:\n\n"
    keyboard_buttons = []

    for user in unconfirmed_users:
        text += f"ID: {user.telegram_id}, Имя: {user.name}, Роль: {user.role}\n"
        
        # Кнопка для подтверждения
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"✅ Подтвердить {user.name} ({user.role})",
                # Callback data: 'confirm:TELEGRAM_ID'
                callback_data=f"confirm_user:{user.telegram_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(text, reply_markup=reply_markup)
    await state.clear()

# --- Callback: Обработка подтверждения пользователя ---
@router.callback_query(F.data.startswith("confirm_user:"))
async def confirm_user_callback(callback: types.CallbackQuery):
    
    try:
        # Извлекаем TELEGRAM_ID
        target_telegram_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID пользователя.")
        return

    db: Session = await asyncio.to_thread(get_db)
    
    # 1. Обновляем статус в ЛОКАЛЬНОЙ БД
    updated_user = await asyncio.to_thread(update_user_confirmation, db, target_telegram_id, is_confirmed=True)

    if updated_user and updated_user.is_confirmed:
        await callback.answer(f"Пользователь {updated_user.name} подтвержден.", show_alert=True)
        
        # 2. Редактируем сообщение, чтобы удалить кнопку
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass # Игнорируем ошибку, если сообщение нельзя изменить
            
        await callback.message.answer(f"✅ Пользователь **{updated_user.name}** ({updated_user.role}) подтвержден и может начать работу.")
        
    else:
        await callback.answer("Ошибка подтверждения пользователя.", show_alert=True)