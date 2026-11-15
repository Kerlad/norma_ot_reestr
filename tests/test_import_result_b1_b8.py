"""B1/B8: import result dialog, safe replace mode, legacy date normalization."""
import os
import tempfile

import pytest
from PySide6.QtWidgets import QMessageBox, QApplication, QTableWidget, QLabel, QFileDialog

from db.database import DatabaseManager
from db.schema import create_schema
from db.workers_data_repo import WorkersDataRepo
from utils.crypto import clear_caches


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def setup_db():
    clear_caches()
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db = DatabaseManager.get_instance(db_path)
    db.initialize()
    create_schema()
    yield db
    db.close_all()
    if os.path.exists(db_path):
        os.remove(db_path)


def _rec(snils="112-233-445 95", program="1", date="04.11.2026"):
    return {'last_name': 'Тестов', 'first_name': 'Тест', 'middle_name': 'Тестович',
            'snils': snils, 'position': 'Инженер', 'employer_inn': '', 'employer_title': '',
            'tc_inn': '', 'tc_title': '', 'result': '1', 'program': program,
            'date': date, 'protocol': '1'}


@pytest.fixture
def tab(app, monkeypatch, tmp_path):
    from tabs.data_entry_tab import DataEntryTab
    from utils.dialog_base import BaseDialog
    from utils.toast import Toast
    monkeypatch.setattr(BaseDialog, "exec", lambda self: 0)
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(Toast, "success", classmethod(lambda cls, *a, **k: None))
    t = DataEntryTab()
    t.data_dir = str(tmp_path)
    t._got = []
    t.data_loaded.connect(lambda recs, merge: t._got.append((recs, merge)))
    return t


def test_result_dialog_numbers_match_report(tab, monkeypatch, tmp_path):
    from utils.dialog_base import BaseDialog
    captured = {}

    def spy_exec(self):
        captured["dialog"] = self
        return 0

    monkeypatch.setattr(BaseDialog, "exec", spy_exec)
    errors = [{'row': 5, 'type': 'Ошибка', 'field': 'СНИЛС', 'message': 'Неверная контрольная сумма',
               'fio': 'Тестов Тест Тестович'}]
    recs = [dict(_rec(), source_row=2), dict(_rec(), source_row=3), dict(_rec(program="2"), source_row=4)]
    tab._finalize_import(recs, False, set(), errors, {5}, auto_fixed=3)

    dlg = captured["dialog"]
    text = dlg.findChild(QLabel, "importSummary").text()
    assert "Загружено:</b> 2" in text and "Строк с ошибками:</b> 1" in text
    assert "Дублей:</b> 1" in text and "автоматически:</b> 3" in text
    table = dlg.findChild(QTableWidget, "importResultTable")
    assert table.rowCount() == 2  # 1 error + 1 duplicate
    assert table.item(0, 0).text() == "5" and table.item(0, 1).text() == "Тестов Тест Тестович"
    assert table.item(1, 0).text() == "3" and "Повтор записи" in table.item(1, 3).text()

    # saved report contains the same rows
    out = str(tmp_path / "r.xlsx")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (out, "")))
    tab._export_error_report(dlg)
    from openpyxl import load_workbook
    ws = load_workbook(out).active
    kinds = [ws.cell(row=r, column=1).value for r in range(2, 4)]
    assert kinds == ["Ошибка", "Дубликат"]
    info = tab._last_import_label.text()
    assert "<b>2</b>" in info and "<b>1</b>" in info


def test_replace_mode_with_no_valid_records_emits_nothing(tab):
    tab._finalize_import([], True, set(), [{'row': 2, 'type': 'Ошибка', 'field': 'СНИЛС',
                                            'message': 'x', 'fio': ''}], {2})
    assert tab._got == []


def test_merge_dialog_text_uses_count(tab, monkeypatch):
    from utils.dialog_base import BaseDialog
    seen = {}

    def spy(self):
        seen["texts"] = [w.text() for w in self.findChildren(QLabel)] + \
                        [b.text() for b in self.findChildren(__import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
        return 0

    monkeypatch.setattr(BaseDialog, "exec", spy)
    tab._show_merge_dialog(7)
    joined = " | ".join(seen["texts"])
    assert "В базе уже есть записей: 7" in joined and "Удалить все 7 и заменить" in joined


def test_replace_all_is_atomic(monkeypatch):
    WorkersDataRepo.add_many([_rec(), _rec(program="2")])
    import db.workers_data_repo as mod
    real = mod.encrypt_value
    calls = {"n": 0}

    def flaky(v):
        calls["n"] += 1
        if calls["n"] > 6:  # fails while building the 2nd record
            raise RuntimeError("boom")
        return real(v)

    monkeypatch.setattr(mod, "encrypt_value", flaky)
    with pytest.raises(RuntimeError):
        WorkersDataRepo.replace_all([_rec(program="3"), _rec(program="4"), _rec(program="5")])
    monkeypatch.setattr(mod, "encrypt_value", real)
    assert WorkersDataRepo.count() == 2
    assert WorkersDataRepo.replace_all([_rec(program="3")]) == 1
    assert WorkersDataRepo.count() == 1


def test_normalize_dates():
    WorkersDataRepo.add_many([_rec(date="04112026"), _rec(program="2", date="05.11.2026")])
    assert WorkersDataRepo.normalize_dates() == 1
    dates = sorted(r['date'] for r in WorkersDataRepo.get_all())
    assert dates == ["04.11.2026", "05.11.2026"]
    assert WorkersDataRepo.normalize_dates() == 0


def test_data_view_shows_formatted_snils_and_replace(app, monkeypatch):
    from tabs.data_view_tab import DataViewTab
    WorkersDataRepo.add_many([_rec(snils="11223344595", date="04112026")])
    view = DataViewTab()
    assert view._model.get_row_data(0)['snils'] == "112-233-445 95"
    assert view._model.get_row_data(0)['date'] == "04.11.2026"
    view.add_data([_rec(program="2")], merge_mode=True)
    assert WorkersDataRepo.count() == 1
    assert WorkersDataRepo.get_all()[0]['program'] == 2
