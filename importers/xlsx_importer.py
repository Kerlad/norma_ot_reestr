"""
Модуль загрузки XLSX файлов со стримингом, прогрессом и отменой.
Правила проверки записи — в utils.record_rules (единый источник).
"""
import os
import logging
from datetime import datetime

from utils.constants import VALID_PROGRAMS_SET as VALID_PROGRAMS
from utils.constants import MAX_XLSX_FILE_SIZE_MB, MAX_XLSX_ROWS
from utils.exceptions import FileTooLargeError, ImportLimitExceededError, ImportCancelledError
from utils.record_rules import (
    format_snils, normalize_date, normalize_record, normalize_result,
    split_programs, validate_date as _rr_validate_date, validate_name as _rr_validate_name,
    validate_record, validate_snils as _rr_validate_snils,
)

logger = logging.getLogger(__name__)

COLUMNS = [
    "Фамилия", "Имя", "Отчество", "СНИЛС", "Должность",
    "ИНН Заказчика", "Наименование ЮЛ Заказчика", "ИНН УЦ",
    "Наименование УЦ", "Результат", "№ программы", "Дата", "№ протокола"
]

FIELD_KEYS = [
    'last_name', 'first_name', 'middle_name', 'snils', 'position',
    'employer_inn', 'employer_title', 'tc_inn', 'tc_title',
    'result', 'program', 'date', 'protocol'
]

# Record key -> Russian column name (for error reports)
_KEY_TO_COLUMN = dict(zip(FIELD_KEYS, COLUMNS))


def _norm_header(text) -> str:
    """Lower-case, drop '№', '.', spaces and non-breaking spaces."""
    s = "" if text is None else str(text).lower()
    return "".join(c for c in s if c != "№" and c != "." and not c.isspace())


HEADER_SYNONYMS = {
    "Фамилия": ["фамилия"],
    "Имя": ["имя"],
    "Отчество": ["отчество"],
    "СНИЛС": ["снилс"],
    "Должность": ["должность", "профессия"],
    "ИНН Заказчика": ["иннзаказчика", "иннработодателя"],
    "Наименование ЮЛ Заказчика": ["наименованиеюлзаказчика", "наименованиезаказчика", "заказчик"],
    "ИНН УЦ": ["иннуц"],
    "Наименование УЦ": ["наименованиеуц"],
    "Результат": ["результат"],
    "№ программы": ["программы", "программа", "номерпрограммы"],
    "Дата": ["дата", "датапроверкизнаний"],
    "№ протокола": ["протокола", "протокол", "номерпротокола"],
}
REQUIRED_COLUMNS = ["Фамилия", "Имя", "СНИЛС", "Должность", "Результат",
                    "№ программы", "Дата", "№ протокола"]

_SYNONYM_LOOKUP = {syn: canon for canon, syns in HEADER_SYNONYMS.items() for syn in syns}

# Filled at the end of every _load_xlsx_openpyxl call (read by the UI)
LAST_IMPORT_STATS = {"auto_fixed": 0}


def _canonical_header(text) -> str:
    raw = "" if text is None else str(text).strip()
    return _SYNONYM_LOOKUP.get(_norm_header(raw), raw)


class FieldValidator:
    """Thin wrappers over utils.record_rules (kept for backward compatibility)."""

    @staticmethod
    def _err(row_num, field, message):
        return {'row': row_num, 'type': 'Ошибка', 'field': field, 'message': message}

    @staticmethod
    def validate_snils(value, row_num: int):
        msg = _rr_validate_snils(value)
        if msg:
            return FieldValidator._err(row_num, 'СНИЛС', msg)
        return None

    @staticmethod
    def validate_program(value, row_num: int):
        programs = split_programs(value)
        invalid = [p for p in programs if p not in VALID_PROGRAMS]
        if invalid:
            return FieldValidator._err(
                row_num, '№ программы', f"Некорректный номер программы: {', '.join(invalid)}")
        return None

    @staticmethod
    def validate_result(value, row_num: int):
        if normalize_result(value) is None:
            return FieldValidator._err(
                row_num, 'Результат',
                "Результат: «Удовлетворительно» или «Неудовлетворительно»")
        return None

    @staticmethod
    def validate_name(field_name: str, value, row_num: int):
        msg = _rr_validate_name(value, False)
        if msg:
            return FieldValidator._err(row_num, field_name, msg)
        return None

    @staticmethod
    def validate_date(value, row_num: int):
        """Returns DD.MM.YYYY string or an error dict."""
        nd = normalize_date(value)
        if nd is None:
            return FieldValidator._err(row_num, 'Дата', "Введите дату как ДД.ММ.ГГГГ")
        msg = _rr_validate_date(nd)
        if msg:
            return FieldValidator._err(row_num, 'Дата', msg)
        return nd

    @staticmethod
    def validate_required(col: str, value, row_num: int):
        if value is None or str(value).strip() == '':
            return FieldValidator._err(row_num, col, f"Пустое обязательное поле '{col}'")
        return None


