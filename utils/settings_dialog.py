"""«Настройки и темы»: sections on the left, content on the right.

Every action lives in the main window (`host`); this dialog only exposes them, so nothing from the
old menu bar is lost: appearance, registry connection, security, session lock, organizations.
"""
from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from utils.dialog_base import BaseDialog
from utils.tahoe_style import THEME_LABELS, THEME_ORDER, get_colors


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsSectionTitle")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsHint")
    label.setWordWrap(True)
    return label


def _button(text: str, handler: Callable, role: str = "secondary") -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("role", role)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(lambda checked=False: handler())
    return btn


class ThemeCard(QPushButton):
    """Checkable card with a colour swatch strip of the theme."""

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("themeCard")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(150, 96)
        c = get_colors(key)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        strip = QHBoxLayout()
        strip.setSpacing(0)
        for color, stretch in ((c.side_bg, 2), (c.page, 5), (c.cta, 1)):
            part = QFrame()
            part.setFixedHeight(40)
            part.setStyleSheet("background-color: %s; border: none;" % color)
            part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            strip.addWidget(part, stretch)
        lay.addLayout(strip)
        name = QLabel(THEME_LABELS[key])
        name.setObjectName("themeCardName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(name)


class SettingsDialog(BaseDialog):
    SECTIONS: List[Tuple[str, str]] = [
        ("appearance", "Внешний вид"),
        ("registry", "Подключение к реестру"),
        ("security", "Безопасность"),
        ("lock", "Блокировка сеанса"),
        ("files", "Файлы"),
        ("orgs", "Организации"),
    ]

    def __init__(self, host, parent=None):
        super().__init__(parent or host, "Настройки и темы", min_width=760, min_height=460)
        self._host = host
        body = QHBoxLayout()
        body.setSpacing(16)
        self.section_list = QListWidget()
        self.section_list.setObjectName("settingsSections")
        self.section_list.setFixedWidth(210)
        self.stack = QStackedWidget()
        self._index: Dict[str, int] = {}
        builders = {
            "appearance": self._build_appearance, "registry": self._build_registry,
            "security": self._build_security, "lock": self._build_lock, "orgs": self._build_orgs,
            "files": self._build_files,
        }
        for key, title in self.SECTIONS:
            self.section_list.addItem(title)
            self._index[key] = self.stack.addWidget(builders[key]())
        self.section_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.section_list.setCurrentRow(0)
        body.addWidget(self.section_list)
        body.addWidget(self.stack, 1)
        self._body_layout.addLayout(body, 1)
        self.add_close_button()

    def show_section(self, key: str) -> None:
        self.section_list.setCurrentRow(self._index[key])

    # -- sections ------------------------------------------------------------

    def _page(self) -> Tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        return page, lay

    def _build_appearance(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(_section_title("Тема оформления"))
        lay.addWidget(_hint("Тема меняет только цвета. Выбор запоминается."))
        row = QHBoxLayout()
        row.setSpacing(12)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self.theme_cards: Dict[str, ThemeCard] = {}
        for key in THEME_ORDER:
            card = ThemeCard(key)
            card.setChecked(key == self._host.current_theme)
            card.clicked.connect(lambda checked=False, k=key: self._host._select_theme(k))
            self._theme_group.addButton(card)
            self.theme_cards[key] = card
            row.addWidget(card)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_hint("Сочетание клавиш Ctrl+D переключает на следующую тему."))
        lay.addStretch(1)
        return page

    def _build_registry(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(_section_title("Подключение к реестру"))
        lay.addWidget(_hint("Прокси-сервер и параметры подключения к реестру обученных Минтруда."))
        lay.addWidget(_button("Настройки прокси…", lambda: self._host._open_proxy_settings(self)))
        lay.addStretch(1)
        return page

    def _build_security(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(_section_title("Безопасность"))
        lay.addWidget(_hint("Ключи шифрования, парольная фраза, резервные копии ключа."))
        lay.addWidget(_button("Безопасность…", self._host._open_security))
        lay.addSpacing(8)
        lay.addWidget(_hint("Журнал событий программы."))
        lay.addWidget(_button("Просмотр журнала событий", self._host.show_log_viewer))
        lay.addSpacing(16)
        lay.addWidget(_section_title("Опасная зона"))
        lay.addWidget(_hint("Удаляет все данные приложения безвозвратно, включая все организации."))
        lay.addWidget(_button("Удалить все данные приложения…", self._host._delete_all_app_data, "danger"))
        lay.addStretch(1)
        return page

    def _build_lock(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(_section_title("Блокировка сеанса"))
        lay.addWidget(_hint("Через указанное время бездействия сеанс блокируется. Ctrl+L блокирует сразу."))
        row = QHBoxLayout()
        row.addWidget(QLabel("Минуты бездействия:"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(self._host.auto_lock.timeout_minutes)
        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)
        row.addWidget(self.timeout_spin)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_button("Заблокировать сейчас", self._host._manual_lock))
        lay.addStretch(1)
        return page

    def _on_timeout_changed(self, value: int) -> None:
        self._host.auto_lock.timeout_minutes = value

    def _build_orgs(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(_section_title("Организации"))
        lay.addWidget(_hint("У каждой организации свои данные. При смене программа перезапускается."))
        for text, handler, role in (
            ("Сменить организацию…", self._host._switch_org, "secondary"),
            ("Добавить организацию…", self._host._add_org, "secondary"),
            ("Удалить организацию…", self._host._delete_org, "danger"),
        ):
            lay.addWidget(_button(text, handler, role))
        lay.addStretch(1)
        return page

    def _build_files(self) -> QWidget:
        from PySide6.QtWidgets import QFileDialog, QLineEdit
        from utils import xml_output
        page, lay = self._page()
        lay.addWidget(_section_title("Папка для XML"))
        lay.addWidget(_hint(
            "Сюда сохраняется файл при «Сформировать XML и перейти к передаче». Имя файла: ДДММГГГГ-ЧЧ-ММ.xml, "
            "при совпадении добавляется «-2». Если своя папка не выбрана, это папка XML рядом с программой "
            "или, если туда нельзя писать, «Документы\\Норма ОТ\\XML»."))
        row = QHBoxLayout()
        self.xml_dir_edit = QLineEdit()
        self.xml_dir_edit.setReadOnly(True)
        row.addWidget(self.xml_dir_edit, 1)
        pick = _button("Выбрать папку…", lambda: self._pick_xml_dir(QFileDialog))
        row.addWidget(pick)
        reset = _button("По умолчанию", self._reset_xml_dir, "ghost")
        row.addWidget(reset)
        lay.addLayout(row)
        self._refresh_xml_dir()
        lay.addStretch(1)
        return page

    def _refresh_xml_dir(self) -> None:
        from utils import xml_output
        custom = xml_output.custom_xml_dir()
        self.xml_dir_edit.setText(custom or xml_output.get_xml_dir())
        self.xml_dir_edit.setToolTip("Своя папка" if custom else "Папка по умолчанию")

    def _pick_xml_dir(self, file_dialog) -> None:
        from utils import xml_output
        start = xml_output.get_xml_dir()
        path = file_dialog.getExistingDirectory(self, "Папка для XML", start)
        if not path:
            return
        if not xml_output.is_writable_dir(path):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Папка для XML", "В эту папку нельзя записывать. Выберите другую.")
            return
        xml_output.set_custom_xml_dir(path)
        self._refresh_xml_dir()

    def _reset_xml_dir(self) -> None:
        from utils import xml_output
        xml_output.set_custom_xml_dir("")
        self._refresh_xml_dir()

    def refresh_theme_cards(self) -> None:
        for key, card in getattr(self, "theme_cards", {}).items():
            card.setChecked(key == self._host.current_theme)
