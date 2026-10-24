import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Isolate the whole test session from the real %APPDATA%: without this, crypto tests
# create master.key in the user's real data dir and app_paths would migrate it.
# Set at import time so it applies before any test module imports app code.
_TEST_APPDATA = tempfile.mkdtemp(prefix="normaot_test_appdata_")
os.environ['APPDATA'] = _TEST_APPDATA
# Same for the Linux XDG dirs (no-ops on Windows, but keep tests off ~/.local and ~/.config).
for _var, _sub in (('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'), ('XDG_RUNTIME_DIR', 'runtime')):
    _xdg = os.path.join(_TEST_APPDATA, 'xdg', _sub)
    os.makedirs(_xdg, mode=0o700, exist_ok=True)
    os.environ[_var] = _xdg


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_APPDATA, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_real_registry(monkeypatch):
    """Keep the UX-16 splash marker out of the user's real HKCU during tests."""
    from utils import nag_state
    store = {}
    monkeypatch.setattr(nag_state, "_reg_read", lambda: store.get("day"))
    monkeypatch.setattr(nag_state, "_reg_write", lambda day: store.__setitem__("day", day))
    # The XDG marker lives under the redirected XDG_CONFIG_HOME; start every test without it.
    shutil.rmtree(os.path.join(os.environ['XDG_CONFIG_HOME'], 'NormaOT'), ignore_errors=True)
