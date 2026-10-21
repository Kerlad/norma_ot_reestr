"""Repeated SNILS query / proxy test must not touch an already deleted QThread."""
import types

from PySide6.QtCore import QCoreApplication, QEvent, QThread
from PySide6.QtWidgets import QApplication

from tabs.data_transfer_tab import DataTransferTab


def _app():
    return QApplication.instance() or QApplication([])


def _tab_stub():
    stub = types.SimpleNamespace(_snils_thread=None)
    stub._forget_thread = types.MethodType(DataTransferTab._forget_thread, stub)
    stub._thread_busy = types.MethodType(DataTransferTab._thread_busy, stub)
    return stub


def _deleted_thread():
    th = QThread()
    th.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return th


def test_deleted_thread_reference_is_idle_and_dropped():
    _app()
    stub = _tab_stub()
    stub._snils_thread = _deleted_thread()
    assert stub._thread_busy("_snils_thread") is False
    assert stub._snils_thread is None


def test_finished_thread_reference_is_forgotten():
    _app()
    stub = _tab_stub()
    th = QThread()
    stub._snils_thread = th
    th.finished.connect(lambda: stub._forget_thread("_snils_thread", th))
    th.start()
    th.quit()
    assert th.wait(3000)
    QCoreApplication.processEvents()
    assert stub._snils_thread is None


def test_forget_keeps_newer_thread():
    _app()
    stub = _tab_stub()
    old, new = QThread(), QThread()
    stub._snils_thread = new
    stub._forget_thread("_snils_thread", old)
    assert stub._snils_thread is new
