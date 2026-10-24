"""Master key protection backends (L-02).

Windows: ``DpapiKeyStore`` (thin delegation to ``utils.crypto._dpapi_*``, behaviour unchanged).
Linux:   ``SecretServiceKeyStore`` (raw key in the desktop keyring, ``master.key`` holds only a marker)
         or ``PassphraseFileKeyStore`` (fallback: key wrapped with a passphrase, PBKDF2-600k + Fernet).

A plaintext 32-byte key is never produced here. The ``master.key`` marker of the non-Windows stores is
``NOTK1`` + ``\\n`` + JSON; it contains no key material for Secret Service.
"""
import base64
import hashlib
import json
import logging
import os
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils import platform_info

logger = logging.getLogger(__name__)

MAGIC = b"NOTK1"
SERVICE_NAME = "NormaOT"
ENV_OVERRIDE = "NORMAOT_KEYSTORE"  # "passphrase_file" forces the fallback store

STORE_DPAPI = "dpapi"
STORE_SECRET_SERVICE = "secret_service"
STORE_PASSPHRASE_FILE = "passphrase_file"

_PBKDF2_ITERATIONS = 600000  # same as crypto._derive_key_from_passphrase


class KeyStoreError(Exception):
    """The store cannot protect/unprotect the key (locked, missing, corrupted marker)."""


class KeyStorePassphraseRequired(KeyStoreError):
    """A passphrase is needed (not provided yet, or wrong)."""


# ---------- marker helpers ----------

def _pack(payload: dict) -> bytes:
    return MAGIC + b"\n" + json.dumps(payload, sort_keys=True).encode("utf-8")


def _unpack(blob: bytes) -> dict:
    if not blob.startswith(MAGIC + b"\n"):
        raise KeyStoreError("not a NormaOT key marker")
    try:
        data = json.loads(blob[len(MAGIC) + 1:].decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise KeyStoreError("key marker is corrupted") from e
    if not isinstance(data, dict):
        raise KeyStoreError("key marker is corrupted")
    return data


def is_marker(blob: bytes) -> bool:
    return blob.startswith(MAGIC + b"\n")


def marker_store_name(blob: bytes) -> Optional[str]:
    """Store recorded in a marker, or None if ``blob`` is not a marker / unreadable."""
    try:
        return _unpack(blob).get("store")
    except KeyStoreError:
        return None


# ---------- passphrase held in memory for the fallback store ----------

_unlock_passphrase: Optional[bytearray] = None


def set_unlock_passphrase(passphrase: Optional[str]) -> None:
    """Remember the passphrase of the fallback store for this process (None clears it)."""
    global _unlock_passphrase
    if _unlock_passphrase is not None:
        for i in range(len(_unlock_passphrase)):
            _unlock_passphrase[i] = 0
    _unlock_passphrase = bytearray(passphrase.encode("utf-8")) if passphrase else None


def has_unlock_passphrase() -> bool:
    return bool(_unlock_passphrase)


def _derive(passphrase: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_PBKDF2_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase))


# ---------- stores ----------

class KeyStore:
    name = ""

    def is_available(self) -> bool:
        raise NotImplementedError

    def protect(self, raw: bytes) -> bytes:
        raise NotImplementedError

    def unprotect(self, blob: bytes) -> bytes:
        raise NotImplementedError

    def forget(self, blob: bytes) -> None:
        """Remove key material held OUTSIDE master.key (factory reset). No-op for file-only stores."""

    def restrict(self, path) -> None:
        """Limit file access to the current user."""
        from utils import crypto
        crypto._restrict_file_access(path)


class DpapiKeyStore(KeyStore):
    name = STORE_DPAPI

    def is_available(self) -> bool:
        try:
            import win32crypt  # noqa: F401
            return True
        except ImportError:
            return False

    def protect(self, raw: bytes) -> bytes:
        from utils import crypto
        return crypto._dpapi_encrypt(raw)

    def unprotect(self, blob: bytes) -> bytes:
        from utils import crypto
        return crypto._dpapi_decrypt(blob)


