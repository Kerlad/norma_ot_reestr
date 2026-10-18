"""UX-10: offline license codes and the support splash."""
import base64
import json
from datetime import date

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from utils import license as lic


@pytest.fixture
def test_key(monkeypatch, tmp_path):
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(lic, "PUBLIC_KEY_B64", base64.b64encode(pub).decode())
    monkeypatch.setattr(lic, "_license_path", lambda: str(tmp_path / "license.json"))
    lic._reset_cache_for_tests()
    yield key
    lic._reset_cache_for_tests()


def make_code(key, tier="org", name="ООО Тест", exp="2027-10-18", v=1, **extra):
    payload = {"v": v, "t": tier, "n": name, "exp": exp, "id": "abc123"}
    payload.update(extra)
    data = lic.encode_payload(payload)
    return lic.build_code(data, key.sign(data))


TODAY = date(2026, 10, 18)


def test_valid_org_code(test_key):
    l = lic.parse_code(make_code(test_key), TODAY)
    assert l.is_org and l.holder == "ООО Тест" and l.expires == date(2027, 10, 18)
    assert l.describe() == "Организация — ООО Тест, до 18.10.2027"


def test_valid_personal_code_with_whitespace(test_key):
    code = make_code(test_key, tier="personal", name="Иванов И.И.")
    wrapped = code[:40] + "\n  " + code[40:]
    l = lic.parse_code(wrapped, TODAY)
    assert not l.is_org and l.tier_title == "Персональная"


def test_expiry_day_inclusive(test_key):
    code = make_code(test_key, exp="2026-10-18")
    assert lic.parse_code(code, TODAY)
    with pytest.raises(lic.LicenseError, match="истёк"):
        lic.parse_code(code, date(2026, 10, 19))


def test_forged_signature(test_key):
    other = Ed25519PrivateKey.generate()
    with pytest.raises(lic.LicenseError, match="недействителен"):
        lic.parse_code(make_code(other), TODAY)


def test_tampered_payload(test_key):
    prefix, payload, sig = make_code(test_key).split(".")
    data = json.loads(lic._b64d(payload))
    data["exp"] = "2099-01-01"
    forged = ".".join([prefix, lic._b64e(lic.encode_payload(data)), sig])
    with pytest.raises(lic.LicenseError, match="недействителен"):
        lic.parse_code(forged, TODAY)


@pytest.mark.parametrize("bad", ["", "abc", "NOT1.a", "XXX1.a.b", "NOT1.!!.??", "NOT1." + "a" * 3000 + ".b"])
def test_malformed(test_key, bad):
    with pytest.raises(lic.LicenseError):
        lic.parse_code(bad, TODAY)


def test_signed_but_invalid_fields(test_key):
    for code in (make_code(test_key, tier="vip"), make_code(test_key, name="  "),
                 make_code(test_key, exp="18.10.2027"), make_code(test_key, v=2)):
        with pytest.raises(lic.LicenseError):
            lic.parse_code(code, TODAY)


def test_activate_stores_encrypted_and_survives_restart(test_key, tmp_path):
    code = make_code(test_key, exp="2099-01-01")
    lic.activate(code)
    raw = (tmp_path / "license.json").read_text(encoding="utf-8")
    assert "ООО" not in raw and code not in raw
    lic._reset_cache_for_tests()
    assert lic.get_license().holder == "ООО Тест"
    assert lic.has_org_license()


def test_activate_invalid_keeps_previous(test_key):
    lic.activate(make_code(test_key, exp="2099-01-01"))
    with pytest.raises(lic.LicenseError):
        lic.activate("NOT1.bad.code")
    assert lic.get_license() is not None


def test_no_license_and_expired_stored(test_key):
    assert lic.get_license() is None
    lic.activate(make_code(test_key, exp="2099-01-01"))
    assert lic.get_license(date(2100, 1, 1)) is None


def test_audit_has_no_holder_name(test_key, monkeypatch):
    calls = []
    import utils.audit
    monkeypatch.setattr(utils.audit, "log_audit", lambda e, d="": calls.append((e, d)))
    lic.activate(make_code(test_key, exp="2099-01-01"))
    assert calls and calls[0][0] == "LICENSE_ACTIVATED"
    assert "ООО" not in calls[0][1] and "Тест" not in calls[0][1]


def test_shipped_public_key_is_valid():
    lic._public_key()  # raises if the embedded key is a placeholder


# --- splash -----------------------------------------------------------------

@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_splash_countdown_blocks_close(qapp, test_key):
    from utils.donation_dialog import SupportDialog
    dlg = SupportDialog(None, seconds=2)
    assert dlg.waiting and not dlg.continue_btn.isEnabled()
    assert "2 с" in dlg.continue_btn.text()
    dlg.reject()
    assert dlg.result() == 0 and dlg.waiting
    dlg._tick(); dlg._tick()
    assert not dlg.waiting and dlg.continue_btn.isEnabled()
    assert dlg.continue_btn.text() == "Продолжить"


def test_splash_activation_ends_wait(qapp, test_key):
    from utils.donation_dialog import SupportDialog
    dlg = SupportDialog(None, seconds=10)
    dlg.code_edit.setText("garbage")
    dlg._activate()
    assert dlg.waiting and dlg.status_label.text()
    dlg.code_edit.setText(make_code(test_key, exp="2099-01-01"))
    dlg._activate()
    assert not dlg.waiting and dlg.activated_license.is_org


def test_splash_require_org_personal_keeps_wait(qapp, test_key):
    from utils.donation_dialog import SupportDialog
    dlg = SupportDialog(None, seconds=30, require_org=True)
    dlg.code_edit.setText(make_code(test_key, tier="personal", exp="2099-01-01"))
    dlg._activate()
    assert dlg.waiting and "«Организация»" in dlg.status_label.text()


def test_needs_wait(test_key):
    from utils.donation_dialog import needs_wait
    assert needs_wait()
    lic.activate(make_code(test_key, tier="personal", exp="2099-01-01"))
    assert not needs_wait() and needs_wait(require_org=True)
    lic.activate(make_code(test_key, tier="org", exp="2099-01-01"))
    assert not needs_wait(require_org=True)
