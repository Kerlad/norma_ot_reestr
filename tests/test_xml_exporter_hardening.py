"""R2/R3: усиление экспорта XML (результат, проверка по XSD, атомарная запись)."""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from exporters import xml_exporter
from exporters.xml_exporter import export_to_xml, build_xml

SCHEMA_FAIL = "Не удалось проверить файл по схеме реестра. Переустановите программу."


def _rec(**kw):
    rec = {
        'last_name': 'Тестов', 'first_name': 'Тест', 'middle_name': 'Тестович',
        'snils': '112-233-445 95', 'position': 'Инженер',
        'employer_inn': '7701234567', 'employer_title': 'ООО Тест',
        'tc_inn': '7707654321', 'tc_title': 'УЦ Тест',
        'result': 'Удовлетворительно', 'program': '1',
        'date': '15.05.2025', 'protocol': 'П-001',
    }
    rec.update(kw)
    return rec


def _leftovers(tmp_path):
    return list(tmp_path.iterdir())


@pytest.mark.parametrize("result", ["удовлетворительно", "", None, "Сдал"])
def test_bad_result_refused(tmp_path, result):
    path = tmp_path / "out.xml"
    ok, msg = export_to_xml([_rec(), _rec(result=result)], str(path))
    assert ok is False
    assert msg == "Запись 2: не указан результат проверки знаний"
    assert _leftovers(tmp_path) == []


def test_failed_result_exports_false(tmp_path):
    path = tmp_path / "out.xml"
    ok, msg = export_to_xml([_rec(result='Неудовлетворительно', snils='123-456-789 64')], str(path))
    assert ok, msg
    assert b'isPassed="false"' in path.read_bytes()


def test_invalid_date_message_has_no_value(tmp_path):
    ok, msg = export_to_xml([_rec(date='секрет-31.31.9999')], str(tmp_path / "o.xml"))
    assert ok is False
    assert "Запись 1" in msg
    assert "секрет" not in msg and "9999" not in msg


def test_schema_missing_refuses(tmp_path):
    path = tmp_path / "out.xml"
    with mock.patch.object(xml_exporter.os.path, "exists", return_value=False):
        ok, msg = export_to_xml([_rec()], str(path))
    assert ok is False
    assert msg == SCHEMA_FAIL
    assert _leftovers(tmp_path) == []


def test_no_lxml_refuses(tmp_path):
    path = tmp_path / "out.xml"
    with mock.patch.dict(sys.modules, {"lxml": None, "lxml.etree": None}):
        ok, msg = export_to_xml([_rec()], str(path))
    assert ok is False
    assert msg == SCHEMA_FAIL
    assert _leftovers(tmp_path) == []


def test_validation_exception_refuses_without_leak(tmp_path, caplog):
    path = tmp_path / "out.xml"
    with mock.patch("lxml.etree.XMLSchema", side_effect=RuntimeError("Тестов 11223344595")):
        with caplog.at_level("DEBUG"):
            ok, msg = export_to_xml([_rec()], str(path))
    assert ok is False
    assert msg == SCHEMA_FAIL
    assert _leftovers(tmp_path) == []
    assert "Тестов" not in caplog.text and "11223344595" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_document_invalid_message_has_no_values(tmp_path):
    path = tmp_path / "out.xml"
    ok, msg = export_to_xml([_rec(program='ПДПРОГРАММА5')], str(path))
    assert ok is False
    assert msg.startswith("Файл не прошёл проверку по схеме реестра")
    assert "ПДПРОГРАММА" not in msg
    assert _leftovers(tmp_path) == []


def test_control_char_in_position_is_stripped(tmp_path):
    path = tmp_path / "out.xml"
    ok, msg = export_to_xml([_rec(position="Инж\x0bенер\x00")], str(path))
    assert ok, msg
    data = path.read_bytes()
    assert "Инженер".encode("utf-8") in data
    assert b"\x0b" not in data
    assert [p.name for p in _leftovers(tmp_path)] == ["out.xml"]


def test_build_xml_strips_control_chars():
    xml = build_xml([_rec(last_name="А\x0cБ", protocol="\x1fП")])
    assert b"\x0c" not in xml and b"\x1f" not in xml
    assert "<LastName>АБ</LastName>".encode("utf-8") in xml


def test_unexpected_exception_becomes_message(tmp_path):
    path = tmp_path / "out.xml"
    with mock.patch.object(xml_exporter, "build_xml", side_effect=ValueError("Тестов")):
        ok, msg = export_to_xml([_rec()], str(path))
    assert (ok, msg) == (False, "Не удалось сформировать XML")


def test_atomic_write_keeps_old_file_on_failure(tmp_path):
    path = tmp_path / "out.xml"
    path.write_bytes(b"OLD")
    with mock.patch.object(xml_exporter.os, "replace", side_effect=OSError("boom")):
        ok, msg = export_to_xml([_rec()], str(path))
    assert ok is False
    assert path.read_bytes() == b"OLD"
    assert [p.name for p in _leftovers(tmp_path)] == ["out.xml"]
