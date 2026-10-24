"""TLS trust configuration (L-04).

Windows: unchanged (urllib/requests defaults, WinHTTP for the wininet backend).
Linux:   system certificate store via ``truststore`` when installed, plus an optional CA file
         (``ca_file`` in proxy settings). Verification is never disabled here.
"""
import logging
import ssl
from typing import Optional

from utils import platform_info

logger = logging.getLogger(__name__)

# Set by utils.proxy_manager.load_proxy_settings/save_proxy_settings (like ENABLE_TLS_VERIFY).
CA_FILE: str = ""


def set_ca_file(path: Optional[str]) -> None:
    global CA_FILE
    CA_FILE = (path or "").strip()


def build_ssl_context(ca_file: Optional[str] = None) -> ssl.SSLContext:
    """Verifying client context. ``ca_file`` extends the trust store (corporate CA)."""
    ca_file = (ca_file if ca_file is not None else CA_FILE) or ""
    ctx = None
    # truststore verifies through the OS store only and ignores extra CA files,
    # so an explicit ca_file switches to the OpenSSL default context + that file.
    if platform_info.IS_LINUX and not ca_file:
        try:
            import truststore
            ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            logger.debug("truststore not installed, using the default CA bundle")
        except Exception as e:  # truststore failed to initialise: stay on the default bundle
            logger.warning("truststore unavailable: %s", type(e).__name__)
    if ctx is None:
        ctx = ssl.create_default_context()
    if ca_file:
        ctx.load_verify_locations(cafile=ca_file)
    return ctx
