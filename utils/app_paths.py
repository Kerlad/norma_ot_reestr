import os
import threading
from pathlib import Path
from typing import Dict, Optional

APP_DIR_NAME = "NormaOT"
LEGACY_APP_DIR_NAME = "Excel_to_XML"

# Migration outcome of the first get_app_data_dir() call in this process.
# Logging/audit are not configured yet at that moment, so main.py reports it later
# via get_migration_status().
MIGRATION_NONE = "none"            # nothing to migrate
MIGRATION_DONE = "migrated"        # legacy dir renamed to the new one
MIGRATION_SKIPPED = "skipped"      # both dirs exist with data, new one used
MIGRATION_FAILED = "failed"        # rename failed, legacy dir used this session

_resolve_lock = threading.Lock()
_resolved: Dict[str, str] = {}
_migration_status: Dict[str, Optional[str]] = {"status": None, "error": None}


def _appdata_base() -> Path:
    base: Optional[str] = os.environ.get('APPDATA')
    if not base:
        base = str(Path.home() / 'AppData' / 'Roaming')
    return Path(base)


def _is_empty_dir(path: Path) -> bool:
    try:
        return path.is_dir() and not any(path.iterdir())
    except OSError:
        return False


def _resolve_data_dir(base: Path) -> Path:
    """Pick the data dir, migrating %APPDATA%/Excel_to_XML -> %APPDATA%/NormaOT once.

    A rename (not copy) is used: both dirs live in the same parent, so it is atomic,
    keeps per-file ACLs set on master.key and leaves no second copy of PD.
    """
    new_dir = base / APP_DIR_NAME
    legacy_dir = base / LEGACY_APP_DIR_NAME

    if not legacy_dir.is_dir():
        _migration_status.update(status=MIGRATION_NONE, error=None)
        return new_dir

    if new_dir.exists():
        if not _is_empty_dir(new_dir):
            _migration_status.update(status=MIGRATION_SKIPPED, error=None)
            return new_dir
        try:
            new_dir.rmdir()
        except OSError as e:
            _migration_status.update(status=MIGRATION_SKIPPED, error=type(e).__name__)
            return new_dir

    try:
        os.rename(str(legacy_dir), str(new_dir))
    except OSError as e:
        # Typically a file is held open by a running old version. Keep working with
        # the legacy dir so no data is lost; migration is retried on next start.
        _migration_status.update(status=MIGRATION_FAILED, error=type(e).__name__)
        return legacy_dir

    _migration_status.update(status=MIGRATION_DONE, error=None)
    return new_dir


def get_app_data_dir() -> str:
    """Возвращает путь к директории данных приложения (%APPDATA%/NormaOT).

    При первом вызове переносит данные из старой папки %APPDATA%/Excel_to_XML.
    """
    base = _appdata_base()
    key = str(base)
    with _resolve_lock:
        path = _resolved.get(key)
        if path is None:
            resolved = _resolve_data_dir(base)
            os.makedirs(str(resolved), exist_ok=True)
            path = str(resolved)
            _resolved[key] = path
    return path


def get_app_log_dir() -> str:
    """Возвращает путь к директории логов (%APPDATA%/NormaOT/log)."""
    path = os.path.join(get_app_data_dir(), "log")
    os.makedirs(path, exist_ok=True)
    return path


def get_migration_status() -> Dict[str, Optional[str]]:
    """Returns {'status': MIGRATION_*, 'error': exception class name or None}.

    status is None until get_app_data_dir() has been called.
    """
    return dict(_migration_status)


def _reset_for_tests() -> None:
    with _resolve_lock:
        _resolved.clear()
        _migration_status.update(status=None, error=None)


def get_resource_dir() -> str:
    """Возвращает корневую директорию проекта (с ресурсами: schema, templates, assets).
    Не использовать для runtime-данных — используйте get_app_data_dir()."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
