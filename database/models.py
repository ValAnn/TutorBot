from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

# Базовый класс для всех моделей
Base = declarative_base()

class User(Base):
    """Модель для пользователей (кураторов и директора)."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    
    # Telegram ID для отправки сообщений
    telegram_id = Column(Integer, unique=True, nullable=False, index=True) 
    
    # Имя и роль
    name = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'curator' или 'director'
    
    # Название вкладки в Google Sheets для куратора
    sheet_tab_name = Column(String, nullable=True) 
    
    # Для Онбординга: True, если директор подтвердил личность
    is_confirmed = Column(Boolean, default=False)
    
    # Связь с задачами (обратная связь)
    tasks = relationship("Task", back_populates="curator")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', role='{self.role}')>"


class Task(Base):
    """Модель для задач кураторов."""
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    
    # Внешний ключ, связывающий задачу с куратором
    curator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Индекс строки в Google Sheet для обратной записи
    sheet_row_index = Column(Integer, nullable=False)
    
    title = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Статус: 'pending' (не выполнено), 'done' (выполнено), 'in_progress'
    status = Column(String, default='pending', nullable=False) 
    
    # Связь с пользователем
    curator = relationship("User", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title[:20]}', status='{self.status}')>"


class ProgressLog(Base):
    """Лог действий кураторов по задачам."""
    __tablename__ = 'progress_log'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String, nullable=False) # 'marked_done', 'status_changed' и т.д.
    comment = Column(String, nullable=True) # Дополнительный комментарий
    
    # Связь с задачей (если нужно)
    task = relationship("Task")

    def __repr__(self):
        return f"<ProgressLog(id={self.id}, action='{self.action}', time='{self.timestamp}')>"

# --- Код для инициализации БД ---

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./bot_database.db" # Путь к файлу SQLite

engine = create_engine(DATABASE_URL)
# Создание таблиц, если они еще не существуют
Base.metadata.create_all(bind=engine)

# Сессия для работы с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Функция для получения сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()