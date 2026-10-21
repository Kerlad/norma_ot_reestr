"""
WinINET HTTP backend using WinHTTP COM object (WinHttp.WinHttpRequest.5.1).
Available on all Windows systems via win32com.
"""
import logging
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from .base_backend import BaseBackend, BackendRegistry

logger = logging.getLogger(__name__)

WININET_AVAILABLE = False

try:
    import win32com.client
    WININET_AVAILABLE = True
except ImportError:
    pass

WINHTTP_ACCESS_TYPE_DEFAULT_PROXY = 0
WINHTTP_ACCESS_TYPE_NO_PROXY = 1
WINHTTP_ACCESS_TYPE_NAMED_PROXY = 3

WINHTTP_AUTOLOGON_POLICY_ALWAYS = 0
WINHTTP_AUTOLOGON_POLICY_ONLY_IF_CHALLENGED = 1
WINHTTP_AUTOLOGON_POLICY_NEVER = 2

# WinHttpRequestOption enum of the COM object (NOT the WINHTTP_OPTION_* C API
# numbers: e.g. 31 there is SECURITY_FLAGS, here it is an unrelated option).
WINHTTP_REQUEST_OPTION_SSL_ERROR_IGNORE_FLAGS = 4
WINHTTP_REQUEST_OPTION_SECURE_PROTOCOLS = 9

SSL_ERROR_IGNORE_UNKNOWN_CA = 0x0100
SSL_ERROR_IGNORE_CERT_WRONG_USAGE = 0x0200
SSL_ERROR_IGNORE_CERT_CN_INVALID = 0x1000
SSL_ERROR_IGNORE_CERT_DATE_INVALID = 0x2000
SSL_ERROR_IGNORE_ALL = (
    SSL_ERROR_IGNORE_UNKNOWN_CA |
    SSL_ERROR_IGNORE_CERT_WRONG_USAGE |
    SSL_ERROR_IGNORE_CERT_CN_INVALID |
    SSL_ERROR_IGNORE_CERT_DATE_INVALID
)

SECURE_PROTOCOL_TLS1_2 = 0x0800
SECURE_PROTOCOL_TLS1_3 = 0x2000
# The COM object does not always follow the system DefaultSecureProtocols:
# on Windows 10 (and 7/8.1) it may offer only SSL3/TLS 1.0, which the
# registry server rejects with ERROR_WINHTTP_SECURE_CHANNEL_ERROR (12157).
# TLS 1.3 is rejected by WinHTTP builds that lack it, hence the fallback.
SECURE_PROTOCOL_CANDIDATES = (
    SECURE_PROTOCOL_TLS1_2 | SECURE_PROTOCOL_TLS1_3,
    SECURE_PROTOCOL_TLS1_2,
)

DISPATCH_PROPERTYPUT = 4

# WinHTTP error codes (HRESULT = 0x80070000 | code)
WINHTTP_TLS_ERRORS = {
    12037: "срок действия сертификата сервера истёк или ещё не наступил",
    12038: "имя в сертификате сервера не совпадает с адресом",
    12044: "сервер запросил клиентский сертификат",
    12045: "сертификат сервера выдан недоверенным центром сертификации",
    12057: "не удалось проверить отзыв сертификата",
    12157: "ошибка защищённого канала (Windows не согласовала с сервером "
           "версию TLS или набор шифров)",
    12169: "сертификат сервера недействителен",
    12170: "сертификат сервера отозван",
    12175: "ошибка проверки защищённого соединения",
    12179: "сертификат сервера не предназначен для этого использования",
}
WINHTTP_NETWORK_ERRORS = {
    12002: "истекло время ожидания ответа сервера",
    12007: "не удалось найти адрес сервера (DNS)",
    12029: "не удалось подключиться к серверу",
    12030: "соединение с сервером прервано",
}


def _set_request_option(http, option: int, value: int) -> bool:
    """Set WinHttpRequest.Option(option) = value; True on success.

    Late-bound win32com cannot assign parameterized properties
    (``http.Option[n] = v`` fails), so the put goes through IDispatch.
    """
    try:
        oleobj = http._oleobj_
        dispid = oleobj.GetIDsOfNames("Option")
        oleobj.Invoke(dispid, 0, DISPATCH_PROPERTYPUT, 0, option, value)
        return True
    except Exception as e:
        logger.debug("WinHTTP: option %d not set: %s", option, str(e))
        return False


def _enable_modern_tls(http) -> None:
    """Allow TLS 1.2 (and 1.3 where supported) on the request."""
    for protocols in SECURE_PROTOCOL_CANDIDATES:
        if _set_request_option(http, WINHTTP_REQUEST_OPTION_SECURE_PROTOCOLS, protocols):
            logger.debug("WinHTTP: secure protocols set to 0x%X", protocols)
            return
    logger.warning("WinHTTP: could not set secure protocols, using system defaults")


def _winhttp_error_code(exc: Exception) -> int:
    """Extract the WinHTTP error code (12xxx) from a COM error, 0 if none."""
    args = getattr(exc, "args", ())
    candidates = []
    if len(args) >= 3 and isinstance(args[2], tuple) and len(args[2]) >= 6:
        candidates.append(args[2][5])
    if args:
        candidates.append(args[0])
    for value in candidates:
        if not isinstance(value, int):
            continue
        value &= 0xFFFFFFFF
        if value & 0xFFFF0000 == 0x80070000:
            code = value & 0xFFFF
            if 12000 <= code < 13000:
                return code
    return 0


