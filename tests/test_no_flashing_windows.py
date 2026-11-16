"""Building pages and dialogs must not show child widgets as separate top-level windows.

setVisible(True) on a widget that has no parent yet shows it as its own window for a moment;
at startup this looked like many "flashing" windows (one per page header).
"""
import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _ShowSpy(QObject):
    def __init__(self):
        super().__init__()
        self.shown = []

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and hasattr(obj, "isWindow") and obj.isWindow():
            self.shown.append("%s(%s)" % (type(obj).__name__, obj.objectName()))
        return False


@pytest.fixture
def spy(app):
    s = _ShowSpy()
    app.installEventFilter(s)
    yield s
    app.removeEventFilter(s)


def test_page_header_with_subtitle_shows_no_window(spy):
    from utils.sidebar import PageHeader
    header = PageHeader("Сводка", "Подзаголовок страницы")
    assert spy.shown == []
    assert not header.subtitle_label.isHidden()
    header.deleteLater()


def test_page_header_without_subtitle_hides_label(spy):
    from utils.sidebar import PageHeader
    header = PageHeader("Сводка")
    assert spy.shown == []
    assert header.subtitle_label.isHidden()
    header.deleteLater()


def test_base_dialog_construction_shows_no_window(spy):
    from utils.dialog_base import BaseDialog
    dlg = BaseDialog(None, "Окно", subtitle="Пояснение к окну")
    dlg.add_action_buttons("ОК", lambda: None)
    assert spy.shown == []
    dlg.deleteLater()
