import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit

from db.database import DatabaseManager
from db.schema import create_schema
from db.send_history_repo import SendHistoryRepo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    d = DatabaseManager.get_instance(path)
    d.initialize()
    create_schema()
    yield d
    d.close_all()
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def tab(app, db):
    from tabs.data_transfer_tab import DataTransferTab
    t = DataTransferTab()
    yield t
    t.cleanup_threads()
    t.deleteLater()


def test_eye_button_hold_to_show(tab):
    btn = tab.api_key_toggle_btn
    assert not btn.icon().isNull()
    assert tab.api_key_input.echoMode() == QLineEdit.EchoMode.Password
    btn.pressed.emit()
    assert tab.api_key_input.echoMode() == QLineEdit.EchoMode.Normal
    btn.released.emit()
    assert tab.api_key_input.echoMode() == QLineEdit.EchoMode.Password


def test_status_icons_not_null(app):
    from utils.icons import status_icon
    for kind in ("signed", "deleted", "unsigned", "unknown"):
        assert not status_icon(kind).isNull()


def test_panel_rows_and_selection(tab):
    SendHistoryRepo.add("S1", "2026-10-25 10:00:00", 2, False, "signed")
    SendHistoryRepo.add("S2", "2026-10-26 11:30:00", 5, True, "unsigned")
    SendHistoryRepo.add("S3", "2026-10-24 09:05:00", 1, False, "deleted")
    panel = tab.history_panel
    panel.reload()
    assert panel.table.rowCount() == 3
    assert panel.table.item(0, 2).text() == "S2"
    assert panel.table.item(0, 1).text() == "26.10.2026 11:30"
    panel.table.selectAll()
    assert set(panel.selected_set_ids()) == {"S1", "S2", "S3"}


def test_history_button_toggles_panel(tab):
    tab.history_btn.setChecked(False)
    assert tab.history_panel.isHidden()
    tab.history_btn.setChecked(True)
    assert not tab.history_panel.isHidden()


def test_refresh_button_emits_empty_list(tab, monkeypatch):
    from tabs import data_transfer_tab as mod
    monkeypatch.setattr(mod.QMessageBox, "warning", staticmethod(lambda *a, **k: 0))
    got = []
    tab.history_panel.refresh_requested.connect(got.append)
    tab.history_panel.refresh_btn.click()
    assert got == [[]]


def test_send_xml_adds_history(tab, monkeypatch, tmp_path):
    from tabs import data_transfer_tab as mod
    xml = tmp_path / "a.xml"
    xml.write_text("<RegistryRecords/>", encoding="utf-8")
    tab.api_key_input.setText("k" * 32)
    tab.xml_file_input.setText(str(xml))
    monkeypatch.setattr(mod, "push_xml", lambda *a, **k: {
        "success": True, "set_id": "SET-77", "send_educated_person": False})
    monkeypatch.setattr(mod.QMessageBox, "exec", lambda self: 0)
    tab.send_xml()
    row = SendHistoryRepo.get("SET-77")
    assert row is not None
    assert row["signed_send"] == 0 and row["status"] == "unsigned"
    assert tab.history_panel.table.rowCount() == 1


def test_history_refresh_updates_status(tab, monkeypatch):
    SendHistoryRepo.add("S1", "2026-10-25 10:00:00", 1, False, "unsigned")
    from tabs import data_transfer_tab as mod
    monkeypatch.setattr(mod.Toast, "info", staticmethod(lambda *a, **k: None))
    tab._on_history_refreshed({"S1": {"ok": True, "records": [{"baseNo": "R1", "Snils": ""}]}})
    assert SendHistoryRepo.get("S1")["status"] == "signed"
    tab._on_history_refreshed({"S1": {"ok": True, "records": []}})
    assert SendHistoryRepo.get("S1")["status"] == "missing"
    tab._on_history_refreshed({"S1": {"ok": False, "error": "x"}})
    assert SendHistoryRepo.get("S1")["status"] == "missing"


