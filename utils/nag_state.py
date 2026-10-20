"""
"Splash already shown today" marker (UX-16).

The 10 s support splash appears once per CALENDAR DAY. The marker is kept in two
places — the registry (`HKCU\\Software\\NormaOT`) and a file in the data dir — so
deleting one of them does not reset it. Reading takes the later of the two dates
and writes it back to both, so a missing or stale copy repairs itself.

Contains no PD: only a date.
"""
import json
import logging
import os
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILE = "support_state.json"
REG_SUBKEY = r"Software\NormaOT"
REG_VALUE = "LastSupportSplash"
_FIELD = "last_splash"


def _state_path() -> str:
    from utils.app_paths import get_app_data_dir
    return os.path.join(get_app_data_dir(), STATE_FILE)


def _parse(value) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _reg_read() -> Optional[date]:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY) as key:
            value, _ = winreg.QueryValueEx(key, REG_VALUE)
        return _parse(value)
    except OSError:
        return None


def _reg_write(day: date) -> None:
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY) as key:
            winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_SZ, day.isoformat())
    except OSError as e:
        logger.debug("Registry marker not written: %s", type(e).__name__)


def _file_read() -> Optional[date]:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return _parse(data.get(_FIELD)) if isinstance(data, dict) else None


def _file_write(day: date) -> None:
    path = _state_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({_FIELD: day.isoformat()}, f)
        os.replace(tmp, path)
    except OSError as e:
        logger.debug("Splash marker file not written: %s", type(e).__name__)


def last_splash_date() -> Optional[date]:
    """The later of the two stored dates; repairs the other copy."""
    reg, file = _reg_read(), _file_read()
    if reg is None and file is None:
        return None
    latest = max(d for d in (reg, file) if d is not None)
    if reg != latest:
        _reg_write(latest)
    if file != latest:
        _file_write(latest)
    return latest


def mark_splash_shown(today: Optional[date] = None) -> None:
    today = today or date.today()
    _reg_write(today)
    _file_write(today)


def splash_due(today: Optional[date] = None) -> bool:
    """True if the splash was not shown on this calendar day.

    A stored date in the future (clock moved back) also counts as due; the date
    is overwritten with today when the splash is shown.
    """
    today = today or date.today()
    return last_splash_date() != today
