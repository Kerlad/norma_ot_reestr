"""
Offline license codes (UX-10).

A code is ``NOT1.<payload>.<signature>`` (both parts base64url without padding).
The payload is compact UTF-8 JSON signed by the author's Ed25519 private key,
which never leaves the author's machine (see ``tools/license_tool.py``); the app
only ships the public key below and works without network access.

Payload fields: ``v`` (format version), ``t`` (tier: ``org`` / ``personal``),
``n`` (holder: organization or person name — PD, never logged), ``exp``
(last valid day, ISO date), ``id`` (random code id).

The activated code is stored encrypted (field-level Fernet) in
``%APPDATA%/NormaOT/license.json``.
"""
import base64
import binascii
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import date
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

logger = logging.getLogger(__name__)

CODE_PREFIX = "NOT1"
FORMAT_VERSION = 1
TIER_ORG = "org"
TIER_PERSONAL = "personal"
TIER_TITLES = {TIER_ORG: "Организация", TIER_PERSONAL: "Персональная"}
LICENSE_FILE = "license.json"
MAX_CODE_LENGTH = 2000

# Author's Ed25519 public key (raw 32 bytes, base64). Replace only together with
# a new key pair from tools/license_tool.py — old codes stop working.
PUBLIC_KEY_B64 = "Q/TKfEaYWLexhD8l91XjDs7HxOpExGEHCxvsYr3fAa0="

_lock = threading.Lock()
_cache: dict = {}


class LicenseError(ValueError):
    """Invalid, tampered or expired license code. str() is a user-facing message."""


@dataclass(frozen=True)
class License:
    tier: str
    holder: str
    expires: date
    code_id: str

    @property
    def tier_title(self) -> str:
        return TIER_TITLES.get(self.tier, self.tier)

    @property
    def is_org(self) -> bool:
        return self.tier == TIER_ORG

    def is_valid_on(self, day: Optional[date] = None) -> bool:
        return (day or date.today()) <= self.expires

    def describe(self) -> str:
        return "%s — %s, до %s" % (self.tier_title, self.holder, self.expires.strftime("%d.%m.%Y"))


def _b64d(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _public_key() -> Ed25519PublicKey:
    try:
        raw = base64.b64decode(PUBLIC_KEY_B64, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, binascii.Error) as e:
        raise LicenseError("Проверка лицензий недоступна в этой сборке") from e


def encode_payload(payload: dict) -> bytes:
    """Canonical payload bytes (shared with tools/license_tool.py)."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def build_code(payload_bytes: bytes, signature: bytes) -> str:
    return "%s.%s.%s" % (CODE_PREFIX, _b64e(payload_bytes), _b64e(signature))


def parse_code(code: str, today: Optional[date] = None) -> License:
    """Verify signature, format and expiry. Raises LicenseError."""
    code = "".join((code or "").split())  # tolerate line breaks/spaces from e-mail
    if not code:
        raise LicenseError("Введите код лицензии")
    if len(code) > MAX_CODE_LENGTH:
        raise LicenseError("Код лицензии слишком длинный")
    parts = code.split(".")
    if len(parts) != 3 or parts[0] != CODE_PREFIX:
        raise LicenseError("Неверный формат кода лицензии")
    try:
        payload_bytes = _b64d(parts[1])
        signature = _b64d(parts[2])
    except (ValueError, binascii.Error):
        raise LicenseError("Неверный формат кода лицензии")
    try:
        _public_key().verify(signature, payload_bytes)
    except InvalidSignature:
        raise LicenseError("Код лицензии недействителен")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("v") != FORMAT_VERSION:
            raise LicenseError("Код выпущен для другой версии программы")
        tier = payload["t"]
        holder = str(payload["n"]).strip()
        expires = date.fromisoformat(payload["exp"])
        code_id = str(payload.get("id", ""))
    except LicenseError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError):
        raise LicenseError("Неверный формат кода лицензии")
    if tier not in TIER_TITLES or not holder:
        raise LicenseError("Неверный формат кода лицензии")
    lic = License(tier=tier, holder=holder, expires=expires, code_id=code_id)
    if not lic.is_valid_on(today):
        raise LicenseError("Срок действия лицензии истёк %s" % expires.strftime("%d.%m.%Y"))
    return lic


def _license_path() -> str:
    from utils.app_paths import get_app_data_dir
    return os.path.join(get_app_data_dir(), LICENSE_FILE)


def _read_stored_code() -> Optional[str]:
    try:
        with open(_license_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        enc = data.get("code_enc") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
    if not enc:
        return None
    try:
        from utils.crypto import decrypt_value
        return decrypt_value(enc)
    except Exception as e:
        logger.warning("Stored license cannot be decrypted: %s", type(e).__name__)
        return None


def get_license(today: Optional[date] = None) -> Optional[License]:
    """Currently activated, valid license or None (cached per process)."""
    with _lock:
        if "code" not in _cache:
            _cache["code"] = _read_stored_code()
        code = _cache["code"]
    if not code:
        return None
    try:
        return parse_code(code, today)
    except LicenseError:
        return None


def has_org_license(today: Optional[date] = None) -> bool:
    lic = get_license(today)
    return bool(lic and lic.is_org)


def activate(code: str, today: Optional[date] = None) -> License:
    """Validate and store a code. Raises LicenseError."""
    lic = parse_code(code, today)
    code = "".join(code.split())
    from utils.crypto import encrypt_value
    path = _license_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"code_enc": encrypt_value(code)}, f)
        os.replace(tmp, path)
    except OSError as e:
        logger.error("Failed to save license: %s", type(e).__name__)
        raise LicenseError("Не удалось сохранить лицензию") from e
    with _lock:
        _cache["code"] = code
    from utils.audit import log_audit
    # Holder name is PD: only tier, expiry and code id are audited.
    log_audit("LICENSE_ACTIVATED", "tier=%s exp=%s id=%s" % (lic.tier, lic.expires.isoformat(), lic.code_id))
    return lic


def _reset_cache_for_tests() -> None:
    with _lock:
        _cache.clear()
