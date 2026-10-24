"""L-04: network behaviour on Linux (platform flags patched, runs anywhere)."""
import builtins
import ssl
import sys

import pytest

from api import mintrud_api
from api.backends import requests_backend, urllib_backend
from utils import platform_info, proxy_manager, tls_context


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
    monkeypatch.setattr(platform_info, "IS_LINUX", True)


@pytest.fixture
def clean_proxy_env(monkeypatch):
    for var in ("http_proxy", "https_proxy", "no_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        monkeypatch.delenv(var, raising=False)


class TestBackendOrder:
    def test_linux_has_no_wininet(self, linux):
        assert mintrud_api._backend_order() == ["requests", "urllib"]

    def test_windows_order_unchanged(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        assert mintrud_api._backend_order() == ["wininet", "urllib", "requests"]

    def test_auto_picks_requests_on_linux(self, linux):
        client = mintrud_api.MintrudClient()
        assert client._backend.name == "requests"

    def test_negotiate_setting_ignored_on_linux(self, linux):
        client = mintrud_api.MintrudClient(proxy_settings={"use_negotiate": True})
        assert client._backend.name == "requests"


class TestProxyDetection:
    def test_https_proxy_from_env(self, linux, clean_proxy_env, monkeypatch):
        monkeypatch.setenv("https_proxy", "proxy.corp:3128")
        assert proxy_manager.detect_system_proxy() == "http://proxy.corp:3128"

    def test_http_proxy_fallback(self, linux, clean_proxy_env, monkeypatch):
        monkeypatch.setenv("http_proxy", "http://p:8080")
        assert proxy_manager.detect_system_proxy() == "http://p:8080"

    def test_no_proxy_excludes_mintrud(self, linux, clean_proxy_env, monkeypatch):
        monkeypatch.setenv("https_proxy", "http://p:8080")
        monkeypatch.setenv("no_proxy", "rosmintrud.ru")
        assert proxy_manager.detect_system_proxy() is None

    def test_no_env_no_proxy(self, linux, clean_proxy_env):
        assert proxy_manager.detect_system_proxy() is None

    def test_windows_still_uses_registry(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        monkeypatch.setattr(proxy_manager, "detect_windows_proxy", lambda: "http://reg:1")
        assert proxy_manager.detect_system_proxy() == "http://reg:1"

    def test_auto_mode_uses_env(self, linux, clean_proxy_env, monkeypatch):
        monkeypatch.setenv("https_proxy", "http://p:1")
        assert proxy_manager.build_proxies_for_requests({"mode": "auto"}) == {
            "http": "http://p:1", "https": "http://p:1"}

    def test_negotiate_not_available_on_linux(self, linux, clean_proxy_env):
        assert proxy_manager.detect_proxy_and_env()["negotiate_available"] is False


class TestNoWindowsImports:
    def test_urllib_backend_does_not_import_sspi(self, linux, monkeypatch):
        tried = []
        real_import = builtins.__import__

        def spy(name, *a, **kw):
            if name in ("win32security", "sspi", "win32com", "win32com.client"):
                tried.append(name)
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", spy)
        urllib_backend.UrllibBackend()._build_opener({"https": "http://p:1"}, True)
        assert tried == []


class TestTls:
    def test_default_context_verifies(self, linux):
        ctx = tls_context.build_ssl_context("")
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_truststore_used_on_linux(self, linux):
        pytest.importorskip("truststore")
        import truststore
        assert isinstance(tls_context.build_ssl_context(""), truststore.SSLContext)

    def test_ca_file_switches_to_openssl_context(self, linux, tmp_path):
        pytest.importorskip("truststore")
        import truststore
        pem = tmp_path / "ca.pem"
        pem.write_text(_SELF_SIGNED_PEM())
        ctx = tls_context.build_ssl_context(str(pem))
        assert not isinstance(ctx, truststore.SSLContext)
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_missing_truststore_falls_back(self, linux, monkeypatch):
        monkeypatch.setitem(sys.modules, "truststore", None)
        assert tls_context.build_ssl_context("").verify_mode == ssl.CERT_REQUIRED

    def test_requests_adapter_on_linux_only(self, linux):
        adapter = requests_backend.RequestsBackend._make_adapter(None, True)
        assert isinstance(adapter, requests_backend._ContextAdapter)
        assert not isinstance(requests_backend.RequestsBackend._make_adapter(None, False),
                              requests_backend._ContextAdapter)

    def test_windows_requests_adapter_is_stock(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_LINUX", False)
        assert not isinstance(requests_backend.RequestsBackend._make_adapter(None, True),
                              requests_backend._ContextAdapter)

    def test_ca_file_persists_through_save(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tls_context, "CA_FILE", "")
        ok, _ = proxy_manager.save_proxy_settings(str(tmp_path), {"mode": "off", "ca_file": "/etc/ca.pem"})
        assert ok and tls_context.CA_FILE == "/etc/ca.pem"
        # the UI saves without a ca_file key: the value must survive
        ok, _ = proxy_manager.save_proxy_settings(str(tmp_path), {"mode": "off"})
        assert proxy_manager.load_proxy_settings(str(tmp_path))["ca_file"] == "/etc/ca.pem"
        tls_context.set_ca_file("")


def _SELF_SIGNED_PEM() -> str:
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode()
