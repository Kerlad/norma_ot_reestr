"""R7: transport error texts (URL, proxy address with credentials) never reach result["error"]."""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

API_KEY = "abcdef1234567890abcdef1234567890"
LEAKY = (
    "HTTPSConnectionPool(host='edu.rosmintrud.ru', port=443): Max retries exceeded with url: /api/set/push "
    "(Caused by NewConnectionError('Failed: http://user:pass@proxy:3128'))"
)


def _client(send_result=None, exc=None):
    from api.mintrud_api import MintrudClient
    backend = MagicMock()
    if exc is not None:
        backend.send.side_effect = exc
    else:
        backend.send.return_value = send_result
    client = MintrudClient(backend="auto")
    client._init_backend = MagicMock()
    client._backend = backend
    client._get_backend_fallback_list = MagicMock(return_value=[(backend, "stub")])
    client._get_proxies = MagicMock(return_value=None)
    client._get_verify = MagicMock(return_value=True)
    return client


def _assert_clean(text):
    low = text.lower()
    for bad in ("proxy:3128", "http", "pass", "user:", "edu.rosmintrud", "/api/"):
        assert bad not in low, bad


@pytest.mark.parametrize("raw,expected", [
    ("Read timed out. (read timeout=60)", "Сервер не ответил за 60 секунд"),
    ("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", "защищённое соединение"),
    ("Tunnel connection failed: 407 Proxy Authentication Required", "Прокси отклонил запрос"),
    ("[Errno 11001] getaddrinfo failed", "Нет соединения с сервером"),
    ("HTTP 500: Internal Server Error", "код 500"),
    ("", "Не удалось выполнить запрос"),
    ("something unexpected http://user:pass@host:3128", "Не удалось выполнить запрос"),
])
def test_user_error_mapping(raw, expected):
    from api.mintrud_api import _user_error
    out = _user_error(raw)
    assert expected in out
    _assert_clean(out)


def test_send_xml_returns_fixed_text_for_backend_error(tmp_path):
    xml = tmp_path / "a.xml"
    xml.write_text("<Data/>", encoding="utf-8")
    result = _client((False, 0, b"", LEAKY)).send_xml(API_KEY, str(xml))
    assert result["success"] is False
    _assert_clean(result["error"])


def test_send_xml_signed_returns_fixed_text(tmp_path):
    xml = tmp_path / "a.xml"
    xml.write_text("<Data/>", encoding="utf-8")
    sig = tmp_path / "a.xml.sig"
    sig.write_bytes(b"sig")
    result = _client((False, 0, b"", LEAKY)).send_xml_signed(API_KEY, str(xml), str(sig))
    _assert_clean(result["error"])


def test_query_returns_fixed_text_for_backend_error():
    result = _client((False, 0, b"", LEAKY)).query_by_setid(API_KEY, "12345")
    assert result["success"] is False
    _assert_clean(result["error"])


def test_backend_exception_text_not_shown():
    result = _client(exc=RuntimeError(LEAKY)).query_by_setid(API_KEY, "12345")
    _assert_clean(result["error"])


def test_ssl_fallback_still_detected_from_raw_text(tmp_path):
    # _is_ssl_error must keep working on the raw text, the user sees only the fixed message
    xml = tmp_path / "a.xml"
    xml.write_text("<Data/>", encoding="utf-8")
    raw = "[SSL: CERTIFICATE_VERIFY_FAILED] http://user:pass@proxy:3128"
    result = _client((False, 0, b"", raw)).send_xml(API_KEY, str(xml))
    assert result.get("ssl_error_detected") is True
    _assert_clean(result["error"])
