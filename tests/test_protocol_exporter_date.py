"""R11: protocol date placeholder uses record_rules.normalize_date."""
from docx import Document

from exporters.protocol_exporter import ProtocolExporter


def _fill(commission, records):
    doc = Document()
    doc.add_paragraph("Дата: {{Дата}}")
    ProtocolExporter._fill_commission_data(doc, commission, "1", None, records)
    return doc.paragraphs[0].text


def test_exam_date_iso_datetime():
    assert "04.11.2026" in _fill({"exam_date": "2026-11-04 00:00:00"}, [])


def test_record_date_fallback_iso_datetime():
    assert "04.11.2026" in _fill({}, [{"date": "2026-11-04 00:00:00"}])


def test_unparseable_date_kept_as_is():
    assert "когда-нибудь" in _fill({"exam_date": "когда-нибудь"}, [])
