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
    res = SummaryMergeResult()
    by_key: Dict[str, EmployeeUpdate] = {}

    # api_records_from_rows пропускает пустые строки, поэтому нумеруем по исходным.
    numbered = []
    rec_idx = 0
    for offset, row in enumerate(row_list, start=2):  # строка 1 — заголовки
        if not row or not any(c not in (None, "") for c in row):
            continue
        if rec_idx < len(records):
            numbered.append((offset, records[rec_idx]))
            rec_idx += 1

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
