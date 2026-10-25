"""Redesigned dialogs: header/footer frame, shared programs picker, plan modes, no hard-coded colours."""
import glob
import io
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_base_dialog_has_header_and_footer_only_when_needed(app):
    from utils.dialog_base import BaseDialog
    dlg = BaseDialog(None, "Заголовок", subtitle="Пояснение")
    dlg.show()
    assert dlg._title_label.text() == "Заголовок"
    assert dlg._subtitle_label.text() == "Пояснение" and not dlg._subtitle_label.isHidden()
    assert not dlg._footer.isVisible()  # no buttons yet
    dlg.close()

    dlg = BaseDialog(None, "С кнопками")
    dlg.add_action_buttons("Сохранить", lambda: None)
    dlg.show()
    assert dlg._footer.isVisible()
    dlg.close()


def test_title_follows_set_window_title(app):
    from utils.dialog_base import BaseDialog
    dlg = BaseDialog(None, "Старый")
    dlg.setWindowTitle("Новый")
    assert dlg._title_label.text() == "Новый" and dlg.windowTitle() == "Новый"


def test_action_buttons_order_and_roles(app):
    from utils.dialog_base import BaseDialog
    dlg = BaseDialog(None, "Т")
    primary, secondary = dlg.add_action_buttons("Добавить", lambda: None, primary_role="danger")
    assert primary.property("role") == "danger" and secondary.property("role") == "secondary"
    layout = dlg._button_layout
    widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
    assert widgets == [secondary, primary]  # [Отмена] [главная]


def test_footer_buttons_keep_insertion_order_on_the_left(app):
    from utils.dialog_base import BaseDialog
    dlg = BaseDialog(None, "Т")
    first = dlg.add_footer_button("Первая", lambda: None)
    second = dlg.add_footer_button("Вторая", lambda: None)
    dlg.add_action_buttons("Ок", lambda: None)
    layout = dlg._button_layout
    assert layout.itemAt(0).widget() is first and layout.itemAt(1).widget() is second


def test_merge_program_ids_keeps_order_and_no_duplicates():
    from utils.programs_picker import merge_program_ids
    assert merge_program_ids("18, 3", ["3", "1"]) == "1, 3, 18"
    assert merge_program_ids("", ["29", "6"]) == "6, 29"


def test_programs_picker_returns_selected_in_catalog_order(app):
    from utils.programs_picker import ProgramsPickerDialog
    dlg = ProgramsPickerDialog(None, [("1", "Первая помощь"), ("2", "СИЗ"), ("3", "Общие")], ["2"])
    assert [it.isSelected() for it in (dlg._list.item(i) for i in range(3))] == [False, True, False]
    dlg._list.item(0).setSelected(True)
    dlg._accept_selected()
    assert dlg.selected_ids() == ["1", "2"]


def _row(priority="Низкий"):
    return {'last_name': 'Тестов', 'first_name': 'Т', 'middle_name': 'Т', 'snils': '000-000-000 00',
            'position': 'Инженер', 'program': '1', 'last_exam_date': '01.01.2024',
            'expiry_date': '01.01.2027', 'reason': 'Плановое', 'priority': priority}


def test_plan_dialog_mode_segment_switches_via_callback(app):
    from tabs.employee_summary_tab import PlanDialog
    seen = []
    dlg = PlanDialog([_row("Высокий"), _row()], "План", None, current_mode="year_current",
                     on_switch=seen.append)
    assert dlg._mode_buttons["year_current"].isChecked()
    dlg._switch("year_current", seen.append, "year_current")  # same mode: nothing happens
    assert seen == []
    dlg._switch("snapshot", seen.append, "year_current")
    QApplication.processEvents()
    assert seen == ["snapshot"]


def test_plan_dialog_sorts_by_priority_rank_and_restores(app):
    from tabs.employee_summary_tab import PlanDialog
    dlg = PlanDialog([_row("Низкий"), _row("Высокий"), _row("Средний")], "План")
    sorter = dlg.table._tristate_sort
    col = [dlg.table.item(r, 9).text() for r in range(3)]
    sorter.on_clicked(9)
    assert [dlg.table.item(r, 9).text() for r in range(3)] == ["Высокий", "Средний", "Низкий"]
    sorter.on_clicked(9)
    sorter.on_clicked(9)
    assert [dlg.table.item(r, 9).text() for r in range(3)] == col


def test_no_hardcoded_hex_colours_in_ui_code():
    """Colours come from the theme tokens (utils/tahoe_style.py). Deliberate exceptions:
    status icon fills (icons.py, toast.py) and the always-dark log view."""
    allowed = {"utils/tahoe_style.py", "utils/icons.py", "utils/toast.py", "utils/log_viewer_dialog.py"}
    hex_re = re.compile(r"#[0-9A-Fa-f]{6}\b")
    offenders = []
    for path in glob.glob("tabs/*.py") + glob.glob("utils/*.py") + ["main.py"]:
        if path.replace("\\", "/") in allowed:
            continue
        for no, line in enumerate(io.open(path, encoding="utf-8"), 1):
            if line.strip().startswith("#") or "hex" in line.lower():
                continue
            if hex_re.search(line):
                offenders.append("%s:%d" % (path, no))
    assert not offenders, offenders


def test_manual_dialog_add_and_more_clears_form(app, monkeypatch):
    """«Добавить и ещё» saves the record and keeps the dialog open for the next one."""
    from tabs import data_entry_tab as det
    tab = det.DataEntryTab()
    emitted = []
    tab.data_loaded.connect(lambda records, merge: emitted.append(records))
    monkeypatch.setattr(det.Toast, "success", classmethod(lambda cls, *a, **k: None))

    from utils.dialog_base import BaseDialog
    captured = {}

    def fake_exec(self):
        captured["dialog"] = self
        tab._last_name_input.setText("Иванов")
        tab._first_name_input.setText("Иван")
        tab._middle_name_input.setText("Иванович")
        tab._position_input.setText("Слесарь")
        tab._snils_input.setText("112-233-445 95")
        tab._program_input.setText("1")
        tab._protocol_input.setText("П-1")
        tab._date_input.setText("01.02.2024")
        tab._more_btn.click()
        return 0

    monkeypatch.setattr(BaseDialog, "exec", fake_exec)
    tab._open_manual_dialog()
    assert len(emitted) == 1 and emitted[0][0]["last_name"] == "Иванов"
    assert tab._last_name_input.text() == "" and tab._snils_input.text() == ""
    assert captured["dialog"].result() == 0  # not accepted: still open for the next entry
