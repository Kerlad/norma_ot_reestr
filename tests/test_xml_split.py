"""C5: export_to_xml_parts — split of >MAX_EXPORT_RECORDS records into several XSD-valid files."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from lxml import etree

from exporters import xml_exporter
from exporters.xml_exporter import export_to_xml_parts
from utils.constants import MAX_EXPORT_RECORDS

XSD = os.path.join(os.path.dirname(__file__), '..', 'schema', 'educated_person_import_v1.0.9.xsd')


def _records(n):
    return [{
        'last_name': 'Иванов', 'first_name': 'Иван', 'middle_name': 'Иванович',
        'snils': '11223344595', 'position': 'Слесарь %d' % i,
        'employer_inn': '7707083893', 'employer_title': 'ООО Тест',
        'tc_inn': '500100732259', 'tc_title': 'УЦ Тест',
        'result': 'Удовлетворительно', 'program': '1', 'date': '01.02.2024', 'protocol': 'П-%d' % i,
    } for i in range(n)]


def _count_and_validate(path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    schema = etree.XMLSchema(etree.parse(XSD, parser))
    doc = etree.parse(path, parser)
    assert schema.validate(doc), schema.error_log
    return len(doc.getroot().findall('RegistryRecord'))


@pytest.mark.parametrize("n,expected", [
    (MAX_EXPORT_RECORDS + 1, [MAX_EXPORT_RECORDS, 1]),
    (2 * MAX_EXPORT_RECORDS, [MAX_EXPORT_RECORDS, MAX_EXPORT_RECORDS]),
])
def test_split_two_parts(tmp_path, n, expected):
    base = str(tmp_path / "report.xml")
    ok, msg, paths = export_to_xml_parts(_records(n), base)
    assert ok, msg
    assert [os.path.basename(p) for p in paths] == ["report-1.xml", "report-2.xml"]
    assert [_count_and_validate(p) for p in paths] == expected
    assert sorted(os.listdir(tmp_path)) == ["report-1.xml", "report-2.xml"]


def test_not_over_limit_uses_single_file(tmp_path):
    base = str(tmp_path / "one.xml")
    ok, msg, paths = export_to_xml_parts(_records(3), base)
    assert ok and paths == [base]
    assert _count_and_validate(base) == 3
    assert os.listdir(tmp_path) == ["one.xml"]


def test_empty_records(tmp_path):
    ok, msg, paths = export_to_xml_parts([], str(tmp_path / "x.xml"))
    assert not ok and paths == []


def test_name_collision_gets_suffix(tmp_path):
    (tmp_path / "report-1.xml").write_text("old", encoding="utf-8")
    ok, msg, paths = export_to_xml_parts(_records(MAX_EXPORT_RECORDS + 1), str(tmp_path / "report.xml"))
    assert ok, msg
    assert [os.path.basename(p) for p in paths] == ["report-2-1.xml", "report-2-2.xml"]
    assert (tmp_path / "report-1.xml").read_text(encoding="utf-8") == "old"


def test_failure_in_second_part_removes_written_parts(tmp_path, monkeypatch):
    real = xml_exporter._validate_against_schema
    calls = []

    def fake(content):
        calls.append(1)
        return "Файл не прошёл проверку по схеме реестра" if len(calls) == 2 else real(content)

    monkeypatch.setattr(xml_exporter, "_validate_against_schema", fake)
    ok, msg, paths = export_to_xml_parts(_records(MAX_EXPORT_RECORDS + 1), str(tmp_path / "r.xml"))
    assert not ok and paths == []
    assert "2 из 2" in msg
    assert os.listdir(tmp_path) == []


def test_write_failure_removes_written_parts(tmp_path, monkeypatch):
    real = xml_exporter._write_atomic
    calls = []

    def fake(path, data):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(xml_exporter, "_write_atomic", fake)
    ok, msg, paths = export_to_xml_parts(_records(MAX_EXPORT_RECORDS + 1), str(tmp_path / "r.xml"))
    assert not ok and paths == []
    assert os.listdir(tmp_path) == []


def test_bad_record_blocks_everything(tmp_path):
    recs = _records(MAX_EXPORT_RECORDS + 1)
    recs[-1]['date'] = 'xx'
    ok, msg, paths = export_to_xml_parts(recs, str(tmp_path / "r.xml"))
    assert not ok and "Запись %d" % (MAX_EXPORT_RECORDS + 1) in msg
    assert os.listdir(tmp_path) == []


def test_export_to_xml_still_refuses_over_limit(tmp_path):
    ok, msg = xml_exporter.export_to_xml(_records(MAX_EXPORT_RECORDS + 1), str(tmp_path / "a.xml"))
    assert not ok and str(MAX_EXPORT_RECORDS) in msg


# ---- tab: confirmation + several files -> folder opened, no auto-transfer

def _stub_tab(n, monkeypatch, answer):
    from PySide6.QtWidgets import QMessageBox
    from tabs import data_view_tab as m
    asked = []

    def fake_question(parent, title, text, *a, **k):
        asked.append(text)
        return answer

    monkeypatch.setattr(QMessageBox, "question", fake_question)
    monkeypatch.setattr(m, "safe_message_box", lambda *a, **k: None)
    stub = SimpleNamespace(_model=SimpleNamespace(rowCount=lambda: n), xml_ready=SimpleNamespace(emit=lambda p: asked.append(("emit", p))))
    stub._prepare_xml_export = lambda: {}
    stub._confirm_split = lambda: m.DataViewTab._confirm_split(stub)
    return m, stub, asked


def test_confirm_split_text_and_cancel(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    m, stub, asked = _stub_tab(5001, monkeypatch, QMessageBox.StandardButton.No)
    assert m.DataViewTab._confirm_split(stub) == -1
    assert asked == ["Записей 5001. Реестр принимает до 5000 в одном файле. Сформировать 2 файлов?"]


def test_confirm_split_not_needed(monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    m, stub, asked = _stub_tab(5000, monkeypatch, QMessageBox.StandardButton.No)
    assert m.DataViewTab._confirm_split(stub) == 0 and asked == []


def test_go_mode_with_parts_opens_folder_without_transfer(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from utils import ui_helpers, xml_output
    m, stub, asked = _stub_tab(5001, monkeypatch, QMessageBox.StandardButton.Yes)
    opened = []
    monkeypatch.setattr(ui_helpers, "open_folder", lambda *a, **k: opened.append(a))
    monkeypatch.setattr(xml_output, "next_xml_path", lambda: str(tmp_path / "x.xml"))
    paths = [str(tmp_path / "x-1.xml"), str(tmp_path / "x-2.xml")]
    stub._write_xml_parts = lambda base, org: (True, "ok", paths)
    m.DataViewTab.convert_to_xml_and_go(stub)
    assert len(opened) == 1 and opened[0][0] == str(tmp_path)
    assert not any(isinstance(a, tuple) for a in asked)  # no xml_ready emit