class SecretServiceKeyStore(KeyStore):
    """Raw key lives in the desktop keyring (Secret Service / KWallet) via ``keyring``.

    ``backend`` is any object with get_password/set_password/delete_password (tests inject a fake).
    """
    name = STORE_SECRET_SERVICE
    _BAD_BACKEND_WORDS = ("fail", "null", "plaintext", "chainer")

    def __init__(self, backend: Any = None):
        self._backend = backend

    def _kr(self):
        if self._backend is not None:
            return self._backend
        import keyring
        return keyring

    def is_available(self) -> bool:
        if self._backend is not None:
            return True
        try:
            import keyring
            kr = keyring.get_keyring()
        except Exception:  # ImportError or backend init failure
            return False
        cls = type(kr).__name__.lower() + type(kr).__module__.lower()
        if any(word in cls for word in self._BAD_BACKEND_WORDS):
            return False
        return getattr(kr, "priority", 1) > 0

    def protect(self, raw: bytes) -> bytes:
        fp = hashlib.sha256(raw).hexdigest()[:32]
        try:
            self._kr().set_password(SERVICE_NAME, fp, base64.b64encode(raw).decode("ascii"))
        except Exception as e:
            raise KeyStoreError("Secret Service refused to store the key: %s" % type(e).__name__) from e
        return _pack({"store": self.name, "fp": fp})

    def unprotect(self, blob: bytes) -> bytes:
        fp = _unpack(blob).get("fp")
        if not isinstance(fp, str):
            raise KeyStoreError("key marker is corrupted")
        try:
            value = self._kr().get_password(SERVICE_NAME, fp)
        except Exception as e:
            raise KeyStoreError("Secret Service unavailable or locked: %s" % type(e).__name__) from e
        if not value:
            raise KeyStoreError("key not found in Secret Service")
        try:
            raw = base64.b64decode(value)
        except ValueError as e:
            raise KeyStoreError("key in Secret Service is corrupted") from e
        if hashlib.sha256(raw).hexdigest()[:32] != fp:
            raise KeyStoreError("key in Secret Service does not match its fingerprint")
        return raw

    def forget(self, blob: bytes) -> None:
        fp = _unpack(blob).get("fp")
        if not isinstance(fp, str):
            return
        try:
            self._kr().delete_password(SERVICE_NAME, fp)
        except Exception as e:  # missing entry, locked keyring, no backend
            raise KeyStoreError("Secret Service could not delete the key: %s" % type(e).__name__) from e

    def restrict(self, path) -> None:
        _chmod_600(path)


class PassphraseFileKeyStore(KeyStore):
    """Fallback: master.key = marker with the key wrapped by a passphrase-derived Fernet key."""
    name = STORE_PASSPHRASE_FILE

    def is_available(self) -> bool:
        return True

    def protect(self, raw: bytes) -> bytes:
        if not _unlock_passphrase:
            raise KeyStorePassphraseRequired("passphrase is required to protect the master key")
        salt = os.urandom(32)
        token = Fernet(_derive(bytes(_unlock_passphrase), salt)).encrypt(raw)
        return _pack({
            "store": self.name,
            "salt": base64.b64encode(salt).decode("ascii"),
            "token": token.decode("ascii"),
        })

    def unprotect(self, blob: bytes) -> bytes:
        data = _unpack(blob)
        try:
            salt = base64.b64decode(data["salt"])
            token = data["token"].encode("ascii")
        except (KeyError, ValueError, AttributeError) as e:
            raise KeyStoreError("key marker is corrupted") from e
        if not _unlock_passphrase:
            raise KeyStorePassphraseRequired("passphrase is required to unlock the master key")
        try:
            return Fernet(_derive(bytes(_unlock_passphrase), salt)).decrypt(token)
        except (InvalidToken, ValueError, TypeError) as e:
            raise KeyStorePassphraseRequired("invalid passphrase") from e

    def restrict(self, path) -> None:
        _chmod_600(path)


def _chmod_600(path) -> None:
    try:
        os.chmod(str(path), 0o600)
    except OSError as e:
        logger.debug("chmod 600 failed: %s", type(e).__name__)


# ---------- selection ----------

def _store_by_name(name: Optional[str]) -> Optional[KeyStore]:
    if name == STORE_SECRET_SERVICE:
        return SecretServiceKeyStore()
    if name == STORE_PASSPHRASE_FILE:
        return PassphraseFileKeyStore()
    return None


def get_keystore(blob: Optional[bytes] = None) -> KeyStore:
    """Store for an existing ``master.key`` (by its marker) or, without one, the best available.

    An existing key is never moved between stores silently.
    """
    if platform_info.IS_WINDOWS:
        return DpapiKeyStore()
    if blob:
        store = _store_by_name(marker_store_name(blob))
        if store is not None:
            return store
    if os.environ.get(ENV_OVERRIDE) == STORE_PASSPHRASE_FILE:
        return PassphraseFileKeyStore()
    ss = SecretServiceKeyStore()
    return ss if ss.is_available() else PassphraseFileKeyStore()
