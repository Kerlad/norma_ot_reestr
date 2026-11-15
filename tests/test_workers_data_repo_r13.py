"""R13: _decrypt_row rename and explicit program check in update()."""
import os
import tempfile

import pytest

from db.database import DatabaseManager
from db.schema import create_schema
from db import workers_data_repo
from db.workers_data_repo import WorkersDataRepo


@pytest.fixture()
def repo():
    with tempfile.TemporaryDirectory() as d:
        db = DatabaseManager.get_instance(os.path.join(d, "w.db"))
        db.initialize()
        create_schema()
        yield WorkersDataRepo
        db.close_all()


REC = {"last_name": "Тестов", "first_name": "Тест", "middle_name": "Тестович",
       "snils": "112-233-445 95", "program": 1, "date": "04.11.2026", "result": 1}


def test_decrypt_row_name():
    assert hasattr(workers_data_repo, "_decrypt_row")
    assert not hasattr(workers_data_repo, "_encrypt_row")


def test_roundtrip_decrypts(repo):
    rid = repo.add(REC)
    assert repo.get_by_id(rid)["last_name"] == "Тестов"


def test_update_non_numeric_program_raises_clear_error(repo):
    rid = repo.add(REC)
    with pytest.raises(ValueError, match="программ"):
        repo.update(rid, {**REC, "program": "abc"})
    assert repo.get_by_id(rid)["program"] == 1
