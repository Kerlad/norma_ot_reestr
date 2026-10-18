"""Регрессия: «[INTEGRITY FAIL]» у только что созданного мастер-ключа.

В v3.2–3.5 метаданные нового ключа подписывались до записи ключа в _MASTER_KEY, и HMAC
брался по байтам ЗАШИФРОВАННОГО master.key; проверка затем считала HMAC по настоящему
ключу и никогда не совпадала.
"""
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

import utils.crypto as crypto
from utils import app_paths


@pytest.fixture
def isolated_key(tmp_path, monkeypatch):
    """Fresh %APPDATA% and fresh in-process key state; restores the session state after."""
    saved_key, saved_fernet = crypto._MASTER_KEY, crypto._FERNET_INSTANCE
    monkeypatch.setenv('APPDATA', str(tmp_path))
    app_paths._reset_for_tests()
    crypto._MASTER_KEY = None
    crypto.clear_caches()
    yield tmp_path / app_paths.APP_DIR_NAME
    crypto._MASTER_KEY, crypto._FERNET_INSTANCE = saved_key, saved_fernet
    crypto.clear_caches()
    app_paths._reset_for_tests()


def _new_process():
    """Simulate a restart: key no longer in memory."""
    crypto._MASTER_KEY = None
    crypto.clear_caches()


def _meta(d):
    return json.loads((d / "master.key.json").read_text(encoding="utf-8"))


def _write_meta(d, meta):
    (d / "master.key.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


class TestNewKeyIntegrity:
    def test_fresh_key_passes(self, isolated_key):
        crypto.encrypt_value("x")
        assert crypto.verify_metadata_integrity() is True
        mode, msg = crypto.check_master_key_security()
        assert "INTEGRITY FAIL" not in msg

    def test_fresh_key_passes_after_restart_and_cold_check(self, isolated_key):
        crypto.encrypt_value("x")
        _new_process()
        # cold: key not loaded in this "process" — must decrypt via DPAPI, not use file bytes
        assert crypto.verify_metadata_integrity() is True
        assert "INTEGRITY FAIL" not in crypto.check_master_key_security()[1]
        assert crypto.decrypt_value(crypto.encrypt_value("y")) == "y"
        assert crypto.verify_metadata_integrity() is True

    def test_tag_is_keyed_by_raw_key_not_file_bytes(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        tag = meta.pop("integrity")
        assert tag == crypto._compute_metadata_hmac(meta, crypto._MASTER_KEY)
        assert tag != crypto._compute_metadata_hmac_ciphertext_keyed(meta)


class TestTamperingDetected:
    def test_modified_field_fails(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        meta["passphrase_protected"] = True  # attacker flips a flag, keeps old tag
        _write_meta(isolated_key, meta)
        _new_process()
        assert crypto.verify_metadata_integrity() is False
        assert "INTEGRITY FAIL" in crypto.check_master_key_security()[1]

    def test_forged_tag_fails(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        meta["integrity"] = "0" * 32
        _write_meta(isolated_key, meta)
        assert crypto.verify_metadata_integrity() is False

    def test_unreadable_key_cannot_verify(self, isolated_key):
        crypto.encrypt_value("x")
        (isolated_key / "master.key").write_bytes(b"garbage-not-dpapi-blob-" * 4)
        _new_process()
        assert crypto.verify_metadata_integrity() is False


class TestMigrationOfBuggyTags:
    def test_v35_ciphertext_keyed_tag_is_accepted_once_and_resigned(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        meta.pop("integrity")
        meta["integrity"] = crypto._compute_metadata_hmac_ciphertext_keyed(meta)  # what 3.5.0 wrote
        _write_meta(isolated_key, meta)
        _new_process()

        assert crypto.verify_metadata_integrity() is True
        resigned = _meta(isolated_key)
        tag = resigned.pop("integrity")
        assert tag == crypto._compute_metadata_hmac(resigned, crypto._raw_master_key_for_hmac())
        assert crypto.verify_metadata_integrity() is True  # stays OK on the next check

    def test_buggy_tag_with_tampered_field_still_fails(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        meta.pop("integrity")
        meta["integrity"] = crypto._compute_metadata_hmac_ciphertext_keyed(meta)
        meta["passphrase_protected"] = True  # changed after signing
        _write_meta(isolated_key, meta)
        _new_process()
        assert crypto.verify_metadata_integrity() is False

    def test_save_without_key_does_not_write_fake_tag(self, isolated_key):
        isolated_key.mkdir(parents=True, exist_ok=True)
        crypto._save_key_metadata({"version": 3})  # no master.key at all
        assert "integrity" not in _meta(isolated_key)


class TestTaglessMetadata:
    """Tech debt 14: removing the integrity tag used to bypass the check."""

    def test_v3_metadata_without_tag_fails(self, isolated_key):
        crypto.encrypt_value("x")
        meta = _meta(isolated_key)
        meta.pop("integrity")
        _write_meta(isolated_key, meta)
        _new_process()
        assert crypto.verify_metadata_integrity() is False
        assert "INTEGRITY FAIL" in crypto.check_master_key_security()[1]

    def test_genuine_legacy_metadata_without_tag_is_signed(self, isolated_key):
        crypto.encrypt_value("x")
        _write_meta(isolated_key, {"version": 1, "passphrase_protected": False})
        _new_process()
        assert crypto.verify_metadata_integrity() is True
        assert "integrity" in _meta(isolated_key)
        assert crypto.verify_metadata_integrity() is True


class TestPassphraseFlagCannotBeStripped:
    def test_wrapped_key_file_means_protected_even_if_flag_removed(self, isolated_key):
        crypto.encrypt_value("x")
        crypto.set_passphrase("correct horse battery")
        assert crypto.is_passphrase_protected() is True
        meta = _meta(isolated_key)
        meta["passphrase_protected"] = False
        _write_meta(isolated_key, meta)
        assert crypto.is_passphrase_protected() is True
        (isolated_key / "master.key.json").unlink()
        assert crypto.is_passphrase_protected() is True

    def test_remove_passphrase_really_removes(self, isolated_key):
        crypto.encrypt_value("x")
        crypto.set_passphrase("correct horse battery")
        crypto.remove_passphrase("correct horse battery")
        assert crypto.is_passphrase_protected() is False
        assert not (isolated_key / "passphrase_wrapped.key").exists()

    def test_remove_passphrase_fails_loudly_if_file_stays(self, isolated_key, monkeypatch):
        crypto.encrypt_value("x")
        crypto.set_passphrase("correct horse battery")
        monkeypatch.setattr(crypto, "_secure_delete", lambda path: None)  # deletion silently fails
        with pytest.raises(crypto.CryptoError):
            crypto.remove_passphrase("correct horse battery")
        assert crypto.is_passphrase_protected() is True
