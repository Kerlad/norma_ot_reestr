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


# --- numeric cells: Excel drops leading zeros and stores whole numbers as floats ---

def _snils_with_check(base9: str) -> str:
    s = sum(int(d) * (9 - k) for k, d in enumerate(base9)) % 101
    return base9 + "%02d" % (0 if s in (100, 101) else s)


def _inn10(base9: str) -> str:
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return base9 + str(sum(a * int(b) for a, b in zip(w, base9)) % 11 % 10)


SNILS_ZERO = _snils_with_check("012345678")   # starts with 0
INN_ZERO = _inn10("012345678")                # organization of region 01


def test_id_cell_text_restores_leading_zeros():
    from utils.record_rules import id_cell_text
    assert id_cell_text(int(SNILS_ZERO), "snils") == SNILS_ZERO
    assert id_cell_text(float(int(SNILS_ZERO)), "snils") == SNILS_ZERO
    assert id_cell_text(int(INN_ZERO), "inn") == INN_ZERO
    assert id_cell_text(float(int("012345678901")), "inn") == "012345678901"
    # text cells are never padded: a typo stays visible to the validator
    assert id_cell_text("123456789", "inn") == "123456789"
    assert id_cell_text(" 112-233-445 95 ", "snils") == "112-233-445 95"
    assert id_cell_text(None, "snils") == ""


def test_numeric_cells_with_leading_zeros_import(tmp_path):
    path = _make(tmp_path, [_row(**{"СНИЛС": int(SNILS_ZERO), "ИНН Заказчика": int(INN_ZERO),
                                    "ИНН УЦ": float(INN_OK), "№ программы": 1.0, "№ протокола": 101})])
    records, errors, _, msg = load_xlsx(path)
    assert not errors and not msg
    rec = records[0]
    assert rec["snils"] == "%s-%s-%s %s" % (SNILS_ZERO[:3], SNILS_ZERO[3:6], SNILS_ZERO[6:9], SNILS_ZERO[9:])
    assert rec["employer_inn"] == INN_ZERO
    assert rec["tc_inn"] == INN_OK
    assert rec["program"] == "1" and rec["protocol"] == "101"


def test_registry_rows_numeric_snils():
    from journal.registry_sync import api_records_from_rows
    headers = ["Номер записи в реестре", "СНИЛС", "Номер программы", "Номер протокола", "Дата"]
    recs = api_records_from_rows(headers, [(12345.0, float(int(SNILS_ZERO)), 7.0, 15, "05.03.2026")])
    assert recs[0]["Snils"] == SNILS_ZERO
    assert all(not str(v).endswith(".0") for v in recs[0].values())
