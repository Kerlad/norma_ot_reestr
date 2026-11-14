"""A5: XLSX import — header synonyms, Excel row numbers, record_rules validation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from openpyxl import Workbook

from importers import xlsx_importer
from importers.xlsx_importer import COLUMNS, load_xlsx

SNILS_A = "112-233-445 95"
SNILS_B = "123-456-789 64"
INN_OK = "7707083893"


def _row(**over):
    base = {
        "Фамилия": "Тестов", "Имя": "Тест", "Отчество": "Тестович",
        "СНИЛС": SNILS_A, "Должность": "Инженер",
        "ИНН Заказчика": INN_OK, "Наименование ЮЛ Заказчика": "ООО Тест",
        "ИНН УЦ": INN_OK, "Наименование УЦ": "УЦ Тест",
        "Результат": "Удовлетворительно", "№ программы": "1",
        "Дата": "01.02.2025", "№ протокола": "П-1",
    }
    base.update(over)
    return base


def _make(tmp_path, rows, headers=None):
    headers = headers or COLUMNS
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    path = str(tmp_path / "in.xlsx")
    wb.save(path)
    wb.close()
    return path


def test_missing_program_column(tmp_path):
    headers = [h for h in COLUMNS if h != "№ программы"]
    path = _make(tmp_path, [_row()], headers)
    records, details, rows, msg = load_xlsx(path)
    assert records is None
    assert "нет столбцов" in msg
    assert "№ программы" in msg


def test_header_synonyms_and_case(tmp_path):
    headers = ["Фамилия", "Имя", "Отчество", "снилс", "Должность",
               "ИНН Заказчика", "Наименование ЮЛ Заказчика", "ИНН УЦ",
               "Наименование УЦ", "Результат", "Программа", "Дата", "№ протокола"]
    row = {h: v for h, v in zip(headers, _row().values())}
    path = _make(tmp_path, [row], headers)
    records, details, rows, msg = load_xlsx(path)
    assert msg == ""
    assert records is not None and len(records) == 1
    assert records[0]["snils"] == SNILS_A
    assert records[0]["program"] == "1"


def test_error_row_is_excel_row_with_fio(tmp_path):
    rows = [_row(СНИЛС=SNILS_A), _row(СНИЛС=SNILS_B), _row(СНИЛС=SNILS_A),
            _row(СНИЛС=SNILS_B, **{"№ программы": "99"})]
    path = _make(tmp_path, rows)
    records, details, err_rows, msg = load_xlsx(path)
    assert err_rows == {5}
    assert details and all(e["row"] == 5 for e in details)
    assert all(e["fio"] for e in details)
    assert all(SNILS_B not in e["message"] for e in details)
    assert len(records) == 3


def test_bad_employer_inn(tmp_path):
    path = _make(tmp_path, [_row(**{"ИНН Заказчика": "12345"})])
    records, details, err_rows, msg = load_xlsx(path)
    assert any(e["field"] == "ИНН Заказчика" for e in details)
    assert "12345" not in " ".join(e["message"] for e in details)


def test_auto_fix_counter(tmp_path):
    path = _make(tmp_path, [_row(**{"Результат": "удовлетворительно",
                                    "№ программы": "1; 2",
                                    "Дата": "4.11.2025"})])
    records, details, err_rows, msg = load_xlsx(path)
    assert msg == "" and not details
    assert len(records) == 2
    assert {r["program"] for r in records} == {"1", "2"}
    assert records[0]["date"] == "04.11.2025"
    assert records[0]["result"] == "Удовлетворительно"
    assert xlsx_importer.LAST_IMPORT_STATS["auto_fixed"] == 1


def test_missing_last_name(tmp_path):
    path = _make(tmp_path, [_row(Фамилия="")])
    records, details, err_rows, msg = load_xlsx(path)
    assert err_rows == {2}
    assert any(e["field"] == "Фамилия" for e in details)
    assert not records
