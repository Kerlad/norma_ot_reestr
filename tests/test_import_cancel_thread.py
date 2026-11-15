"""R8: cancelling an XLSX import never calls QThread.terminate() and waits for the thread."""
from unittest.mock import patch

from PySide6.QtCore import QThread, QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication

from utils.workers import ExcelImportWorker


def _app():
    return QApplication.instance() or QApplication([])


def _pump(cond, timeout_ms=5000):
    import time
    end = time.time() + timeout_ms / 1000
    while not cond() and time.time() < end:
        QCoreApplication.processEvents(QEventLoop.AllEvents, 50)
        time.sleep(0.01)
    return cond()


def test_worker_cancel_check_emits_cancelled():
    _app()
    w = ExcelImportWorker("synthetic.xlsx")
    got = []
    w.cancelled.connect(lambda: got.append(1))

    def fake_load(path, pw, progress_callback=None, cancel_check=None):
        w.cancel()
        assert cancel_check() is True
        return [], [], set(), ""

    with patch("importers.xlsx_importer.load_xlsx", fake_load), \
         patch("utils.audit.log_audit"):
        w.run()
    assert got == [1]


def test_cancel_import_no_terminate_and_flag_reset(tmp_path):
    _app()
    from tabs.data_entry_tab import DataEntryTab
    tab = DataEntryTab()

    def slow_load(path, pw, progress_callback=None, cancel_check=None):
        import time
        for _ in range(500):
            if cancel_check():
                break
            time.sleep(0.01)
        return [], [], set(), ""

    with patch("importers.xlsx_importer.load_xlsx", slow_load), \
         patch("utils.audit.log_audit"), \
         patch.object(QThread, "terminate") as term:
        tab._start_xlsx_import("synthetic.xlsx", False, set())
        assert tab._is_xlsx_importing
        tab._cancel_import()
        assert tab._import_status_label.text() == "Отмена импорта…"
        assert tab._is_xlsx_importing  # still waiting for the thread
        assert _pump(lambda: not tab._is_xlsx_importing)
        assert _pump(lambda: tab._import_thread is None)
        term.assert_not_called()
    tab.cleanup_threads()
