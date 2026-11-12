import os
import tempfile

import pytest

from importers import xml_importer
from importers.xml_importer import load_xml

XSD_ANY = '''<?xml version="1.0" encoding="utf-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" elementFormDefault="qualified">
  <xs:element name="RegistrySet">
    <xs:complexType>
      <xs:sequence>
        <xs:any minOccurs="0" maxOccurs="unbounded" processContents="lax"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>'''

XML_VALID = '''<?xml version="1.0"?>
<RegistrySet>
    <RegistryRecord>
        <Worker>
            <LastName>Иванов</LastName><FirstName>Иван</FirstName><MiddleName>Иванович</MiddleName>
            <Snils>123-456-789 00</Snils><Position>Инженер</Position>
            <EmployerInn>7701123456</EmployerInn><EmployerTitle>ООО Тест</EmployerTitle>
        </Worker>
        <Organization><Inn>7701123456</Inn><Title>УЦ Тест</Title></Organization>
        <Test isPassed="true" learnProgramId="1">
            <Date>2025-09-25</Date><ProtocolNumber>П-001</ProtocolNumber>
        </Test>
    </RegistryRecord>
</RegistrySet>'''


def _write(content, suffix):
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode='w', encoding='utf-8') as f:
        f.write(content)
        return f.name


def test_successful_xml_import_does_not_log_validation_error(monkeypatch):
    calls = []

    import utils.audit as audit_mod

    def fake_log_audit(event, detail=""):
        calls.append((event, detail))

    # xml_importer imports log_audit from utils.audit inside load_xml(), so patch the source module.
    monkeypatch.setattr(audit_mod, "log_audit", fake_log_audit)

    xml_path = _write(XML_VALID, '.xml')
    xsd_path = _write(XSD_ANY, '.xsd')
    try:
        records, err_count, err_msgs, xsd_errors = load_xml(xml_path, xsd_path=xsd_path)
    finally:
        os.remove(xml_path)
        os.remove(xsd_path)

    # The import itself succeeded and XSD validation ran without errors
    assert xsd_errors == []
    assert err_count == 0
    assert len(records) == 1
    assert not any(event == "XML_VALIDATION_ERROR" for event, _ in calls)
