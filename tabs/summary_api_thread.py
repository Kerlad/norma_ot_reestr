"""Background registry query thread of the summary tab (moved from employee_summary_tab)."""
import time
import logging
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from db import DatabaseManager, EmployeesRepo, EmployeeProgramsRepo
from api.mintrud_api import get_by_snils
from utils.logger import filter_sensitive_text

logger = logging.getLogger(__name__)


def _normalize_api_date(date_str: str) -> str:
    if not date_str:
        return ""
    date_str = date_str.strip()
    if '.' in date_str:
        parts = date_str.split()[0]
        if len(parts) == 10 and parts[2] == '.' and parts[5] == '.':
            return parts
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    if '-' in date_str:
        parts = date_str.split()[0]
        try:
            dt = datetime.strptime(parts, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except (ValueError, IndexError):
            pass
    return date_str


def _dmy_gt(a: str, b: str) -> bool:
    """Compare two DD.MM.YYYY dates, returns True if a > b chronologically."""
    try:
        return datetime.strptime(a.strip(), '%d.%m.%Y') > datetime.strptime(b.strip(), '%d.%m.%Y')
    except (ValueError, AttributeError):
        return False



class ApiQueryThread(QThread):
    finished = Signal(int, int)
    error_signal = Signal(str)
    progress = Signal(int, int)

    def __init__(self, employees, api_key, proxy_settings=None):
        super().__init__()
        self.employees = employees
        self.api_key = api_key
        self.proxy_settings = proxy_settings or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.employees)
        updated = 0
        errors = 0
        for idx, emp in enumerate(self.employees):
            if self._cancelled:
                self.finished.emit(updated, errors)
                DatabaseManager.close_thread_connection()
                return
            try:
                snils_clean = emp['snils'].replace('-', '').replace(' ', '')
                result = get_by_snils(self.api_key, snils_clean, proxy_settings=self.proxy_settings)
                if result.get("success"):
                    records = result.get("records", [])
                    self._process_api_records(emp['id'], records)
                    updated += 1
                    now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                    EmployeesRepo.update_sync(emp['id'], now)
                else:
                    errors += 1
                    err_msg = result.get('error', 'Неизвестная ошибка API')
                    logger.warning("API error: %s", filter_sensitive_text(str(err_msg)))
                    self.error_signal.emit(f"{emp.get('last_name','')} {emp.get('first_name','')}: {err_msg}")
            except Exception:
                errors += 1
                logger.exception("Registry API exception")
                self.error_signal.emit(f"{emp.get('last_name','')} {emp.get('first_name','')}: ошибка запроса к реестру")
            self.progress.emit(idx + 1, total)
            if idx < total - 1 and not self._cancelled:
                time.sleep(0.5)
        DatabaseManager.close_thread_connection()
        self.finished.emit(updated, errors)

    def _process_api_records(self, employee_id, records):
        seen_programs = {}
        for rec in records:
            prog_id = rec.get('learnProgramId', '')
            if not prog_id:
                continue
            exam_date = _normalize_api_date(rec.get('Date', ''))
            protocol = rec.get('ProtocolNumber', '')
            base_no = rec.get('baseNo', '')
            is_passed = rec.get('isPassed', '')
            result = 1 if is_passed and is_passed.lower() in ('true', '1', 'да', 'удовлетворительно') else 0
            if prog_id not in seen_programs or (exam_date and _dmy_gt(exam_date, seen_programs[prog_id].get('exam_date', ''))):
                seen_programs[prog_id] = { 'exam_date': exam_date,
                    'protocol': protocol, 'base_no': base_no, 'result': result,}
        for prog_id, data in seen_programs.items():
            try:
                EmployeeProgramsRepo.update_from_api(
                    employee_id, int(prog_id),
                    data['exam_date'], data['protocol'], data['base_no'], data['result']
                )
            except (ValueError, TypeError):
                pass
        if records:
            first_rec = records[0]
            emp = EmployeesRepo.get_by_id(employee_id)
            if emp:
                updates = {}
                if not emp.get('last_name'): updates['last_name'] = first_rec.get('LastName', '')
                if not emp.get('first_name'): updates['first_name'] = first_rec.get('FirstName', '')
                if not emp.get('middle_name'): updates['middle_name'] = first_rec.get('MiddleName', '')
                if not emp.get('position'): updates['position'] = first_rec.get('Position', '')
                if updates:
                    updates['snils'] = emp['snils']
                    EmployeesRepo.upsert(updates)
