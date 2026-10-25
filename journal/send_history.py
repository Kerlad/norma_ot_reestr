"""Send history helpers without Qt: status rules and date formatting."""
from datetime import datetime
from typing import List, Optional

STATUSES = ("signed", "unsigned", "deleted", "unknown")

STATUS_TEXT = {
    "signed": "В реестре, подписано",
    "unsigned": "В реестре, не подписано",
    "deleted": "Удалено из реестра",
    "unknown": "Статус неизвестен — нажмите «Обновить данные»",
}


def status_from_send(send_educated_person: Optional[bool]) -> str:
    """Status right after sending, from the SendEducatedPerson flag of the response."""
    if send_educated_person is True:
        return "signed"
    if send_educated_person is False:
        return "unsigned"
    return "unknown"


def derive_status(prev_status: str, query_ok: bool, records: List[dict]) -> str:
    """Status after a SetId query. Returns one of: signed, unsigned, deleted, unknown."""
    if prev_status not in STATUSES:
        prev_status = "unknown"
    if not query_ok:
        return prev_status
    if records:
        return "signed"
    if prev_status == "signed":
        return "deleted"
    return prev_status


def count_registered(records: List[dict]) -> int:
    return sum(1 for r in records if (r.get("baseNo") or "").strip())


def format_sent_at(sent_at: str) -> str:
    """ISO 'YYYY-MM-DD HH:MM:SS' -> 'ДД.ММ.ГГГГ ЧЧ:ММ'; unparsable text is returned as is."""
    try:
        return datetime.strptime(sent_at, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return sent_at or ""
