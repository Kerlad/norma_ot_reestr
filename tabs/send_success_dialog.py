"""Success window after an XML send: the set number on a notice plate with a copy button."""
from html import escape

from PySide6.QtWidgets import QApplication

from utils.dialog_base import BaseDialog
from utils.ui_helpers import notice_label


class SendSuccessDialog(BaseDialog):
    def __init__(self, parent, message: str, set_id: str):
        super().__init__(parent, title="Успех", min_width=480, min_height=220)
        self._set_id = set_id or ""

        text = notice_label(escape(message), "ok")
        self.body_layout().addWidget(text)

        self.set_id_plate = notice_label(
            "Запишите номер набора: <b>%s</b>" % escape(self._set_id or "—"), "warn")
        self.body_layout().addWidget(self.set_id_plate)
        self.body_layout().addStretch(1)

        self.copy_btn = self.add_footer_button(
            "Скопировать номер набора", self._copy_set_id, role="secondary")
        self.copy_btn.setEnabled(bool(self._set_id))
        self.add_close_button()

    def _copy_set_id(self) -> None:
        from utils.clipboard_guard import ClipboardGuard
        ClipboardGuard.mark_own_copy()
        QApplication.clipboard().setText(self._set_id)
        from utils.toast import Toast
        Toast.info(self, "Номер набора скопирован")
