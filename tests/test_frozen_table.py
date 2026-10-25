"""Frozen columns, grouped header and the redesigned «Сводка» table."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication

from utils.frozen_table import FrozenColumnsTable


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _model(rows=30, cols=20):
    model = QStandardItemModel(rows, cols)
    for r in range(rows):
        for c in range(cols):
            model.setItem(r, c, QStandardItem("r%dc%d" % (r, c)))
    for c in range(cols):
        model.setHeaderData(c, Qt.Orientation.Horizontal, "H%d" % c)
    return model


def test_frozen_part_width_is_sum_of_real_column_widths(app):
    table = FrozenColumnsTable(3)
    table.setModel(_model())
    table.resize(600, 300)
    table.show()
    table.setColumnWidth(0, 200)
    table.setColumnWidth(1, 90)
    table.setColumnWidth(2, 60)
    app.processEvents()
    frozen = table.frozen_view()
    assert frozen.width() == 350
    assert [frozen.isColumnHidden(c) for c in (0, 1, 2, 3, 19)] == [False, False, False, True, True]


def test_resizing_a_frozen_column_updates_the_overlay(app):
    table = FrozenColumnsTable(2)
    table.setModel(_model())
    table.resize(600, 300)
    table.show()
    app.processEvents()
    before = table.frozen_view().width()
    table.frozen_view().setColumnWidth(0, table.columnWidth(0) + 50)
    app.processEvents()
    assert table.frozen_view().width() == before + 50
    assert table.columnWidth(0) == table.frozen_view().columnWidth(0)


def test_frozen_stays_put_on_horizontal_scroll_and_follows_vertical(app):
    table = FrozenColumnsTable(3)
    table.setModel(_model(rows=80))
    table.resize(500, 250)
    table.show()
    app.processEvents()
    x = table.frozen_view().x()
    table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
    table.verticalScrollBar().setValue(120)
    app.processEvents()
    assert table.frozen_view().x() == x
    assert table.frozen_view().verticalScrollBar().value() == 120


def test_selection_is_shared_between_both_views(app):
    table = FrozenColumnsTable(3)
    table.setModel(_model())
    table.show()
    table.selectRow(4)
    assert table.frozen_view().selectionModel() is table.selectionModel()
    assert [i.row() for i in table.selectionModel().selectedRows()] == [4]


def test_grouped_header_has_two_levels(app):
    table = FrozenColumnsTable(3)
    table.setModel(_model())
    table.horizontalHeader().set_groups([(3, 4, "№1"), (7, 4, "№2")])
    table.set_header_levels(2)
    assert table.horizontalHeader().height() == 56 == table.frozen_header().height()


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


def _seed():
    from db.employee_programs_repo import EmployeeProgramsRepo
    from db.employees_repo import EmployeesRepo
    people = [("Алексеев", "Борис", "Ильич", "Слесарь", "100-200-300 10", "15.03.2024"),
              ("Борисова", "Вера", "Петровна", "Бухгалтер", "100-200-301 11", None),
              ("Яковлев", "Глеб", "Олегович", "Кладовщик", "100-200-302 12", "01.02.2020")]
    for last, first, mid, pos, snils, date in people:
        eid = EmployeesRepo.upsert(dict(last_name=last, first_name=first, middle_name=mid, snils=snils,
                                        position=pos, required_programs="1"))
        EmployeeProgramsRepo.upsert(eid, dict(program_id=1, need_training=1, exam_date=date,
                                              protocol="П-1", result=1))


def _names(tab):
    from tabs.employee_summary_tab import ROLE_FIO
    return [tab._proxy.index(r, 0).data(ROLE_FIO) for r in range(tab._proxy.rowCount())]


def test_summary_table_status_icons_and_two_line_name(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab, ROLE_POSITION, STATUS_TEXT
    _seed()
    tab = EmployeeSummaryTab()
    tab.resize(1200, 600)
    tab.show()
    assert tab._proxy.rowCount() == 3
    idx = tab._proxy.index(0, 0)
    assert idx.data(ROLE_POSITION) and "\n" in idx.data(Qt.ItemDataRole.DisplayRole)
    tips = {tab._proxy.index(r, 2).data(Qt.ItemDataRole.ToolTipRole) for r in range(3)}
    assert tips <= set(STATUS_TEXT.values())
    for r in range(3):  # status column: icon only, no text, accessible name present
        status_idx = tab._proxy.index(r, 2)
        assert status_idx.data(Qt.ItemDataRole.DisplayRole) in ("", None)
        assert status_idx.data(Qt.ItemDataRole.DecorationRole) is not None
        assert status_idx.data(Qt.ItemDataRole.AccessibleTextRole) in STATUS_TEXT.values()
    tab.deleteLater()


def test_summary_header_click_cycles_three_states(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    _seed()
    tab = EmployeeSummaryTab()
    natural = _names(tab)
    tab._sorter.on_clicked(0)
    assert _names(tab) == sorted(natural, key=str.lower)
    tab._sorter.on_clicked(0)
    assert _names(tab) == sorted(natural, key=str.lower, reverse=True)
    tab._sorter.on_clicked(0)
    assert _names(tab) == natural
    tab.deleteLater()


def test_summary_status_sort_puts_not_trained_first(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    _seed()
    tab = EmployeeSummaryTab()
    tab._sorter.on_clicked(2)
    first = tab._proxy.index(0, 2).data(Qt.ItemDataRole.AccessibleTextRole)
    assert first == "Не обучен"
    tab.deleteLater()


def test_summary_selected_ids_and_toggle_use_model_rows(app, summary_db):
    from tabs.employee_summary_tab import EmployeeSummaryTab
    _seed()
    tab = EmployeeSummaryTab()
    tab.table.selectRow(1)
    assert len(tab._selected_emp_ids()) == 1
    tab.deleteLater()
