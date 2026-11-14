"""A6/A7: start folder of «Save as» dialogs, XLSX template via a save dialog."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from utils import xml_output, save_paths


@pytest.fixture
def docs(tmp_path, monkeypatch):
    d = tmp_path / "Docs"
    monkeypatch.setattr(xml_output, "_documents_dir", lambda: str(d))
    monkeypatch.setattr(xml_output, "custom_xml_dir", lambda: "")
    return d


def _capture_dialog(monkeypatch, result=("", "")):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        return result

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake)
    return calls


def test_default_save_dir_is_documents_and_not_created(docs):
    expected = os.path.join(str(docs), "Норма ОТ", "XML")
    assert save_paths.default_save_dir() == expected
    assert save_paths.suggest_path("a.xlsx") == os.path.join(expected, "a.xlsx")
    assert not docs.exists()


def test_default_save_dir_uses_custom_folder(docs, tmp_path, monkeypatch):
    mine = tmp_path / "mine"
    mine.mkdir()
    monkeypatch.setattr(xml_output, "custom_xml_dir", lambda: str(mine))
    assert save_paths.default_save_dir() == str(mine)


def test_default_save_dir_is_not_app_data_dir(docs):
    from utils.app_paths import get_app_data_dir
    assert not save_paths.default_save_dir().startswith(get_app_data_dir())


def test_create_template_saves_where_user_chose(docs, tmp_path, monkeypatch):
    from openpyxl import load_workbook
    from importers.xlsx_importer import COLUMNS
    from tabs import data_entry_tab
    from tabs.data_entry_tab import DataEntryTab
    from utils.app_paths import get_app_data_dir

    target = tmp_path / "out" / "Шаблон.xlsx"
    target.parent.mkdir()
    calls = _capture_dialog(monkeypatch, (str(target), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pytest.fail("no warning expected"))
    toasts = []
    monkeypatch.setattr(data_entry_tab.Toast, "success", classmethod(lambda cls, parent, msg, *a, **k: toasts.append(msg)))

    fake = SimpleNamespace(data_dir=get_app_data_dir())
    DataEntryTab.create_template(fake)

    assert calls[0][2].startswith(save_paths.default_save_dir())
    assert target.is_file()
    assert [c.value for c in load_workbook(str(target)).active[1]] == COLUMNS
    assert toasts == ["Шаблон сохранён"]
    assert not os.path.exists(os.path.join(get_app_data_dir(), "Шаблон.xlsx"))


def test_create_template_cancel_writes_nothing(docs, monkeypatch):
    from tabs.data_entry_tab import DataEntryTab
    _capture_dialog(monkeypatch, ("", ""))
    DataEntryTab.create_template(SimpleNamespace(data_dir=""))
    assert not docs.exists()


def test_create_template_error_text_has_no_exception(docs, tmp_path, monkeypatch):
    from tabs import data_entry_tab
    from tabs.data_entry_tab import DataEntryTab
    _capture_dialog(monkeypatch, (str(tmp_path / "missing_dir" / "x.xlsx"), ""))
    shown = []
    monkeypatch.setattr(data_entry_tab, "safe_message_box", lambda *a, **k: shown.append(a[-1]))
    DataEntryTab.create_template(SimpleNamespace(data_dir=""))
    assert shown == ["Не удалось сохранить шаблон. Проверьте, что файл не открыт в Excel."]


def test_error_report_dialog_starts_in_default_folder(docs, monkeypatch):
    from tabs.data_entry_tab import DataEntryTab
    calls = _capture_dialog(monkeypatch)
    DataEntryTab._export_error_report(SimpleNamespace(), SimpleNamespace(close=lambda: None))
    assert calls[0][2].startswith(save_paths.default_save_dir())
    assert os.path.basename(calls[0][2]).startswith("Ошибки_")


def test_journal_template_dialog_starts_in_default_folder(docs, monkeypatch):
    from tabs.exam_journal_tab import ExamJournalTab
    calls = _capture_dialog(monkeypatch)
    ExamJournalTab._create_journal_template(SimpleNamespace())
    assert calls[0][2] == save_paths.suggest_path("Шаблон_журнала.xlsx")


def test_data_view_export_starts_in_default_folder(docs, monkeypatch):
    from tabs.data_view_tab import DataViewTab
    calls = _capture_dialog(monkeypatch)
    fake = SimpleNamespace(_model=SimpleNamespace(rowCount=lambda: 1))
    DataViewTab._export_xlsx(fake)
    assert calls[0][2].startswith(save_paths.default_save_dir())
    assert os.path.basename(calls[0][2]).startswith("Данные_")
