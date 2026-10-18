"""
Диалог «Запросить по…» журнала проверки знаний (UX-07):
выбор SetId / СНИЛС, ввод значения, запрос в реестр Минтруда в фоновом потоке.
"""
import logging

from PySide6.QtCore import QObject, QThread, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
)

from utils.dialog_base import BaseDialog
from utils.field_validators import validate_snils
from journal.registry_sync import format_snils, snils_key

logger = logging.getLogger(__name__)

MODE_SETID = "setid"
MODE_SNILS = "snils"


def validate_query_value(mode: str, text: str):
    """Returns (normalized_value, error). SetId — только цифры, СНИЛС — 11 цифр с контрольной суммой."""
    text = (text or "").strip()
    if mode == MODE_SETID:
        if not text:
            return "", "Введите SetId"
        if not text.isdigit():
            return "", "SetId должен состоять только из цифр"
        return text, None
    if not text:
        return "", "Введите СНИЛС"
    if len(snils_key(text)) != 11:
        return "", "СНИЛС должен содержать 11 цифр"
    err = validate_snils(text)
    if err:
        return "", err
    return format_snils(text), None


class RegistryQueryWorker(QObject):
    finished = Signal(dict)

    def __init__(self, mode, value, api_key, proxy_settings):
        super().__init__()
        self.mode, self.value = mode, value
        self.api_key, self.proxy_settings = api_key, proxy_settings

    def run(self):
        from api.mintrud_api import get_by_set_id, get_by_snils
        try:
            if self.mode == MODE_SETID:
                result = get_by_set_id(self.api_key, self.value, proxy_settings=self.proxy_settings)
            else:
                result = get_by_snils(self.api_key, self.value, proxy_settings=self.proxy_settings)
        except Exception as e:  # network/backends raise many types; UI shows a safe message
            logger.warning("Registry query failed: %s", type(e).__name__)
            result = {"success": False, "error": str(e), "records": []}
        result["mode"], result["value"] = self.mode, self.value
        self.finished.emit(result)


class RegistryQueryDialog(BaseDialog):
    """После «Запросить» диалог закрывается с Accepted; mode()/value() — что запросить."""

    def __init__(self, parent=None):
        super().__init__(parent, title="Запрос в реестр Минтруда", min_width=420, min_height=200)
        bl = self.body_layout()

        radio_row = QHBoxLayout()
        self.setid_radio = QRadioButton("SetId")
        self.snils_radio = QRadioButton("СНИЛС")
        self.setid_radio.setChecked(True)
        self._group = QButtonGroup(self)
        self._group.addButton(self.setid_radio)
        self._group.addButton(self.snils_radio)
        radio_row.addWidget(QLabel("Запросить по:"))
        radio_row.addWidget(self.setid_radio)
        radio_row.addWidget(self.snils_radio)
        radio_row.addStretch()
        bl.addLayout(radio_row)

        self.value_input = QLineEdit()
        bl.addWidget(self.value_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("fieldErrorLabel")
        self.error_label.setWordWrap(True)
        bl.addWidget(self.error_label)
        bl.addStretch()

        self.query_btn = QPushButton("Запросить")
        self.query_btn.setObjectName("dialogPrimaryBtn")
        self.query_btn.setDefault(True)
        self.query_btn.clicked.connect(self._on_query)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        self.add_buttons([self.query_btn, cancel_btn])

        self.setid_radio.toggled.connect(self._apply_mode)
        self._apply_mode()

    def mode(self) -> str:
        return MODE_SETID if self.setid_radio.isChecked() else MODE_SNILS

    def value(self) -> str:
        return self._value

    def _apply_mode(self, *args):
        self.value_input.clear()
        self.error_label.clear()
        if self.mode() == MODE_SETID:
            self.value_input.setPlaceholderText("Номер набора (SetId), только цифры")
            self.value_input.setMaxLength(20)
            self.value_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,20}"), self))
        else:
            self.value_input.setPlaceholderText("XXX-XXX-XXX XX")
            self.value_input.setMaxLength(14)
            self.value_input.setValidator(QRegularExpressionValidator(QRegularExpression(r"[\d\- ]{0,14}"), self))
        self.value_input.setFocus()

    def _on_query(self):
        value, err = validate_query_value(self.mode(), self.value_input.text())
        if err:
            self.error_label.setText(err)
            from utils.ui_helpers import mark_invalid
            mark_invalid(self.value_input)
            return
        self._value = value
        self.accept()

    _value = ""
