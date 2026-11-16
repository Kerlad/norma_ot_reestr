"""Main-window frame widgets: dark side menu with the «today» block and the page header."""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget,
)

from utils.icons import nav_icon

logger = logging.getLogger(__name__)

SIDEBAR_WIDTH = 220
TODAY_REFRESH_MS = 30000
# The sidebar needs ~686 px (layout minimumSize measured with the «today» block; the block alone is
# ~150 px, without it ~536 px). A 1366x728 screen leaves ~690 px of client height, so the block must
# stay visible at 690; the 4 px reserve absorbs 1-2 px font-metric differences (Linux).
TODAY_MIN_HEIGHT = 688


def compute_status_counts() -> Tuple[int, int, int, int, int]:
    """(employees, expired, not_trained, records, expiring).

    The first three follow the same rules as the «Сводка» cards (FR-001/002); `records` is the
    number of rows in «Просмотр данных» waiting to be sent (WorkersDataRepo); `expiring` is the
    number of fully trained employees with a program ending within SIDEBAR_PERIOD days (C4).
    """
    from db.employee_programs_repo import EmployeeProgramsRepo
    from db.employees_repo import EmployeesRepo
    from db.workers_data_repo import WorkersDataRepo
    from tabs.summary_expiry import SIDEBAR_PERIOD, employee_expires_within
    from utils.training_rules import get_dynamic_status

    employees = EmployeesRepo.get_all()
    progs_by_emp = EmployeeProgramsRepo.get_by_employee_ids([e["id"] for e in employees])
    expired = not_trained = expiring = 0
    for emp in employees:
        entry = progs_by_emp.get(emp["id"])
        progs = entry["programs"] if isinstance(entry, dict) else (entry or [])
        statuses = []
        for pr in progs:
            if pr.get("need_training") != 1:
                continue
            statuses.append(get_dynamic_status(
                pr.get("status", "not_trained"), pr.get("exam_date", ""),
                pr.get("program_id", 0), True, result=pr.get("result")))
        if not statuses:
            continue
        if employee_expires_within(progs, SIDEBAR_PERIOD, True):
            expiring += 1
        if "not_trained" in statuses:
            not_trained += 1
        elif "expired" in statuses:
            expired += 1
    return len(employees), expired, not_trained, WorkersDataRepo.count(), expiring


