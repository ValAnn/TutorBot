# Файл: database/crud.py
from sqlalchemy.orm import Session
from .models import User, SessionLocal
from config import DIRECTOR_ROLE, CURATOR_ROLE

# 📌 Вспомогательная функция для получения сессии
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# --- CRUD для User ---

def get_user_by_telegram_id(db: Session, telegram_id: int):
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_user(db: Session, telegram_id: int, name: str, role: str, sheet_name: str | None = None):
    db_user = User(
        telegram_id=telegram_id, 
        name=name, 
        role=role, 
        is_confirmed=False,
        sheet_name=sheet_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_confirmation(db: Session, telegram_id: int, is_confirmed: bool = True):
    user = get_user_by_telegram_id(db, telegram_id)
    if user:
        user.is_confirmed = is_confirmed
        db.commit()
        db.refresh(user)
    return user

def get_unconfirmed_users(db: Session):
    return db.query(User).filter(User.is_confirmed == False).all()

def get_all_curators(db: Session):
    return db.query(User).filter(User.role == CURATOR_ROLE, User.is_confirmed == True).all()

def get_director(db: Session):
    return db.query(User).filter(User.role == DIRECTOR_ROLE, User.is_confirmed == True).first()

# 📌 УДАЛЕНО: get_curator_tasks_for_period, update_task_status и все, что связано с Task/ProgressLog