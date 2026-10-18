import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication, QTableView
from PySide6.QtGui import QStandardItemModel

from utils.ui_helpers import HeaderStatePersistence, TABLE_LAYOUTS_FILE


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _table(columns=5):
    view = QTableView()
    view.setModel(QStandardItemModel(0, columns))
    return view


class TestHeaderStatePersistence:
    def test_widths_and_hidden_columns_survive_restart(self, qapp, tmp_path):
        view = _table()
        p = HeaderStatePersistence(view.horizontalHeader(), "t", data_dir=str(tmp_path))
        assert p.restored is False
        view.setColumnWidth(1, 234)
        view.setColumnHidden(3, True)
        p.save()

        view2 = _table()
        p2 = HeaderStatePersistence(view2.horizontalHeader(), "t", data_dir=str(tmp_path))
        assert p2.restored is True
        assert view2.columnWidth(1) == 234
        assert view2.isColumnHidden(3)

    def test_column_count_change_ignores_saved_state(self, qapp, tmp_path):
        view = _table(5)
        p = HeaderStatePersistence(view.horizontalHeader(), "t", data_dir=str(tmp_path))
        view.setColumnWidth(0, 300)
        p.save()

        view2 = _table(6)
        p2 = HeaderStatePersistence(view2.horizontalHeader(), "t", data_dir=str(tmp_path))
        assert p2.restored is False
        assert view2.columnWidth(0) != 300

    def test_keys_are_independent_and_file_tolerates_garbage(self, qapp, tmp_path):
        (tmp_path / TABLE_LAYOUTS_FILE).write_text("not json", encoding="utf-8")
        a, b = _table(), _table()
        pa = HeaderStatePersistence(a.horizontalHeader(), "a", data_dir=str(tmp_path))
        pb = HeaderStatePersistence(b.horizontalHeader(), "b", data_dir=str(tmp_path))
        a.setColumnWidth(0, 150); pa.save()
        b.setColumnWidth(0, 250); pb.save()
        data = json.loads((tmp_path / TABLE_LAYOUTS_FILE).read_text(encoding="utf-8"))
        assert set(data) == {"a", "b"}
        assert all(v["columns"] == 5 for v in data.values())

    def test_resize_schedules_debounced_save(self, qapp, tmp_path):
        view = _table()
        p = HeaderStatePersistence(view.horizontalHeader(), "t", data_dir=str(tmp_path))
        view.setColumnWidth(2, 177)
        assert p._timer.isActive()
        assert not (tmp_path / TABLE_LAYOUTS_FILE).exists()


class TestSummarySettingsCompat:
    """UX-04: the B-period toggle is gone; legacy b_period_3years=False is ignored."""

    def test_legacy_false_flag_ignored(self, tmp_path):
        from tabs.employee_summary_tab import EmployeeSummaryTab
        (tmp_path / "summary_programs.json").write_text(
            json.dumps({"programs": ["1", "18"], "b_period_3years": False}), encoding="utf-8")
        saved = EmployeeSummaryTab._load_saved_settings(str(tmp_path))
        assert saved == {"programs": ["1", "18"]}

    def test_save_no_longer_writes_flag(self, tmp_path):
        from tabs.employee_summary_tab import EmployeeSummaryTab
        EmployeeSummaryTab._save_settings(str(tmp_path), ["3"])
        data = json.loads((tmp_path / "summary_programs.json").read_text(encoding="utf-8"))
        assert data == {"programs": ["3"]}
