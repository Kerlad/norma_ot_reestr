"""R9: transaction() retries only BEGIN IMMEDIATE, never the body."""
import os
import sqlite3
import tempfile

import pytest

from db.database import DatabaseManager, DatabaseLockError


@pytest.fixture()
def db():
    with tempfile.TemporaryDirectory() as d:
        inst = DatabaseManager.get_instance(os.path.join(d, "t.db"))
        inst.initialize()
        inst._get_connection().execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
        yield inst
        inst.close_all()


class _FakeConn:
    """Wraps a real connection; fails BEGIN IMMEDIATE with 'locked' N times."""

    def __init__(self, real, begin_failures):
        self._real = real
        self.begin_failures = begin_failures
        self.begins = 0
        self.rollbacks = 0
        self.commits = 0

    def execute(self, sql, *a):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            self.begins += 1
            if self.begin_failures > 0:
                self.begin_failures -= 1
                raise sqlite3.OperationalError("database is locked")
        return self._real.execute(sql, *a)

    def commit(self):
        self.commits += 1
        self._real.commit()

    def rollback(self):
        self.rollbacks += 1
        self._real.rollback()


def _patch(db, fake):
    db._local.conn = fake


def test_begin_locked_twice_then_success_runs_body_once(db):
    fake = _FakeConn(db._get_connection(), begin_failures=2)
    _patch(db, fake)
    runs = []
    with db.transaction() as conn:
        runs.append(1)
        conn.execute("INSERT INTO t VALUES (1)")
    assert len(runs) == 1
    assert fake.begins == 3
    assert fake.commits == 1


def test_begin_locked_always_raises_lock_error(db):
    fake = _FakeConn(db._get_connection(), begin_failures=99)
    _patch(db, fake)
    with pytest.raises(DatabaseLockError):
        with db.transaction():
            pytest.fail("body must not run")


def test_exception_in_body_rolls_back_and_is_not_repeated(db):
    runs = []
    with pytest.raises(ValueError):
        with db.transaction() as conn:
            runs.append(1)
            conn.execute("INSERT INTO t VALUES (1)")
            raise ValueError("boom")
    assert len(runs) == 1
    assert db.fetchone("SELECT COUNT(*) AS c FROM t")["c"] == 0


def test_lock_error_inside_body_is_not_retried(db):
    """Before the fix: body re-entered -> RuntimeError from contextmanager."""
    runs = []
    with pytest.raises(sqlite3.OperationalError):
        with db.transaction():
            runs.append(1)
            raise sqlite3.OperationalError("database is locked")
    assert len(runs) == 1
