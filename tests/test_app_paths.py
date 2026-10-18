import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from utils import app_paths
from utils.app_paths import (
    get_app_data_dir, get_app_log_dir, get_migration_status,
    APP_DIR_NAME, LEGACY_APP_DIR_NAME,
    MIGRATION_NONE, MIGRATION_DONE, MIGRATION_SKIPPED, MIGRATION_FAILED,
)


@pytest.fixture
def appdata(tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    app_paths._reset_for_tests()
    yield tmp_path
    app_paths._reset_for_tests()


def _make_legacy(base, files=None):
    legacy = base / LEGACY_APP_DIR_NAME
    (legacy / "log").mkdir(parents=True)
    (legacy / "backups").mkdir()
    for name, content in (files or {
        "app_data.db": b"db-bytes",
        "master.key": b"key-bytes",
        "master.key.json": b"{}",
        "log/audit.log": b"audit",
        "backups/b1.zip": b"zip",
    }).items():
        (legacy / name).write_bytes(content)
    return legacy


class TestFreshInstall:
    def test_creates_new_dir_only(self, appdata):
        path = get_app_data_dir()
        assert path == str(appdata / APP_DIR_NAME)
        assert os.path.isdir(path)
        assert not (appdata / LEGACY_APP_DIR_NAME).exists()
        assert get_migration_status()['status'] == MIGRATION_NONE

    def test_log_dir_inside_data_dir(self, appdata):
        assert get_app_log_dir() == os.path.join(str(appdata / APP_DIR_NAME), "log")
        assert os.path.isdir(get_app_log_dir())


class TestMigration:
    def test_legacy_moved_with_all_content(self, appdata):
        _make_legacy(appdata)
        path = get_app_data_dir()
        new = appdata / APP_DIR_NAME
        assert path == str(new)
        assert not (appdata / LEGACY_APP_DIR_NAME).exists()
        assert (new / "app_data.db").read_bytes() == b"db-bytes"
        assert (new / "master.key").read_bytes() == b"key-bytes"
        assert (new / "master.key.json").exists()
        assert (new / "log" / "audit.log").read_bytes() == b"audit"
        assert (new / "backups" / "b1.zip").exists()
        assert get_migration_status() == {'status': MIGRATION_DONE, 'error': None}

    def test_empty_new_dir_does_not_block_migration(self, appdata):
        _make_legacy(appdata)
        (appdata / APP_DIR_NAME).mkdir()
        get_app_data_dir()
        assert (appdata / APP_DIR_NAME / "master.key").exists()
        assert not (appdata / LEGACY_APP_DIR_NAME).exists()
        assert get_migration_status()['status'] == MIGRATION_DONE

    def test_both_with_data_keeps_both_untouched(self, appdata):
        _make_legacy(appdata)
        new = appdata / APP_DIR_NAME
        new.mkdir()
        (new / "app_data.db").write_bytes(b"new-db")
        path = get_app_data_dir()
        assert path == str(new)
        assert (new / "app_data.db").read_bytes() == b"new-db"
        assert (appdata / LEGACY_APP_DIR_NAME / "app_data.db").read_bytes() == b"db-bytes"
        assert get_migration_status()['status'] == MIGRATION_SKIPPED

    def test_rename_failure_falls_back_to_legacy(self, appdata, monkeypatch):
        legacy = _make_legacy(appdata)

        def boom(src, dst):
            raise PermissionError("locked")
        monkeypatch.setattr(app_paths.os, "rename", boom)

        path = get_app_data_dir()
        assert path == str(legacy)
        assert (legacy / "master.key").exists()
        assert get_migration_status() == {'status': MIGRATION_FAILED, 'error': 'PermissionError'}

    def test_migration_runs_once_per_process(self, appdata, monkeypatch):
        _make_legacy(appdata)
        first = get_app_data_dir()
        calls = []
        monkeypatch.setattr(app_paths, "_resolve_data_dir",
                            lambda base: calls.append(base) or base / "other")
        assert get_app_data_dir() == first
        assert get_app_log_dir().startswith(first)
        assert calls == []


class TestCryptoUsesSameDir:
    def test_key_dir_matches_app_data_dir(self, appdata):
        from utils.crypto import _key_dir
        assert str(_key_dir()) == get_app_data_dir()

    def test_key_dir_follows_migration(self, appdata):
        _make_legacy(appdata)
        from utils.crypto import _key_dir
        assert _key_dir() == appdata / APP_DIR_NAME
        assert (_key_dir() / "master.key").read_bytes() == b"key-bytes"
