"""C3: поиск в справочнике программ и очистка merge_program_ids."""
import pytest
from PySide6.QtWidgets import QApplication

from utils.programs_picker import ProgramsPickerDialog, merge_program_ids

ITEMS = [("1", "Первая помощь"), ("3", "Общие вопросы"), ("10", "Пожароопасные работы")]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _visible(dlg):
    return [dlg._list.item(i).data(0x0100) for i in range(dlg._list.count())
            if not dlg._list.item(i).isHidden()]


def test_search_by_title_case_insensitive(app):
    dlg = ProgramsPickerDialog(None, ITEMS)
    dlg._search.setText("ПОЖАР")
    assert _visible(dlg) == ["10"]
    dlg._search.setText("")
    assert _visible(dlg) == ["1", "3", "10"]


def test_search_by_number(app):
    dlg = ProgramsPickerDialog(None, ITEMS)
    dlg._search.setText("3")
    assert _visible(dlg) == ["3"]
    dlg._search.setText("1")
    assert _visible(dlg) == ["1", "10"]


def test_tooltip_has_full_title(app):
    dlg = ProgramsPickerDialog(None, ITEMS)
    # official (registry) wording, not the short UI label
    assert "Безопасные методы и приемы выполнения пожароопасных работ" in dlg._list.item(2).toolTip()


def test_search_matches_full_title(app):
    dlg = ProgramsPickerDialog(None, ITEMS)
    dlg._search.setText("приемы выполнения пожароопасных")
    visible = [dlg._list.item(i) for i in range(dlg._list.count()) if not dlg._list.item(i).isHidden()]
    assert len(visible) == 1 and "10" in visible[0].text()


def test_merge_drops_invalid():
    assert merge_program_ids("А", ["3"]) == "3"
    assert merge_program_ids("1, 5, x", ["3"]) == "1, 3"
    assert merge_program_ids("10, 2", ["2", "1"]) == "1, 2, 10"
