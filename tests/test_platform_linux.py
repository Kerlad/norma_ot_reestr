"""L-03: Linux branches of app_paths / secure_temp / nag_state.

The flags in utils.platform_info are patched, so these run on Windows too; the
permission checks need POSIX and are skipped there.
"""
import os
import stat
import sys
from datetime import date, timedelta

import pytest

from utils import app_paths, nag_state, platform_info, secure_temp

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
    monkeypatch.setattr(platform_info, "IS_LINUX", True)
    app_paths._reset_for_tests()
    yield
    app_paths._reset_for_tests()


class TestAppPaths:
    def test_uses_xdg_data_home(self, linux, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        path = app_paths.get_app_data_dir()
        assert path == str(tmp_path / app_paths.APP_DIR_NAME)
        assert os.path.isdir(path)
        assert os.path.isdir(app_paths.get_app_log_dir())

    def test_default_is_local_share(self, linux, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(app_paths.Path, "home", lambda: tmp_path)
        assert app_paths._data_base() == tmp_path / ".local" / "share"

    def test_relative_xdg_value_ignored(self, linux, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", "relative/dir")
        monkeypatch.setattr(app_paths.Path, "home", lambda: tmp_path)
        assert app_paths._data_base() == tmp_path / ".local" / "share"

    def test_no_migration_of_legacy_dir(self, linux, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        legacy = tmp_path / app_paths.LEGACY_APP_DIR_NAME
        legacy.mkdir()
        (legacy / "master.key").write_bytes(b"k")
        path = app_paths.get_app_data_dir()
        assert path == str(tmp_path / app_paths.APP_DIR_NAME)
        assert (legacy / "master.key").exists()
        assert app_paths.get_migration_status()["status"] == app_paths.MIGRATION_NONE

    @posix_only
    def test_data_dir_is_0700_despite_umask(self, linux, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        old = os.umask(0)
        try:
            path = app_paths.get_app_data_dir()
        finally:
            os.umask(old)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o700


class TestSecureTemp:
    @pytest.fixture(autouse=True)
    def _reset(self, monkeypatch):
        secure_temp._cleanup_secure_temp()
        monkeypatch.setattr(secure_temp, "_secure_temp_dir", None)
        yield
        secure_temp._cleanup_secure_temp()

    @posix_only
    def test_prefers_private_runtime_dir(self, linux, tmp_path, monkeypatch):
        runtime = tmp_path / "run"
        runtime.mkdir(mode=0o700)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
        d = secure_temp.get_secure_temp_dir()
        assert os.path.dirname(d) == str(runtime)
        assert stat.S_IMODE(os.stat(d).st_mode) == 0o700

    @posix_only
    def test_group_readable_runtime_dir_rejected(self, linux, tmp_path, monkeypatch):
        runtime = tmp_path / "run"
        runtime.mkdir()
        os.chmod(runtime, 0o750)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
        assert secure_temp._temp_base() != str(runtime)

    def test_missing_runtime_dir_falls_back_to_tmp(self, linux, monkeypatch):
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        import tempfile
        assert secure_temp._temp_base() == tempfile.gettempdir()

    @posix_only
    def test_temp_file_is_0600(self, linux, monkeypatch):
        path = secure_temp.create_secure_temp_file()
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


class TestNagMarker:
    @pytest.fixture
    def marker(self, linux, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        monkeypatch.setattr(nag_state, "_state_path", lambda: str(tmp_path / nag_state.STATE_FILE))
        return tmp_path

    def test_marker_written_under_xdg_config(self, marker):
        nag_state.mark_splash_shown(date(2026, 10, 1))
        f = marker / "cfg" / "NormaOT" / "support_state"
        assert f.read_text(encoding="utf-8") == "2026-10-01"

    def test_later_date_wins_and_repairs_others(self, marker):
        nag_state.mark_splash_shown(date(2026, 10, 1))
        (marker / nag_state.STATE_FILE).unlink()
        assert nag_state.last_splash_date() == date(2026, 10, 1)
        assert nag_state._file_read() == date(2026, 10, 1)

    def test_deleting_xdg_marker_does_not_reset(self, marker):
        today = date.today()
        nag_state.mark_splash_shown(today)
        os.remove(marker / "cfg" / "NormaOT" / "support_state")
        assert nag_state.splash_due(today) is False

    def test_future_xdg_date_is_due(self, marker):
        nag_state.mark_splash_shown(date.today() + timedelta(days=5))
        assert nag_state.splash_due() is True

    def test_noop_on_windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform_info, "IS_LINUX", False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        nag_state._xdg_write(date(2026, 10, 1))
        assert nag_state._xdg_read() is None
        assert not (tmp_path / "NormaOT").exists()