class PageHeader(QFrame):
    """60 px screen header: title, explanatory subtitle, actions on the right."""

    def __init__(self, title: str, subtitle: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("pageHeader")
        self.setFixedHeight(60)
        row = QHBoxLayout(self)
        row.setContentsMargins(24, 0, 24, 0)
        row.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("pageSubtitle")
        texts.addStretch(1)
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        texts.addStretch(1)
        row.addLayout(texts, 1)
        # Only after the label has a parent: setVisible(True) on a parentless widget shows it
        # as a separate top-level window for a moment (startup "flashing windows").
        self.subtitle_label.setVisible(bool(subtitle))
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        row.addLayout(self._actions)

    def add_action(self, widget: QWidget) -> QWidget:
        self._actions.addWidget(widget)
        return widget


class _ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class Sidebar(QFrame):
    """Dark side menu: organization, sections, protocols, «today» block, settings/help/version."""

    page_selected = Signal(int)
    settings_requested = Signal()
    help_requested = Signal()
    version_requested = Signal()
    about_requested = Signal()
    org_switch_requested = Signal()
    org_add_requested = Signal()
    org_delete_requested = Signal()

    # (icon, title, group); group "main" or "protocols"
    ITEMS: List[Tuple[str, str, str]] = [
        ("entry", "Внесение данных", "main"),
        ("view", "Просмотр данных", "main"),
        ("transfer", "Передача данных", "main"),
        ("journal", "Журнал проверки знаний", "main"),
        ("summary", "Сводка по сотрудникам", "main"),
        ("protocols", "Настройка протоколов", "protocols"),
        ("quick", "Быстрый протокол", "protocols"),
    ]

    def __init__(self, version: str, org_name: str = "", app_icon_path: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._buttons: List[QPushButton] = []
        self._icon_color = QColor()  # set from the theme by apply_theme_colors()
        self._icon_color_active = QColor()
        self._active_index = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 14, 10, 12)
        root.setSpacing(2)

        # brand
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setObjectName("sidebarLogo")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if app_icon_path:
            from utils.ui_helpers import sharp_pixmap
            pm = sharp_pixmap(app_icon_path, 28, logo)
            if not pm.isNull():
                logo.setPixmap(pm)
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel("Норма ОТ")
        title.setObjectName("sidebarTitle")
        sub = QLabel("Реестр обучения")
        sub.setObjectName("sidebarMuted")
        names.addWidget(title)
        names.addWidget(sub)
        brand.addLayout(names, 1)
        root.addLayout(brand)
        root.addSpacing(10)

        # organization
        self.org_button = QPushButton()
        self.org_button.setObjectName("sidebarOrg")
        self.org_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.org_button.setToolTip("Организация")
        self.org_button.setIconSize(QSize(16, 16))
        self.org_menu = QMenu(self)
        self.org_menu.addAction("Сменить организацию…", self.org_switch_requested.emit)
        self.org_menu.addAction("Добавить организацию…", self.org_add_requested.emit)
        self.org_menu.addSeparator()
        self.org_menu.addAction("Удалить организацию…", self.org_delete_requested.emit)
        self.org_button.setMenu(self.org_menu)
        self.set_org_name(org_name)
        root.addWidget(self.org_button)
        root.addSpacing(12)

        # sections
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        protocols_label_added = False
        for page_index, (icon, text, group) in enumerate(self.ITEMS):
            if group == "protocols" and not protocols_label_added:
                root.addSpacing(8)
                line = QFrame()
                line.setObjectName("sidebarLine")
                line.setFixedHeight(1)
                root.addWidget(line)
                label = QLabel("ПРОТОКОЛЫ")
                label.setObjectName("sidebarSection")
                root.addWidget(label)
                protocols_label_added = True
            btn = QPushButton(text)
            btn.setObjectName("sidebarItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            btn.setIconSize(QSize(18, 18))
            btn.setProperty("icon_name", icon)
            btn.setToolTip("%s  (Ctrl+%d)" % (text, page_index + 1))
            self._group.addButton(btn, page_index)
            self._buttons.append(btn)
            root.addWidget(btn)
        self._group.idClicked.connect(self._on_clicked)

        root.addStretch(1)

        # today block
        self.today_box = QFrame()
        self.today_box.setObjectName("sidebarToday")
        tb = QVBoxLayout(self.today_box)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(2)
        caption = QLabel("СЕГОДНЯ")
        caption.setObjectName("sidebarSection")
        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("sidebarClock")
        self.date_label = QLabel("")
        self.date_label.setObjectName("sidebarMuted")
        tb.addWidget(caption)
        tb.addWidget(self.time_label)
        tb.addWidget(self.date_label)
        tb.addSpacing(4)
        self.employees_value = self._counter_row(tb, "Сотрудников в сводке")
        self.expired_value = self._counter_row(tb, "Просрочено")
        self.not_trained_value = self._counter_row(tb, "Не обучено")
        self.expiring_value = self._counter_row(tb, "Истекает за 60 дней")
        self.records_value = self._counter_row(tb, "Записей к отправке")
        root.addWidget(self.today_box)
        root.addSpacing(6)

        # bottom
        self.settings_button = self._bottom_button("settings", "Настройки и темы")
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self.help_button = self._bottom_button("help", "Справка")
        self.help_button.setToolTip("Справка (F1)")
        self.help_button.clicked.connect(self.help_requested.emit)
        self.about_button = self._bottom_button("info", "О программе")
        self.about_button.clicked.connect(self.about_requested.emit)
        root.addWidget(self.settings_button)
        root.addWidget(self.help_button)
        root.addWidget(self.about_button)
        self.version_label = _ClickableLabel("Версия %s" % version)
        self.version_label.setObjectName("sidebarMuted")
        self.version_label.setToolTip("Что нового в этой версии")
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.clicked.connect(self.version_requested.emit)
        self.version_label.setContentsMargins(10, 4, 0, 0)
        root.addWidget(self.version_label)

        self._clock = QTimer(self)
        self._clock.setInterval(TODAY_REFRESH_MS)
        self._clock.timeout.connect(self.update_clock)
        self._clock.start()
        self.update_clock()
        self.apply_theme_colors()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Hide the block when it would squeeze the menu; hiding changes the layout, not our size.
        self.today_box.setVisible(self.height() >= TODAY_MIN_HEIGHT)

    # -- building blocks --------------------------------------------------

    def _counter_row(self, layout: QVBoxLayout, text: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setObjectName("sidebarMuted")
        value = QLabel("0")
        value.setObjectName("sidebarCount")
        row.addWidget(label, 1)
        row.addWidget(value)
        layout.addLayout(row)
        return value

    def _bottom_button(self, icon: str, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("sidebarBottom")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(32)
        btn.setIconSize(QSize(18, 18))
        btn.setProperty("icon_name", icon)
        return btn

    # -- state ----------------------------------------------------------------

    def set_org_name(self, name: str) -> None:
        text = name or "Организация"
        metrics = self.org_button.fontMetrics()
        self.org_button.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, SIDEBAR_WIDTH - 100))

    def set_current(self, index: int) -> None:
        """Highlight a section without emitting page_selected."""
        self._active_index = index
        btn = self._group.button(index)
        if btn is not None:
            btn.setChecked(True)
        self._refresh_icons()

    def _on_clicked(self, index: int) -> None:
        self._active_index = index
        self._refresh_icons()
        self.page_selected.emit(index)

    def update_clock(self) -> None:
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        self.date_label.setText(now.strftime("%d.%m.%Y"))

    def set_counts(self, employees: int, expired: int, not_trained: int, records: int,
                   expiring: int = 0) -> None:
        self.employees_value.setText(str(employees))
        self.expired_value.setText(str(expired))
        self.not_trained_value.setText(str(not_trained))
        self.expiring_value.setText(str(expiring))
        self.records_value.setText(str(records))

    def refresh_counts(self) -> None:
        """Recount from the database (cheap enough for the UI thread at the supported sizes)."""
        try:
            self.set_counts(*compute_status_counts())
        except Exception as e:
            logger.debug("Sidebar counters unavailable: %s", type(e).__name__)

    def apply_theme_colors(self) -> None:
        """Rebuild icons with the colours of the current theme (side_text / side_active_fg)."""
        from utils.tahoe_style import get_colors, get_current_theme
        c = get_colors(get_current_theme())
        self._icon_color, self._icon_color_active = QColor(c.side_text), QColor(c.side_active_fg)
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        for i, btn in enumerate(self._buttons):
            color = self._icon_color_active if i == self._active_index else self._icon_color
            btn.setIcon(nav_icon(btn.property("icon_name"), color, 18))
        for btn in (self.settings_button, self.help_button, self.about_button):
            btn.setIcon(nav_icon(btn.property("icon_name"), self._icon_color, 18))
        self.org_button.setIcon(nav_icon("org", self._icon_color, 16))
