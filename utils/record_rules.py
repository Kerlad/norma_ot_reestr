"""Single source of validation rules for a training record (no Qt).

Used by the manual entry form, the XLSX importer and the record edit dialog.
Standard library and utils.constants only.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from utils.constants import VALID_PROGRAMS_SET

RESULT_PASSED = "Удовлетворительно"
RESULT_FAILED = "Неудовлетворительно"
MAX_NAME_LEN = 100
MAX_POSITION_LEN = 255
MIDDLE_NAME_REQUIRED = False   # owner decision Q1 (12.11.2026): optional + warning

_INN10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN12_A = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN12_B = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


@dataclass
class FieldError:
    field: str      # record key: 'last_name', 'snils', 'date', ...
    message: str    # Russian text for the user, without the field value


def _is_ascii_digits(s: str) -> bool:
    return bool(s) and all("0" <= c <= "9" for c in s)


def cell_text(v) -> str:
    """Spreadsheet cell as stripped text; whole floats lose the '.0' tail."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def id_cell_text(v, kind: str) -> str:
    """SNILS / INN cell as text. A number cell loses leading zeros in Excel
    (СНИЛС 012-…, ИНН регионов 01–09): they are restored to the full length.
    kind: "snils" (11 digits) or "inn" (10 for an organization, 12 for ИП)."""
    s = cell_text(v)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not _is_ascii_digits(s):
        return s
    if kind == "snils":
        return s.zfill(11) if 8 <= len(s) < 11 else s
    if kind == "inn":
        if len(s) in (8, 9):
            return s.zfill(10)
        if len(s) == 11:
            return s.zfill(12)
    return s


def snils_digits(raw) -> str:
    s = "" if raw is None else str(raw)
    return "".join(
        c for c in s
        if unicodedata.category(c) != "Zs" and c not in "\t-"
    )


def snils_checksum_ok(clean_digits: str) -> bool:
    if len(clean_digits) != 11 or not clean_digits.isdigit():
        return False
    digits = [int(c) for c in clean_digits[:9]]
    check = int(clean_digits[9:])
    total = sum(d * (9 - i) for i, d in enumerate(digits))
    if total < 100:
        control = total
    elif total in (100, 101):
        control = 0
    else:
        control = total % 101
        if control in (100, 101):
            control = 0
    return control == check


def format_snils(raw) -> Optional[str]:
    d = snils_digits(raw)
    if len(d) == 11 and _is_ascii_digits(d):
        return f"{d[0:3]}-{d[3:6]}-{d[6:9]} {d[9:11]}"
    return None


def validate_snils(raw) -> Optional[str]:
    d = snils_digits(raw)
    if not d:
        return "Укажите СНИЛС"
    if len(d) != 11 or not _is_ascii_digits(d):
        return "СНИЛС должен содержать 11 цифр"
    if not snils_checksum_ok(d):
        return "Неверная контрольная сумма СНИЛС"
    return None


def validate_inn(raw, required: bool = False) -> Optional[str]:
    s = "" if raw is None else "".join(
        c for c in str(raw) if not c.isspace() and unicodedata.category(c) != "Zs")
    if not s:
        return "Укажите ИНН" if required else None
    if not _is_ascii_digits(s) or len(s) not in (10, 12):
        return "ИНН: 10 цифр для организации, 12 для ИП"
    d = [int(c) for c in s]
    if len(d) == 10:
        ok = sum(k * v for k, v in zip(_INN10, d[:9])) % 11 % 10 == d[9]
    else:
        c1 = sum(k * v for k, v in zip(_INN12_A, d[:10])) % 11 % 10
        c2 = sum(k * v for k, v in zip(_INN12_B, d[:11])) % 11 % 10
        ok = c1 == d[10] and c2 == d[11]
    if not ok:
        return "ИНН: контрольное число не сходится"
    return None


def _make_date(d: int, m: int, y: int) -> Optional[str]:
    try:
        return date(y, m, d).strftime("%d.%m.%Y")
    except ValueError:
        return None


