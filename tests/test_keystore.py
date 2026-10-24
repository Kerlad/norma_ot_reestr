"""L-02: master key stores. Linux branches run on any OS (platform flags patched, fake keyring)."""
import sys

import pytest

from utils import crypto, keystore, platform_info


class FakeKeyring:
    """In-memory stand-in for the `keyring` module. Never the real Secret Service."""
    priority = 5

    def __init__(self):
        self.data = {}
        self.locked = False

    def get_keyring(self):
        return self

    def set_password(self, service, user, value):
        if self.locked:
            raise RuntimeError("locked")
        self.data[(service, user)] = value

    def get_password(self, service, user):
        if self.locked:
            raise RuntimeError("locked")
        return self.data.get((service, user))


@pytest.fixture
def linux_keys(tmp_path, monkeypatch):
    """Linux code path, key dir in tmp_path, clean crypto/keystore state."""
    monkeypatch.setattr(platform_info, "IS_WINDOWS", False)
    monkeypatch.setattr(platform_info, "IS_LINUX", True)
    monkeypatch.setattr(crypto, "_key_dir", lambda: tmp_path)
    monkeypatch.delenv(keystore.ENV_OVERRIDE, raising=False)
    monkeypatch.delenv("EXCEL_XML_PROD", raising=False)
    monkeypatch.setattr(crypto, "_MASTER_KEY", None)
    monkeypatch.setattr(crypto, "_FERNET_INSTANCE", None)
    keystore.set_unlock_passphrase(None)
    yield tmp_path
    keystore.set_unlock_passphrase(None)


@pytest.fixture
def fake_keyring(monkeypatch):
    kr = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", kr)
    return kr


