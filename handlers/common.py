from aiogram import Router, types, F, Bot 
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
import asyncio
from aiogram.filters import Command
from database.crud import get_user_by_telegram_id, create_user, get_director, get_unconfirmed_users, confirm_user
from database.crud import get_db # Используем синхронный CRUD, поэтому нужны потоки
from config import DIRECTOR_ROLE, CURATOR_ROLE
from database.models import User

router = Router()

# --- FSM States для Onboarding ---
class Onboarding(StatesGroup):
    """Состояния для процесса регистрации пользователя."""
    waiting_for_name = State()
    waiting_for_role = State()

# --- FSM States для Подтверждения Директором ---
class DirectorConfirm(StatesGroup):
    """Состояния для подтверждения нового куратора директором."""
    waiting_for_curator_id = State()
    waiting_for_tab_name = State()

# --- /start ---
@router.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext):
    # 1. Проверка наличия пользователя в БД
    db: Session = await asyncio.to_thread(get_db)
    user = await asyncio.to_thread(get_user_by_telegram_id, db, message.from_user.id)
    
    if user:
        if user.is_confirmed:
            greeting = "С возвращением!"
            # По умолчанию удаляем старую клавиатуру, если не назначим новую
            reply_markup = types.ReplyKeyboardRemove() 
            
            if user.role == DIRECTOR_ROLE:
                greeting += " Вы - Директор. Ваш функционал доступен. 👇"
                
                # --- Создание клавиатуры Директора ---
                director_keyboard = types.ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            types.KeyboardButton(text="📊 Отчетность"),
                            types.KeyboardButton(text="👤 Подтверждение пользователей")
                        ],
                        # Здесь можно добавить другие команды, если появятся
                    ],
                    resize_keyboard=True # Делает кнопки компактными
                )
                reply_markup = director_keyboard
                
            else:
                greeting += f" Вы - Куратор ({user.name}). Начните работу с /tasks."
                
                # --- Создание клавиатуры Куратора (опционально, но логично) ---
                curator_keyboard = types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(text="📋 Мои задачи")],
                    ],
                    resize_keyboard=True
                )
                reply_markup = curator_keyboard
        else:
            greeting = "Привет! Вы уже зарегистрированы, но <b>ожидаете подтверждения</b> Директором."
            reply_markup = types.ReplyKeyboardRemove() # Удаляем любые клавиатуры

        # Отправляем сообщение вместе с соответствующей клавиатурой
        await message.answer(greeting, reply_markup=reply_markup)
        await state.clear()
        return

    # 2. Если пользователя нет - начинаем Onboarding
    await message.answer(
        "Здравствуйте! Я - ваш помощник по задачам.\n"
        "Как вас зовут? (Введите полностью: Фамилия и Имя)"
    )
    await state.set_state(Onboarding.waiting_for_name)

