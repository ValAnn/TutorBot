import gspread
import pandas as pd
from datetime import datetime
from config import SERVICE_ACCOUNT_KEY_FILE, SPREADSHEET_NAME, DATABASE_URL
from database.models import User, Task
from database.crud import create_or_update_task, get_all_curators, get_db

class GoogleSheetsService:
    """
    Класс для управления подключением и операциями с Google Sheets.
    Использует библиотеку gspread и Сервисный Аккаунт.
    """
    def __init__(self):
        # 1. Аутентификация с помощью файла ключа
        try:
            self.gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY_FILE)
            self.spreadsheet = self.gc.open(SPREADSHEET_NAME)
        except Exception as e:
            print(f"Ошибка при подключении к Google Sheets или аутентификации: {e}")
            self.gc = None
            self.spreadsheet = None

    def read_tasks_from_sheet(self, curator: User) -> int:
        """
        Читает задачи с вкладки конкретного куратора и синхронизирует их с БД.
        Возвращает количество синхронизированных задач.
        """
        if not self.spreadsheet or not curator.sheet_tab_name:
            return 0

        try:
            worksheet = self.spreadsheet.worksheet(curator.sheet_tab_name)
            # Получаем все данные (в виде списка списков)
            data = worksheet.get_all_values()
            if not data:
                return 0

            # Первая строка - заголовки (Название, Начало, Конец, Статус)
            header = data[0] 
            tasks_data = data[1:] # Данные задач
            
            synced_count = 0
            db = get_db()
            
            # Предполагаем, что колонки идут в порядке: Название (0), Срок Начало (1), Срок Конец (2), Статус (последняя)
            # Индекс строки в Google Sheets начинается с 1. Задачи начинаются со строки 2 (индекс 1)
            for row_index, row in enumerate(tasks_data, start=2): 
                if len(row) < 4 or not row[0]: # Если мало колонок или нет названия
                    continue

                try:
                    title = row[0]
                    # Парсим даты. Нужно быть аккуратным с форматами!
                    start_date = datetime.strptime(row[1], '%d.%m.%Y').date() 
                    end_date = datetime.strptime(row[2], '%d.%m.%Y').date() 
                    # Последний элемент - статус. Если пустой, берем дефолтный.
                    status = row[-1] if row[-1] else DEFAULT_STATUS
                    
                    # Создание/Обновление задачи в БД
                    create_or_update_task(
                        db,
                        curator_id=curator.id,
                        sheet_row_index=row_index,
                        title=title,
                        start_date=start_date,
                        end_date=end_date,
                        status=status
                    )
                    synced_count += 1
                except ValueError as ve:
                    # Ошибка парсинга даты или неверный формат строки - пропускаем
                    print(f"Ошибка парсинга строки {row_index} в таблице {curator.sheet_tab_name}: {ve}")
                    continue

            return synced_count

        except gspread.WorksheetNotFound:
            print(f"Вкладка '{curator.sheet_tab_name}' не найдена!")
            return 0
        except Exception as e:
            print(f"Неожиданная ошибка при чтении Sheet: {e}")
            return 0
        
    def update_status_in_sheet(self, task: Task, new_status: str) -> bool:
        """
        Обновляет статус задачи в Google Sheet по ее индексу строки.
        """
        if not self.spreadsheet:
            return False
        
        db = get_db()
        curator = db.query(User).filter(User.id == task.curator_id).first()
        if not curator or not curator.sheet_tab_name:
            print(f"Не найден куратор или его вкладка для задачи {task.id}")
            return False

        try:
            worksheet = self.spreadsheet.worksheet(curator.sheet_tab_name)
            # Колонка со статусом - 4-я (D), если считать с 1. Но лучше проверить.
            # Если в таблице 4 колонки: A-Название, B-Начало, C-Конец, D-Статус
            # Тогда колонка статуса - 4
            status_col_index = 4 
            
            # Формат: R<строка>C<колонка>
            cell_address = gspread.utils.rowcol_to_a1(task.sheet_row_index, status_col_index)
            
            # Обновление ячейки
            worksheet.update(cell_address, new_status)
            return True
        
        except gspread.WorksheetNotFound:
            print(f"Вкладка '{curator.sheet_tab_name}' не найдена для обновления.")
            return False
        except Exception as e:
            print(f"Ошибка при обновлении статуса задачи {task.id} в Sheet: {e}")
            return False

    def sync_all_tasks(self) -> int:
        """Синхронизирует задачи всех кураторов с БД."""
        db = get_db()
        curators = get_all_curators(db)
        total_synced = 0
        
        for curator in curators:
            if curator.sheet_tab_name:
                total_synced += self.read_tasks_from_sheet(curator)
                
        return total_synced