def _cell_text(v) -> str:
    """Cell value as stripped text; whole floats lose the '.0' tail (numeric INN/SNILS cells)."""
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _fio(row_dict) -> str:
    last = _cell_text(row_dict.get('Фамилия'))
    first = _cell_text(row_dict.get('Имя'))
    middle = _cell_text(row_dict.get('Отчество'))
    parts = [last]
    if first:
        parts.append(first[0].upper() + '.')
    if middle:
        parts.append(middle[0].upper() + '.')
    return ' '.join(p for p in parts if p)


def validate_row(row_dict, row_num):
    """
    Валидация строки из Excel через utils.record_rules.
    Возвращает (True, records, fixed) или (False, errors, fixed).
    errors — список словарей {'row','type','field','message','fio'} (без значений полей).
    fixed — True, если дата/результат/программы были нормализованы автоматически.
    """
    fio = _fio(row_dict)
    raw_date = row_dict.get('Дата')
    raw_result = row_dict.get('Результат')
    raw_programs = row_dict.get('№ программы')

    programs = split_programs(raw_programs)

    fixed = False
    if isinstance(raw_date, str):
        nd = normalize_date(raw_date)
        if nd is not None and nd != raw_date.strip():
            fixed = True
    if isinstance(raw_result, str):
        nr = normalize_result(raw_result)
        if nr is not None and nr != raw_result.strip():
            fixed = True
    if programs:
        tokens = [t.strip() for t in str(raw_programs).split(',') if t.strip()]
        if tokens != programs:
            fixed = True

    errors = []
    seen = set()

    def add_error(field_col, message):
        key = (field_col, message)
        if key not in seen:
            seen.add(key)
            errors.append({'row': row_num, 'type': 'Ошибка', 'field': field_col,
                           'message': message, 'fio': fio})

    if not programs:
        add_error('№ программы', 'Укажите номер программы')

    records = []
    for prog in (programs or ['']):
        rec = {
            'last_name': _cell_text(row_dict.get('Фамилия')),
            'first_name': _cell_text(row_dict.get('Имя')),
            'middle_name': _cell_text(row_dict.get('Отчество')),
            'snils': _cell_text(row_dict.get('СНИЛС')),
            'position': _cell_text(row_dict.get('Должность')),
            'employer_inn': _cell_text(row_dict.get('ИНН Заказчика')),
            'employer_title': _cell_text(row_dict.get('Наименование ЮЛ Заказчика')),
            'tc_inn': _cell_text(row_dict.get('ИНН УЦ')),
            'tc_title': _cell_text(row_dict.get('Наименование УЦ')),
            'result': raw_result if raw_result is not None else '',
            'program': prog,
            'date': raw_date if raw_date is not None else '',
            'protocol': _cell_text(row_dict.get('№ протокола')),
        }
        rec = normalize_record(rec)
        for err in validate_record(rec):
            if err.field == 'program' and not programs:
                continue
            add_error(_KEY_TO_COLUMN.get(err.field, err.field), err.message)
        rec['source_row'] = row_num
        records.append(rec)

    if errors:
        return False, errors, fixed
    return True, records, fixed