@pytest.fixture
def no_keyring(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", None)  # import -> ImportError


def _reload():
    """Simulate a new process: drop the in-memory key."""
    crypto._MASTER_KEY = None
    crypto._FERNET_INSTANCE = None


class TestSecretService:
    def test_create_and_reload(self, linux_keys, fake_keyring):
        key = crypto._get_or_create_master_key()
        blob = (linux_keys / "master.key").read_bytes()
        assert blob.startswith(b"NOTK1\n")
        assert key not in blob
        assert len(fake_keyring.data) == 1
        _reload()
        assert crypto._get_or_create_master_key() == key

    def test_locked_keyring_never_regenerates_key(self, linux_keys, fake_keyring):
        crypto._get_or_create_master_key()
        before = (linux_keys / "master.key").read_bytes()
        _reload()
        fake_keyring.locked = True
        with pytest.raises(crypto.CryptoUnavailableError):
            crypto._get_or_create_master_key()
        assert (linux_keys / "master.key").read_bytes() == before
        assert not (linux_keys / "corrupted_keys").exists()

    def test_fingerprint_mismatch_rejected(self, linux_keys, fake_keyring):
        crypto._get_or_create_master_key()
        (user,) = [k[1] for k in fake_keyring.data]
        fake_keyring.data[(keystore.SERVICE_NAME, user)] = "AAAA"
        _reload()
        with pytest.raises(crypto.CryptoUnavailableError):
            crypto._get_or_create_master_key()

    def test_security_status(self, linux_keys, fake_keyring):
        crypto._get_or_create_master_key()
        mode, _ = crypto.check_master_key_security()
        assert mode == "secret_service"

    def test_plaintext_backend_not_accepted(self, linux_keys, monkeypatch):
        class PlaintextKeyring(FakeKeyring):
            pass
        kr = PlaintextKeyring()
        monkeypatch.setitem(sys.modules, "keyring", kr)
        assert keystore.SecretServiceKeyStore().is_available() is False
        assert keystore.get_keystore().name == keystore.STORE_PASSPHRASE_FILE


class TestPassphraseFile:
    def test_create_requires_passphrase_and_writes_nothing(self, linux_keys, no_keyring):
        with pytest.raises(crypto.CryptoPassphraseRequiredError):
            crypto._get_or_create_master_key()
        assert not (linux_keys / "master.key").exists()

    def test_roundtrip(self, linux_keys, no_keyring):
        assert crypto.keystore_needs_passphrase() is True
        crypto.unlock_keystore("correct horse")
        key = crypto._get_or_create_master_key()
        blob = (linux_keys / "master.key").read_bytes()
        assert blob.startswith(b"NOTK1\n") and key not in blob
        _reload()
        keystore.set_unlock_passphrase(None)
        assert crypto.keystore_needs_passphrase() is True
        crypto.unlock_keystore("correct horse")
        assert crypto._get_or_create_master_key() == key

    def test_wrong_passphrase(self, linux_keys, no_keyring):
        crypto.unlock_keystore("right")
        crypto._get_or_create_master_key()
        _reload()
        keystore.set_unlock_passphrase(None)
        with pytest.raises(crypto.CryptoPassphraseRequiredError):
            crypto.unlock_keystore("wrong")
        assert keystore.has_unlock_passphrase() is False
        assert not (linux_keys / "corrupted_keys").exists()

    def test_missing_passphrase_does_not_regenerate(self, linux_keys, no_keyring):
        crypto.unlock_keystore("right")
        crypto._get_or_create_master_key()
        before = (linux_keys / "master.key").read_bytes()
        _reload()
        keystore.set_unlock_passphrase(None)
        with pytest.raises(crypto.CryptoPassphraseRequiredError):
            crypto._get_or_create_master_key()
        assert (linux_keys / "master.key").read_bytes() == before

    def test_env_override_forces_fallback(self, linux_keys, fake_keyring, monkeypatch):
        monkeypatch.setenv(keystore.ENV_OVERRIDE, keystore.STORE_PASSPHRASE_FILE)
        assert keystore.get_keystore().name == keystore.STORE_PASSPHRASE_FILE

    def test_existing_marker_wins_over_availability(self, linux_keys, fake_keyring, no_keyring):
        crypto.unlock_keystore("p")
        crypto._get_or_create_master_key()
        blob = (linux_keys / "master.key").read_bytes()
        # a keyring appears later: the existing key must stay in its store
        assert keystore.get_keystore(blob).name == keystore.STORE_PASSPHRASE_FILE

    def test_status_with_second_layer(self, linux_keys, no_keyring):
        crypto.unlock_keystore("p")
        crypto._get_or_create_master_key()
        mode, _ = crypto.check_master_key_security()
        assert mode == "passphrase_file"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_master_key_file_is_0600(self, linux_keys, no_keyring):
        import os, stat
        crypto.unlock_keystore("p")
        crypto._get_or_create_master_key()
        assert stat.S_IMODE(os.stat(linux_keys / "master.key").st_mode) == 0o600


class TestLinuxRejects:
    def test_plaintext_key_file_refused(self, linux_keys, fake_keyring):
        (linux_keys / "master.key").write_bytes(b"\x01" * 32)
        with pytest.raises(crypto.CryptoProductionModeError):
            crypto._get_or_create_master_key()
        assert (linux_keys / "master.key").exists()

    def test_foreign_blob_is_corrupted_and_archived(self, linux_keys, fake_keyring):
        (linux_keys / "master.key").write_bytes(b"\x01\x00\x00\x00" + b"x" * 200)  # DPAPI-like
        crypto._get_or_create_master_key()
        assert list((linux_keys / "corrupted_keys").glob("master.key.corrupted.*"))

    def test_environment_check_prod(self, linux_keys, no_keyring, monkeypatch):
        monkeypatch.setenv("EXCEL_XML_PROD", "1")
        ok, _ = crypto.check_environment()
        assert ok is True  # passphrase-file store is always available


class TestBackupAcrossOS:
    def test_restore_of_other_os_key_refused_and_key_untouched(self, linux_keys, fake_keyring, tmp_path):
        pytest.importorskip("pyzipper")
        crypto._get_or_create_master_key()
        ok, zip_path = crypto.create_master_key_backup(str(tmp_path / "bk"))
        assert ok
        before = (linux_keys / "master.key").read_bytes()
        # (key stays loaded: the backup password is derived from it)
        # pretend we are on Windows: the NOTK1 marker must not replace a DPAPI key
        platform_info.IS_WINDOWS = True
        try:
            ok, msg = crypto.restore_master_key_backup(zip_path)
        finally:
            platform_info.IS_WINDOWS = False
        assert ok is False and "другой ОС" in msg
        assert (linux_keys / "master.key").read_bytes() == before


class TestSelection:
    def test_windows_always_dpapi(self, monkeypatch):
        monkeypatch.setattr(platform_info, "IS_WINDOWS", True)
        assert keystore.get_keystore(b"NOTK1\n{}").name == keystore.STORE_DPAPI

    def test_marker_helpers(self):
        assert keystore.is_marker(b"NOTK1\n{}")
        assert not keystore.is_marker(b"\x01" * 32)
        assert keystore.marker_store_name(b"NOTK1\nnot json") is None
