"""
Organization profiles (UX-10, step 5): several organizations in one installation.

Every organization has its own database, API key and organization/protocol settings.
The first (``default``) organization keeps living in the root data dir, so existing
installations need no migration; added ones live in ``%APPDATA%/NormaOT/orgs/<id>/``.
Global for all organizations: master key, logs/audit, license, theme, window and
table layouts, proxy settings.

The registry ``organizations.json`` (root data dir) stores names encrypted
(an ИП name is PD). The active organization is chosen once per process
(startup dialog / ``--org=<id>``); switching relaunches the app.
"""
import json
import logging
import os
import re
import secrets
import shutil
import threading
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

ORGS_FILE = "organizations.json"
ORGS_SUBDIR = "orgs"
DEFAULT_ORG_ID = "default"
DEFAULT_ORG_NAME = "Основная организация"
MAX_NAME_LENGTH = 200
_ID_RE = re.compile(r"^[0-9a-f]{12}$")

# Per-organization files in the root dir (default org); deleted with that org.
DEFAULT_ORG_FILES = (
    "app_data.db", "app_data.db-wal", "app_data.db-shm", "api_key.json", "org_settings.json",
    "commission_data.json", "programs_data.json", "programs_settings.json",
    "protocol_settings.json", "summary_programs.json", "journal_settings.json", "Шаблон.xlsx",
)
DEFAULT_ORG_DIRS = ("backups",)

_lock = threading.Lock()
_active = {"id": None}


class OrgError(ValueError):
    """User-facing error (str() is shown in the UI)."""


@dataclass(frozen=True)
class Org:
    id: str
    name: str


def _root() -> str:
    from utils.app_paths import get_app_data_dir
    return get_app_data_dir()


def _registry_path() -> str:
    return os.path.join(_root(), ORGS_FILE)


def _enc(text: str) -> str:
    from utils.crypto import encrypt_value
    return encrypt_value(text)


def _dec(text: str) -> str:
    from utils.crypto import decrypt_value
    try:
        return decrypt_value(text)
    except Exception as e:
        logger.warning("Organization name cannot be decrypted: %s", type(e).__name__)
        return "(организация)"


