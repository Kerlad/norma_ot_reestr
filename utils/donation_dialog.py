"""
«Поддержите проект» splash (UX-10).

Shown at startup (10 s) and before multi-organization actions without an
«Организация» license (30 s switch, 60 s add). The continue button stays disabled
during a visible countdown; a valid license code closes it at once. Works offline.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton

from utils.dialog_base import BaseDialog

logger = logging.getLogger(__name__)

SITE_URL = "https://normaot.ru/"
STARTUP_SECONDS = 10
ORG_SWITCH_SECONDS = 30
ORG_ADD_SECONDS = 60
PRICE_ORG = 1500
PRICE_PERSONAL = 499


class SupportDialog(BaseDialog):
    """Nag screen with countdown and license code input.

    seconds=0 — opened by the user (About/Help), closable at once.
    require_org=True — only an «Организация» license skips the wait.
    """

    def __init__(self, parent=None, seconds: int = STARTUP_SECONDS, reason: str = "",
                 require_org: bool = False):
        super().__init__(parent, title="Поддержите проект «Норма ОТ»", min_width=520, min_height=300)
        self._remaining = max(0, int(seconds))
        self._require_org = require_org
        self.activated_license = None

        bl = self.body_layout()
        header = QLabel("❤️ Поддержите проект")
        header.setObjectName("aboutTitleLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(header)

        if reason:
            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("font-weight: bold;")
            bl.addWidget(reason_label)

        text = QLabel(
            "Норма ОТ бесплатна для всех. Лицензия на 1 год отключает это окно "
            "и помогает развивать программу:<br>"
            "• <b>«Организация» — %d ₽/год</b>: для юрлиц, покрывает все организации в программе;<br>"
            "• <b>«Персональная» — %d ₽/год</b>: для работы на себя или одного работодателя.<br>"
            "Как получить код — на сайте <a href=\"%s\">normaot.ru</a>."
            % (PRICE_ORG, PRICE_PERSONAL, SITE_URL)
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)
        bl.addWidget(text)

        code_row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Код лицензии (NOT1.…)")
        self.code_edit.returnPressed.connect(self._activate)
        code_row.addWidget(self.code_edit, 1)
        self.activate_btn = QPushButton("Активировать")
        self.activate_btn.setObjectName("dialogPrimaryBtn")
        self.activate_btn.clicked.connect(self._activate)
        code_row.addWidget(self.activate_btn)
        bl.addLayout(code_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("fieldErrorLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        bl.addWidget(self.status_label)
        bl.addStretch()

        support_btn = QPushButton("Поддержать проект")
        support_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SITE_URL)))
        self._button_layout.addWidget(support_btn)
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
    def waiting(self) -> bool:
        return self._remaining > 0

    def _update_continue(self):
        if self._remaining:
            self.continue_btn.setText("Продолжить через %d с" % self._remaining)
            self.continue_btn.setEnabled(False)
        else:
            self.continue_btn.setText("Продолжить")
            self.continue_btn.setEnabled(True)

    def _tick(self):
        self._remaining = max(0, self._remaining - 1)
        if not self._remaining:
            self._timer.stop()
        self._update_continue()

    def _show_status(self, text: str, error: bool):
        self.status_label.setText(text)
        self.status_label.setObjectName("fieldErrorLabel" if error else "aboutInfoLabel")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setVisible(True)

    def _activate(self):
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
        self._show_status("Лицензия активирована: %s" % lic.describe(), error=False)
        self._remaining = 0
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


def needs_wait(require_org: bool = False) -> bool:
    from utils.license import get_license
    lic = get_license()
    if lic is None:
        return True
    return require_org and not lic.is_org


def show_support_if_needed(parent=None, seconds: int = STARTUP_SECONDS, reason: str = "",
                           require_org: bool = False) -> None:
    """Blocks for `seconds` unless a suitable license is active."""
    try:
        if not needs_wait(require_org):
            return
    except Exception as e:
        logger.warning("License check failed: %s", type(e).__name__)
    SupportDialog(parent, seconds=seconds, reason=reason, require_org=require_org).exec()


def show_support_dialog(parent=None) -> Optional[object]:
    """Opened from About/Help: no wait. Returns the activated License, if any."""
    dlg = SupportDialog(parent, seconds=0)
    dlg.exec()
    return dlg.activated_license
