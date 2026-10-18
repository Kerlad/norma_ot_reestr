"""
Сопоставление ответов реестра Минтруда с журналом проверки знаний (UX-07).

Используется тремя путями с одинаковой логикой:
- импорт файла-ответа по SetId (XLSX из «Передача данных → Запрос по SetId»);
- запрос из журнала по SetId или СНИЛС (диалог «Запросить по…»);
- запрос по SetId на вкладке «Передача данных».

Без Qt и без сети — только чистые функции, чтобы покрывать тестами.
"""
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from db.exam_journal_repo import JournalRecord

# Заголовки XLSX из api.mintrud_api.export_records_to_xlsx -> ключи записи API
API_XLSX_HEADERS = {
    "Номер записи в реестре": "baseNo",
    "Фамилия": "LastName",
    "Имя": "FirstName",
    "Отчество": "MiddleName",
    "СНИЛС": "Snils",
    "Должность": "Position",
    "ИНН работодателя": "EmployerInn",
    "Наименование работодателя": "EmployerTitle",
    "Номер программы": "learnProgramId",
    "Название программы": "LearnProgramTitle",
    "Номер протокола": "ProtocolNumber",
    "Дата": "Date",
    "Зачёт": "isPassed",
}
API_XLSX_REQUIRED = ("Номер записи в реестре", "СНИЛС", "Номер программы", "Номер протокола", "Дата")

RESULT_PASSED = "Удовлетворительно"
RESULT_FAILED = "Неудовлетворительно"


def snils_key(value) -> str:
    """Только цифры СНИЛС (ключ сравнения)."""
    return re.sub(r"\D", "", str(value or ""))


def format_snils(digits: str) -> str:
    d = snils_key(digits)
    if len(d) != 11:
        return str(digits or "").strip()
    return f"{d[:3]}-{d[3:6]}-{d[6:9]} {d[9:]}"


def normalize_date(value) -> str:
    """ISO (2025-09-26T00:00:00), datetime или DD.MM.YYYY -> DD.MM.YYYY."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    s = str(value).strip()
    head = s.split()[0] if s else ""
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", head):
        return head
    head = head.split("T")[0]
    try:
        return datetime.strptime(head, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return s


def setid_from_filename(path: str) -> str:
    """«Передача данных» предлагает имя файла `<SetId>.xlsx`; берём его, если это число."""
    stem = os.path.splitext(os.path.basename(path or ""))[0].strip()
    return stem if stem.isdigit() else ""


def _norm_program(value) -> str:
    s = str(value or "").strip()
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def _norm_protocol(value) -> str:
    return str(value or "").strip().lower()


def is_api_xlsx_headers(headers: Iterable) -> bool:
    hs = {str(h).strip() for h in headers if h is not None}
    return all(h in hs for h in API_XLSX_REQUIRED)


def api_records_from_rows(headers: List, rows: Iterable[Tuple]) -> List[Dict[str, str]]:
    """Строки XLSX-ответа -> записи в формате API (как от get_by_set_id)."""
    idx = {}
    for i, h in enumerate(headers):
        key = API_XLSX_HEADERS.get(str(h).strip()) if h is not None else None
        if key:
            idx[key] = i
    out = []
    for row in rows:
        if not row or not any(c not in (None, "") for c in row):
            continue
        rec = {}
        for key, i in idx.items():
            v = row[i] if i < len(row) else None
            rec[key] = normalize_date(v) if key == "Date" else ("" if v is None else str(v).strip())
        out.append(rec)
    return out


def _result_from_api(rec: Dict) -> str:
    v = str(rec.get("isPassed", "")).strip().lower()
    return RESULT_FAILED if v in ("false", "0", "нет") else RESULT_PASSED


@dataclass
class MergeResult:
    # (uuid, base_no, set_id or "") для обновления существующих записей
    updates: List[Tuple[str, str, str]] = field(default_factory=list)
    already: int = 0
    new_records: List[JournalRecord] = field(default_factory=list)
    skipped: int = 0  # записи ответа без СНИЛС/программы

    @property
    def updated(self) -> int:
        return len(self.updates)


def api_record_to_journal(rec: Dict, set_id: str = "", program_titles: Optional[Dict] = None) -> JournalRecord:
    pid = _norm_program(rec.get("learnProgramId"))
    title = (rec.get("LearnProgramTitle") or "").strip() or (program_titles or {}).get(pid, "")
    base_no = (rec.get("baseNo") or "").strip()
    return JournalRecord(
        uuid=str(uuid.uuid4()), send_date="", set_id=set_id or "", xml_file="",
        last_name=(rec.get("LastName") or "").strip(),
        first_name=(rec.get("FirstName") or "").strip(),
        middle_name=(rec.get("MiddleName") or "").strip(),
        snils=format_snils(rec.get("Snils")),
        position=(rec.get("Position") or "").strip(),
        program_id=pid, program_title=title,
        exam_date=normalize_date(rec.get("Date")),
        protocol=(rec.get("ProtocolNumber") or "").strip(),
        result=_result_from_api(rec), base_no=base_no,
        status="received" if base_no else "pending",
    )


def merge_registry_records(api_records: Iterable[Dict], existing: Iterable[JournalRecord],
                           set_id: str = "", program_titles: Optional[Dict] = None) -> MergeResult:
    """Сопоставить записи реестра с журналом.

    Совпадение: СНИЛС + № программы + (№ протокола или дата проверки).
    Совпавшие записи получают рег. номер, статус «получен» и SetId (если был пуст).
    Несовпавшие возвращаются в new_records (добавлять ли — решает UI).
    """
    by_key: Dict[Tuple[str, str], List[JournalRecord]] = {}
    for r in existing:
        by_key.setdefault((snils_key(r.snils), _norm_program(r.program_id)), []).append(r)

    result = MergeResult()
    seen_updates = set()
    seen_new = set()
    for rec in api_records:
        sk = snils_key(rec.get("Snils"))
        pid = _norm_program(rec.get("learnProgramId"))
        if len(sk) != 11 or not pid:
            result.skipped += 1
            continue
        proto = _norm_protocol(rec.get("ProtocolNumber"))
        date = normalize_date(rec.get("Date"))
        base_no = (rec.get("baseNo") or "").strip()

        matches = [
            r for r in by_key.get((sk, pid), [])
            if (proto and _norm_protocol(r.protocol) == proto)
            or (date and normalize_date(r.exam_date) == date)
        ]
        if not matches:
            key = (sk, pid, proto, date)
            if key not in seen_new:
                seen_new.add(key)
                result.new_records.append(api_record_to_journal(rec, set_id, program_titles))
            continue
        for r in matches:
            if r.uuid in seen_updates:
                continue
            fill_set_id = set_id if (set_id and not r.set_id) else ""
            if not base_no or (r.base_no == base_no and r.status == "received" and not fill_set_id):
                result.already += 1
                continue
            seen_updates.add(r.uuid)
            result.updates.append((r.uuid, base_no, fill_set_id))
    return result


def describe_merge(res: MergeResult, added: int = 0) -> str:
    parts = [f"Обновлено записей журнала: {res.updated}"]
    if res.already:
        parts.append(f"уже актуальны: {res.already}")
    if added:
        parts.append(f"добавлено новых: {added}")
    elif res.new_records:
        parts.append(f"нет в журнале: {len(res.new_records)}")
    if res.skipped:
        parts.append(f"пропущено (нет СНИЛС/программы): {res.skipped}")
    return "; ".join(parts)
