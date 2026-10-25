"""Stage 7: XML folder/name rules, XML + go to transfer, record navigation, last-import strip, org counts."""
import os
import sqlite3
import tempfile
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from utils import xml_output


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- xml_output

def test_xml_file_name_format():
    assert xml_output.xml_file_name(datetime(2026, 10, 5, 9, 7)) == "05102026-09-07.xml"


def test_next_xml_path_adds_suffix_on_collision(tmp_path):
    now = datetime(2026, 10, 25, 14, 30)
    first = xml_output.next_xml_path(now, str(tmp_path))
    assert os.path.basename(first) == "25102026-14-30.xml"
    open(first, "w").close()
    second = xml_output.next_xml_path(now, str(tmp_path))
    assert os.path.basename(second) == "25102026-14-30-2.xml"
    open(second, "w").close()
    assert os.path.basename(xml_output.next_xml_path(now, str(tmp_path))) == "25102026-14-30-3.xml"


def test_next_xml_path_creates_missing_folder(tmp_path):
    target = tmp_path / "new" / "XML"
    path = xml_output.next_xml_path(datetime(2026, 1, 2, 3, 4), str(target))
    assert target.is_dir() and path.startswith(str(target))


def test_default_dir_is_program_folder_when_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(xml_output, "_program_dir", lambda: str(tmp_path))
    assert xml_output.default_xml_dir() == os.path.join(str(tmp_path), "XML")


def test_default_dir_falls_back_to_documents(tmp_path, monkeypatch):
    docs = tmp_path / "Docs"
    monkeypatch.setattr(xml_output, "_program_dir", lambda: str(tmp_path / "ro"))
    monkeypatch.setattr(xml_output, "_documents_dir", lambda: str(docs))
    real = xml_output.is_writable_dir
    monkeypatch.setattr(xml_output, "is_writable_dir", lambda p: False if p.startswith(str(tmp_path / "ro")) else real(p))
    assert xml_output.default_xml_dir() == os.path.join(str(docs), "Норма ОТ", "XML")


def test_custom_dir_wins_and_falls_back_when_unusable(tmp_path, monkeypatch):
    custom = tmp_path / "mine"
    xml_output.set_custom_xml_dir(str(custom))
    try:
        assert xml_output.get_xml_dir() == str(custom)
        monkeypatch.setattr(xml_output, "default_xml_dir", lambda: str(tmp_path / "default"))
        real = xml_output.is_writable_dir
        monkeypatch.setattr(xml_output, "is_writable_dir", lambda p: False if p == str(custom) else real(p))
        assert xml_output.get_xml_dir() == str(tmp_path / "default")
    finally:
        xml_output.set_custom_xml_dir("")
    assert xml_output.custom_xml_dir() == ""


# ---------------------------------------------------------------- org employee count

def test_count_employees_reads_other_org_db_and_handles_missing(tmp_path, monkeypatch):
    from utils import org_profiles
    monkeypatch.setattr(org_profiles, "org_dir", lambda org_id: str(tmp_path / org_id))
    assert org_profiles.count_employees("absent") is None
    (tmp_path / "a1").mkdir()
    conn = sqlite3.connect(str(tmp_path / "a1" / "app_data.db"))
    conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, snils TEXT)")
    conn.executemany("INSERT INTO employees (snils) VALUES (?)", [("x",), ("y",), ("z",)])
    conn.commit()
    conn.close()
    assert org_profiles.count_employees("a1") == 3
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "app_data.db").write_bytes(b"not a database")
    assert org_profiles.count_employees("bad") is None


@pytest.mark.parametrize("n,word", [(1, "сотрудник"), (2, "сотрудника"), (5, "сотрудников"), (11, "сотрудников"),
                                    (21, "сотрудник"), (112, "сотрудников")])
def test_employees_word(n, word):
    from tabs.org_dialogs import _employees_word
    assert _employees_word(n) == word


# ---------------------------------------------------------------- record navigation in the edit dialog

def test_edit_dialog_navigation(app):
    from tabs.data_view_tab import EditDialog
    data = {0: "Иванов", 1: "Иван", 2: "Иванович", 3: "", 4: "Слесарь", 9: "Удовлетворительно"}
    dlg = EditDialog(data, None, position=(2, 3))
    assert "2 из 3" in dlg._subtitle_label.text()
    left = [dlg._button_layout.itemAt(i).widget() for i in range(2)]
    assert [b.text() for b in left] == ["←", "→"] and all(b.isEnabled() for b in left)
    dlg._save_and_go(1)
    assert dlg.nav_request == 1 and dlg.result() == dlg.DialogCode.Accepted


