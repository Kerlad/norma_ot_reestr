from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QWidget, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt


class BaseDialog(QDialog):
    """Базовый класс для всех диалогов приложения.

    scrollable=True: содержимое прокручивается, кнопки остаются внизу, а высота окна
    ограничивается доступной высотой экрана (для низких разрешений).
    """

    SCREEN_HEIGHT_RATIO = 0.9

    def __init__(self, parent: Optional[QWidget] = None, title: str = "", min_width: int = 480,
                 min_height: int = 320, scrollable: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(min_width, min_height)
        self._fields: List[QLineEdit] = []
        self._scrollable = scrollable

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        self._body_layout = QVBoxLayout()
        self._body_layout.setSpacing(12)
        if scrollable:
            body = QWidget()
            body.setLayout(self._body_layout)
            self._body_layout.setContentsMargins(0, 0, 0, 0)
            self._scroll_area = QScrollArea()
            self._scroll_area.setWidgetResizable(True)
            self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll_area.setWidget(body)
            # Inherit the dialog background in both themes
            self._scroll_area.setObjectName("dialogScrollArea")
            self._scroll_area.setStyleSheet("#dialogScrollArea { background: transparent; }")
            self._scroll_area.viewport().setAutoFillBackground(False)
            body.setObjectName("dialogScrollBody")
            body.setAutoFillBackground(False)
            body.setStyleSheet("#dialogScrollBody { background: transparent; }")
            main_layout.addWidget(self._scroll_area, 1)
        else:
            main_layout.addLayout(self._body_layout)

        self._button_layout = QHBoxLayout()
        self._button_layout.setSpacing(10)
        main_layout.addLayout(self._button_layout)

    def _available_height(self) -> int:
        screen = self.screen() or (self.parentWidget().screen() if self.parentWidget() else None)
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry().height() if screen else 0

    def showEvent(self, event) -> None:
        if self._scrollable:
            avail = self._available_height()
            if avail > 0:
                max_h = int(avail * self.SCREEN_HEIGHT_RATIO)
                body = self._scroll_area.widget()
                # Word-wrapped labels: height depends on the actual width.
                margins = self.layout().contentsMargins()
                body_w = max(self.width(), self.minimumWidth()) - margins.left() - margins.right()
                body_h = body.heightForWidth(body_w) if body.hasHeightForWidth() else -1
                if body_h <= 0:
                    body_h = body.sizeHint().height()
                chrome_h = self.sizeHint().height() - self._scroll_area.sizeHint().height()
                wanted = body_h + chrome_h + 4
                if self.minimumHeight() > max_h:
                    self.setMinimumHeight(max_h)
                self.resize(self.width(), max(self.minimumHeight(), min(wanted, max_h)))
                self._max_fit_height = max_h
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._grow_to_fit)
        super().showEvent(event)

    def _grow_to_fit(self) -> None:
        """Estimate may be a few px short (wrapping, scrollbar): grow while the screen allows."""
        sb = self._scroll_area.verticalScrollBar()
        missing = sb.maximum()
        if missing > 0 and self.height() < self._max_fit_height:
            self.resize(self.width(), min(self.height() + missing + 2, self._max_fit_height))

    def body_layout(self) -> QVBoxLayout:
        return self._body_layout

    def register_field(self, field: QLineEdit) -> None:
        self._fields.append(field)

    def validate_fields(self) -> bool:
        for field in self._fields:
            validator_fn = getattr(field, '_validator', None)
            if validator_fn:
                error = validator_fn(field.text())
                if error:
                    from utils.ui_helpers import mark_invalid
                    mark_invalid(field)
                    field.setToolTip(error)
                    field.setFocus()
                    return False
                from utils.ui_helpers import mark_invalid
                mark_invalid(field, False)
                field.setToolTip("")
        return True

    def add_buttons(self, buttons: List[QPushButton]) -> None:
        self._button_layout.addStretch()
        for btn in buttons:
            self._button_layout.addWidget(btn)

    def add_close_button(self, text: str = "Закрыть", primary: bool = True) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("dialogPrimaryBtn" if primary else "dialogDangerBtn")
        btn.clicked.connect(self.close)
        self._button_layout.addStretch()
        self._button_layout.addWidget(btn)
        return btn

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def show_validation_error(parent: QWidget, field: QLineEdit, message: str) -> None:
        from utils.ui_helpers import mark_invalid
        mark_invalid(field)
        field.setToolTip(message)
        field.setFocus()
