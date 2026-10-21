"""WinHTTP backend: TLS protocol option and readable COM error messages."""
import pytest

from api.backends import wininet_backend as wb
from api.mintrud_api import _is_ssl_error


def _com_error(code: int) -> Exception:
    """Exception shaped like pywintypes.com_error for WinHTTP error `code`."""
    scode = (0x80070000 | code) - (1 << 32)  # signed HRESULT as COM reports it
    return Exception(-2147352567, "Ошибка.", (0, "WinHttp.WinHttpRequest",
                                              "Ошибка поддержки безопасных каналов\r\n",
                                              None, 0, scode), None)


class _FakeOle:
    def __init__(self, rejected=()):
        self.rejected = set(rejected)
        self.puts = []

    def GetIDsOfNames(self, name):
        assert name == "Option"
        return 6

    def Invoke(self, dispid, lcid, flags, result_wanted, option, value):
        assert flags == wb.DISPATCH_PROPERTYPUT
        if (option, value) in self.rejected:
            raise Exception(-2147024809, "Параметр задан неверно.", None, None)
        self.puts.append((option, value))


class _FakeHttp:
    def __init__(self, ole):
        self._oleobj_ = ole


def test_winhttp_error_code_from_com_error():
    assert wb._winhttp_error_code(_com_error(12157)) == 12157
    assert wb._winhttp_error_code(Exception("plain")) == 0


def test_secure_channel_error_is_reported_as_tls_and_triggers_fallback():
    msg = wb._describe_winhttp_error(_com_error(12157))
    assert "TLS" in msg and "12157" in msg
    assert _is_ssl_error(msg)


def test_untrusted_ca_is_tls_error():
    assert _is_ssl_error(wb._describe_winhttp_error(_com_error(12045)))


def test_timeout_is_network_error_not_tls():
    msg = wb._describe_winhttp_error(_com_error(12002))
    assert "12002" in msg
    assert not _is_ssl_error(msg)


def test_enable_modern_tls_prefers_tls13():
    ole = _FakeOle()
    wb._enable_modern_tls(_FakeHttp(ole))
    assert ole.puts == [(wb.WINHTTP_REQUEST_OPTION_SECURE_PROTOCOLS,
                         wb.SECURE_PROTOCOL_TLS1_2 | wb.SECURE_PROTOCOL_TLS1_3)]


def test_enable_modern_tls_falls_back_to_tls12_when_tls13_unsupported():
    opt = wb.WINHTTP_REQUEST_OPTION_SECURE_PROTOCOLS
    ole = _FakeOle(rejected={(opt, wb.SECURE_PROTOCOL_TLS1_2 | wb.SECURE_PROTOCOL_TLS1_3)})
    wb._enable_modern_tls(_FakeHttp(ole))
    assert ole.puts == [(opt, wb.SECURE_PROTOCOL_TLS1_2)]


def test_set_request_option_survives_missing_oleobj():
    assert wb._set_request_option(object(), 9, 0x800) is False


@pytest.mark.skipif(not wb.WININET_AVAILABLE, reason="pywin32 not installed")
def test_real_winhttp_object_accepts_tls_options():
    import win32com.client
    http = win32com.client.Dispatch("WinHttp.WinHttpRequest.5.1")
    http.Open("GET", "https://example.invalid/", False)
    assert wb._set_request_option(
        http, wb.WINHTTP_REQUEST_OPTION_SECURE_PROTOCOLS, wb.SECURE_PROTOCOL_TLS1_2)
    assert wb._set_request_option(
        http, wb.WINHTTP_REQUEST_OPTION_SSL_ERROR_IGNORE_FLAGS, wb.SSL_ERROR_IGNORE_ALL)
