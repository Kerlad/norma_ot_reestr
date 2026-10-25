from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QWidget, QScrollArea, QFrame, QLabel,
)
from PySide6.QtCore import Qt


class BaseDialog(QDialog):
    """Базовый класс для всех диалогов приложения.

    scrollable=True: содержимое прокручивается, кнопки остаются внизу, а высота окна
    ограничивается доступной высотой экрана (для низких разрешений).
    """

    SCREEN_HEIGHT_RATIO = 0.9

    def __init__(self, parent: Optional[QWidget] = None, title: str = "", min_width: int = 480,
                 min_height: int = 320, scrollable: bool = False, subtitle: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(min_width, min_height)
        self._fields: List[QLineEdit] = []
        self._scrollable = scrollable

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # header: title (Space Grotesk 17) and an optional one-line explanation
        self._header = QFrame()
        self._header.setObjectName("dialogHeader")
        header_lay = QVBoxLayout(self._header)
        header_lay.setContentsMargins(20, 12, 20, 12)
        header_lay.setSpacing(0)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("dialogTitle")
        header_lay.addWidget(self._title_label)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setObjectName("dialogSubtitle")
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setVisible(bool(subtitle))
        header_lay.addWidget(self._subtitle_label)
        self._header.setVisible(bool(title))
        main_layout.addWidget(self._header)

        self._body_layout = QVBoxLayout()
        self._body_layout.setSpacing(12)
        self._body_layout.setContentsMargins(20, 16, 20, 16)
        if scrollable:
            body = QWidget()
            body.setLayout(self._body_layout)
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
            main_layout.addLayout(self._body_layout, 1)

        # footer on a subtle surface, buttons on the right; hidden while it has no buttons
        self._footer = QFrame()
        self._footer.setObjectName("dialogFooter")
        self._button_layout = QHBoxLayout(self._footer)
        self._button_layout.setContentsMargins(20, 12, 20, 12)
        self._button_layout.setSpacing(10)
        self._left_buttons = 0
        main_layout.addWidget(self._footer)

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        label = getattr(self, "_title_label", None)
        if label is not None:
            label.setText(title)
            self._header.setVisible(bool(title))

    def set_subtitle(self, text: str) -> None:
        self._subtitle_label.setText(text)
        self._subtitle_label.setVisible(bool(text))

    def _available_height(self) -> int:
        screen = self.screen() or (self.parentWidget().screen() if self.parentWidget() else None)
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry().height() if screen else 0

    def showEvent(self, event) -> None:
        self._footer.setVisible(self._button_layout.count() > 0)
        if self._scrollable:
            avail = self._available_height()
            if avail > 0:
                max_h = int(avail * self.SCREEN_HEIGHT_RATIO)
                body = self._scroll_area.widget()
                # Word-wrapped labels: height depends on the actual width.
                margins = self._body_layout.contentsMargins()
                body_w = max(self.width(), self.minimumWidth())
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

    def add_action_buttons(self, primary_text: str, on_primary, secondary_text: str = "Отмена",
                           on_secondary=None, primary_role: str = "primary"):
        """Footer: [secondary] [primary] on the right. Returns (primary_button, secondary_button)."""
        secondary = QPushButton(secondary_text)
        secondary.setProperty("role", "secondary")
        secondary.clicked.connect(on_secondary if on_secondary is not None else self.reject)
        primary = QPushButton(primary_text)
        primary.setProperty("role", primary_role)
        primary.clicked.connect(on_primary)
        self._button_layout.addStretch()
        self._button_layout.addWidget(secondary)
        self._button_layout.addWidget(primary)
        return primary, secondary

    def add_footer_button(self, text: str, handler, role: str = "secondary") -> QPushButton:
        """Extra button at the left edge of the footer."""
        btn = QPushButton(text)
        btn.setProperty("role", role)
        btn.clicked.connect(handler)
        self._button_layout.insertWidget(self._left_buttons, btn)
        self._left_buttons += 1
        return btn

    def add_close_button(self, text: str = "Закрыть", primary: bool = True) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("dialogPrimaryBtn" if primary else "dialogDangerBtn")
        btn.setProperty("role", "primary" if primary else "secondary")
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
