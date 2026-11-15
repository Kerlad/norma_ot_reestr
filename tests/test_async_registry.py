"""B2, B3, R5, R14: network calls run in workers, results are handled in UI slots, no real network."""
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from db.database import DatabaseManager
from db.schema import create_schema

API_KEY = "0" * 32  # test value, length only
SNILS_A = "112-233-445 95"
SNILS_B = "123-456-789 64"


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
    t.api_key_input.setText(API_KEY)
    t._get_proxy_settings = mock.Mock(return_value={})
    yield t
    t.cleanup_threads()
    t.deleteLater()


def _records():
    return [
        {"Snils": SNILS_A, "LastName": "Тестов", "FirstName": "Тест", "MiddleName": "Тестович",
         "learnProgramId": "2", "Date": "2026-11-04", "baseNo": "R-1"},
        {"snils": SNILS_B, "LastName": "Проверкина", "FirstName": "Анна", "MiddleName": "",
         "learnProgramId": "18", "Date": "05.11.2026", "baseNo": "R-2"},
    ]


# ---------------------------------------------------------------- workers

def test_setid_worker_success_and_exception_without_text(app):
    import tabs.data_transfer_tab as dt
    got = []
    with mock.patch.object(dt, "get_by_set_id", return_value={"success": True, "records": [1]}):
        w = dt._SetIdQueryWorker(API_KEY, "42", {})
        w.finished.connect(got.append)
        w.run()
    assert got[-1]["success"] is True
    with mock.patch.object(dt, "get_by_set_id", side_effect=RuntimeError("http://user:pass@proxy:3128")):
        w = dt._SetIdQueryWorker(API_KEY, "42", {})
        w.finished.connect(got.append)
        w.run()
    assert got[-1] == {"success": False, "error": "Ошибка запроса", "records": []}


def test_send_worker_picks_signed_or_plain_and_hides_exception_text(app):
    import tabs.data_transfer_tab as dt
    got = []
    with mock.patch.object(dt, "push_xml", return_value={"success": True, "set_id": "1"}) as plain, \
            mock.patch.object(dt, "push_xml_signed", return_value={"success": True, "set_id": "2"}) as signed:
        w = dt._SendXmlWorker(API_KEY, "a.xml", "", {})
        w.finished.connect(got.append)
        w.run()
        w = dt._SendXmlWorker(API_KEY, "a.xml", "a.sig", {})
        w.finished.connect(got.append)
        w.run()
    assert plain.call_count == 1 and signed.call_count == 1
    assert [g["set_id"] for g in got] == ["1", "2"]
    with mock.patch.object(dt, "push_xml", side_effect=ValueError("secret path C:\\x")):
        w = dt._SendXmlWorker(API_KEY, "a.xml", "", {})
        w.finished.connect(got.append)
        w.run()
    assert got[-1]["success"] is False and "secret" not in got[-1]["error"]


# ---------------------------------------------------------------- B2: query by SetId

def test_query_by_setid_returns_before_result_and_slot_gets_it(tab, monkeypatch):
    import tabs.data_transfer_tab as dt
    thread_cls = mock.Mock()
    monkeypatch.setattr(dt, "QThread", thread_cls)
    worker_spy = mock.Mock()
    monkeypatch.setattr(dt, "_SetIdQueryWorker", worker_spy)
    get = mock.Mock(side_effect=AssertionError("network call on the UI thread"))
    monkeypatch.setattr(dt, "get_by_set_id", get)

    tab.query_setid_input.setText("777")
    tab.query_by_setid()

    get.assert_not_called()
    thread_cls.assert_called_once()
    worker_spy.assert_called_once()
    assert tab._pending_set_id == "777"
    assert not tab.query_snils_btn.isEnabled() and tab.query_snils_btn.text() == "Запрос…"

    # the real worker, run directly, hands its result to the slot
    monkeypatch.undo()
    got = []
    w = dt._SetIdQueryWorker(API_KEY, "777", {})
    w.finished.connect(got.append)
    with mock.patch.object(dt, "get_by_set_id", return_value={"success": True, "records": _records()}):
        w.run()
    shown = []
    tab._show_registry_result = lambda *a: shown.append(a)
    tab._pending_set_id = "777"
    tab._journal_update_callback = mock.Mock()
    tab._on_setid_query_result(got[0])
    tab._journal_update_callback.assert_called_once()
    sid, mapping = tab._journal_update_callback.call_args.args
    assert sid == "777" and mapping == {SNILS_A.replace("-", "").replace(" ", ""): "R-1"}
    assert shown and shown[0][0] == "SetId 777" and len(shown[0][1]) == 2


def test_empty_answer_shows_message_not_dialog(tab, monkeypatch):
    import tabs.data_transfer_tab as dt
    box = mock.Mock()
    monkeypatch.setattr(dt, "safe_message_box", box)
    tab._show_registry_result = mock.Mock()
    tab._pending_set_id = "1"
    tab._on_setid_query_result({"success": True, "records": []})
    tab._on_snils_query_result({"success": True, "records": []})
    assert box.call_count == 2
    assert box.call_args.args[3] == "В реестре нет записей по этому запросу"
    tab._show_registry_result.assert_not_called()


