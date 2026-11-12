"""Tests for utils/record_rules.py (no Qt)."""
from datetime import date, datetime, timedelta

from utils import record_rules as rr
from utils.record_rules import (
    FieldError, format_snils, normalize_date, normalize_record, normalize_result,
    record_warnings, snils_checksum_ok, snils_digits, split_programs,
    validate_date, validate_inn, validate_name, validate_position,
    validate_record, validate_snils,
)


def good_record():
    return {
        "last_name": "Тестов", "first_name": "Тест", "middle_name": "Тестович",
        "snils": "112-233-445 95", "position": "Электромонтёр 4 разряда",
        "program": "1", "date": "04.11.2026", "result": rr.RESULT_PASSED,
        "protocol": "12", "employer_inn": "7707083893", "tc_inn": "",
    }


def test_no_pyside_import():
    src = open(rr.__file__, encoding="utf-8").read()
    assert "PySide6" not in src


def test_snils_valid_and_invalid():
    assert validate_snils("112-233-445 95") is None
    assert validate_snils("123-456-789 64") is None
    assert validate_snils("11223344595") is None
    assert validate_snils("123-456-789 00") == "Неверная контрольная сумма СНИЛС"
    assert validate_snils("") == "Укажите СНИЛС"
    assert validate_snils("123") == "СНИЛС должен содержать 11 цифр"
    assert validate_snils("abc-456-789 64") == "СНИЛС должен содержать 11 цифр"


def test_snils_helpers():
    assert snils_digits("112 233-445\t95") == "11223344595"
    assert snils_checksum_ok("11223344595")
    assert not snils_checksum_ok("1122334459")
    assert format_snils("11223344595") == "112-233-445 95"
    assert format_snils("123") is None


def test_field_validators_reuse():
    import importlib.util
    if importlib.util.find_spec("PySide6") is None:
        return
    from utils import field_validators as fv
    assert fv._snils_checksum_valid is snils_checksum_ok


def test_inn():
    assert validate_inn("7707083893") is None
    assert validate_inn("500100732259") is None
    assert validate_inn("7707083894") == "ИНН: контрольное число не сходится"
    assert validate_inn("500100732250") == "ИНН: контрольное число не сходится"
    assert validate_inn("1234567890") is not None
    assert validate_inn("12345") == "ИНН: 10 цифр для организации, 12 для ИП"
    assert validate_inn("77070abcde") == "ИНН: 10 цифр для организации, 12 для ИП"
    assert validate_inn("") is None
    assert validate_inn("  ") is None
    assert validate_inn("", required=True) == "Укажите ИНН"
    assert validate_inn("7707 083893") is None


def test_normalize_date():
    assert normalize_date(datetime(2026, 11, 4)) == "04.11.2026"
    assert normalize_date(date(2026, 11, 4)) == "04.11.2026"
    assert normalize_date("4.11.2026") == "04.11.2026"
    assert normalize_date("04112026") == "04.11.2026"
    assert normalize_date("2026-11-04") == "04.11.2026"
    assert normalize_date("2026-11-04T00:00:00") == "04.11.2026"
    assert normalize_date("4.11.26") == "04.11.2026"
    assert normalize_date("4/11/2026") == "04.11.2026"
    assert normalize_date("31.02.2026") is None
    assert normalize_date("") is None
    assert normalize_date(None) is None
    assert normalize_date("мусор") is None
    serial = (datetime(2026, 11, 4) - datetime(1899, 12, 30)).days
    assert normalize_date(serial) == "04.11.2026"
    assert normalize_date(float(serial)) == "04.11.2026"
    assert normalize_date(1e18) is None


def test_validate_date():
    assert validate_date("04.11.2020") is None
    assert validate_date("") == "Введите дату как ДД.ММ.ГГГГ"
    assert validate_date("31.02.2026") == "Введите дату как ДД.ММ.ГГГГ"
    future = (date.today() + timedelta(days=2)).strftime("%d.%m.%Y")
    assert validate_date(future) == "Дата не может быть больше текущей"


def test_normalize_result():
    assert normalize_result(" удовлетворительно ") == rr.RESULT_PASSED
    assert normalize_result("НЕУДОВЛЕТВОРИТЕЛЬНО") == rr.RESULT_FAILED
    assert normalize_result("сдал") is None
    assert normalize_result(None) is None


def test_split_programs():
    assert split_programs("1; 2") == ["1", "2"]
    assert split_programs("1,2,") == ["1", "2"]
    assert split_programs("3.0") == ["3"]
    assert split_programs("1 1 2") == ["1", "2"]
    assert split_programs("") == []
    assert split_programs(None) == []


def test_position_and_name():
    assert validate_position("Электромонтёр 4 разряда") is None
    assert validate_position("Машинист (кочегар)") is None
    assert validate_position("Инженер «№1»") is None
    assert validate_position("") == "Укажите должность"
    assert validate_position("а" * 256) == "Не длиннее 255 символов"
    assert validate_position("a\x01b") == "Недопустимые символы"
    assert validate_name("Тестов", True) is None
    assert validate_name("Анна-Мария", True) is None
    assert validate_name("О'Брайен", True) is None
    assert validate_name("", True) == "Заполните поле"
    assert validate_name("", False) is None
    assert validate_name("Иванов1", True) == "Допустимы буквы, пробел, дефис, апостроф"
    assert validate_name("а" * 101, True) == "Не длиннее 100 символов"


def test_normalize_record():
    rec = {"last_name": " Тестов ", "snils": "11223344595", "date": "4.11.2026",
           "result": "удовлетворительно", "program": "1.0", "protocol": " 5 "}
    out = normalize_record(rec)
    assert out is not rec
    assert rec["snils"] == "11223344595"
    assert out["last_name"] == "Тестов"
    assert out["snils"] == "112-233-445 95"
    assert out["date"] == "04.11.2026"
    assert out["result"] == rr.RESULT_PASSED
    assert out["program"] == "1"
    assert out["protocol"] == "5"
    bad = normalize_record({"snils": "12", "date": "xx", "result": "?"})
    assert bad == {"snils": "12", "date": "xx", "result": "?"}


def test_validate_record_ok_and_multiple_errors():
    assert validate_record(good_record()) == []
    rec = good_record()
    rec.update(snils="123-456-789 00", program="5", date="")
    errs = validate_record(rec)
    assert len(errs) == 3
    assert {e.field for e in errs} == {"snils", "program", "date"}
    assert all(isinstance(e, FieldError) for e in errs)
    prog_err = [e for e in errs if e.field == "program"][0]
    assert prog_err.message == "Номер программы: 1–4 или 6–29"


def test_validate_record_result_protocol_inn():
    rec = good_record()
    rec.update(result="сдал", protocol="", employer_inn="7707083894", tc_inn="12345")
    assert {e.field for e in validate_record(rec)} == {
        "result", "protocol", "employer_inn", "tc_inn"}


def test_empty_middle_name_is_warning_not_error():
    rec = good_record()
    rec["middle_name"] = ""
    assert validate_record(rec) == []
    w = record_warnings(rec)
    assert len(w) == 1 and w[0].field == "middle_name"
    assert record_warnings(good_record()) == []