def test_setid_of_another_set_is_missing(tab, monkeypatch):
    from journal.send_history import outer_ids_fingerprint
    from tabs import data_transfer_tab as mod
    monkeypatch.setattr(mod.Toast, "info", staticmethod(lambda *a, **k: None))
    SendHistoryRepo.add("S9", "2026-10-25 10:00:00", 1, False, "unsigned",
                        outer_hash=outer_ids_fingerprint(["mine"]))
    journal_calls = []
    tab._journal_update_callback = lambda *a: journal_calls.append(a)
    tab._on_history_refreshed({"S9": {"ok": True, "records": [
        {"baseNo": "R1", "Snils": "11223344595", "outerId": "foreign",
         "baseDateCreated": "2026-10-26T00:00:00"}]}})
    row = SendHistoryRepo.get("S9")
    assert row["status"] == "missing" and row["reg_count"] == 0
    assert journal_calls == []


def test_send_xml_stores_outer_id_fingerprint(tab, monkeypatch, tmp_path):
    from journal.send_history import outer_ids_fingerprint
    from tabs import data_transfer_tab as mod
    xml = tmp_path / "b.xml"
    xml.write_text(
        '<RegistryRecords><RegistryRecord outerId="u-1"><Worker><LastName>Т</LastName></Worker>'
        '<Test learnProgramId="1"><Date>2026-10-01</Date></Test></RegistryRecord></RegistryRecords>',
        encoding="utf-8")
    tab.api_key_input.setText("k" * 32)
    tab.xml_file_input.setText(str(xml))
    monkeypatch.setattr(mod, "push_xml", lambda *a, **k: {
        "success": True, "set_id": "SET-90", "send_educated_person": False})
    monkeypatch.setattr(mod.QMessageBox, "exec", lambda self: 0)
    tab.send_xml()
    row = SendHistoryRepo.get("SET-90")
    assert row["outer_hash"] == outer_ids_fingerprint(["u-1"])
    assert row["record_count"] == 1


def test_send_xml_records_file_name(tab, monkeypatch, tmp_path):
    from tabs import data_transfer_tab as mod
    xml = tmp_path / "file_01.xml"
    xml.write_text("<RegistryRecords/>", encoding="utf-8")
    tab.api_key_input.setText("k" * 32)
    tab.xml_file_input.setText(str(xml))
    monkeypatch.setattr(mod, "push_xml", lambda *a, **k: {
        "success": True, "set_id": "SET-78", "send_educated_person": False})
    monkeypatch.setattr(mod.QMessageBox, "exec", lambda self: 0)
    tab.send_xml()
    assert SendHistoryRepo.get("SET-78")["xml_file"] == "file_01.xml"
    from tabs.send_history_panel import COL_FILE
    assert tab.history_panel.table.item(0, COL_FILE).text() == "file_01.xml"


def test_file_name_falls_back_to_journal(db):
    db.execute("INSERT INTO exam_journal (uuid, set_id, xml_file) VALUES (?, ?, ?)",
               ("u1", "OLD-1", "old.xml"))
    SendHistoryRepo.add("OLD-1", "2026-10-20 10:00:00", 1, False, "signed")
    rows = SendHistoryRepo.list_all()
    assert rows[0]["file_name"] == "old.xml"


def test_setid_column_is_nine_chars(tab):
    from tabs.send_history_panel import COL_SETID
    fm = tab.history_panel.table.fontMetrics()
    assert tab.history_panel.table.columnWidth(COL_SETID) < fm.horizontalAdvance("0" * 12)


def test_send_error_uses_scrollable_dialog(tab, monkeypatch, tmp_path):
    from tabs import data_transfer_tab as mod
    from tabs.send_error_dialog import SendErrorDialog
    xml = tmp_path / "a.xml"
    xml.write_text("<RegistryRecords/>", encoding="utf-8")
    tab.api_key_input.setText("k" * 32)
    tab.xml_file_input.setText(str(xml))
    long_text = "Ошибка валидации\n\nПодробности: " + "\n".join("строка %d" % i for i in range(500))
    monkeypatch.setattr(mod, "push_xml", lambda *a, **k: {
        "success": False, "error": long_text, "raw_response": "<Error/>"})
    shown = []
    monkeypatch.setattr(SendErrorDialog, "exec", lambda self: shown.append(self) or 0)
    tab.send_xml()
    dlg = shown[0]
    assert dlg.summary_label.text() == "Ошибка валидации"
    assert "строка 499" in dlg.details_view.toPlainText()
