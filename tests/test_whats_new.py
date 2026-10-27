"""«Что нового» by the version label, «О программе» in the sidebar, themed spin/combo arrows."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from utils import whats_new_dialog
from utils.about_dialog import VERSION


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_version_notes_of_current_version():
    notes = whats_new_dialog.read_version_notes()
    assert notes.startswith("## v%s" % VERSION)
    assert "\n## v" not in notes  # only this version's section


def test_version_notes_unknown_version():
    assert "0.0.0" in whats_new_dialog.read_version_notes("0.0.0")


def test_version_notes_missing_changelog(monkeypatch, tmp_path):
    monkeypatch.setattr(whats_new_dialog, "get_resource_dir", lambda: str(tmp_path))
    assert whats_new_dialog.read_version_notes() == "Описание изменений недоступно."


def test_sidebar_version_and_about_signals(app):
    from PySide6.QtTest import QTest
    from utils.sidebar import Sidebar
    bar = Sidebar(VERSION, org_name="Тест")
    got = []
    bar.version_requested.connect(lambda: got.append("version"))
    bar.about_requested.connect(lambda: got.append("about"))
    QTest.mouseClick(bar.version_label, Qt.MouseButton.LeftButton)
    QTest.mouseClick(bar.version_label, Qt.MouseButton.RightButton)
    bar.about_button.click()
    assert got == ["version", "about"]


def test_settings_have_no_about_section():
    from utils.settings_dialog import SettingsDialog
    assert "about" not in [key for key, _ in SettingsDialog.SECTIONS]


def test_stylesheet_has_themed_arrows(app):
    from utils.tahoe_style import get_global_stylesheet
    qss = get_global_stylesheet("norma")
    assert "QSpinBox::up-arrow" in qss
    assert "image: url(" in qss
