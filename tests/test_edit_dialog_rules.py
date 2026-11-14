"""A3: EditDialog uses utils.record_rules (checksum, normalization, one error dialog)."""
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _row(snils="112-233-445 95", date="01.02.2024"):
    return {0: "Тестов", 1: "Тест", 2: "Тестович", 3: snils, 4: "Слесарь",
            5: "", 6: "", 7: "", 8: "", 9: "Удовлетворительно",
            10: "1", 11: date, 12: "П-1"}


@pytest.fixture
def dialog(app, monkeypatch):
    from tabs import data_view_tab
    from utils import error_utils
    shown = []
    monkeypatch.setattr(error_utils, "show_error_dialog",
                        lambda parent, title, msg, *a, **k: shown.append(msg))

    def make(row):
        dlg = data_view_tab.EditDialog(row)
        calls = []
        monkeypatch.setattr(dlg, "accept", lambda: calls.append(1))
        return dlg, calls
    make.shown = shown
    return make


def test_bad_snils_checksum_blocks_accept(dialog):
    dlg, accepted = dialog(_row(snils="123-456-789 00"))
    dlg.validate_and_save()
    assert accepted == []
    assert len(dialog.shown) == 1
    assert "СНИЛС" in dialog.shown[0]


def test_all_errors_in_one_dialog(dialog):
    dlg, accepted = dialog(_row(snils="123-456-789 00", date="32.13.2024"))
    dlg.validate_and_save()
    assert accepted == []
    assert len(dialog.shown) == 1
    lines = dialog.shown[0].split("\n")
    assert len(lines) == 2
    assert all(": " in line for line in lines)


def test_valid_record_is_normalized(dialog):
    dlg, accepted = dialog(_row(snils="11223344595", date="2024-02-01"))
    dlg.validate_and_save()
    assert accepted == [1]
    assert dialog.shown == []
    data = dlg.get_data()
    assert data[3] == "112-233-445 95"
    assert data[11] == "01.02.2024"