def _read() -> dict:
    try:
        with open(_registry_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("orgs"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"active": DEFAULT_ORG_ID, "orgs": []}


def _write(data: dict) -> None:
    path = _registry_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _entries(data: dict) -> list:
    entries = [e for e in data["orgs"] if isinstance(e, dict) and
               (e.get("id") == DEFAULT_ORG_ID or _ID_RE.match(str(e.get("id", ""))))]
    has_default = any(e["id"] == DEFAULT_ORG_ID for e in entries)
    # After the default org was deleted its slot (root dir) is reused only when
    # no other organization is left.
    if not has_default and (not data.get("default_deleted") or not entries):
        entries.insert(0, {"id": DEFAULT_ORG_ID, "name_enc": ""})
    return entries


def list_orgs() -> List[Org]:
    with _lock:
        data = _read()
    return [Org(e["id"], _dec(e["name_enc"]) if e.get("name_enc") else DEFAULT_ORG_NAME)
            for e in _entries(data)]


def has_multiple_orgs() -> bool:
    return len(list_orgs()) > 1


def get_last_active_id() -> str:
    with _lock:
        data = _read()
    ids = {e["id"] for e in _entries(data)}
    active = data.get("active")
    return active if active in ids else DEFAULT_ORG_ID


def org_dir(org_id: str) -> str:
    if org_id == DEFAULT_ORG_ID:
        return _root()
    if not _ID_RE.match(org_id or ""):
        raise OrgError("Неверный идентификатор организации")
    return os.path.join(_root(), ORGS_SUBDIR, org_id)


def set_active_org(org_id: str) -> None:
    """Select the organization for this process (before any tab/DB is created)."""
    with _lock:
        data = _read()
        entries = _entries(data)
        if org_id not in {e["id"] for e in entries}:
            raise OrgError("Организация не найдена")
        _active["id"] = org_id
        if data.get("active") != org_id:
            data["active"] = org_id
            data["orgs"] = entries
            try:
                _write(data)
            except OSError as e:
                logger.warning("Failed to save active organization: %s", type(e).__name__)
    os.makedirs(org_dir(org_id), exist_ok=True)


def get_active_org_id() -> str:
    return _active["id"] or DEFAULT_ORG_ID


def get_active_org() -> Org:
    oid = get_active_org_id()
    for org in list_orgs():
        if org.id == oid:
            return org
    return Org(DEFAULT_ORG_ID, DEFAULT_ORG_NAME)


def get_org_data_dir() -> str:
    """Data dir of the active organization (DB, API key, org/protocol settings)."""
    path = org_dir(get_active_org_id())
    os.makedirs(path, exist_ok=True)
    return path


def _clean_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise OrgError("Введите название организации")
    if len(name) > MAX_NAME_LENGTH:
        raise OrgError("Название слишком длинное (не более %d символов)" % MAX_NAME_LENGTH)
    if name.casefold() in {o.name.casefold() for o in list_orgs()}:
        raise OrgError("Организация с таким названием уже есть")
    return name


def add_org(name: str) -> Org:
    name = _clean_name(name)
    with _lock:
        data = _read()
        entries = _entries(data)
        oid = secrets.token_hex(6)
        os.makedirs(os.path.join(_root(), ORGS_SUBDIR, oid), exist_ok=True)
        entries.append({"id": oid, "name_enc": _enc(name)})
        data["orgs"] = entries
        _write(data)
    from utils.audit import log_audit
    log_audit("ORG_ADDED", "id=%s total=%d" % (oid, len(entries)))
    return Org(oid, name)


def rename_org(org_id: str, name: str) -> None:
    current = {o.id: o.name for o in list_orgs()}
    if current.get(org_id, "").casefold() == " ".join((name or "").split()).casefold():
        return
    name = _clean_name(name)
    with _lock:
        data = _read()
        entries = _entries(data)
        for e in entries:
            if e["id"] == org_id:
                e["name_enc"] = _enc(name)
                break
        else:
            raise OrgError("Организация не найдена")
        data["orgs"] = entries
        _write(data)


def delete_org(org_id: str) -> None:
    """Delete one organization's data. The last remaining one cannot be deleted
    this way (use «Удалить все данные приложения»)."""
    with _lock:
        data = _read()
        entries = _entries(data)
        if org_id not in {e["id"] for e in entries}:
            raise OrgError("Организация не найдена")
        if len(entries) < 2:
            raise OrgError("Нельзя удалить единственную организацию")
        if org_id == get_active_org_id():
            from db.database import DatabaseManager
            DatabaseManager.close_all()
        if org_id == DEFAULT_ORG_ID:
            root = _root()
            for fn in DEFAULT_ORG_FILES:
                p = os.path.join(root, fn)
                if os.path.isfile(p):
                    os.unlink(p)
            for dn in DEFAULT_ORG_DIRS:
                shutil.rmtree(os.path.join(root, dn), ignore_errors=True)
            # The slot stays (root dir), but becomes a fresh empty organization
            # hidden from the list until it is the only one left.
            entries = [e for e in entries if e["id"] != DEFAULT_ORG_ID]
            data["default_deleted"] = True
        else:
            shutil.rmtree(org_dir(org_id), ignore_errors=False)
            entries = [e for e in entries if e["id"] != org_id]
        data["orgs"] = entries
        if data.get("active") == org_id:
            data["active"] = entries[0]["id"] if entries else DEFAULT_ORG_ID
        _write(data)
    from utils.audit import log_audit
    log_audit("ORG_DELETED", "id=%s" % org_id)


def _reset_for_tests() -> None:
    _active["id"] = None
