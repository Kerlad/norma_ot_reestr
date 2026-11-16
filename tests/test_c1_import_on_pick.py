"""C1: выбор файла сразу запускает импорт; отмена диалога не импортирует."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication

from tabs import data_entry_tab
from tabs.data_entry_tab import DataEntryTab


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    t = DataEntryTab.__new__(DataEntryTab)
    # минимальная заглушка без полной инициализации UI
    from PySide6.QtWidgets import QLineEdit, QWidget
    QWidget.__init__(t)
    t.file_path_input = QLineEdit()
    t._is_xlsx_importing = False
    t.upload_file = MagicMock()
    return t


def test_pick_starts_import_with_default_dir(tab):
    with patch.object(data_entry_tab, "default_save_dir", return_value="X"), \
            patch.object(data_entry_tab.QFileDialog, "getOpenFileName",
                         return_value=("a.xlsx", "")) as dlg:
        tab.select_file()
    assert dlg.call_args[0][2] == "X"
    assert tab.file_path_input.text() == "a.xlsx"
    tab.upload_file.assert_called_once()


def test_cancel_does_not_import(tab):
    with patch.object(data_entry_tab.QFileDialog, "getOpenFileName", return_value=("", "")):
        tab.select_file()
    tab.upload_file.assert_not_called()
    assert tab.file_path_input.text() == ""


def test_drop_imports_once(tab):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile("C:/x/a.xlsx"), QUrl.fromLocalFile("C:/x/b.xlsx")])
    ev = MagicMock()
    ev.mimeData.return_value = md
    tab.dropEvent(ev)
    tab.upload_file.assert_called_once()
