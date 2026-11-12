import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_about_dialog_has_no_github_mention(qapp, monkeypatch):
    # Never open a modal dialog during the test
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    from utils.about_dialog import AboutDialog

    dlg = AboutDialog()
    try:
        parts = [dlg.windowTitle()]
        for label in dlg.findChildren(QLabel):
            parts.append(label.text())
            url = getattr(label, "_url", None)
            if url:
                parts.append(url)
        text = "\n".join(parts)

        assert "Репозиторий" in text  # sanity: the dialog was actually built
        assert "github" not in text.lower()
    finally:
        dlg.close()
        dlg.deleteLater()
