"""L-05: platform-dependent UI helpers (flags patched, run on any OS)."""
import importlib
import os

import pytest
from PySide6.QtWidgets import QApplication

from utils import platform_info, ui_helpers

_app = QApplication.instance() or QApplication([])


class TestOpenFolder:
    def test_linux_opens_folder_via_desktop_services(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
        opened = []
        from PySide6.QtGui import QDesktopServices
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
        ui_helpers.open_folder(str(tmp_path))
        assert opened == [str(tmp_path)]

    def test_linux_select_file_opens_its_folder(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
        opened = []
        from PySide6.QtGui import QDesktopServices
        monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
        ui_helpers.open_folder("ignored", select_file=str(tmp_path / "a.xlsx"))
        assert opened == [str(tmp_path)]

    def test_windows_uses_explorer(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        calls = []
        import subprocess
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(a[0]))
        ui_helpers.open_folder(r"C:\logs")
        ui_helpers.open_folder("x", select_file=r"C:\x\a.xlsx")
        assert calls == [["explorer", r"C:\logs"], r'explorer /select,"C:\x\a.xlsx"']


class TestFonts:
    def test_windows_keeps_consolas(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        assert ui_helpers.monospace_font(11).family() == "Consolas"

    def test_linux_uses_system_fixed_font(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
        font = ui_helpers.monospace_font(11)
        assert font.family() != "Consolas" and font.pointSize() == 11


class TestHelpTexts:
    @pytest.fixture
    def help_module(self, monkeypatch):
        from utils import help_dialog
        yield help_dialog
        importlib.reload(help_dialog)  # restore the real platform's texts

    def _storage_text(self, module):
        return next(s["body"] for s in module.HELP_SECTIONS if s["title"] == "Хранение данных")

    def test_linux_text_has_no_windows_specifics(self, monkeypatch, help_module):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
        importlib.reload(help_module)
        text = self._storage_text(help_module)
        assert "APPDATA" not in text and "DPAPI" not in text
        assert ".local/share/NormaOT" in text and "Secret Service" in text

    def test_windows_text_unchanged(self, monkeypatch, help_module):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        importlib.reload(help_module)
        text = self._storage_text(help_module)
        assert "%APPDATA%\NormaOT" in text and "Windows DPAPI" in text and "Excel_to_XML" in text


def test_app_icon_is_png_off_windows(monkeypatch):
    import main
    monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
    assert main._app_icon_path().endswith("icon.png") and os.path.exists(main._app_icon_path())
    monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
    assert main._app_icon_path().endswith("ico.ico")
