"""C2 (sidebar «today» block hides on low windows) and C4 (expiry reminders). Fictional data only."""
import os
import tempfile
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from dateutil.relativedelta import relativedelta
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from db.database import DatabaseManager
from db.employee_programs_repo import EmployeeProgramsRepo
from db.employees_repo import EmployeesRepo
from db.schema import create_schema
from utils.crypto import clear_caches
from utils.training_rules import days_to_expiry


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def summary_db(monkeypatch):
    from tabs import send_history_panel
    clear_caches()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    db = DatabaseManager.get_instance(path)
    db.initialize()
    create_schema()
    # modal dialogs must never open; prefs stay in the (redirected) data dir, reset around the test
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    send_history_panel.save_ui_pref("summary_expiry_days", 60)
    yield db
    send_history_panel.save_ui_pref("summary_expiry_days", 60)
    db.close_all()
    os.remove(path)


def exam_for(days_left: int, program_id: int = 1) -> str:
    """Exam date (DD.MM.YYYY) whose period ends `days_left` days from today."""
    exam = date.today() + timedelta(days=days_left) - relativedelta(years=3)
    while days_to_expiry(exam.strftime("%d.%m.%Y"), program_id) < days_left:  # 29 Feb edge
        exam += timedelta(days=1)
    return exam.strftime("%d.%m.%Y")


def _emp(n: int, exam_date: str, need: int = 1, program: int = 1, extra=None):
    eid = EmployeesRepo.upsert(dict(last_name="Тестов%d" % n, first_name="Тест", middle_name="Тестович",
                                    snils="112-233-445 %02d" % (90 + n), position="Инженер",
                                    required_programs=str(program)))
    EmployeeProgramsRepo.upsert(eid, dict(program_id=program, need_training=need, exam_date=exam_date,
                                          protocol="П-1", result=1))
    for prog, ed in (extra or []):
        EmployeeProgramsRepo.upsert(eid, dict(program_id=prog, need_training=1, exam_date=ed,
                                              protocol="П-2", result=1))
    return eid


# -- days_to_expiry ---------------------------------------------------------------

@pytest.mark.parametrize("left", [0, 1, 60, 61, 90])
def test_days_to_expiry_boundaries(left):
    assert days_to_expiry(exam_for(left), 1) == left


def test_days_to_expiry_past_is_negative():
    assert days_to_expiry(exam_for(-5), 1) == -5


@pytest.mark.parametrize("bad", ["", None, "   ", "not a date", "31.02.2025", "2025-01-01"])
def test_days_to_expiry_empty_or_invalid_is_none(bad):
    assert days_to_expiry(bad, 1) is None


def test_days_to_expiry_respects_b_period():
    d = exam_for(0, 7)
    assert days_to_expiry(d, 7, True) == 0
    assert days_to_expiry(d, 7, False) < 0  # 1-year branch: long past


# -- employee_expires_within ------------------------------------------------------

def test_employee_expires_within_rules():
    from tabs.summary_expiry import employee_expires_within

    def pr(left, need=1, pid=1):
        return {"need_training": need, "status": "trained", "exam_date": exam_for(left, pid),
                "program_id": pid, "result": 1}

    assert employee_expires_within([pr(60)], 60)
    assert not employee_expires_within([pr(61)], 60)
    assert employee_expires_within([pr(61)], 90)
    assert not employee_expires_within([pr(-5)], 90)              # expired: counted elsewhere
    assert not employee_expires_within([pr(10), pr(-5, pid=2)], 60)  # one expired program wins
    assert not employee_expires_within([pr(10), {"need_training": 1, "status": "not_trained",
                                                 "exam_date": "", "program_id": 2}], 60)
    assert not employee_expires_within([pr(10, need=0)], 60)       # not required
    assert employee_expires_within([pr(10), pr(300, pid=2)], 30)   # soonest program decides
    assert not employee_expires_within([], 60)


# -- sidebar counter --------------------------------------------------------------

def test_compute_status_counts_expiring(app, summary_db):
    from utils.sidebar import compute_status_counts
    _emp(1, exam_for(10))                          # expiring
    _emp(2, exam_for(60))                          # expiring (edge)
    _emp(3, exam_for(61))                          # later
    _emp(4, exam_for(-3))                          # expired
    _emp(5, "")                                    # not trained
    _emp(6, exam_for(5), need=0)                   # not required
    _emp(7, exam_for(400), extra=[(2, exam_for(20))])  # second program soon
    total, expired, not_trained, _records, expiring = compute_status_counts()
    assert (total, expired, not_trained, expiring) == (7, 1, 1, 3)


def test_sidebar_set_counts_shows_expiring(app):
    from utils.sidebar import Sidebar
    side = Sidebar("3.10.0")
    side.set_counts(10, 2, 3, 4, 5)
    assert side.expiring_value.text() == "5"


# -- C2: today block on low windows -----------------------------------------------

def test_sidebar_today_box_hides_on_low_window(app):
    from utils.sidebar import Sidebar
    side = Sidebar("3.10.0")
    side.show()  # resize events reach a widget only once it is shown
    side.resize(220, 600)
    assert side.today_box.isHidden()
    side.resize(220, 690)  # 1366x728 screen: ~690 px client
    assert not side.today_box.isHidden()
    side.resize(220, 800)
    assert not side.today_box.isHidden()
    side.resize(220, 600)
    assert side.today_box.isHidden()
    side.close()


# -- summary chip -----------------------------------------------------------------

def test_summary_chip_counts_filters_and_persists(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    from tabs.send_history_panel import load_ui_pref
    _emp(1, exam_for(10))
    _emp(2, exam_for(45))
    _emp(3, exam_for(80))
    _emp(4, exam_for(-3))
    tab = EmployeeSummaryTab()
    try:
        assert tab._proxy.rowCount() == 4
        assert tab._expiry.chip.text() == "Истекает скоро · 2"
        tab._expiry.chip.click()
        assert tab._proxy.rowCount() == 2
        tab._expiry.combo.setCurrentIndex(0)  # 30 days
        assert load_ui_pref("summary_expiry_days", None) == 30
        assert tab._proxy.rowCount() == 1
        assert tab._expiry.chip.text() == "Истекает скоро · 1"
        tab._expiry.combo.setCurrentIndex(2)  # 90 days
        assert tab._proxy.rowCount() == 3
        tab._expiry.chip.click()  # off
        assert tab._proxy.rowCount() == 4
    finally:
        tab.deleteLater()

    from tabs.summary_expiry import ExpiryFilter
    assert ExpiryFilter().days() == 90  # restored from the saved preference
