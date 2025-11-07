# Файл: database/models.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL, DIRECTOR_ROLE, CURATOR_ROLE

# Настройка SQLAlchemy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """Модель для хранения информации о пользователях (Директор/Кураторы)."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'director' или 'curator'
    is_confirmed = Column(Boolean, default=False)
    
    # 📌 Ключевое поле: название вкладки в Google Sheets для этого Куратора/Директора
    sheet_name = Column(String, nullable=True) 

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', role='{self.role}')>"

# 📌 УДАЛЕНО: Классы Task и ProgressLog (мы больше не храним их в БД)