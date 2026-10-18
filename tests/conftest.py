import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Isolate the whole test session from the real %APPDATA%: without this, crypto tests
# create master.key in the user's real data dir and app_paths would migrate it.
# Set at import time so it applies before any test module imports app code.
_TEST_APPDATA = tempfile.mkdtemp(prefix="normaot_test_appdata_")
os.environ['APPDATA'] = _TEST_APPDATA


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_APPDATA, ignore_errors=True)