# ---------------------------------------------------------------- B3

def test_dialog_has_row_per_record_and_cancelled_save_keeps_last_result(tab, monkeypatch):
    from tabs import registry_result_dialog as rd
    monkeypatch.setattr(rd.BaseDialog, "exec", lambda self: 0)
    holder = {}
    orig_init = rd.RegistryResultDialog.__init__

    def spy(self, *a, **k):
        orig_init(self, *a, **k)
        holder["dlg"] = self
    monkeypatch.setattr(rd.RegistryResultDialog, "__init__", spy)

    assert not tab.last_response_btn.isEnabled()
    tab._show_registry_result("SetId 5", _records(), "5.xlsx")
    dlg = holder["dlg"]
    assert dlg.table.rowCount() == 2
    cells = {dlg.table.item(r, 0).text(): [dlg.table.item(r, c).text() for c in range(5)]
             for r in range(2)}
    assert cells["Тестов Тест Тестович"] == ["Тестов Тест Тестович", SNILS_A, "2", "04.11.2026", "R-1"]
    assert cells["Проверкина Анна"][1:] == [SNILS_B, "18", "05.11.2026", "R-2"]

    export = mock.Mock()
    monkeypatch.setattr(rd, "export_records_to_xlsx", export)
    monkeypatch.setattr(rd.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dlg._save_xlsx()
    export.assert_not_called()
    assert tab._last_registry_result == ("SetId 5", _records())
    assert tab.last_response_btn.isEnabled()

    # saving: the dialog is not closed and the result is kept
    monkeypatch.setattr(rd.QFileDialog, "getSaveFileName", lambda *a, **k: ("x.xlsx", ""))
    export.return_value = (True, "ok")
    monkeypatch.setattr(rd, "safe_message_box", mock.Mock())
    dlg._save_xlsx()
    export.assert_called_once()
    assert tab._last_registry_result is not None


def test_snils_result_opens_dialog_without_snils_in_file_name(tab, monkeypatch):
    tab._show_registry_result = mock.Mock()
    tab._on_snils_query_result({"success": True, "records": _records()})
    title, records, file_name = tab._show_registry_result.call_args.args
    assert len(records) == 2
    assert "112" not in file_name and "233" not in file_name and file_name.endswith(".xlsx")


# ---------------------------------------------------------------- R5 / R14

def _ctx(signed=False):
    return {"signed": signed, "api_key": API_KEY, "xml_file": "x.xml", "sig_file": "",
            "records": [{"outer_id": "1"}]}


def test_send_xml_starts_thread_and_locks_both_buttons(tab, monkeypatch, tmp_path):
    import tabs.data_transfer_tab as dt
    xml = tmp_path / "a.xml"
    xml.write_text("<x/>", encoding="utf-8")
    tab.xml_file_input.setText(str(xml))
    thread_cls, worker_cls = mock.Mock(), mock.Mock()
    monkeypatch.setattr(dt, "QThread", thread_cls)
    monkeypatch.setattr(dt, "_SendXmlWorker", worker_cls)
    push = mock.Mock(side_effect=AssertionError("network call on the UI thread"))
    monkeypatch.setattr(dt, "push_xml", push)

    tab.send_xml()

    push.assert_not_called()
    thread_cls.assert_called_once()
    assert not tab.send_xml_btn.isEnabled() and not tab.send_xml_signed_btn.isEnabled()
    assert not tab.send_progress.isHidden()
    tab._send_thread = None  # mock thread: leave nothing for cleanup_threads


def test_send_success_slot_writes_journal_history_and_shows_dialog(tab, monkeypatch):
    import tabs.data_transfer_tab as dt
    from tabs import send_success_dialog as sd
    shown = []
    monkeypatch.setattr(sd.BaseDialog, "exec", lambda self: shown.append(self) or 0)
    tab._journal_add_callback = mock.Mock()
    tab._record_send = mock.Mock()
    tab._send_ctx = _ctx()
    tab._set_send_busy(True)

    tab._on_send_result({"success": True, "set_id": "9001", "send_educated_person": False})

    tab._journal_add_callback.assert_called_once()
    tab._record_send.assert_called_once()
    assert tab.last_setid_display.text() == "9001"
    assert shown and "9001" in shown[0].set_id_plate.text()
    assert tab.send_xml_btn.isEnabled() and tab.send_xml_signed_btn.isEnabled()
    assert tab.send_xml_btn.text() == tab.SEND_TEXT
    assert tab._send_ctx is None
    assert dt  # module imported for the patches above


def test_success_dialog_copy_button_copies_set_id(app, monkeypatch):
    from tabs.send_success_dialog import SendSuccessDialog
    from utils import toast
    monkeypatch.setattr(toast.Toast, "info", lambda *a, **k: None)
    dlg = SendSuccessDialog(None, "Данные загружены", "12345")
    assert dlg.copy_btn.text() == "Скопировать номер набора"
    dlg.copy_btn.click()
    assert QApplication.clipboard().text() == "12345"
    assert "color" not in dlg.set_id_plate.text().lower()
    assert dlg.set_id_plate.objectName() == "notice"


def test_ssl_error_retry_goes_through_worker_with_tls_off(tab, monkeypatch):
    import tabs.data_transfer_tab as dt
    monkeypatch.setattr(dt.QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(dt.QMessageBox, "warning", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(dt, "log_audit", mock.Mock())
    monkeypatch.setattr(tab, "_save_tls_setting", mock.Mock())
    started = []
    tab._start_send = lambda ctx: started.append(ctx)
    tab._send_ctx = ctx = _ctx()
    tab._set_send_busy(True)
    tab.tls_checkbox.setChecked(True)

    tab._on_send_result({"success": False, "ssl_error_detected": True, "ssl_recommendation": ""})

    assert started == [ctx]
    assert not tab.tls_checkbox.isChecked()
    assert not tab.send_xml_btn.isEnabled(), "buttons stay locked during the retry"


def test_send_error_shows_dialog_and_unlocks(tab, monkeypatch):
    tab._show_send_error = mock.Mock()
    tab._send_ctx = _ctx(signed=True)
    tab._set_send_busy(True)
    assert tab.send_xml_signed_btn.text() == "Отправка..."
    tab._on_send_result({"success": False, "error": "x"})
    tab._show_send_error.assert_called_once()
    assert tab.send_xml_signed_btn.isEnabled()
    assert tab.send_xml_signed_btn.text() == tab.SEND_SIGNED_TEXT


# ---------------------------------------------------------------- journal tab (B2.3) and shutdown

@pytest.fixture
def journal_tab(app, db, tmp_path):
    import tabs.exam_journal_tab as jt
    from journal.journal_manager import JournalManager
    t = jt.ExamJournalTab(JournalManager(str(tmp_path)), str(tmp_path))
    yield t
    t.cleanup_threads()
    t.deleteLater()


def test_journal_update_slot_updates_base_numbers_on_ui_thread(journal_tab, monkeypatch):
    import tabs.exam_journal_tab as jt
    monkeypatch.setattr(jt.Toast, "success", lambda *a, **k: None)
    monkeypatch.setattr(jt.Toast, "info", lambda *a, **k: None)
    journal_tab.journal = mock.Mock()
    journal_tab.journal.update_base_no_by_set_id.return_value = 1
    journal_tab.refresh_journal = mock.Mock()
    journal_tab._on_setid_update_result({
        "10": {"ok": True, "records": _records()},
        "11": {"ok": False, "error": "x"},
    })
    journal_tab.journal.update_base_no_by_set_id.assert_called_once_with(
        "10", {SNILS_A.replace("-", "").replace(" ", ""): "R-1"})  # SetId answers use the Snils key
    journal_tab.refresh_journal.assert_called_once()


def test_cleanup_waits_for_finishing_thread_and_parks_stuck_one(tab, journal_tab):
    import tabs.data_transfer_tab as dt
    stuck = mock.Mock()
    stuck.isRunning.return_value = True
    stuck.wait.return_value = False
    tab._send_thread = stuck
    tab._send_worker = None
    tab.cleanup_threads()
    stuck.quit.assert_called()
    assert stuck in dt._PARKED_THREADS
    dt._PARKED_THREADS.remove(stuck)

    quick = mock.Mock()
    quick.isRunning.return_value = True
    quick.wait.return_value = True
    journal_tab._setid_thread = quick
    journal_tab.cleanup_threads()
    quick.quit.assert_called()
    assert quick not in dt._PARKED_THREADS


def test_main_stops_threads_of_both_tabs():
    import re
    src = open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), encoding="utf-8").read()
    body = src.split("def _stop_background_threads", 1)[1].split("\ndef ", 1)[0]
    assert "data_transfer_tab" in body and "exam_journal_tab" in body
    assert re.search(r"cleanup_threads\(\)", body)


def test_ssl_retry_declined_at_tls_warning_does_not_resend(tab, monkeypatch):
    import tabs.data_transfer_tab as dt
    monkeypatch.setattr(dt.QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(dt.QMessageBox, "warning", lambda *a, **k: QMessageBox.No)
    monkeypatch.setattr(dt, "log_audit", mock.Mock())
    monkeypatch.setattr(dt, "safe_message_box", mock.Mock())
    tab._start_send = mock.Mock()
    tab._send_ctx = _ctx()
    tab.tls_checkbox.setChecked(True)
    tab._on_send_result({"success": False, "ssl_error_detected": True})
    tab._start_send.assert_not_called()
    assert tab.tls_checkbox.isChecked() and tab.send_xml_btn.isEnabled()
