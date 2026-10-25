import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from db.database import DatabaseManager
from db.schema import create_schema
from db.send_history_repo import SendHistoryRepo
from journal.send_history import (
    derive_status, status_from_send, format_sent_at, count_registered,
)


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    d = DatabaseManager.get_instance(path)
    d.initialize()
    create_schema()
    yield d
    d.close_all()
    if os.path.exists(path):
        os.remove(path)


class TestDeriveStatus:
    def test_send_flag(self):
        assert status_from_send(True) == "signed"
        assert status_from_send(False) == "unsigned"
        assert status_from_send(None) == "unknown"

    def test_query_failed_keeps_status(self):
        assert derive_status("signed", False, []) == "signed"
        assert derive_status("unsigned", False, []) == "unsigned"

    def test_records_found_means_signed(self):
        assert derive_status("unsigned", True, [{"baseNo": "1"}]) == "signed"
        assert derive_status("unknown", True, [{"baseNo": ""}]) == "signed"

    def test_empty_after_signed_means_deleted(self):
        assert derive_status("signed", True, []) == "deleted"

    def test_empty_keeps_unsigned_and_unknown(self):
        assert derive_status("unsigned", True, []) == "unsigned"
        assert derive_status("unknown", True, []) == "unknown"
        assert derive_status("deleted", True, []) == "deleted"

    def test_invalid_prev_status(self):
        assert derive_status("???", True, []) == "unknown"

    def test_count_registered(self):
        assert count_registered([{"baseNo": "1"}, {"baseNo": " "}, {}]) == 1

    def test_format_sent_at(self):
        assert format_sent_at("2026-10-25 09:05:33") == "25.10.2026 09:05"
        assert format_sent_at("garbage") == "garbage"


class TestRepo:
    def test_add_and_ignore_duplicate(self, db):
        assert SendHistoryRepo.add("S1", "2026-10-25 10:00:00", 3, True, "signed")
        assert not SendHistoryRepo.add("S1", "2026-10-25 11:00:00", 9, False, "unsigned")
        assert SendHistoryRepo.count() == 1
        assert SendHistoryRepo.get("S1")["record_count"] == 3

    def test_latest_order_and_limit(self, db):
        for i in range(7):
            SendHistoryRepo.add("S%d" % i, "2026-10-2%d 10:00:00" % i, i, False, "unknown")
        latest = SendHistoryRepo.latest(5)
        assert [r["set_id"] for r in latest] == ["S6", "S5", "S4", "S3", "S2"]
        assert len(SendHistoryRepo.list_all()) == 7

    def test_update_status(self, db):
        SendHistoryRepo.add("S1", "2026-10-25 10:00:00", 1, False, "unsigned")
        SendHistoryRepo.update_status("S1", "signed", 1)
        row = SendHistoryRepo.get("S1")
        assert row["status"] == "signed" and row["reg_count"] == 1 and row["last_check"]

    def test_backfill_from_journal(self, db):
        db.execute(
            "INSERT INTO exam_journal (uuid, send_date, set_id, base_no) VALUES (?,?,?,?)",
            ("u1", "25.10.2026 10:30:00", "SET-A", "REG1"))
        db.execute(
            "INSERT INTO exam_journal (uuid, send_date, set_id, base_no) VALUES (?,?,?,?)",
            ("u2", "25.10.2026 10:30:00", "SET-A", ""))
        db.execute(
            "INSERT INTO exam_journal (uuid, send_date, set_id, base_no) VALUES (?,?,?,?)",
            ("u3", "bad-date", "SET-B", ""))
        assert SendHistoryRepo.backfill_from_journal() == 1
        row = SendHistoryRepo.get("SET-A")
        assert row["record_count"] == 2 and row["reg_count"] == 1
        assert row["status"] == "signed" and row["sent_at"] == "2026-10-25 10:30:00"
        assert SendHistoryRepo.backfill_from_journal() == 0

    def test_journal_delete_keeps_history(self, db):
        SendHistoryRepo.add("S1", "2026-10-25 10:00:00", 1, False, "unsigned")
        db.execute(
            "INSERT INTO exam_journal (uuid, send_date, set_id) VALUES (?,?,?)",
            ("u1", "25.10.2026 10:30:00", "S1"))
        db.execute("DELETE FROM exam_journal")
        assert SendHistoryRepo.count() == 1