def normalize_date(value) -> Optional[str]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (datetime, date)):
        try:
            return value.strftime("%d.%m.%Y")
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=value)).strftime("%d.%m.%Y")
        except (ValueError, OverflowError):
            return None
    s = str(value).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?", s)
    if m:
        return _make_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if re.fullmatch(r"\d{8}", s):
        return _make_date(int(s[:2]), int(s[2:4]), int(s[4:]))
    parts = re.split(r"[./-]", s)
    if len(parts) == 3 and all(p.isdigit() and p.isascii() for p in parts):
        dd, mm, yy = parts
        if len(yy) == 2:
            y = 2000 + int(yy)
        elif len(yy) == 4:
            y = int(yy)
        else:
            return None
        if len(dd) > 2 or len(mm) > 2:
            return None
        return _make_date(int(dd), int(mm), y)
    return None


def validate_date(value) -> Optional[str]:
    nd = normalize_date(value)
    if nd is None:
        return "Введите дату как ДД.ММ.ГГГГ"
    if datetime.strptime(nd, "%d.%m.%Y").date() > date.today():
        return "Дата не может быть больше текущей"
    return None


def normalize_result(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s == "удовлетворительно":
        return RESULT_PASSED
    if s == "неудовлетворительно":
        return RESULT_FAILED
    return None


def _norm_program(p: str) -> str:
    if re.fullmatch(r"\d+\.0+", p):
        return p.split(".")[0]
    return p


def split_programs(value) -> List[str]:
    if value is None:
        return []
    s = str(value).replace(";", ",")
    out: List[str] = []
    for p in re.split(r"[,\s]+", s):
        p = _norm_program(p.strip())
        if p and p not in out:
            out.append(p)
    return out


def validate_name(value, required: bool) -> Optional[str]:
    s = "" if value is None else str(value).strip()
    if not s:
        return "Заполните поле" if required else None
    if len(s) > MAX_NAME_LEN:
        return "Не длиннее 100 символов"
    if not all(c.isalpha() or c in " -'." for c in s):
        return "Допустимы буквы, пробел, дефис, апостроф"
    return None


def validate_position(value) -> Optional[str]:
    s = "" if value is None else str(value).strip()
    if not s:
        return "Укажите должность"
    if len(s) > MAX_POSITION_LEN:
        return "Не длиннее 255 символов"
    if any(ord(c) < 32 for c in s):
        return "Недопустимые символы"
    return None


def normalize_record(rec: dict) -> dict:
    out = dict(rec)
    for k, v in out.items():
        if isinstance(v, str):
            out[k] = v.strip()
    if "snils" in out:
        f = format_snils(out["snils"])
        if f is not None:
            out["snils"] = f
    if "date" in out:
        n = normalize_date(out["date"])
        if n is not None:
            out["date"] = n
    if "result" in out:
        n = normalize_result(out["result"])
        if n is not None:
            out["result"] = n
    if "program" in out and out["program"] is not None:
        out["program"] = _norm_program(str(out["program"]).strip())
    return out


def validate_record(rec: dict) -> List[FieldError]:
    errors: List[FieldError] = []

    def add(field: str, msg: Optional[str]) -> None:
        if msg:
            errors.append(FieldError(field, msg))

    add("last_name", validate_name(rec.get("last_name"), True))
    add("first_name", validate_name(rec.get("first_name"), True))
    add("middle_name", validate_name(rec.get("middle_name"), MIDDLE_NAME_REQUIRED))
    add("snils", validate_snils(rec.get("snils")))
    add("position", validate_position(rec.get("position")))
    prog = rec.get("program")
    if str(prog if prog is not None else "").strip() not in VALID_PROGRAMS_SET:
        add("program", "Номер программы: 1–4 или 6–29")
    add("date", validate_date(rec.get("date")))
    if rec.get("result") not in (RESULT_PASSED, RESULT_FAILED):
        add("result", "Результат: «Удовлетворительно» или «Неудовлетворительно»")
    if not str(rec.get("protocol") or "").strip():
        add("protocol", "Укажите номер протокола")
    add("employer_inn", validate_inn(rec.get("employer_inn"), required=False))
    add("tc_inn", validate_inn(rec.get("tc_inn"), required=False))
    return errors


def record_warnings(rec: dict) -> List[FieldError]:
    warnings: List[FieldError] = []
    if not str(rec.get("middle_name") or "").strip():
        warnings.append(FieldError(
            "middle_name",
            "Отчество не указано. Оставьте пустым, только если его нет в документах"))
    return warnings
