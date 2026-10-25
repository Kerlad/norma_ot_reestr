"""Three-state sorting (ascending -> descending -> natural order) and smart keys."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

from utils import table_sort as ts


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_dates_sort_by_value_not_text():
    keys = sorted(["15.03.2024", "01.12.2023", "02.01.2025"], key=ts.smart_key)
    assert keys == ["01.12.2023", "15.03.2024", "02.01.2025"]


def test_numbers_sort_by_value_and_empties_go_last():
    values = ["10", "9", "", "2", "—", "abc"]
    ordered = sorted(values, key=ts.smart_key)
    assert ordered[:3] == ["2", "9", "10"] and ordered[3] == "abc"
    assert set(ordered[4:]) == {"", "—"}


def _table(app, values):
    table = QTableWidget(len(values), 2)
    for r, (a, b) in enumerate(values):
        table.setItem(r, 0, QTableWidgetItem(a))
        table.setItem(r, 1, QTableWidgetItem(b))
    return table


def _col(table, c=0):
    return [table.item(r, c).text() for r in range(table.rowCount())]


def test_widget_header_click_cycles_asc_desc_natural(app):
    table = _table(app, [("b", "2"), ("c", ""), ("a", "1")])
    sorter = ts.install_widget_sort(table)
    sorter.on_clicked(0)
    assert _col(table) == ["a", "b", "c"]
    sorter.on_clicked(0)
    assert _col(table) == ["c", "b", "a"]
    sorter.on_clicked(0)
    assert _col(table) == ["b", "c", "a"]  # natural order restored
    assert table.horizontalHeader().sortIndicatorSection() == -1


def test_empty_cells_stay_last_in_both_directions(app):
    table = _table(app, [("b", "2"), ("c", ""), ("a", "1")])
    sorter = ts.install_widget_sort(table)
    sorter.on_clicked(1)
    assert _col(table, 1) == ["1", "2", ""]
    sorter.on_clicked(1)
    assert _col(table, 1) == ["2", "1", ""]


def test_switching_column_restarts_at_ascending(app):
    table = _table(app, [("b", "2"), ("c", "3"), ("a", "1")])
    sorter = ts.install_widget_sort(table)
    sorter.on_clicked(0)
    sorter.on_clicked(0)
    sorter.on_clicked(1)
    assert sorter.order == Qt.SortOrder.AscendingOrder and _col(table, 1) == ["1", "2", "3"]


def test_reload_done_keeps_current_sort(app):
    table = _table(app, [("b", "2"), ("a", "1")])
    sorter = ts.install_widget_sort(table)
    sorter.on_clicked(0)
    table.setRowCount(0)
    table.setRowCount(2)
    for r, text in enumerate(["z", "y"]):
        table.setItem(r, 0, QTableWidgetItem(text))
    sorter.reload_done()
    assert _col(table) == ["y", "z"]


def test_journal_model_three_state_sort(app):
    from types import SimpleNamespace
    from utils.table_models import ExamJournalTableModel

    def rec(protocol, date):
        return SimpleNamespace(protocol=protocol, exam_date=date, last_name="", first_name="", middle_name="",
                               snils="", base_no="", program_id="", program_title="", position="",
                               result="", set_id="", send_date="", status="pending", uuid=protocol)

    model = ExamJournalTableModel()
    model.load_records([rec("П-2", "15.03.2024"), rec("П-3", "01.12.2023"), rec("П-1", "02.01.2025")])
    model.sort(1, Qt.SortOrder.AscendingOrder)
    assert [r.protocol for r in model.get_records()] == ["П-3", "П-2", "П-1"]
    model.sort(1, Qt.SortOrder.DescendingOrder)
    assert [r.protocol for r in model.get_records()] == ["П-1", "П-2", "П-3"]
    model.sort(-1)
    assert [r.protocol for r in model.get_records()] == ["П-2", "П-3", "П-1"]
    model.sort(0)
    model.load_records([rec("П-9", ""), rec("П-5", "")])
    assert [r.protocol for r in model.get_records()] == ["П-5", "П-9"]  # sort survives a reload


def test_proxy_sorts_dates_as_dates(app):
    from PySide6.QtGui import QStandardItem, QStandardItemModel
    source = QStandardItemModel()
    for text in ("15.03.2024", "01.12.2023", "02.01.2025", ""):
        source.appendRow([QStandardItem(text)])
    proxy = ts.SmartSortProxyModel()
    proxy.setSourceModel(source)
    proxy.sort(0, Qt.SortOrder.AscendingOrder)
    assert [proxy.index(r, 0).data() for r in range(4)] == ["01.12.2023", "15.03.2024", "02.01.2025", ""]
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    assert [proxy.index(r, 0).data() for r in range(4)] == ["02.01.2025", "15.03.2024", "01.12.2023", ""]
    proxy.sort(-1)
    assert [proxy.index(r, 0).data() for r in range(4)] == ["15.03.2024", "01.12.2023", "02.01.2025", ""]
