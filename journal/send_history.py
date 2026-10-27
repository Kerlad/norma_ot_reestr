"""Send history helpers without Qt: status rules and date formatting."""
import hashlib
from datetime import datetime
from typing import Iterable, List, Optional

STATUSES = ("signed", "unsigned", "deleted", "missing", "unknown")

STATUS_TEXT = {
    "signed": "В реестре, подписано",
    "unsigned": "В реестре, не подписано",
    "deleted": "Удалено из реестра",
    "missing": "Данных в реестре нет: по SetId записей не найдено "
               "(набор не подписан или удалён)",
    "unknown": "Статус неизвестен — нажмите «Обновить данные»",
}

def status_from_send(send_educated_person: Optional[bool]) -> str:
    """Status right after sending, from the SendEducatedPerson flag of the response."""
    if send_educated_person is True:
        return "signed"
    if send_educated_person is False:
        return "unsigned"
    return "unknown"


def outer_ids_fingerprint(outer_ids: Iterable[str]) -> str:
    """SHA-256 of the sorted outerId of the set records ('' when there are none)."""
    ids = sorted({(i or "").strip() for i in outer_ids} - {""})
    if not ids:
        return ""
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def derive_status(prev_status: str, query_ok: bool, records: List[dict],
                  sent: Optional[dict] = None) -> str:
    """Status after a SetId query. Returns one of STATUSES.

    Only the SetId is checked: any records returned -> 'signed', none -> 'missing'.
    `sent` is accepted for compatibility and ignored.
    """
    if prev_status not in STATUSES:
        prev_status = "unknown"
    if not query_ok:
        return prev_status
    if not records:
        return "missing"
    return "signed"


def count_registered(records: List[dict]) -> int:
    return sum(1 for r in records if (r.get("baseNo") or "").strip())


def format_sent_at(sent_at: str) -> str:
    """ISO 'YYYY-MM-DD HH:MM:SS' -> 'ДД.ММ.ГГГГ ЧЧ:ММ'; unparsable text is returned as is."""
    try:
        return datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return sent_at or ""
