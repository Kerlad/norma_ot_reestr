"""Registry response on screen: a read-only table and an optional XLSX export."""
import logging

from PySide6.QtWidgets import QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView
from PySide6.QtCore import Qt

from api.mintrud_api import export_records_to_xlsx
from utils.dialog_base import BaseDialog
from utils.error_utils import safe_message_box
from utils.record_rules import normalize_date
from utils.save_paths import suggest_path
from utils.table_sort import install_widget_sort

logger = logging.getLogger(__name__)

HEADERS = ["ФИО", "СНИЛС", "Программа", "Дата", "Рег. номер"]


def _first(rec: dict, *keys) -> str:
    """The first non-empty value among the keys (the two response formats name SNILS differently)."""
    for key in keys:
        value = rec.get(key)
        if value:
            return str(value).strip()
    return ""


def record_row(rec: dict) -> list:
    """Cell texts of one registry record, in HEADERS order."""
    name = " ".join(p for p in (_first(rec, "LastName"), _first(rec, "FirstName"),
                                _first(rec, "MiddleName")) if p)
    date_raw = _first(rec, "Date")
    date = normalize_date(date_raw) or date_raw if date_raw else ""
    return [name, _first(rec, "Snils", "snils"), _first(rec, "learnProgramId"),
            date, _first(rec, "baseNo")]


class RegistryResultDialog(BaseDialog):
    """Shows the records returned by the registry; saving to XLSX does not close the window."""

    def __init__(self, parent, title: str, records: list, file_name: str = "Ответ_реестра.xlsx"):
        super().__init__(parent, title="Ответ реестра", min_width=760, min_height=420,
                         subtitle="Записей: %d" % len(records))
        self._records = list(records)
        self._file_name = file_name
        self._source_title = title

        self.table = QTableWidget(len(self._records), len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        for r, rec in enumerate(self._records):
            for c, text in enumerate(record_row(rec)):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.resizeColumnsToContents()
        self._sorter = install_widget_sort(self.table)
        self._sorter.reload_done()
        self.body_layout().addWidget(self.table, 1)

        self.save_btn, self.close_btn = self.add_action_buttons(
            "Сохранить XLSX…", self._save_xlsx, secondary_text="Закрыть",
            on_secondary=self.close, primary_role="primary")

    def _save_xlsx(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить XLSX", suggest_path(self._file_name), "Excel Files (*.xlsx)")
        if not file_path:
            return
        ok, msg = export_records_to_xlsx(self._records, file_path)
        if ok:
            safe_message_box(self, QMessageBox.Icon.Information, "Успех",
                             "Сохранено записей: %d\n%s" % (len(self._records), msg))
        else:
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", msg)
