"""3.10 B4 (Russian standard dialog buttons) and B7 (sidebar counters, «Сводка» empty-state hint).

All names are synthetic. No modal dialog is opened: the tests only build widgets.
"""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def summary_db():
    from db.database import DatabaseManager
    from db.schema import create_schema
    from utils.crypto import clear_caches
    clear_caches()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    db = DatabaseManager.get_instance(path)
    db.initialize()
    create_schema()
    yield db
    db.close_all()
    os.remove(path)


# -- B4: translator -------------------------------------------------------------

def test_qtbase_ru_translator_makes_cancel_button_russian(app):
    # Same calls as main.py right after QApplication(...), but on a throwaway translator
    # so the rest of the test session keeps English strings.
    translator = QTranslator(app)
    loaded = translator.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    assert loaded, "qtbase_ru.qm not found in the Qt translations path"
    app.installTranslator(translator)
    try:
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        assert box.button(QDialogButtonBox.StandardButton.Cancel).text() == "Отмена"
    finally:
        app.removeTranslator(translator)


# -- B7: sidebar counters --------------------------------------------------------

def test_compute_status_counts_returns_four_numbers(app, monkeypatch):
    from db.employee_programs_repo import EmployeeProgramsRepo
    from db.employees_repo import EmployeesRepo
    from db.workers_data_repo import WorkersDataRepo
    from utils.sidebar import compute_status_counts

    employees = [{"id": 1}, {"id": 2}, {"id": 3}]
    programs = {
        1: [{"need_training": 1, "status": "not_trained", "program_id": 1, "exam_date": ""}],
        2: [{"need_training": 0, "status": "not_trained", "program_id": 2, "exam_date": ""}],
        3: [],
    }
    monkeypatch.setattr(EmployeesRepo, "get_all", staticmethod(lambda *a, **k: employees))
    monkeypatch.setattr(EmployeeProgramsRepo, "get_by_employee_ids",
                        staticmethod(lambda ids: {i: programs.get(i, []) for i in ids}))
    monkeypatch.setattr(WorkersDataRepo, "count", staticmethod(lambda: 7))

    result = compute_status_counts()
    assert len(result) == 4
    employees_total, expired, not_trained, records = result
    assert (employees_total, not_trained, records) == (3, 1, 7)
    assert expired == 0


def test_sidebar_labels_and_set_counts(app):
    from utils.sidebar import Sidebar

    side = Sidebar("3.10.0")
    texts = {lbl.text() for lbl in side.findChildren(QLabel)}
    assert "Сотрудников в сводке" in texts
    assert "Записей к отправке" in texts
    assert "Внесено работников" not in texts

    side.set_counts(10, 2, 3, 4)
    assert side.employees_value.text() == "10"
    assert side.expired_value.text() == "2"
    assert side.not_trained_value.text() == "3"
    assert side.records_value.text() == "4"


def test_sidebar_refresh_counts_writes_four_values(app, monkeypatch):
    from utils import sidebar as sidebar_mod

    monkeypatch.setattr(sidebar_mod, "compute_status_counts", lambda: (5, 1, 2, 9))
    side = sidebar_mod.Sidebar("3.10.0")
    side.refresh_counts()
    assert side.records_value.text() == "9"
    assert side.employees_value.text() == "5"


# -- B7: «Сводка» empty-state hint -------------------------------------------------

def _seed_one_employee():
    from db.employee_programs_repo import EmployeeProgramsRepo
    from db.employees_repo import EmployeesRepo
    eid = EmployeesRepo.upsert(dict(last_name="Тестов", first_name="Тест", middle_name="Тестович",
                                    snils="112-233-445 95", position="Тестовая должность",
                                    required_programs="1"))
    EmployeeProgramsRepo.upsert(eid, dict(program_id=1, need_training=1, exam_date="", protocol="",
                                          result=None))


def test_summary_empty_hint_names_real_buttons(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    tab = EmployeeSummaryTab()
    try:
        overlay = tab._empty_overlay
        text = overlay.text()
        assert "«Добавить сотрудника»" in text
        assert "«Импорт XLSX»" in text
        assert "«Перенести в сводку»" in text
        assert "«Просмотр данных»" in text
        assert not overlay.isHidden()
    finally:
        tab.deleteLater()


def test_summary_empty_hint_hides_when_employees_exist(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    _seed_one_employee()
    tab = EmployeeSummaryTab()
    try:
        tab.refresh_table()
        assert tab._empty_overlay.isHidden()
    finally:
        tab.deleteLater()
