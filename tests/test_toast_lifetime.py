"""Toast lifetime: no Qt parent, goes away with its host window, fades out by window opacity.

3.11.0 crashed (access violation, Windows) when the «Номер набора скопирован» toast, a translucent
Tool window owned by the modal «Успех» dialog, was deleted right after the dialog was closed.
"""
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog
from shiboken6 import isValid


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


def test_toast_has_no_qt_parent_and_no_graphics_effect(app):
    from utils.toast import Toast
    host = QDialog()
    host.show()
    toast = Toast(host, "Номер набора скопирован")
    assert toast.parent() is None
    assert toast.graphicsEffect() is None
    toast._remove_and_close()
    host.close()
    _pump(50)


def test_toast_removed_when_host_dialog_closes(app):
    from utils.toast import Toast
    host = QDialog()
    host.show()
    toast = Toast(host, "Номер набора скопирован", duration_ms=10000)
    _pump(120)  # shown after 50 ms
    assert toast.isVisible()
    host.close()
    _pump(100)
    assert not isValid(toast)
    assert toast not in Toast._ACTIVE_TOASTS


def test_toast_fades_out_and_is_deleted(app):
    from utils.toast import Toast
    host = QDialog()
    host.show()
    toast = Toast(host, "Готово", duration_ms=100)
    _pump(900)  # 50 ms show + 100 ms + 500 ms fade
    assert not isValid(toast)
    host.close()
    _pump(50)


def test_toast_not_shown_if_host_closed_before_it_appears(app):
    from utils.toast import Toast
    host = QDialog()
    host.show()
    toast = Toast(host, "Номер набора скопирован")
    host.close()  # before the 50 ms show timer
    _pump(150)
    assert not isValid(toast)
