from sqlalchemy.orm import Session
from datetime import date
from .models import User, Task, ProgressLog, SessionLocal
from config import DIRECTOR_ROLE, CURATOR_ROLE, DEFAULT_STATUS

# --- Вспомогательная функция для получения сессии ---
def get_db():
    """Получает и закрывает сессию БД."""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# --- Функции для Пользователей (User) ---

def create_user(db: Session, telegram_id: int, name: str, role: str) -> User:
    """Создает нового пользователя в процессе Onboarding."""
    db_user = User(
        telegram_id=telegram_id,
        name=name,
        role=role,
        is_confirmed=False # Ждет подтверждения от директора
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_telegram_id(db: Session, telegram_id: int) -> User | None:
    """Находит пользователя по Telegram ID."""
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def get_unconfirmed_users(db: Session) -> list[User]:
    """Получает список пользователей, ожидающих подтверждения (для директора)."""
    return db.query(User).filter(User.is_confirmed == False).all()

def confirm_user(db: Session, user_id: int, sheet_tab_name: str | None = None) -> User | None:
    """Подтверждает пользователя и, если это куратор, привязывает вкладку."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user:
        db_user.is_confirmed = True
        if db_user.role == CURATOR_ROLE and sheet_tab_name:
            db_user.sheet_tab_name = sheet_tab_name
        db.commit()
        db.refresh(db_user)
    return db_user

def get_director(db: Session) -> User | None:
    """Получает объект директора."""
    return db.query(User).filter(User.role == DIRECTOR_ROLE).first()

def get_all_curators(db: Session) -> list[User]:
    """Получает всех подтвержденных кураторов."""
    return db.query(User).filter(User.role == CURATOR_ROLE, User.is_confirmed == True).all()

# --- Функции для Задач (Task) ---

def create_or_update_task(
    db: Session, 
    curator_id: int, 
    sheet_row_index: int, 
    title: str, 
    start_date: date, 
    end_date: date, 
    status: str = DEFAULT_STATUS
) -> Task:
    """
    Создает новую задачу или обновляет существующую на основе индекса строки в Sheet.
    """
    db_task = db.query(Task).filter(
        Task.curator_id == curator_id,
        Task.sheet_row_index == sheet_row_index
    ).first()

    if db_task:
        # Задача существует, обновляем ее
        db_task.title = title
        db_task.start_date = start_date
        db_task.end_date = end_date
        db_task.status = status
    else:
        # Новая задача
        db_task = Task(
            curator_id=curator_id,
            sheet_row_index=sheet_row_index,
            title=title,
            start_date=start_date,
            end_date=end_date,
            status=status
        )
        db.add(db_task)
    
    db.commit()
    db.refresh(db_task)
    return db_task

def get_curator_tasks_for_period(
    db: Session, 
    curator_id: int, 
    start: date, 
    end: date, 
    include_done: bool = True
) -> list[Task]:
    """Получает задачи куратора, сроки которых пересекаются с заданным периодом."""
    query = db.query(Task).filter(
        Task.curator_id == curator_id,
        # Задача начинается до конца периода И заканчивается после начала периода
        Task.start_date <= end,
        Task.end_date >= start
    )
    
    # Твое пожелание: видеть ВСЕ задачи, включая выполненные
    # if not include_done:
    #     query = query.filter(Task.status != 'done')
        
    return query.all()

def update_task_status(db: Session, task_id: int, new_status: str) -> Task | None:
    """Обновляет статус задачи и создает запись в ProgressLog."""
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task:
        db_task.status = new_status
        
        # Запись в лог
        log_entry = ProgressLog(
            task_id=task_id,
            action=f"status_changed_to_{new_status}",
            comment=f"Статус обновлен куратором через бота"
        )
        db.add(log_entry)
        
        db.commit()
        db.refresh(db_task)
    return db_task