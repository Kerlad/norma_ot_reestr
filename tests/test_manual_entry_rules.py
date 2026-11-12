"""A2: manual entry form uses utils.record_rules; errors under fields, no message boxes."""
import pytest
from PySide6.QtWidgets import QMessageBox, QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(app, monkeypatch):
    from tabs.data_entry_tab import DataEntryTab
    from utils.dialog_base import BaseDialog
    from utils.toast import Toast
    monkeypatch.setattr(BaseDialog, "exec", lambda self: 0)
    box = {"n": 0}

    def boxed(*a, **k):
        box["n"] += 1
        return QMessageBox.StandardButton.Ok

    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(boxed))
    toasts = []
    monkeypatch.setattr(Toast, "success", classmethod(lambda cls, p, m, *a, **k: toasts.append(("ok", m))))
    monkeypatch.setattr(Toast, "warning", classmethod(lambda cls, p, m, *a, **k: toasts.append(("warn", m))))
    t = DataEntryTab()
    t._open_manual_dialog()
    t._boxes = box
    t._toasts = toasts
    t._got = []
    t.data_loaded.connect(lambda recs, merge: t._got.append(recs))
    return t


class _Dlg:
    def accept(self):
        pass


def _fill(t, **kw):
    vals = dict(last="Тестов", first="Тест", middle="Тестович", snils="112-233-445 95",
                position="Электромонтёр 4 разряда", program="1", date="04.11.2026", protocol="ПР-1")
    vals.update(kw)
    t._last_name_input.setText(vals["last"])
    t._first_name_input.setText(vals["first"])
    t._middle_name_input.setText(vals["middle"])
    t._snils_input.setText(vals["snils"])
    t._position_input.setText(vals["position"])
    t._program_input.setText(vals["program"])
    t._date_input.setText(vals["date"])
    t._protocol_input.setText(vals["protocol"])


def test_bad_snils_checksum_shows_hint_and_blocks(tab):
    _fill(tab, snils="123-456-789 00")
    tab._save_manual_from_dialog(_Dlg())
    assert tab._got == []
    assert "контрольная сумма" in tab._field_hints["snils"].text()
    assert tab._boxes["n"] == 0


def test_valid_record_without_middle_name_is_normalized_and_saved(tab):
    _fill(tab, middle="", date="04112026")
    tab._save_manual_from_dialog(_Dlg())
    assert len(tab._got) == 1
    rec = tab._got[0][0]
    assert rec["snils"] == "112-233-445 95"
    assert rec["date"] == "04.11.2026"
    assert rec["middle_name"] == ""
    kind, text = tab._toasts[-1]
    assert kind == "ok" and "не отправлена" in text and "Отчество не указано" in text
    assert tab._boxes["n"] == 0


def test_three_bad_fields_three_hints_no_message_box(tab):
    _fill(tab, snils="123", program="99", date="31.02.2026")
    tab._save_manual_from_dialog(_Dlg())
    assert tab._got == []
    shown = [k for k, h in tab._field_hints.items() if h.text()]
    assert set(shown) == {"snils", "program", "date"}
    assert tab._boxes["n"] == 0
    # typing in a field clears its error
    tab._snils_input.setText("112-233-445 9")
    assert tab._field_hints["snils"].text() == ""
