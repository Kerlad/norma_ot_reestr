"""
«Поддержите проект» splash and support panel (UX-10, UX-16).

The splash is shown at startup once per calendar day (`utils/nag_state.py`), for
10 s, and before multi-organization actions without an «Организация» license
(30 s switch, 60 s add). The same content is embedded, without any timer, into
the employee-query waiting screen. With an active license the content turns into
«Спасибо за поддержку!» with the license details. Works offline.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from utils.dialog_base import BaseDialog

logger = logging.getLogger(__name__)

SITE_URL = "https://normaot.ru/"
STARTUP_SECONDS = 10
ORG_SWITCH_SECONDS = 30
ORG_ADD_SECONDS = 60
PRICE_ORG = 1500
PRICE_PERSONAL = 499
EXPIRY_WARN_DAYS = 30


def _current_license(require_org: bool = False):
    """Active license that covers the action, or None."""
    from utils.license import get_license
    try:
        lic = get_license()
    except Exception as e:
        logger.warning("License check failed: %s", type(e).__name__)
        return None
    if lic is None or (require_org and not lic.is_org):
        return None
    return lic


def needs_wait(require_org: bool = False) -> bool:
    return _current_license(require_org) is None


def _days_left(lic) -> int:
    from datetime import date
    return (lic.expires - date.today()).days


class SupportPanel(QWidget):
    """Support text + license code field, or the thank-you note when licensed.

    Used by SupportDialog and embedded in the employee-query waiting screen.
    """

    activated = Signal(object)

    def __init__(self, parent=None, require_org: bool = False, compact: bool = False):
        super().__init__(parent)
        self._require_org = require_org
        self._compact = compact
        self.activated_license = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._header = QLabel()
        self._header.setObjectName("aboutTitleLabel")
        if not compact:
            self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._header)

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.TextFormat.RichText)
        self._text.setOpenExternalLinks(True)
        layout.addWidget(self._text)

        self._code_row = QWidget()
        code_layout = QHBoxLayout(self._code_row)
        code_layout.setContentsMargins(0, 0, 0, 0)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Код лицензии (NOT1.…)")
        self.code_edit.returnPressed.connect(self.activate)
        code_layout.addWidget(self.code_edit, 1)
        self.activate_btn = QPushButton("Активировать")
        self.activate_btn.setObjectName("dialogPrimaryBtn")
        self.activate_btn.clicked.connect(self.activate)
        code_layout.addWidget(self.activate_btn)
        layout.addWidget(self._code_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("fieldErrorLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.refresh()

    # --- content ---------------------------------------------------------

    def refresh(self):
        lic = _current_license(self._require_org)
        self._license = lic
        if lic is None:
            self._show_offer()
        else:
            self._show_thanks(lic)

    def _show_offer(self):
        self._header.setText("Поддержите проект")
        if self._compact:
            self._text.setText(
                "Норма ОТ бесплатна для всех. Лицензия на 1 год убирает это окно: "
                "<b>«Организация» — %d ₽/год</b> (покрывает все организации в программе), "
                "<b>«Персональная» — %d ₽/год</b>. Как получить код — на сайте "
                "<a href=\"%s\">normaot.ru</a>." % (PRICE_ORG, PRICE_PERSONAL, SITE_URL))
        else:
            self._text.setText(
                "Норма ОТ бесплатна для всех. Лицензия на 1 год отключает это окно "
                "и помогает развивать программу:<br>"
                "• <b>«Организация» — %d ₽/год</b>: для юрлиц, покрывает все организации в "
                "программе;<br>"
                "• <b>«Персональная» — %d ₽/год</b>: для работы на себя или одного работодателя.<br>"
                "Как получить код — на сайте <a href=\"%s\">normaot.ru</a>."
                % (PRICE_ORG, PRICE_PERSONAL, SITE_URL))
        self._code_row.setVisible(True)
        self.activate_btn.setText("Активировать")
        self.code_edit.setPlaceholderText("Код лицензии (NOT1.…)")

    def _show_thanks(self, lic):
        from html import escape
        self._header.setText("Спасибо за поддержку!")
        left = _days_left(lic)
        text = ("Лицензия: <b>%s — %s</b><br>Действует до <b>%s</b>"
                % (escape(lic.tier_title), escape(lic.holder), lic.expires.strftime("%d.%m.%Y")))
        expiring = left <= EXPIRY_WARN_DAYS
        if expiring:
            text += " (осталось %d %s)" % (left, _days_word(left)) if left >= 0 else ""
            text += ("<br>Продлить лицензию можно на сайте <a href=\"%s\">normaot.ru</a>; "
                     "новый код введите ниже." % SITE_URL)
        self._text.setText(text)
        # The code field is only needed to renew an expiring license.
        self._code_row.setVisible(expiring)
        self.activate_btn.setText("Продлить")
        self.code_edit.setPlaceholderText("Новый код лицензии (NOT1.…)")

    def _show_status(self, text: str, error: bool):
        self.status_label.setText(text)
        self.status_label.setObjectName("fieldErrorLabel" if error else "aboutInfoLabel")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setVisible(True)

    # --- activation ------------------------------------------------------

    def activate(self):
        from utils.license import LicenseError, activate
        try:
            lic = activate(self.code_edit.text())
        except LicenseError as e:
            self._show_status(str(e), error=True)
            return
        self.activated_license = lic
        self.code_edit.clear()
        if self._require_org and not lic.is_org:
            self._show_status(
                "Лицензия «%s» активирована. Для работы с несколькими организациями "
                "без ожидания нужна лицензия «Организация»." % lic.tier_title, error=False)
            return
        self.refresh()
        self._show_status("Лицензия активирована: %s" % lic.describe(), error=False)
        self.activated.emit(lic)


def _days_word(n: int) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return "дней"
    tail = n % 10
    if tail == 1:
        return "день"
    if tail in (2, 3, 4):
        return "дня"
    return "дней"


class SupportDialog(BaseDialog):
    """Splash with a countdown and a license code field.

    seconds=0 — opened by the user (About/Help), closable at once.
    require_org=True — only an «Организация» license skips the wait.
    """

    def __init__(self, parent=None, seconds: int = STARTUP_SECONDS, reason: str = "",
                 require_org: bool = False):
        super().__init__(parent, title="Поддержите проект «Норма ОТ»", min_width=520, min_height=300)
        self._remaining = max(0, int(seconds))
        self._opened_without_wait = self._remaining == 0
        self.activated_license = None

        bl = self.body_layout()
        if reason:
            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("font-weight: bold;")
            bl.addWidget(reason_label)

        self.panel = SupportPanel(self, require_org=require_org)
        self.panel.activated.connect(self._on_activated)
        bl.addWidget(self.panel)
        bl.addStretch()

        self.support_btn = QPushButton("Поддержать проект")
        self.support_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SITE_URL)))
        self._button_layout.addWidget(self.support_btn)
        self._button_layout.addStretch()
        self.continue_btn = QPushButton()
        self.continue_btn.setObjectName("dialogPrimaryBtn")
        self.continue_btn.setMinimumHeight(36)
        self.continue_btn.clicked.connect(self._finish)
        self._button_layout.addWidget(self.continue_btn)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._update_continue()
        if self._remaining:
            self._timer.start()

    @property
    def code_edit(self):  # kept for convenience in tests and callers
        return self.panel.code_edit

    @property
    def status_label(self):
        return self.panel.status_label

    @property
    def waiting(self) -> bool:
        return self._remaining > 0

    def _activate(self):
        self.panel.activate()
        self.activated_license = self.panel.activated_license

    def _on_activated(self, lic):
        self.activated_license = lic
        self._remaining = 0
        self._timer.stop()
        self._update_continue()

    def _update_continue(self):
        if self._remaining:
            self.continue_btn.setText("Продолжить через %d с" % self._remaining)
            self.continue_btn.setEnabled(False)
        else:
            # Nothing was blocked (opened from About/Help or licensed): plain «Закрыть»
            self.continue_btn.setText("Закрыть" if self._opened_without_wait else "Продолжить")
            self.continue_btn.setEnabled(True)

    def _tick(self):
        self._remaining = max(0, self._remaining - 1)
        if not self._remaining:
            self._timer.stop()
        self._update_continue()

    def _finish(self):
        if not self.waiting:
            self.accept()

    # The wait cannot be skipped with Esc or the window close button.
    def reject(self):
        if not self.waiting:
            super().reject()

    def closeEvent(self, event):
        if self.waiting:
            event.ignore()
        else:
            super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.waiting:
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self.code_edit.hasFocus():
            self._finish()
            return
        super().keyPressEvent(event)


def show_support_if_needed(parent=None, seconds: int = STARTUP_SECONDS, reason: str = "",
                           require_org: bool = False) -> None:
    """Blocks for `seconds` unless a suitable license is active."""
    if not needs_wait(require_org):
        return
    SupportDialog(parent, seconds=seconds, reason=reason, require_org=require_org).exec()


def maybe_show_startup_splash(parent=None, seconds: int = STARTUP_SECONDS) -> bool:
    """UX-16: the startup splash appears once per calendar day. True if shown."""
    from utils import nag_state
    if not needs_wait():
        return False
    try:
        due = nag_state.splash_due()
    except Exception as e:
        logger.warning("Splash marker unreadable: %s", type(e).__name__)
        due = True
    if not due:
        return False
    SupportDialog(parent, seconds=seconds).exec()
    try:
        nag_state.mark_splash_shown()
    except Exception as e:
        logger.warning("Splash marker not saved: %s", type(e).__name__)
    return True


def show_support_dialog(parent=None) -> Optional[object]:
    """Opened from About/Help: no wait; shows the thank-you note when licensed."""
    dlg = SupportDialog(parent, seconds=0)
    dlg.exec()
    return dlg.activated_license
