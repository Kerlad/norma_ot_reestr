"""EmployeesRepo.upsert on an existing employee updates only the fields passed."""
import pytest

from db.database import DatabaseManager
from db.employees_repo import EmployeesRepo


@pytest.fixture
def db(tmp_path):
    from db.schema import create_schema
    inst = DatabaseManager.get_instance(str(tmp_path / "t.db"))
    inst.initialize()
    create_schema()
    yield inst
    inst.close_all()


def _full():
    return {"snils": "112-233-445 95", "last_name": "Тестов", "first_name": "Тест",
            "middle_name": "Тестович", "position": "Слесарь", "required_programs": "1;2"}


def test_partial_update_keeps_other_fields(db):
    emp_id = EmployeesRepo.upsert(_full())
    EmployeesRepo.upsert({"snils": "112-233-445 95", "position": "Мастер"})
    emp = EmployeesRepo.get_by_id(emp_id)
    assert emp["last_name"] == "Тестов"
    assert emp["first_name"] == "Тест"
    assert emp["middle_name"] == "Тестович"
    assert emp["position"] == "Мастер"
    assert emp["required_programs"] == "1;2"


def test_explicit_empty_value_still_clears(db):
    emp_id = EmployeesRepo.upsert(_full())
    EmployeesRepo.upsert({"snils": "112-233-445 95", "middle_name": ""})
    assert EmployeesRepo.get_by_id(emp_id)["middle_name"] == ""