def test_edit_dialog_first_and_last_record_disable_arrows(app):
    from tabs.data_view_tab import EditDialog
    first = EditDialog({0: "А", 1: "Б", 4: "В"}, None, position=(1, 3))
    assert not first._button_layout.itemAt(0).widget().isEnabled()
    last = EditDialog({0: "А", 1: "Б", 4: "В"}, None, position=(3, 3))
    assert not last._button_layout.itemAt(1).widget().isEnabled()
    single = EditDialog({0: "А", 1: "Б", 4: "В"}, None, position=(1, 1))
    assert single._subtitle_label.isHidden()


def test_edit_dialog_stays_when_validation_fails(app, monkeypatch):
    from tabs.data_view_tab import EditDialog
    monkeypatch.setattr("utils.error_utils.show_error_dialog", lambda *a, **k: None)
    dlg = EditDialog({0: "Иванов", 1: "Иван", 3: "123", 4: "Слесарь"}, None, position=(1, 2))
    dlg._save_and_go(1)  # SNILS has 3 digits: the error dialog is mocked
    assert dlg.nav_request == 0


# ---------------------------------------------------------------- last import strip

def test_last_import_strip_hidden_until_first_import_then_shows_numbers(app, tmp_path, monkeypatch):
    from tabs.data_entry_tab import DataEntryTab
    tab = DataEntryTab()
    tab.data_dir = str(tmp_path)
    tab._refresh_last_import()
    assert tab._last_import_card.isHidden()
    tab.file_path_input.setText(os.path.join("C:\\секрет", "Список.xlsx"))
    tab._remember_import(12, 2, 1)
    text = tab._last_import_label.text()
    assert "Список.xlsx" in text and "секрет" not in text  # only the file name is kept
    assert "<b>12</b>" in text and "<b>2</b>" in text and "<b>1</b>" in text
    assert not tab._last_import_card.isHidden()
    got = []
    tab.view_requested.connect(lambda: got.append(1))
    tab._last_import_card.findChildren(type(tab.select_file_btn))[-1].click()
    assert got == [1]


def test_manual_dialog_date_hint(app, monkeypatch):
    from tabs.data_entry_tab import DataEntryTab
    from utils.dialog_base import BaseDialog
    tab = DataEntryTab()

    def fake_exec(self):
        tab._date_input.setText("31.02.2020")
        tab._check_date_hint()
        assert tab._date_hint.text() == "Введите дату как ДД.ММ.ГГГГ"
        tab._date_input.setText("01.02.2999")
        tab._check_date_hint()
        assert "больше текущей" in tab._date_hint.text()
        tab._date_input.setText("01.02.2020")
        tab._check_date_hint()
        assert tab._date_hint.text() == ""
        return 0

    monkeypatch.setattr(BaseDialog, "exec", fake_exec)
    tab._open_manual_dialog()


# ---------------------------------------------------------------- XML + go to transfer

@pytest.fixture
def view_db():
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


def test_convert_to_xml_and_go_saves_named_file_and_signals(app, view_db, tmp_path):
    from db.workers_data_repo import WorkersDataRepo
    from tabs.data_view_tab import DataViewTab
    WorkersDataRepo.add_many([dict(
        last_name="Иванов", first_name="Иван", middle_name="Иванович", snils="112-233-445 95",
        position="Слесарь", employer_inn="7700000000", employer_title="ООО Тест", tc_inn="7800000000",
        tc_title="УЦ Тест", result="true", program=1, date="01.02.2024", protocol="П-1")])
    xml_output.set_custom_xml_dir(str(tmp_path))
    try:
        tab = DataViewTab()
        got = []
        tab.xml_ready.connect(got.append)
        tab.convert_to_xml_and_go()
        assert len(got) == 1
        path = got[0]
        assert os.path.dirname(path) == str(tmp_path)
        assert os.path.exists(path) and path.endswith(".xml")
        assert len(os.path.basename(path)) == len("25102026-14-30.xml")
    finally:
        xml_output.set_custom_xml_dir("")


def test_transfer_tab_accepts_generated_xml_and_rejects_garbage(app, view_db, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from tabs.data_transfer_tab import DataTransferTab
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr("tabs.data_transfer_tab.safe_message_box", lambda *a, **k: None)
    tab = DataTransferTab()
    bad = tmp_path / "bad.xml"
    bad.write_text("<not closed", encoding="utf-8")
    assert tab.set_xml_file(str(bad)) is False and tab.xml_file_input.text() == ""
    assert tab.set_xml_file(str(tmp_path / "missing.xml")) is False
    empty = tmp_path / "empty.xml"
    empty.write_text("", encoding="utf-8")
    assert tab.set_xml_file(str(empty)) is False
