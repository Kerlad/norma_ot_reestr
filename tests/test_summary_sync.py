"""UX-14: импорт отчёта реестра (ответ по SetId) в «Сводку по сотрудникам»."""
import pytest

from journal.summary_sync import (
    describe_summary_merge, merge_summary_records, _rows_phrase,
)

HEADERS = ["Номер записи в реестре", "Фамилия", "Имя", "Отчество", "СНИЛС", "Должность",
           "ИНН работодателя", "Наименование работодателя", "Номер программы",
           "Название программы", "Номер протокола", "Дата", "Зачёт"]

# Синтетические СНИЛС с верной контрольной суммой
SNILS_A = "112-233-445 95"
SNILS_B = "008-586-840 81"


def row(snils=SNILS_A, program="1", date="01.02.2026", protocol="П-1", base="R-1",
        passed="true", last="Иванов", first="Иван", middle="Иванович", position="Слесарь"):
    return ["R-%s" % base, last, first, middle, snils, position, "7700000000", "ООО Тест",
            program, "Программа", protocol, date, passed]


def test_matches_existing_employee_by_snils():
    res = merge_summary_records(HEADERS, [row()], {"11223344595"})
    assert not res.new and len(res.existing) == 1
    emp = res.existing[0]
    assert emp.snils == SNILS_A and emp.full_name == "Иванов Иван Иванович"
    assert emp.programs[1].exam_date == "01.02.2026" and emp.programs[1].passed


@pytest.mark.parametrize("raw", ["112-233-445 95", "11223344595", " 112 233 445 95 ", "112233445 95"])
def test_snils_normalization(raw):
    res = merge_summary_records(HEADERS, [row(snils=raw)], {"11223344595"})
    assert len(res.existing) == 1 and res.existing[0].snils == SNILS_A


def test_unknown_snils_goes_to_new():
    res = merge_summary_records(HEADERS, [row()], known_snils=set())
    assert len(res.new) == 1 and res.new[0].is_new and not res.existing


def test_no_directory_means_everyone_is_new():
    res = merge_summary_records(HEADERS, [row(), row(snils=SNILS_B)], None)
    assert len(res.new) == 2


@pytest.mark.parametrize("bad,reason", [
    ("", "не указан СНИЛС"),
    ("123", "11 цифр"),
    ("112-233-445 96", "контрольная сумма"),
])
def test_invalid_snils_is_reported_not_imported(bad, reason):
    res = merge_summary_records(HEADERS, [row(snils=bad)], set())
    assert not res.employees
    assert len(res.errors) == 1 and res.errors[0][0] == 2 and reason in res.errors[0][1]


@pytest.mark.parametrize("bad", ["", "abc", "0", "5", "30", "-2"])
def test_invalid_program_is_reported(bad):
    res = merge_summary_records(HEADERS, [row(program=bad)], set())
    assert not res.employees and len(res.errors) == 1


def test_error_row_numbers_match_the_file():
    rows = [row(), [], row(snils="123"), row(program="999")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    assert [n for n, _ in res.errors] == [4, 5]  # пустая строка не сдвигает нумерацию


def test_duplicates_prefer_passed_record():
    rows = [row(date="01.02.2026", passed="false", protocol="П-плохой"),
            row(date="10.01.2026", passed="true", protocol="П-хороший")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    prog = res.existing[0].programs[1]
    assert prog.passed and prog.protocol == "П-хороший"


def test_duplicates_take_latest_among_passed():
    rows = [row(date="01.02.2026", protocol="П-старый"), row(date="05.09.2026", protocol="П-новый")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    assert res.existing[0].programs[1].protocol == "П-новый"


def test_failed_only_program_is_kept_as_failed():
    rows = [row(passed="false", date="01.02.2026"), row(passed="false", date="05.09.2026")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    prog = res.existing[0].programs[1]
    assert not prog.passed and prog.exam_date == "05.09.2026"


def test_several_programs_and_employees():
    rows = [row(program="1"), row(program="9"), row(snils=SNILS_B, program="3", last="Петров")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    assert sorted(res.existing[0].programs) == [1, 9]
    assert len(res.new) == 1 and res.new[0].last_name == "Петров"
    assert res.program_count == 3


def test_iso_date_is_normalized():
    res = merge_summary_records(HEADERS, [row(date="2026-09-26T00:00:00")], {"11223344595"})
    assert res.existing[0].programs[1].exam_date == "26.09.2026"


def test_repeated_import_produces_the_same_updates():
    rows = [row(), row(program="9")]
    first = merge_summary_records(HEADERS, rows, {"11223344595"})
    second = merge_summary_records(HEADERS, rows, {"11223344595"})
    assert first.program_count == second.program_count == 2
    assert not second.new  # работник уже в справочнике — дублей не будет


def test_description_has_counts_and_no_personal_data():
    rows = [row(), row(snils=SNILS_B, last="Петров", first="Пётр"), row(snils="123")]
    res = merge_summary_records(HEADERS, rows, {"11223344595"})
    text = describe_summary_merge(res, added=1)
    assert "Обновлено работников: 1" in text
    assert "Добавлено новых работников: 1" in text
    assert "строка 4" in text
    assert "Петров" not in text and SNILS_B not in text


def test_description_counts_skipped_new():
    res = merge_summary_records(HEADERS, [row()], set())
    assert "Не добавлено (нет в справочнике): 1" in describe_summary_merge(res, skipped_new=1)


def test_description_truncates_long_error_list():
    rows = [row(snils="123") for _ in range(15)]
    res = merge_summary_records(HEADERS, rows, set())
    text = describe_summary_merge(res)
    assert "Пропущено строк с ошибками: 15" in text and "и ещё 5 строк" in text


@pytest.mark.parametrize("n,word", [(1, "1 строка"), (3, "3 строки"), (5, "5 строк"), (11, "11 строк")])
def test_rows_phrase(n, word):
    assert _rows_phrase(n) == word


def test_empty_file():
    res = merge_summary_records(HEADERS, [], set())
    assert not res.employees and not res.errors and res.program_count == 0