# --- Onboarding: Получение Имени ---
@router.message(Onboarding.waiting_for_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Куратор")],
            [types.KeyboardButton(text="Директор")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("Какова ваша роль в системе?", reply_markup=keyboard)
    await state.set_state(Onboarding.waiting_for_role)

# --- Onboarding: Получение Роли и Регистрация ---
@router.message(Onboarding.waiting_for_role, F.text.in_({"Куратор", "Директор"}))
async def process_role(message: types.Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    role_text = message.text
    
    role = DIRECTOR_ROLE if role_text == "Директор" else CURATOR_ROLE
    
    db: Session = await asyncio.to_thread(get_db)
    new_user = await asyncio.to_thread(
        create_user, 
        db, 
        message.from_user.id, 
        user_data['name'], 
        role
    )

    await message.answer(
        f"Спасибо, {user_data['name']}! Вы зарегистрированы как <b>{role_text}</b>.\n\n"
        "Ваша заявка отправлена Директору на подтверждение. Ожидайте, пожалуйста."
    )
    await state.clear()
    
    # Уведомление Директора
    director = await asyncio.to_thread(get_director, db)
    if director and director.is_confirmed:
        await bot.send_message(
            chat_id=director.telegram_id,
            text=f"🚨 **Новая заявка на регистрацию!**\n\n"
                 f"Пользователь: {new_user.name} ({role_text})\n"
                 f"Используйте команду /confirm для подтверждения."
        )

# --- Логика Подтверждения (Director) ---

@router.message(Command("confirm") | F.text == "👤 Подтверждение пользователей") # <-- ДОБАВЛЕНО
async def command_confirm(message: types.Message, state: FSMContext):
    # Добавим Мидлвар позже для проверки роли, пока проверяем вручную
    db: Session = await asyncio.to_thread(get_db)
    user = await asyncio.to_thread(get_user_by_telegram_id, db, message.from_user.id)
    
    if not user or user.role != DIRECTOR_ROLE or not user.is_confirmed:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    
    unconfirmed_users = await asyncio.to_thread(get_unconfirmed_users, db)
    
    if not unconfirmed_users:
        await message.answer("Нет новых пользователей, ожидающих подтверждения.")
        await state.clear()
        return

    # Формируем список ожидающих
    text = "Выберите пользователя для подтверждения:\n\n"
    keyboard_buttons = []
    
    for u in unconfirmed_users:
        text += f"ID: `{u.id}` | {u.name} ({'Куратор' if u.role == CURATOR_ROLE else 'Директор'})\n"
        keyboard_buttons.append([types.KeyboardButton(text=str(u.id))])
        
    reply_markup = types.ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    await state.set_state(DirectorConfirm.waiting_for_curator_id)

@router.message(DirectorConfirm.waiting_for_curator_id, F.text.isdigit())
async def process_confirm_curator_id(message: types.Message, state: FSMContext):
    curator_id = int(message.text)
    await state.update_data(curator_id=curator_id)
    
    db: Session = await asyncio.to_thread(get_db)
    user_to_confirm = await asyncio.to_thread(lambda: db.query(User).filter(User.id == curator_id).first())
    
    if not user_to_confirm:
        await message.answer("Пользователь с таким ID не найден. Попробуйте снова или нажмите /cancel.")
        return

    if user_to_confirm.role == DIRECTOR_ROLE:
        # Если подтверждаем Директора, ему не нужна вкладка
        confirmed_user = await asyncio.to_thread(confirm_user, db, curator_id)
        await message.answer(
            f"Директор {confirmed_user.name} подтвержден! \n"
            f"Уведомляю пользователя...",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        await message.bot.send_message(
            chat_id=confirmed_user.telegram_id,
            text="✅ **Ваш аккаунт Директора подтвержден!** Можете начинать работу."
        )
    else:
        # Если подтверждаем Куратора, нужно имя вкладки
        await message.answer(
            f"Подтверждаем Куратора: **{user_to_confirm.name}**.\n\n"
            "Введите точное название его вкладки (таба) в Google Sheets:",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN
        )
        await state.set_state(DirectorConfirm.waiting_for_tab_name)

@router.message(DirectorConfirm.waiting_for_tab_name, F.text)
async def process_confirm_tab_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    curator_id = data['curator_id']
    tab_name = message.text.strip()
    
    db: Session = await asyncio.to_thread(get_db)
    confirmed_user = await asyncio.to_thread(confirm_user, db, curator_id, tab_name)

    if confirmed_user:
        await message.answer(
            f"✅ Куратор **{confirmed_user.name}** подтвержден и привязан к вкладке **'{tab_name}'**.\n\n"
            "Уведомляю пользователя...",
            parse_mode=ParseMode.MARKDOWN
        )
        await message.bot.send_message(
            chat_id=confirmed_user.telegram_id,
            text=f"✅ **Ваш аккаунт Куратора подтвержден!** Вы привязаны к вкладке **'{tab_name}'**."
        )
    else:
        await message.answer("Произошла ошибка при подтверждении. Проверьте ID и попробуйте снова.")
        
    await state.clear()