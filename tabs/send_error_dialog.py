"""Error of an XML send: long server messages scroll inside the dialog."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from utils.dialog_base import BaseDialog

RAW_RESPONSE_LIMIT = 2000


def split_error_text(error: str) -> tuple:
    """'Summary\\n\\nПодробности: ...' -> (summary, details)."""
    text = (error or "").strip() or "Неизвестная ошибка"
    head, sep, rest = text.partition("\n\n")
    if not sep:
        return head, ""
    rest = rest.strip()
    if rest.startswith("Подробности:"):
        rest = rest[len("Подробности:"):].strip()
    return head, rest


class SendErrorDialog(BaseDialog):
    """Summary line + scrollable server text; the dialog never grows past the screen."""

    def __init__(self, parent, error: str, raw_response: str = ""):
        super().__init__(parent, title="Ошибка загрузки", min_width=600, min_height=360,
                         subtitle="Набор не создан. Исправьте данные и отправьте XML снова.")
        summary, details = split_error_text(error)
        self._full_text = (error or "").strip()

        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("cardTitle")
        self.summary_label.setWordWrap(True)
        self.body_layout().addWidget(self.summary_label)

        self.details_view = QPlainTextEdit()
        self.details_view.setReadOnly(True)
        self.details_view.setPlainText(details or summary)
        self.details_view.setMinimumHeight(200)
        self.body_layout().addWidget(self.details_view, 1)

        self.raw_view = None
        raw = (raw_response or "").strip()
        if raw:
            self.raw_view = QPlainTextEdit()
            self.raw_view.setReadOnly(True)
            self.raw_view.setPlainText(raw[:RAW_RESPONSE_LIMIT])
            self.raw_view.setMinimumHeight(120)
            self.raw_view.setVisible(False)
            self.body_layout().addWidget(self.raw_view, 1)
            self.raw_btn = self.add_footer_button("Ответ сервера", self._toggle_raw, role="ghost")
            self.raw_btn.setCheckable(True)

        self.add_footer_button("Копировать текст", self._copy, role="secondary")
        self.add_close_button()

    def _toggle_raw(self, checked: bool) -> None:
        if self.raw_view is not None:
            self.raw_view.setVisible(bool(checked))

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._full_text)
        from utils.toast import Toast
        Toast.info(self, "Текст ошибки скопирован")
