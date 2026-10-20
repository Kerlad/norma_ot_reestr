"""UX-16: once-a-day splash marker, waiting-screen panel and license thank-you note."""
import base64
import json
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from utils import donation_dialog as dd
from utils import license as lic
from utils import nag_state


@pytest.fixture
def marker(tmp_path, monkeypatch):
    """File copy in tmp_path; the registry copy is faked by conftest."""
    monkeypatch.setattr(nag_state, "_state_path", lambda: str(tmp_path / nag_state.STATE_FILE))
    return tmp_path


@pytest.fixture
def licensed(monkeypatch, tmp_path):
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(lic, "PUBLIC_KEY_B64", base64.b64encode(pub).decode())
    monkeypatch.setattr(lic, "_license_path", lambda: str(tmp_path / "license.json"))
    import utils.audit
    monkeypatch.setattr(utils.audit, "log_audit", lambda *a, **k: None)
    lic._reset_cache_for_tests()
    yield key
    lic._reset_cache_for_tests()


def make_code(key, tier="org", name="ООО Тест", exp="2099-01-01"):
    payload = {"v": 1, "t": tier, "n": name, "exp": exp, "id": "abc123"}
    data = lic.encode_payload(payload)
    return lic.build_code(data, key.sign(data))


TODAY = date(2026, 10, 20)


# --- marker -----------------------------------------------------------------

def test_due_on_first_run_then_not_again_today(marker):
    assert nag_state.splash_due(TODAY)
    nag_state.mark_splash_shown(TODAY)
    assert not nag_state.splash_due(TODAY)
    assert nag_state.splash_due(TODAY + timedelta(days=1))


def test_deleting_the_file_does_not_reset_the_marker(marker):
    nag_state.mark_splash_shown(TODAY)
    (marker / nag_state.STATE_FILE).unlink()
    assert not nag_state.splash_due(TODAY)
    # reading repaired the file copy from the registry copy
    assert (marker / nag_state.STATE_FILE).exists()


def test_clearing_the_registry_does_not_reset_the_marker(marker, monkeypatch):
    nag_state.mark_splash_shown(TODAY)
    monkeypatch.setattr(nag_state, "_reg_read", lambda: None)
    written = []
    monkeypatch.setattr(nag_state, "_reg_write", lambda day: written.append(day))
    assert not nag_state.splash_due(TODAY)
    assert written == [TODAY]  # registry copy repaired from the file


def test_later_of_the_two_dates_wins(marker, monkeypatch):
    nag_state.mark_splash_shown(TODAY - timedelta(days=5))
    monkeypatch.setattr(nag_state, "_reg_read", lambda: TODAY)
    assert not nag_state.splash_due(TODAY)


def test_clock_moved_back_shows_splash_again(marker):
    nag_state.mark_splash_shown(TODAY + timedelta(days=3))
    assert nag_state.splash_due(TODAY)


def test_corrupt_values_are_ignored(marker, monkeypatch):
    (marker / nag_state.STATE_FILE).write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(nag_state, "_reg_read", lambda: None)
    assert nag_state.last_splash_date() is None
    (marker / nag_state.STATE_FILE).write_text(json.dumps({"last_splash": "20.10.2026"}), encoding="utf-8")
    assert nag_state.last_splash_date() is None


def test_unwritable_marker_does_not_raise(marker, monkeypatch):
    monkeypatch.setattr(nag_state, "_state_path", lambda: str(marker / "missing" / "s.json"))
    nag_state.mark_splash_shown(TODAY)  # must not raise


# --- startup splash ---------------------------------------------------------

@pytest.fixture
def fake_dialog(monkeypatch):
    shown = []

    class FakeDialog:
        def __init__(self, parent=None, seconds=0, reason="", require_org=False):
            shown.append(seconds)

        def exec(self):
            return 1

    monkeypatch.setattr(dd, "SupportDialog", FakeDialog)
    return shown


def test_startup_splash_once_per_day(marker, licensed, fake_dialog):
    assert dd.maybe_show_startup_splash() is True
    assert fake_dialog == [dd.STARTUP_SECONDS]
    assert dd.maybe_show_startup_splash() is False
    assert fake_dialog == [dd.STARTUP_SECONDS]


def test_no_startup_splash_with_license(marker, licensed, fake_dialog):
    lic.activate(make_code(licensed))
    assert dd.maybe_show_startup_splash() is False
    assert fake_dialog == []
    assert nag_state.splash_due()  # marker untouched


def test_startup_splash_still_shown_if_marker_unreadable(marker, licensed, fake_dialog, monkeypatch):
    def boom():
        raise OSError("locked")
    monkeypatch.setattr(nag_state, "splash_due", boom)
    monkeypatch.setattr(nag_state, "mark_splash_shown", lambda *a: boom())
    assert dd.maybe_show_startup_splash() is True


def test_org_actions_ignore_the_daily_marker(marker, licensed, fake_dialog):
    nag_state.mark_splash_shown()
    dd.show_support_if_needed(seconds=dd.ORG_ADD_SECONDS, require_org=True)
    assert fake_dialog == [dd.ORG_ADD_SECONDS]


# --- panel ------------------------------------------------------------------

@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_panel_offers_license_without_one(qapp, licensed):
    panel = dd.SupportPanel()
    assert "Поддержите проект" in panel._header.text()
    assert "1500" in panel._text.text() and "499" in panel._text.text()
    assert panel._code_row.isVisibleTo(panel)


def test_panel_thanks_when_licensed(qapp, licensed):
    lic.activate(make_code(licensed, name="ООО Ромашка"))
    panel = dd.SupportPanel()
    assert "Спасибо за поддержку" in panel._header.text()
    text = panel._text.text()
    assert "Организация" in text and "ООО Ромашка" in text and "01.01.2099" in text
    assert not panel._code_row.isVisibleTo(panel)  # nothing to renew yet


def test_panel_offers_renewal_near_expiry(qapp, licensed):
    soon = (date.today() + timedelta(days=10)).isoformat()
    lic.activate(make_code(licensed, exp=soon))
    panel = dd.SupportPanel()
    assert "осталось 10 дней" in panel._text.text()
    assert panel._code_row.isVisibleTo(panel)


def test_panel_switches_to_thanks_after_activation(qapp, licensed):
    panel = dd.SupportPanel()
    got = []
    panel.activated.connect(got.append)
    panel.code_edit.setText(make_code(licensed))
    panel.activate()
    assert "Спасибо за поддержку" in panel._header.text()
    assert got and got[0].is_org


@pytest.mark.parametrize("n,word", [(1, "день"), (2, "дня"), (5, "дней"), (11, "дней"), (21, "день")])
def test_days_word(n, word):
    assert dd._days_word(n) == word


def test_waiting_screen_panel_has_no_timer_and_hides(qapp, licensed):
    from tabs.employee_summary_tab import QueryProgressDialog
    dlg = QueryProgressDialog(3)
    from PySide6.QtWidgets import QPushButton
    box = dlg._support_box
    assert box.isVisibleTo(dlg)
    assert not dlg.findChildren(dd.SupportPanel)[0].findChildren(type(dlg._timer))
    hide_btn = [b for b in box.findChildren(QPushButton) if b.text() == "Скрыть"]
    assert hide_btn, "кнопка «Скрыть» должна быть в блоке"
    hide_btn[0].click()
    assert not box.isVisibleTo(dlg)
