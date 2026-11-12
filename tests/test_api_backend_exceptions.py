"""R1: any exception raised by a backend must become a failed result, not NameError."""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

API_KEY = "abcdef1234567890abcdef1234567890"


def _client(exc):
    from api.mintrud_api import MintrudClient
    backend = MagicMock()
    backend.send.side_effect = exc
    client = MintrudClient(backend="auto")
    client._init_backend = MagicMock()
    client._backend = backend
    client._get_backend_fallback_list = MagicMock(return_value=[(backend, "stub")])
    client._get_proxies = MagicMock(return_value=None)
    client._get_verify = MagicMock(return_value=True)
    return client


@pytest.mark.parametrize("exc", [RuntimeError("x"), ValueError("x")])
def test_send_xml_backend_exception(tmp_path, exc):
    xml = tmp_path / "a.xml"
    xml.write_text("<Data/>", encoding="utf-8")
    result = _client(exc).send_xml(API_KEY, str(xml))
    assert result["success"] is False
    assert "x" != result["error"]


@pytest.mark.parametrize("exc", [RuntimeError("x"), ValueError("x")])
def test_send_xml_signed_backend_exception(tmp_path, exc):
    xml = tmp_path / "a.xml"
    xml.write_text("<Data/>", encoding="utf-8")
    sig = tmp_path / "a.xml.sig"
    sig.write_bytes(b"sig")
    result = _client(exc).send_xml_signed(API_KEY, str(xml), str(sig))
    assert result["success"] is False


@pytest.mark.parametrize("exc", [RuntimeError("x"), ValueError("x")])
def test_query_by_setid_backend_exception(exc):
    result = _client(exc).query_by_setid(API_KEY, "12345")
    assert result["success"] is False
