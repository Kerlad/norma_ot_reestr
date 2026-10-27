"""Right-hand panel of the «Передача данных» tab: history of sent sets."""
import json
import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMenu,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from journal.send_history import STATUS_TEXT, format_sent_at
from utils.icons import status_icon
from utils.ui_helpers import EmptyStateOverlay, HeaderStatePersistence
from utils.table_sort import SORT_ROLE

logger = logging.getLogger(__name__)

UI_PREFS_FILE = "ui_prefs.json"
PREF_HISTORY_VISIBLE = "transfer_history_visible"
MAX_REFRESH_SELECTED = 20

COL_STATUS, COL_DATE, COL_SETID, COL_COUNT, COL_FILE = range(5)
SETID_WIDTH_CHARS = 9


def load_ui_pref(key: str, default, data_dir: str = None):
    if data_dir is None:
        from utils.app_paths import get_app_data_dir
        data_dir = get_app_data_dir()
    try:
        with open(os.path.join(data_dir, UI_PREFS_FILE), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(key, default) if isinstance(data, dict) else default
    except (OSError, ValueError):
        return default


def save_ui_pref(key: str, value, data_dir: str = None) -> None:
    if data_dir is None:
        from utils.app_paths import get_app_data_dir
        data_dir = get_app_data_dir()
    path = os.path.join(data_dir, UI_PREFS_FILE)
    try:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        data[key] = value
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        logger.warning("ui prefs save failed: %s", type(e).__name__)


class SendHistoryPanel(QFrame):
    """Table of sent sets (status icon, date, SetId, record count, file name)."""

    refresh_requested = Signal(list)  # list of SetId

    def __init__(self, parent=None, layout_dir: str = None):
        super().__init__(parent)
        self.setObjectName("sendHistoryPanel")
        self.setMinimumWidth(360)
        self.setMaximumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 24, 20)
        layout.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("История отправок")
        title.setObjectName("cardTitle")
        head.addWidget(title)
        head.addStretch()
        self.refresh_btn = QPushButton("Обновить данные")
        self.refresh_btn.setProperty("role", "dark")
        self.refresh_btn.setToolTip("Запросить статус последних 5 наборов в реестре")
        head.addWidget(self.refresh_btn)
        layout.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Дата и время", "SetId", "Записей", "Файл"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(COL_STATUS, 36)
        self.table.setColumnWidth(COL_DATE, 120)
        # SetId: 9 characters wide; layouts saved for the old 4 columns are not restored
        fm = self.table.fontMetrics()
        self.table.setColumnWidth(COL_SETID, fm.horizontalAdvance("0" * SETID_WIDTH_CHARS) + 16)
        self.table.setColumnWidth(COL_COUNT, 64)
        self._persistence = HeaderStatePersistence(header, "transfer_send_history", layout_dir)
        from utils.table_sort import install_widget_sort
        self._sorter = install_widget_sort(self.table)
        layout.addWidget(self.table, 1)
        self._empty = EmptyStateOverlay(self.table, "Отправленных наборов пока нет")

        self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit([]))

    # ---- data ----

    def reload(self) -> None:
        from db.send_history_repo import SendHistoryRepo
        rows = SendHistoryRepo.list_all()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            status = r.get("status", "unknown")
            text = STATUS_TEXT.get(status, STATUS_TEXT["unknown"])
            st = QTableWidgetItem(status_icon(status), "")
            st.setToolTip(text)
            st.setData(Qt.ItemDataRole.AccessibleTextRole, text)
            st.setData(Qt.ItemDataRole.UserRole, status)
            st.setData(SORT_ROLE, text)
            items = [
                st,
                QTableWidgetItem(format_sent_at(r.get("sent_at", ""))),
                QTableWidgetItem(r.get("set_id", "")),
                QTableWidgetItem(str(r.get("record_count", 0))),
                QTableWidgetItem(r.get("file_name") or r.get("xml_file") or ""),
            ]
            items[COL_COUNT].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for c, it in enumerate(items):
                if c == COL_FILE and it.text():
                    it.setToolTip(it.text())
                elif c != COL_STATUS:
                    it.setToolTip(text)
                self.table.setItem(i, c, it)
        self._empty.setVisible(not rows)
        self._sorter.reload_done()

    def selected_set_ids(self) -> list:
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        ids = []
        for r in rows:
            it = self.table.item(r, COL_SETID)
            if it is not None and it.text():
                ids.append(it.text())
        return ids

    def set_busy(self, busy: bool, done: int = 0, total: int = 0) -> None:
        self.refresh_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, max(total, 1))
            self.progress.setValue(done)

    # ---- context menu ----

    def _show_menu(self, pos) -> None:
        ids = self.selected_set_ids()
        menu = QMenu(self.table)
        act_refresh = menu.addAction("Обновить данные")
        act_refresh.setEnabled(bool(ids))
        act_copy = menu.addAction("Копировать SetId")
        act_copy.setEnabled(bool(ids))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is act_refresh and ids:
            self.refresh_requested.emit(ids)
        elif chosen is act_copy and ids:
            QGuiApplication.clipboard().setText("\n".join(ids))