def load_xlsx(file_path, password=None, progress_callback=None, cancel_check=None):
    """
    Загрузка XLSX файла со стримингом, прогрессом и поддержкой отмены.

    Аргументы:
        file_path — путь к файлу
        password — пароль для защищённого файла (необязательно)
        progress_callback(current: int, total: int) — вызывается каждые 100 строк
            total=0 если неизвестно
        cancel_check() -> bool — вызывается каждую строку; True = отмена

    Возвращает (records, error_details, error_rows_set, error_msg).
    При отмене records=None, error_msg=["Импорт отменён"].
    """
    if not file_path.lower().endswith('.xlsx'):
        return None, [], set(), ["Неподдерживаемый формат. Используйте .xlsx"]

    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info("Loading XLSX: %s (%.1f MB)", os.path.basename(file_path), size_mb)
        if size_mb > MAX_XLSX_FILE_SIZE_MB:
            msg = f"Файл превышает лимит {MAX_XLSX_FILE_SIZE_MB} МБ ({size_mb:.1f} МБ)"
            logger.warning("File too large: %s", msg)
            return None, [], set(), [msg]
    except OSError as e:
        logger.error("File access error: %s", type(e).__name__)
        return None, [], set(), ["Не удалось открыть файл. Проверьте, что он существует и не открыт в другой программе"]

    try:
        from openpyxl import load_workbook
        return _load_xlsx_openpyxl(file_path, password, progress_callback, cancel_check)
    except ImportError as e:
        logger.error("Missing openpyxl: %s", type(e).__name__)
        return None, [], set(), ["Не установлен модуль openpyxl. Переустановите программу"]
    except FileTooLargeError as e:
        logger.warning(str(e))
        return None, [], set(), [str(e)]
    except ImportLimitExceededError as e:
        logger.warning(str(e))
        return None, [], set(), [str(e)]
    except ImportCancelledError:
        logger.info("XLSX import cancelled by user")
        return None, [], set(), ["Импорт отменён пользователем"]


def _load_xlsx_openpyxl(file_path, password=None, progress_callback=None, cancel_check=None):
    """Загрузка .xlsx через openpyxl в read_only режиме со стримингом."""
    from openpyxl import load_workbook

    LAST_IMPORT_STATS["auto_fixed"] = 0
    auto_fixed = 0

    wb = load_workbook(file_path, data_only=True, read_only=True)
    try:
        ws = wb.active
        logger.debug("Active sheet: %s", ws.title)

        records = []
        error_details = []
        error_rows_set = set()

        headers = None
        row_count = 0
        progress_interval = 100

        for row in ws.iter_rows(values_only=True):
            if cancel_check and cancel_check():
                logger.info("Cancel requested at row %d", row_count)
                raise ImportCancelledError(f"Cancelled at row {row_count}")

            row_count += 1

            if row_count == 1:
                headers = [_canonical_header(c) for c in row]
                missing_cols = [col for col in REQUIRED_COLUMNS if col not in headers]
                if missing_cols:
                    error_msg = (
                        f"В файле нет столбцов: {', '.join(missing_cols)}. "
                        f"Ожидаются: {', '.join(COLUMNS)}. "
                        "Скачайте шаблон на вкладке «Внесение данных»."
                    )
                    logger.warning("Missing columns: %s", missing_cols)
                    return None, [{"row": 1, "type": "Ошибка", "field": "Заголовки", "message": error_msg}], {1}, error_msg
                continue

            if row_count > MAX_XLSX_ROWS:
                logger.warning("Row limit exceeded: %d > %d", row_count, MAX_XLSX_ROWS)
                raise ImportLimitExceededError(
                    f"Превышено максимальное количество строк: {MAX_XLSX_ROWS}"
                )

            row_dict = {}
            all_empty = True
            for c_idx, col_name in enumerate(headers):
                val = row[c_idx] if c_idx < len(row) else None
                if col_name not in row_dict:
                    row_dict[col_name] = val if val is not None else ''
                if val is not None and str(val).strip() != '':
                    all_empty = False

            if all_empty:
                continue

            # row_count is the Excel sheet row number (header = 1)
            is_valid, result, fixed = validate_row(row_dict, row_count)
            if is_valid:
                records.extend(result)
                if fixed:
                    auto_fixed += 1
            else:
                error_details.extend(result)
                error_rows_set.add(row_count)

            if progress_callback and row_count % progress_interval == 0:
                progress_callback(row_count, 0)

    finally:
        wb.close()
        logger.debug("Workbook closed")

    if progress_callback:
        progress_callback(row_count, 0)

    LAST_IMPORT_STATS["auto_fixed"] = auto_fixed
    logger.info("XLSX import completed: %d rows, %d records, %d errors, %d auto-fixed",
                row_count - 1, len(records), len(error_details), auto_fixed)

    return records, error_details, error_rows_set, ""
