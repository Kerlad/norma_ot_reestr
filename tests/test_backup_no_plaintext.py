"""L-00b: backups must never be created unencrypted."""
import os
import sys

import pytest

from db.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    from db.schema import create_schema

    manager = DatabaseManager.get_instance(str(tmp_path / "t.db"))
    manager.initialize()
    create_schema()
    yield manager
    manager.close_all()


@pytest.fixture
def no_pyzipper(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyzipper", None)  # `import pyzipper` -> ImportError


def test_master_key_backup_refused_without_pyzipper(tmp_path, monkeypatch, no_pyzipper):
    from utils import crypto

    kd = tmp_path / "keys"
    kd.mkdir()
    (kd / "master.key").write_bytes(b"x" * 32)
    monkeypatch.setattr(crypto, "_key_dir", lambda: kd)
    out = tmp_path / "out"

    ok, msg = crypto.create_master_key_backup(str(out))

    assert ok is False
    assert "pyzipper" in msg
    assert not list(out.glob("*"))


def test_db_backup_refused_without_pyzipper(db, no_pyzipper):
    db.execute("INSERT INTO employees (snils_enc, snils_hash) VALUES (?, ?)", ("a", "b"))

    assert db.create_backup() == ""

    backup_dir = os.path.join(os.path.dirname(db.db_path), "backups")
    leftovers = [f for f in os.listdir(backup_dir)] if os.path.isdir(backup_dir) else []
    assert not any(f.endswith(".backup.1.zip") or f.endswith(".backup.1") for f in leftovers)


def test_db_backup_oserror_leaves_no_plain_copy(db, monkeypatch):
    import pyzipper

    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(pyzipper, "AESZipFile", boom)

    assert db.create_backup() == ""

    backup_dir = os.path.join(os.path.dirname(db.db_path), "backups")
    base = os.path.basename(db.db_path)
    assert not os.path.exists(os.path.join(backup_dir, f"{base}.backup.1"))
    assert not os.path.exists(os.path.join(backup_dir, f"{base}.backup.1.zip"))
