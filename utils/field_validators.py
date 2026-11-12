from typing import Optional, Callable
from PySide6.QtWidgets import QLineEdit, QWidget
from PySide6.QtCore import Qt


from utils.constants import VALID_PROGRAMS_SET
from utils.record_rules import snils_checksum_ok as _snils_checksum_valid
from utils.ui_helpers import mark_invalid


class ValidatedLineEdit(QLineEdit):
    """QLineEdit с визуальной валидацией (красная обводка + tooltip)."""

    def __init__(self, parent: Optional[QWidget] = None,
                 validator: Optional[Callable[[str], Optional[str]]] = None):
        super().__init__(parent)
        self._validator = validator
        self._valid = True
        self.textChanged.connect(self._on_text_changed)

    def set_validator_fn(self, validator: Callable[[str], Optional[str]]) -> None:
        self._validator = validator

    def _on_text_changed(self, text: str) -> None:
        if self._validator:
            error = self._validator(text)
            self._valid = error is None
            mark_invalid(self, bool(error))
            self.setToolTip(error if error else "")
        else:
            self._valid = True
            mark_invalid(self, False)
            self.setToolTip("")

    def is_valid(self) -> bool:
        if not self._validator:
            return True
        return self._validator(self.text()) is None

    def set_invalid(self, error: str) -> None:
        self._valid = False
        mark_invalid(self)
        self.setToolTip(error)

    def clear_validation(self) -> None:
        self._valid = True
        mark_invalid(self, False)
        self.setToolTip("")


def validate_snils(snils: str) -> Optional[str]:
    """Проверяет СНИЛС. Возвращает ошибку или None."""
    clean = snils.replace("-", "").replace(" ", "").replace("\xa0", "")
    if not clean:
        return None
    if not clean.isdigit() or len(clean) != 11:
        return "СНИЛС должен содержать 11 цифр"
    if not _snils_checksum_valid(clean):
        return "Неверная контрольная сумма СНИЛС"
    return None


def validate_required(text: str, field_name: str = "Поле") -> Optional[str]:
    """Проверяет, что поле не пустое."""
    if not text.strip():
        return f"{field_name} обязательно для заполнения"
    return None


def validate_program_id(pid: str) -> Optional[str]:
    """Проверяет номер программы."""
    clean = pid.strip()
    if not clean:
        return None
    if clean not in VALID_PROGRAMS_SET:
        return "Некорректный номер программы (допустимо: 1-4, 6-29)"
    return None


def validate_date(date_str: str) -> Optional[str]:
    """Проверяет дату в формате DD.MM.YYYY."""
    from datetime import datetime
    clean = date_str.replace("-", "").replace(".", "").strip()
    if not clean:
        return None
    if not clean.isdigit() or len(clean) != 8:
        return "Дата должна быть в формате ДД.ММ.ГГГГ"
    try:
        dt = datetime.strptime(clean, "%d%m%Y")
        if dt.date() > datetime.now().date():
            return "Дата не может быть больше текущей"
    except ValueError:
        return "Дата некорректна"
    return None


def validate_name(name: str) -> Optional[str]:
    """Проверяет, что имя/фамилия содержит только буквы."""
    clean = name.strip().replace(" ", "").replace("-", "")
    if not clean:
        return None
    if not clean.replace(".", "").isalpha():
        return "Допускаются только буквы"
    return None
