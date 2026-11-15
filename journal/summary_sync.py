"""
Сопоставление отчёта реестра (ответ по SetId) со справочником сотрудников (UX-14).

Файл-ответ — тот же XLSX, что и для журнала (`api.mintrud_api.export_records_to_xlsx`,
заголовки — `registry_sync.API_XLSX_HEADERS`), но здесь строки группируются по
работникам: ключ — СНИЛС, внутри работника — по номеру программы.

Без Qt и без БД: только чистые функции, чтобы покрыть тестами.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from journal.registry_sync import (
    RESULT_PASSED, _result_from_api, api_records_from_rows, format_snils, snils_key,
)

MAX_PROGRAM_ID = 29


@dataclass
class ProgramUpdate:
    """Данные одной программы работника из отчёта."""
    program_id: int
    exam_date: str = ""
    protocol: str = ""
    base_no: str = ""
    result: int = 1

    @property
    def passed(self) -> bool:
        return self.result == 1


@dataclass
class EmployeeUpdate:
    """Работник из отчёта: ПДн не логировать."""
    key: str                      # только цифры СНИЛС
    snils: str                    # XXX-XXX-XXX XX
    last_name: str = ""
    first_name: str = ""
    middle_name: str = ""
    position: str = ""
    programs: Dict[int, ProgramUpdate] = field(default_factory=dict)
    is_new: bool = False

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.middle_name) if p)


@dataclass
class SummaryMergeResult:
    existing: List[EmployeeUpdate] = field(default_factory=list)
    new: List[EmployeeUpdate] = field(default_factory=list)
    errors: List[Tuple[int, str]] = field(default_factory=list)   # (строка файла, причина)

    @property
    def employees(self) -> List[EmployeeUpdate]:
        return self.existing + self.new

    @property
    def program_count(self) -> int:
        return sum(len(e.programs) for e in self.employees)


def _parse_date(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, "%d.%m.%Y")
    except (ValueError, TypeError):
        return None


def _better(new: ProgramUpdate, old: ProgramUpdate) -> bool:
    """Из дублей по одной программе берём сданную, среди равных — самую позднюю дату."""
    if new.passed != old.passed:
        return new.passed
    nd, od = _parse_date(new.exam_date), _parse_date(old.exam_date)
    if nd and od:
        return nd > od
    return bool(nd) and not od


def _validate_row(rec: dict) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """-> (ключ СНИЛС, номер программы, текст ошибки)."""
    from utils.field_validators import validate_snils

    raw_snils = str(rec.get("Snils", "") or "").strip()
    key = snils_key(raw_snils)
    if not key:
        return None, None, "не указан СНИЛС"
    err = validate_snils(raw_snils)
    if err:
        return None, None, err.lower()

    raw_prog = str(rec.get("learnProgramId", "") or "").strip()
    if not raw_prog:
        return None, None, "не указан номер программы"
    try:
        pid = int(float(raw_prog))
    except (ValueError, TypeError):
        return None, None, "номер программы «%s» не число" % raw_prog[:20]
    if pid < 1 or pid > MAX_PROGRAM_ID or pid == 5:
        return None, None, "программы №%d не существует" % pid
    return key, pid, None


def merge_summary_records(headers: Iterable, rows: Iterable[Tuple],
                          known_snils: Optional[Set[str]] = None) -> SummaryMergeResult:
    """Строки XLSX-отчёта -> обновления по работникам.

    known_snils — ключи СНИЛС (только цифры) уже имеющихся в справочнике работников.
    Строки с ошибками не импортируются и попадают в `errors` (номер строки файла).
    """
    known = {snils_key(s) for s in (known_snils or set())}
    header_list = list(headers)
    row_list = list(rows)
    records = api_records_from_rows(header_list, row_list)
    # api_records_from_rows пропускает пустые строки, поэтому нумеруем по исходным.
    numbered = []
    rec_idx = 0
    for offset, row in enumerate(row_list, start=2):  # строка 1 — заголовки
        if not row or not any(c not in (None, "") for c in row):
            continue
        if rec_idx < len(records):
            numbered.append((offset, records[rec_idx]))
            rec_idx += 1

    return _merge_numbered(numbered, known)


def merge_summary_dicts(records: Iterable[dict],
                        known_snils: Optional[Set[str]] = None) -> SummaryMergeResult:
    """Same merge for records already in API form (keys Snils, LastName, learnProgramId,
    Date, ProtocolNumber, baseNo, isPassed). Error row numbers are 1-based list positions."""
    known = {snils_key(s) for s in (known_snils or set())}
    return _merge_numbered(list(enumerate(records, start=1)), known)


def _merge_numbered(numbered: List[Tuple[int, dict]], known: Set[str]) -> SummaryMergeResult:
    res = SummaryMergeResult()
    by_key: Dict[str, EmployeeUpdate] = {}

    for row_no, rec in numbered:
        key, pid, err = _validate_row(rec)
        if err:
            res.errors.append((row_no, err))
            continue
        emp = by_key.get(key)
        if emp is None:
            emp = EmployeeUpdate(
                key=key,
                snils=format_snils(key),
                last_name=str(rec.get("LastName", "") or "").strip(),
                first_name=str(rec.get("FirstName", "") or "").strip(),
                middle_name=str(rec.get("MiddleName", "") or "").strip(),
                position=str(rec.get("Position", "") or "").strip(),
                is_new=key not in known,
            )
            by_key[key] = emp
            (res.new if emp.is_new else res.existing).append(emp)

        upd = ProgramUpdate(
            program_id=pid,
            exam_date=str(rec.get("Date", "") or "").strip(),
            protocol=str(rec.get("ProtocolNumber", "") or "").strip(),
            base_no=str(rec.get("baseNo", "") or "").strip(),
            result=1 if _result_from_api(rec) == RESULT_PASSED else 0,
        )
        current = emp.programs.get(pid)
        if current is None or _better(upd, current):
            emp.programs[pid] = upd

    return res


def workers_records_to_api(rows: Iterable[dict]) -> Tuple[List[dict], int]:
    """«Просмотр данных» records -> API-form dicts for `merge_summary_dicts`.

    Records that fail `validate_record` are not converted; returns (dicts, invalid_count).
    """
    from utils.record_rules import RESULT_FAILED, normalize_record, validate_record

    out: List[dict] = []
    invalid = 0
    for row in rows:
        rec = normalize_record({
            "last_name": row.get("last_name", ""), "first_name": row.get("first_name", ""),
            "middle_name": row.get("middle_name", ""), "snils": row.get("snils", ""),
            "position": row.get("position", ""), "employer_inn": row.get("employer_inn", ""),
            "tc_inn": row.get("tc_inn", ""), "result": row.get("result", ""),
            "program": row.get("program", ""), "date": row.get("date", ""),
            "protocol": row.get("protocol", ""),
        })
        if validate_record(rec):
            invalid += 1
            continue
        out.append({
            "Snils": rec["snils"], "LastName": rec["last_name"],
            "FirstName": rec["first_name"], "MiddleName": rec["middle_name"],
            "Position": rec["position"], "learnProgramId": rec["program"],
            "Date": rec["date"], "ProtocolNumber": rec["protocol"], "baseNo": "",
            "isPassed": "false" if rec["result"] == RESULT_FAILED else "true",
        })
    return out, invalid


def apply_summary_merge(employees: Iterable[EmployeeUpdate],
                        keep_newer: bool = False) -> Tuple[int, int]:
    """Write merged employees and their programs to the DB in ONE transaction.

    Returns (added, updated) employee counts (judged by the DB, not by `is_new`).
    keep_newer=True: an existing program row with a better record (passed beats failed,
    later exam date beats earlier) is left untouched. Any error rolls everything back
    and is re-raised.
    """
    from db.database import DatabaseManager
    from db.employee_programs_repo import EmployeeProgramsRepo
    from db.employees_repo import EmployeesRepo
    from utils.crypto import hash_for_search

    added = updated = 0
    db = DatabaseManager.get_instance()
    with db.transaction() as conn:
        for emp in employees:
            known = conn.execute("SELECT 1 FROM employees WHERE snils_hash = ?",
                                 (hash_for_search(emp.snils),)).fetchone()
            emp_data = {
                'snils': emp.snils,
                'last_name': emp.last_name,
                'first_name': emp.first_name,
                'middle_name': emp.middle_name,
            }
            if emp.position:
                emp_data['position'] = emp.position
            emp_id = EmployeesRepo.upsert(emp_data, conn=conn)
            if known:
                updated += 1
            else:
                added += 1
            for prog in emp.programs.values():
                if keep_newer:
                    row = conn.execute(
                        "SELECT exam_date, result FROM employee_programs "
                        "WHERE employee_id = ? AND program_id = ?",
                        (emp_id, prog.program_id)).fetchone()
                    if row and row["exam_date"]:
                        old = ProgramUpdate(program_id=prog.program_id,
                                            exam_date=str(row["exam_date"]),
                                            result=0 if row["result"] == 0 else 1)
                        if not _better(prog, old):
                            continue
                EmployeeProgramsRepo.update_from_api(
                    emp_id, prog.program_id, prog.exam_date,
                    prog.protocol, prog.base_no, prog.result, conn=conn)
    return added, updated


def _rows_phrase(n: int) -> str:
    """1 строка, 2 строки, 5 строк, 21 строка, 11 строк."""
    if n % 10 == 1 and n % 100 != 11:
        word = "строка"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "строки"
    else:
        word = "строк"
    return "%d %s" % (n, word)


def describe_summary_merge(res: SummaryMergeResult, added: int = 0, skipped_new: int = 0) -> str:
    """Текст отчёта для пользователя. Без ПДн."""
    lines = [
        "Обновлено работников: %d" % len(res.existing),
        "Обновлено программ: %d" % res.program_count,
    ]
    if added:
        lines.append("Добавлено новых работников: %d" % added)
    if skipped_new:
        lines.append("Не добавлено (нет в справочнике): %d" % skipped_new)
    if res.errors:
        lines.append("")
        lines.append("Пропущено строк с ошибками: %d" % len(res.errors))
        for row_no, err in res.errors[:10]:
            lines.append("  строка %d — %s" % (row_no, err))
        if len(res.errors) > 10:
            lines.append("  …и ещё %s" % _rows_phrase(len(res.errors) - 10))
    return "\n".join(lines)
