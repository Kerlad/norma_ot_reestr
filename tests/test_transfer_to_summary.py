"""B9: «Перенести в сводку» in «Просмотр данных»."""
import os
import tempfile

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from db.database import DatabaseManager
from db.employee_programs_repo import EmployeeProgramsRepo
from db.employees_repo import EmployeesRepo
from db.schema import create_schema
from db.workers_data_repo import WorkersDataRepo
from utils.crypto import clear_caches

OK = "Удовлетворительно"
BAD = "Неудовлетворительно"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def setup_db():
    clear_caches()
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = DatabaseManager.get_instance(db_path)
    db.initialize()
    create_schema()
    yield db
    db.close_all()
    if os.path.exists(db_path):
        os.remove(db_path)


def _rec(snils="112-233-445 95", program="1", date="04.11.2025", result=OK, protocol="1"):
    return {'last_name': 'Тестов', 'first_name': 'Тест', 'middle_name': 'Тестович',
            'snils': snils, 'position': 'Инженер', 'employer_inn': '', 'employer_title': '',
            'tc_inn': '', 'tc_title': '', 'result': result, 'program': program,
            'date': date, 'protocol': protocol}


@pytest.fixture
def tab(app, monkeypatch):
    from tabs.data_view_tab import DataViewTab
    from utils.dialog_base import BaseDialog
    monkeypatch.setattr(BaseDialog, "exec", lambda self: 0)
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    t = DataViewTab()
    t._asked = []
    t._open = False

    def fake_ask(text):
        t._asked.append(text)
        return t._open
    t._ask_open_summary = fake_ask
    return t


def _prog(snils, pid):
    emp = EmployeesRepo.get_by_snils(snils)
    return EmployeeProgramsRepo.get(emp['id'], pid)


def test_button_disabled_when_empty_and_enabled_with_data(tab):
    assert tab.transfer_btn.text() == "Перенести в сводку"
    assert not tab.transfer_btn.isEnabled()
    WorkersDataRepo.add(_rec())
    tab._load_all_data()
    assert tab.transfer_btn.isEnabled()


def test_two_programs_one_employee(tab):
    WorkersDataRepo.add(_rec(program="1"))
    WorkersDataRepo.add(_rec(program="2"))
    tab.transfer_to_summary()
    assert EmployeesRepo.count() == 1
    emp = EmployeesRepo.get_by_snils("112-233-445 95")
    assert len(EmployeeProgramsRepo.get_by_employee(emp['id'])) == 2
    assert "Добавлено сотрудников: 1 · Обновлено: 0 · Пропущено записей с ошибками: 0" in tab._asked[0]
    # records to send stay in place
    assert WorkersDataRepo.count() == 2


def test_repeat_transfer_adds_nothing(tab):
    WorkersDataRepo.add(_rec())
    tab.transfer_to_summary()
    tab.transfer_to_summary()
    assert "Добавлено сотрудников: 0 · Обновлено: 1" in tab._asked[1]
    assert EmployeesRepo.count() == 1


def test_older_date_does_not_overwrite_newer(tab):
    WorkersDataRepo.add(_rec(date="04.11.2025", protocol="NEW"))
    tab.transfer_to_summary()
    WorkersDataRepo.clear()
    WorkersDataRepo.add(_rec(date="01.01.2024", protocol="OLD"))
    tab.transfer_to_summary()
    p = _prog("112-233-445 95", 1)
    assert p['exam_date'] == "04.11.2025" and p['protocol'] == "NEW"


def test_newer_date_overwrites_older(tab):
    WorkersDataRepo.add(_rec(date="01.01.2024", protocol="OLD"))
    tab.transfer_to_summary()
    WorkersDataRepo.clear()
    WorkersDataRepo.add(_rec(date="04.11.2025", protocol="NEW"))
    tab.transfer_to_summary()
    assert _prog("112-233-445 95", 1)['protocol'] == "NEW"


def test_invalid_snils_not_transferred(tab):
    WorkersDataRepo.add(_rec(snils="123-456-789 00"))
    WorkersDataRepo.add(_rec(snils="123-456-789 64"))
    tab.transfer_to_summary()
    assert EmployeesRepo.count() == 1
    assert EmployeesRepo.get_by_snils("123-456-789 00") is None
    assert "Пропущено записей с ошибками: 1" in tab._asked[0]


def test_failed_result_is_transferred_as_not_trained(tab):
    WorkersDataRepo.add(_rec(result=BAD))
    tab.transfer_to_summary()
    p = _prog("112-233-445 95", 1)
    assert p['result'] == 0 and p['status'] == 'not_trained'


def test_open_summary_signal_and_counters(tab):
    got = []
    tab.summary_requested.connect(lambda: got.append("open"))
    tab.summary_changed.connect(lambda: got.append("changed"))
    WorkersDataRepo.add(_rec())
    tab._open = True
    tab.transfer_to_summary()
    assert got == ["changed", "open"]


def test_audit_has_only_numbers(tab, monkeypatch):
    import tabs.data_view_tab as mod
    events = []
    monkeypatch.setattr(mod, "log_audit", lambda ev, detail="": events.append((ev, detail)))
    WorkersDataRepo.add(_rec())
    tab.transfer_to_summary()
    ev = [d for e, d in events if e == "IMPORT_XLSX"]
    assert ev == ["source=data_view, employees=1, added=1, errors=0"]


def test_failure_rolls_back_everything(tab, monkeypatch):
    from journal import summary_sync
    WorkersDataRepo.add(_rec(snils="112-233-445 95"))
    WorkersDataRepo.add(_rec(snils="123-456-789 64"))
    calls = {"n": 0}
    real = EmployeeProgramsRepo.update_from_api

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*a, **k)
    monkeypatch.setattr(EmployeeProgramsRepo, "update_from_api", staticmethod(flaky))
    tab.transfer_to_summary()
    assert EmployeesRepo.count() == 0
    assert summary_sync  # module imported fine
