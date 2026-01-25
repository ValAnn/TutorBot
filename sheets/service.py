# Файл: sheets/service.py
import gspread
import pandas as pd
from datetime import date, datetime
from config import TASK_STATUS_DONE

class TaskData:
    """Класс для моделирования данных задачи, полученных из Google Sheets."""
    def __init__(self, task_id, title, curator_sheet, start_date_str, end_date_str, status):
        self.id = int(task_id)
        self.title = title
        self.curator_sheet = curator_sheet 
        self.start_date = self._parse_date(start_date_str)
        self.end_date = self._parse_date(end_date_str)
        self.status = status.lower()

    def _parse_date(self, date_str):
        if not date_str:
            return date.today()
        # Попытка парсинга разных форматов дат
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(str(date_str).strip(), fmt).date()
            except ValueError:
                continue
        return date.today() 

class CuratorSheetInfo:
    """Модель для Куратора, где вся информация - это имя листа."""
    def __init__(self, sheet_name: str):
        self.sheet_name = sheet_name
        self.name = sheet_name # Имя куратора = название листа

class GoogleSheetsService:
    def __init__(self, spreadsheet_name, key_file):
        self.key_file = key_file
        self.gc = gspread.service_account(filename=key_file)
        self.spreadsheet = self.gc.open(spreadsheet_name)

    def get_curator_tasks_for_period(self, curator_sheet_name: str, start_date: date, end_date: date) -> list[TaskData]:
        """Получает задачи из вкладки Куратора за период и фильтрует их."""
        try:
            worksheet = self.spreadsheet.worksheet(curator_sheet_name)
            df = pd.DataFrame(worksheet.get_all_records())
            
            # Предполагаем, что колонки: ID, TITLE, START_DATE, END_DATE, STATUS
            df.columns = [col.upper().replace(' ', '_') for col in df.columns]

            tasks = []
            for _, row in df.iterrows():
                task_date = TaskData(
                    task_id=row['№'], # Если '№' не преобразуется, оставьте как есть, или используйте 'ID'
                    title=row['МЕРОПРИЯТИЕ'], # ИСПРАВЛЕНО
                    curator_sheet=curator_sheet_name, 
                    start_date_str=row['ДАТА_НАЧАЛА'], # ИСПРАВЛЕНО (если было с пробелом)
                    end_date_str=row['ДАТА_ОКОНЧАНИЯ'], # ИСПРАВЛЕНО
                    status=row['СДЕЛАНО'] # ИСПРАВЛЕНО
                )
                if start_date <= task_date.end_date <= end_date:
                    tasks.append(task_date)
            return tasks
        except gspread.exceptions.WorksheetNotFound:
            return []
        except Exception as e:
            print(f"Ошибка чтения задач Куратора ({curator_sheet_name}): {e}")
            return []

    def get_all_curator_sheets(self) -> list[CuratorSheetInfo]:
        """Получает названия всех листов, исключая служебные (например, лист Директора)."""
        worksheets = self.spreadsheet.worksheets()
        curator_sheets = []
        
        # Определяем листы, которые не являются Кураторами (служебные)
        # ВАЖНО: замените "DIRECTOR_STAT" на реальное имя листа директора/статистики
        EXCLUDED_SHEETS = ["Лист1", "DIRECTOR_STAT", "Template"] 
        
        for ws in worksheets:
            if ws.title not in EXCLUDED_SHEETS:
                curator_sheets.append(CuratorSheetInfo(sheet_name=ws.title))
        return curator_sheets
    
    def update_status_in_sheet(self, task_id: int, curator_sheet_name: str, new_status: str) -> bool:
        """Обновляет статус задачи в таблице Куратора по ID."""
        try:
            worksheet = self.spreadsheet.worksheet(curator_sheet_name)
            
            # 1. Находим строку по ID задачи (предполагаем, что ID в первом столбце)
            cell = worksheet.find(str(task_id), in_column=1) 
            
            # 2. Обновляем статус, предполагая, что столбец STATUS - 5-й
            status_col = 5 
            worksheet.update_cell(cell.row, status_col, new_status)
            return True
        except gspread.exceptions.CellNotFound:
            print(f"Задача ID {task_id} не найдена на листе {curator_sheet_name}.")
            return False
        except Exception as e:
            print(f"Ошибка при обновлении статуса в Sheet: {e}")
            return False