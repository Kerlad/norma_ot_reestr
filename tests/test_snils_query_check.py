"""A8: SNILS checksum is checked before a registry query is sent (N-12)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest import mock

import pytest
from PySide6.QtWidgets import QApplication

from db.database import DatabaseManager
from db.schema import create_schema

BAD_SNILS = "123-456-789 00"
GOOD_SNILS = "112-233-445 95"
API_KEY = "0" * 32  # test value, length only


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    d = DatabaseManager.get_instance(path)
    d.initialize()
    create_schema()
    yield d
    d.close_all()
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def tab(app, db):
    from tabs.data_transfer_tab import DataTransferTab
    t = DataTransferTab()
    t.api_key_input.setText(API_KEY)
    t._get_proxy_settings = mock.Mock(return_value={})
    yield t
    t.cleanup_threads()
    t.deleteLater()


@pytest.fixture
def no_modal(monkeypatch):
    """Nothing modal opens; the query thread is replaced by a mock."""
    import tabs.data_transfer_tab as dt
    msg_warning = mock.Mock()
    toast_warning = mock.Mock()
    thread_cls = mock.Mock()
    worker_cls = mock.Mock()
    monkeypatch.setattr(dt.QMessageBox, "warning", msg_warning)
    monkeypatch.setattr(dt.Toast, "warning", toast_warning)
    monkeypatch.setattr(dt, "QThread", thread_cls)
    monkeypatch.setattr(dt, "_SnilsQueryWorker", worker_cls)
    return {"msg": msg_warning, "toast": toast_warning,
            "thread": thread_cls, "worker": worker_cls}


def test_bad_checksum_does_not_start_query(tab, no_modal):
    tab.query_snils_input.setText(BAD_SNILS)

    tab.query_by_snils()

    no_modal["thread"].assert_not_called()
    no_modal["worker"].assert_not_called()
    assert tab._snils_thread is None
    no_modal["toast"].assert_called_once()
    assert "контрольная сумма" in no_modal["toast"].call_args.args[1]
    assert tab.query_snils_input.property("fieldState") == "invalid"


def test_valid_checksum_passes_check_and_starts_query(tab, no_modal):
    tab.query_snils_input.setText(GOOD_SNILS)

    tab.query_by_snils()

    no_modal["toast"].assert_not_called()
    no_modal["thread"].assert_called_once()
    no_modal["worker"].assert_called_once()
    assert no_modal["worker"].call_args.kwargs["snils"] == GOOD_SNILS
    assert tab.query_snils_input.property("fieldState") in (None, "")


def test_editing_field_clears_invalid_highlight(tab, no_modal):
    tab.query_snils_input.setText(BAD_SNILS)
    tab.query_by_snils()
    assert tab.query_snils_input.property("fieldState") == "invalid"

    tab.query_snils_input.setText("123-456-789 6")

    assert tab.query_snils_input.property("fieldState") in (None, "")
    assert tab.query_snils_input.toolTip().startswith("СНИЛС:")


def test_registry_dialog_clears_error_on_edit(app, monkeypatch):
    from tabs.registry_query_dialog import RegistryQueryDialog, MODE_SNILS
    dlg = RegistryQueryDialog()
    try:
        dlg.snils_radio.setChecked(True)
        dlg.value_input.setText(BAD_SNILS)
        dlg._on_query()
        assert dlg.value_input.property("fieldState") == "invalid"
        assert dlg.error_label.text()

        dlg.value_input.setText("1")

        assert dlg.value_input.property("fieldState") in (None, "")
        assert dlg.error_label.text() == ""
        assert dlg.mode() == MODE_SNILS
    finally:
        dlg.deleteLater()
