import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QHeaderView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _row(i):
    return {
        'last_name': 'Тестов%d' % i, 'first_name': 'Тест', 'middle_name': 'Тестович',
        'snils': '000-000-000 0%d' % i, 'position': 'Инженер', 'program': 'А',
        'last_exam_date': '01.01.2024', 'expiry_date': '01.01.2027',
        'reason': 'Плановое', 'priority': 'Низкий',
    }


def test_plan_dialog_columns_are_resizable(app):
    from tabs.employee_summary_tab import PlanDialog
    dlg = PlanDialog([_row(1), _row(2)], "План")
    header = dlg.table.horizontalHeader()
    for col in range(dlg.table.columnCount()):
        assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive
    dlg.deleteLater()


def test_help_toc_follows_scroll(app):
    from utils.help_dialog import HelpDialog
    dlg = HelpDialog()
    dlg.resize(900, 600)
    dlg.show()
    app.processEvents()
    bar = dlg._content_scroll.verticalScrollBar()
    bar.setValue(dlg._section_groups[4].y())
    assert dlg._selected_index == 4
    bar.setValue(bar.maximum())
    assert dlg._selected_index == len(dlg._section_groups) - 1
    dlg._scroll_to_section(2)
    app.processEvents()
    assert dlg._selected_index == 2
    dlg.close()


def test_help_has_history_section():
    from utils.help_dialog import HELP_SECTIONS
    assert any(s["title"] == "История отправок" for s in HELP_SECTIONS)
