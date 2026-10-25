import logging
from datetime import datetime
from typing import List, Dict

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class SendHistoryRepo:
    """History of XML sets sent to the registry. No personal data is stored."""

    @staticmethod
    def add(set_id: str, sent_at: str, record_count: int,
            signed_send: bool, status: str) -> bool:
        db = DatabaseManager.get_instance()
        with db.transaction() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO send_history "
                "(set_id, sent_at, record_count, signed_send, status) VALUES (?, ?, ?, ?, ?)",
                (set_id, sent_at, int(record_count), 1 if signed_send else 0, status),
            )
            return cur.rowcount > 0

    @staticmethod
    def list_all() -> List[Dict]:
        return DatabaseManager.get_instance().fetchall(
            "SELECT * FROM send_history ORDER BY sent_at DESC, id DESC")

    @staticmethod
    def latest(n: int = 5) -> List[Dict]:
        return DatabaseManager.get_instance().fetchall(
            "SELECT * FROM send_history ORDER BY sent_at DESC, id DESC LIMIT ?", (int(n),))

    @staticmethod
    def get(set_id: str):
        return DatabaseManager.get_instance().fetchone(
            "SELECT * FROM send_history WHERE set_id = ?", (set_id,))

    @staticmethod
    def update_status(set_id: str, status: str, reg_count: int, last_check: str = "") -> None:
        last_check = last_check or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        DatabaseManager.get_instance().execute(
            "UPDATE send_history SET status = ?, reg_count = ?, last_check = ? WHERE set_id = ?",
            (status, int(reg_count), last_check, set_id),
        )

    @staticmethod
    def count() -> int:
        r = DatabaseManager.get_instance().fetchone("SELECT COUNT(*) AS cnt FROM send_history")
        return r["cnt"] if r else 0

    @staticmethod
    def backfill_from_journal() -> int:
        """Fill an empty history from the exam journal (one row per SetId). Returns rows added."""
        if SendHistoryRepo.count() > 0:
            return 0
        db = DatabaseManager.get_instance()
        rows = db.fetchall(
            "SELECT set_id, MIN(send_date) AS first_send, COUNT(*) AS cnt, "
            "SUM(CASE WHEN base_no <> '' THEN 1 ELSE 0 END) AS reg "
            "FROM exam_journal WHERE set_id <> '' GROUP BY set_id"
        )
        added = 0
        with db.transaction() as conn:
            for r in rows:
                try:
                    dt = datetime.strptime(r["first_send"], "%d.%m.%Y %H:%M:%S")
                except (ValueError, TypeError):
                    logger.warning("send history backfill: skipped a row with invalid date")
                    continue
                reg = int(r["reg"] or 0)
                cur = conn.execute(
                    "INSERT OR IGNORE INTO send_history "
                    "(set_id, sent_at, record_count, status, reg_count, source) "
                    "VALUES (?, ?, ?, ?, ?, 'journal')",
                    (r["set_id"], dt.strftime("%Y-%m-%d %H:%M:%S"), int(r["cnt"]),
                     "signed" if reg else "unknown", reg),
                )
                added += cur.rowcount
        return added
