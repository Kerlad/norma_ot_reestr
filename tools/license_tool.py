"""
License code issuing tool for the author (UX-10). Not part of the app build.

The private key lives OUTSIDE the repository (default: %USERPROFILE%\\NormaOT_license_keys).
Never commit it, never put it on the website. Keep an offline backup: without it
no new codes compatible with released builds can be issued.

Usage:
  python tools/license_tool.py init                      # create key pair, print public key
  python tools/license_tool.py issue --tier org --name "ООО Ромашка"
  python tools/license_tool.py issue --tier personal --name "Иванов И.И." --days 365
  python tools/license_tool.py verify NOT1.xxx.yyy

Each issued code is appended to issued.csv in the key directory (buyer records stay
on the author's machine only).
"""
import argparse
import base64
import csv
import os
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils import license as lic_mod  # noqa: E402

PRIVATE_KEY_FILE = "license_private_key.pem"
PUBLIC_KEY_FILE = "license_public_key.txt"
ISSUED_FILE = "issued.csv"


def default_key_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "NormaOT_license_keys"


def _check_outside_repo(key_dir: Path) -> None:
    try:
        key_dir.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return
    sys.exit("Refusing to use a key directory inside the repository: %s" % key_dir)


def cmd_init(key_dir: Path) -> None:
    _check_outside_repo(key_dir)
    priv_path = key_dir / PRIVATE_KEY_FILE
    if priv_path.exists():
        sys.exit("Key already exists: %s (delete it manually to regenerate — old codes will stop working)" % priv_path)
    key_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    priv_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub_b64 = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    (key_dir / PUBLIC_KEY_FILE).write_text(pub_b64 + "\n", encoding="ascii")
    print("Private key: %s  (BACK IT UP OFFLINE, never commit)" % priv_path)
    print("Public key (put into utils/license.py PUBLIC_KEY_B64):")
    print(pub_b64)


def _load_private_key(key_dir: Path) -> Ed25519PrivateKey:
    path = key_dir / PRIVATE_KEY_FILE
    if not path.exists():
        sys.exit("No private key at %s — run 'init' first" % path)
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def sign_payload(key: Ed25519PrivateKey, payload: dict) -> str:
    data = lic_mod.encode_payload(payload)
    return lic_mod.build_code(data, key.sign(data))


def cmd_issue(key_dir: Path, tier: str, name: str, days: int) -> None:
    _check_outside_repo(key_dir)
    name = name.strip()
    if not name:
        sys.exit("--name is required")
    key = _load_private_key(key_dir)
    issued = date.today()
    payload = {
        "v": lic_mod.FORMAT_VERSION,
        "t": tier,
        "n": name,
        "exp": (issued + timedelta(days=days)).isoformat(),
        "id": secrets.token_hex(6),
    }
    code = sign_payload(key, payload)
    lic_mod.parse_code(code)  # self-check against the canonical parser

    issued_path = key_dir / ISSUED_FILE
    new_file = not issued_path.exists()
    with open(issued_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if new_file:
            w.writerow(["issued", "id", "tier", "holder", "expires", "code"])
        w.writerow([issued.isoformat(), payload["id"], tier, name, payload["exp"], code])
    print("Tier: %s, holder: %s, valid until: %s, id: %s" % (tier, name, payload["exp"], payload["id"]))
    print(code)


def cmd_verify(code: str) -> None:
    try:
        lic = lic_mod.parse_code(code)
    except lic_mod.LicenseError as e:
        sys.exit("INVALID: %s" % e)
    print("OK: %s (id %s)" % (lic.describe(), lic.code_id))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="NormaOT license codes")
    p.add_argument("--key-dir", type=Path, default=default_key_dir())
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    pi = sub.add_parser("issue")
    pi.add_argument("--tier", choices=[lic_mod.TIER_ORG, lic_mod.TIER_PERSONAL], required=True)
    pi.add_argument("--name", required=True, help="organization or person name shown in the app")
    pi.add_argument("--days", type=int, default=365)
    pv = sub.add_parser("verify")
    pv.add_argument("code")
    a = p.parse_args(argv)
    if a.cmd == "init":
        cmd_init(a.key_dir)
    elif a.cmd == "issue":
        cmd_issue(a.key_dir, a.tier, a.name, a.days)
    else:
        cmd_verify(a.code)


if __name__ == "__main__":
    main()