def _describe_winhttp_error(exc: Exception) -> str:
    """Human-readable message for a WinHTTP COM error.

    TLS failures always contain "TLS" so MintrudClient treats them as SSL
    errors and retries through the next (OpenSSL-based) backend.
    """
    code = _winhttp_error_code(exc)
    if code in WINHTTP_TLS_ERRORS:
        return "Ошибка TLS/SSL: %s (WinHTTP %d)" % (WINHTTP_TLS_ERRORS[code], code)
    if code in WINHTTP_NETWORK_ERRORS:
        return "Ошибка сети: %s (WinHTTP %d)" % (WINHTTP_NETWORK_ERRORS[code], code)
    args = getattr(exc, "args", ())
    text = ""
    if len(args) >= 3 and isinstance(args[2], tuple) and len(args[2]) >= 3 and args[2][2]:
        text = str(args[2][2]).strip()
    elif len(args) >= 2 and args[1]:
        text = str(args[1]).strip()
    if code:
        return "Ошибка WinHTTP %d: %s" % (code, text or "неизвестная ошибка")
    return text or str(exc)


def _make_request(
    method: str,
    url: str,
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    verify: bool = True,
    proxies: Optional[Dict[str, str]] = None,
) -> tuple[bool, int, bytes, str]:
    """Execute HTTP request via WinHTTP COM object."""
    try:
        http = win32com.client.Dispatch("WinHttp.WinHttpRequest.5.1")
        http.SetTimeouts(timeout * 1000, timeout * 1000, timeout * 1000, timeout * 1000)
        http.Open(method, url, False)

        http.SetAutoLogonPolicy(WINHTTP_AUTOLOGON_POLICY_ALWAYS)
        _enable_modern_tls(http)

        if not verify:
            _set_request_option(
                http, WINHTTP_REQUEST_OPTION_SSL_ERROR_IGNORE_FLAGS, SSL_ERROR_IGNORE_ALL
            )
            logger.warning(
                "WinINET: TLS certificate verification disabled "
                "(corporate SSL inspection mode)"
            )

        if proxies:
            proxy_url = proxies.get('https') or proxies.get('http')
            if proxy_url:
                http.SetProxy(WINHTTP_ACCESS_TYPE_NAMED_PROXY, proxy_url, "")
                logger.debug("WinINET: using proxy %s", proxy_url)
        else:
            http.SetProxy(WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, "", "")

        if headers:
            for k, v in headers.items():
                http.SetRequestHeader(k, v)

        if body:
            http.Send(body)
        else:
            http.Send()

        status_code = http.Status
        raw_bytes = http.ResponseBody
        response_bytes = bytes(raw_bytes) if raw_bytes is not None else b""

        if status_code >= 400:
            err_text = "HTTP %d" % status_code
            try:
                status_text = str(http.StatusText)
                if status_text:
                    err_text += ": " + status_text
            except (AttributeError, TypeError):
                pass
            return False, status_code, response_bytes, err_text

        return True, status_code, response_bytes, ""

    except AttributeError as e:
        logger.error("WinHTTP COM error: %s", str(e))
        return False, 0, b"", str(e)
    except OSError as e:
        err_msg = str(e)
        logger.error("WinHTTP network error: %s", err_msg)
        return False, 0, b"", err_msg
    except ValueError as e:
        logger.error("WinHTTP value error: %s", str(e))
        return False, 0, b"", str(e)
    except Exception as e:
        err_msg = _describe_winhttp_error(e)
        logger.error("WinHTTP error: %s", err_msg)
        return False, 0, b"", err_msg


class WinINETBackend(BaseBackend):
    """HTTP backend using WinHTTP COM (best for Windows/corporate proxy)."""

    name = "wininet"

    def is_available(self) -> bool:
        """Check if WinHTTP COM is available (Windows only)."""
        return WININET_AVAILABLE and os.name == 'nt'

    def send(
        self,
        url: str,
        files: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        verify: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> tuple[bool, int, bytes, str]:
        """Send POST request using WinHTTP COM."""
        if not WININET_AVAILABLE:
            return False, 0, b"", "WinINET not available"

        parsed = urlparse(url)
        logger.info("WinINETBackend: POST %s://%s%s", parsed.scheme, parsed.netloc, parsed.path)

        try:
            boundary = "----FormBoundary" + os.urandom(8).hex()

            body_parts = []
            for field_name, (filename, content, content_type) in files.items():
                part = b''
                part += b'--' + boundary.encode() + b'\r\n'
                cd_header = 'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (field_name, filename)
                part += cd_header.encode()
                part += ('Content-Type: %s\r\n\r\n' % content_type).encode()
                part += content.encode() if isinstance(content, str) else content
                part += b'\r\n'
                body_parts.append(part)

            body = b''.join(body_parts)
            body += b'--' + boundary.encode() + b'--\r\n'

            req_headers = {"Content-Type": "multipart/form-data; boundary=%s" % boundary}
            if headers:
                for k, v in headers.items():
                    if k.lower() != 'content-type':
                        req_headers[k] = v

            return _make_request("POST", url, body, req_headers, timeout, verify, proxies)

        except (ValueError, OSError, TypeError) as e:
            logger.error("WinINET error: %s", str(e))
            return False, 0, b"", str(e)

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: int = 60,
        verify: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> tuple[bool, int, bytes, str]:
        """Send GET request using WinHTTP COM."""
        if not WININET_AVAILABLE:
            return False, 0, b"", "WinINET not available"

        import urllib.parse

        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        parsed = urlparse(url)
        logger.info("WinINETBackend: GET %s://%s%s", parsed.scheme, parsed.netloc, parsed.path)

        try:
            return _make_request("GET", url, None, headers, timeout, verify, proxies)
        except (ValueError, OSError, TypeError) as e:
            logger.error("WinINET error: %s", str(e))
            return False, 0, b"", str(e)


BackendRegistry.register(WinINETBackend)
