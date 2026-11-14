"""A4: XML export is blocked when any record breaks the rules."""
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _rec(snils):
    return dict(last_name="Тестов", first_name="Тест", middle_name="Тестович", snils=snils,
                position="Слесарь", employer_inn="", employer_title="", tc_inn="", tc_title="",
                result="Удовлетворительно", program="1", date="01.02.2024", protocol="П-1")


def _stub(records):
    from PySide6.QtWidgets import QWidget
    from tabs.data_view_tab import DataViewTab

    class _Tab(QWidget):
        _check_records_before_xml = DataViewTab._check_records_before_xml

    stub = _Tab()
    stub._model = SimpleNamespace(rowCount=lambda: len(records), get_row_data=lambda r: dict(records[r]))
    return stub


def test_bad_record_blocks_export(app, monkeypatch):
    from tabs import data_view_tab
    from tabs.data_view_tab import DataViewTab
    from utils.dialog_base import BaseDialog
    execs = []
    monkeypatch.setattr(BaseDialog, "exec", lambda self: execs.append(self.windowTitle()) or 0)
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    exported = []
    monkeypatch.setattr(data_view_tab, "export_to_xml", lambda *a, **k: exported.append(1))
    stub = _stub([_rec("112-233-445 95"), _rec("123-456-789 00")])
    assert DataViewTab._prepare_xml_export(stub) is None
    assert exported == []
    assert execs == ["XML не сформирован: в 1 записях ошибки"]


def test_good_records_pass_guard(app, monkeypatch):
    from utils.dialog_base import BaseDialog
    monkeypatch.setattr(BaseDialog, "exec", lambda self: pytest.fail("dialog must not open"))
    stub = _stub([_rec("112-233-445 95"), _rec("123-456-789 64")])
    assert stub._check_records_before_xml() is True
