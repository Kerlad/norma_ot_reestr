"""Send history helpers without Qt: status rules and date formatting."""
import hashlib
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

STATUSES = ("signed", "unsigned", "deleted", "missing", "unknown")

STATUS_TEXT = {
    "signed": "В реестре, подписано",
    "unsigned": "В реестре, не подписано",
    "deleted": "Удалено из реестра",
    "missing": "Данных в реестре нет: набор не подписан, удалён "
               "или номер SetId присвоен другому набору",
    "unknown": "Статус неизвестен — нажмите «Обновить данные»",
}

# Registry date (baseDateCreated) may be in Moscow time: allow one day of clock difference
DATE_TOLERANCE = timedelta(days=1)


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


def _parse_registry_date(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    for fmt, size in (("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d %H:%M:%S", 19),
                      ("%Y-%m-%d", 10), ("%d.%m.%Y %H:%M:%S", 19), ("%d.%m.%Y", 10)):
        try:
            return datetime.strptime(value[:size], fmt)
        except ValueError:
            continue
    return None


def set_mismatch(sent: Optional[dict], records: List[dict]) -> str:
    """Why the records returned for a SetId are not the set we sent ('' = they match).

    The API has no set metadata, so a SetId given to another set is detected by the
    records themselves: outerId of every record (we generate them), record count,
    and baseDateCreated (a record cannot be created before the set was sent).
    """
    if not sent or not records:
        return ""
    expected_hash = (sent.get("outer_hash") or "").strip()
    returned = [(r.get("outerId") or "").strip() for r in records]
    if expected_hash and all(returned):
        if outer_ids_fingerprint(returned) != expected_hash:
            return "outer_id"
    count = int(sent.get("record_count") or 0)
    if count > 0 and len(records) != count:
        return "count"
    try:
        sent_at = datetime.strptime(sent.get("sent_at") or "", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        sent_at = None
    if sent_at is not None:
        dates = [d for d in (_parse_registry_date(r.get("baseDateCreated")) for r in records) if d]
        if dates and min(dates) < sent_at.replace(hour=0, minute=0, second=0) - DATE_TOLERANCE:
            return "date"
    return ""


def derive_status(prev_status: str, query_ok: bool, records: List[dict],
                  sent: Optional[dict] = None) -> str:
    """Status after a SetId query. Returns one of STATUSES.

    No records, or records of another set under the same SetId -> 'missing'.
    """
    if prev_status not in STATUSES:
        prev_status = "unknown"
    if not query_ok:
        return prev_status
    if not records or set_mismatch(sent, records):
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
