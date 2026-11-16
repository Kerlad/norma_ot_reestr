"""XLSX export and trained-programs report of the summary tab (moved from employee_summary_tab)."""
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QMessageBox, QFileDialog, QDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from db import DatabaseManager
from utils.save_paths import suggest_path
from utils.error_utils import safe_message_box
from utils.dialog_base import BaseDialog
from utils.constants import VALID_PROGRAMS
from utils.training_rules import get_training_period_years
from utils.audit import log_audit

logger = logging.getLogger(__name__)


def _export_xlsx(tab, filtered=True):
    from tabs.employee_summary_tab import ROLE_FIO, ROLE_POSITION, BASE_COLUMNS, SUB_COLUMNS  # circular import
    reply = QMessageBox.warning(
        tab, "Экспорт данных",
        "Файл будет содержать персональные данные (ФИО, СНИЛС).\n"
        "Убедитесь, что файл сохраняется на зашифрованном диске (BitLocker).",
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )
    if reply != QMessageBox.StandardButton.Ok:
        return
    file_path, _ = QFileDialog.getSaveFileName(
        tab, "Сохранить XLSX", suggest_path("Сводка_сотрудников.xlsx"), "Excel Files (*.xlsx)")
    if not file_path:
        return
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment

        log_audit("EXPORT_XLSX", f"table_rows={tab._proxy.rowCount()}")
        wb = Workbook()
        ws = wb.active
        ws.title = "Сводка"

        programs = tab._selected_programs if filtered else VALID_PROGRAMS

        headers = ["ФИО", "СНИЛС", "Должность"]
        for p in programs:
            headers.append(f"программа #{p} Потребность")
            headers.append(f"программа #{p} Дата обучения")
            headers.append(f"программа #{p} Протокол")
            headers.append(f"программа #{p} Рег.№")
        ws.append(headers)

        hf = Font(bold=True, color="FFFFFF")
        hfill = PatternFill(start_color="4169E1", end_color="4169E1", fill_type="solid")
        for cell in ws[1]:
            cell.font = hf; cell.fill = hfill; cell.alignment = Alignment(horizontal="center")

        for r in range(tab._proxy.rowCount()):
            name_idx = tab._proxy.index(r, 0)
            row_data = [name_idx.data(ROLE_FIO) or '',
                        tab._proxy.index(r, 1).data(Qt.ItemDataRole.DisplayRole) or '',
                        name_idx.data(ROLE_POSITION) or '']
            for p in programs:
                pos = tab._selected_programs.index(p) if p in tab._selected_programs else -1
                col_start = BASE_COLUMNS + pos * SUB_COLUMNS
                for sub in range(SUB_COLUMNS):
                    if pos < 0:
                        row_data.append('')
                        continue
                    text = tab._proxy.index(r, col_start + sub).data(Qt.ItemDataRole.DisplayRole) or ''
                    row_data.append('' if text in ('—', 'нет') and sub else text)
            ws.append(row_data)

        for col in ws.columns:
            max_len = 0
            for cell in col:
                if cell.value: max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        wb.save(file_path)
        safe_message_box(tab, QMessageBox.Icon.Information, "Успех", f"Файл сохранён:\n{file_path}")
    except Exception:
        logger.exception("Export error")
        safe_message_box(tab, QMessageBox.Icon.Warning, "Ошибка", "Не удалось сохранить файл. Проверьте путь и права на запись")


def _generate_trained_report(tab):
    year = datetime.now().year

    categories = [
        ('А', [3]), ('Б', [4]),
        ('В', list(range(6, 30))),
        ('ОПП', [1]), ('СИЗ', [2]),
    ]

    db = DatabaseManager.get_instance()
    all_programs = db.fetchall(
        "SELECT program_id, exam_date FROM employee_programs WHERE need_training = 1"
    )

    report_data = {}
    for cat_name, prog_ids in categories:
        count_liable = 0
        count_trained = 0
        for row in all_programs:
            if row['program_id'] not in prog_ids: continue
            exam_date = row['exam_date']
            if not exam_date or not exam_date.strip():
                count_liable += 1
                continue
            try:
                exam_date_str = exam_date.split()[0]
                exam_year = datetime.strptime(exam_date_str, '%d.%m.%Y').year
                if exam_year == year:
                    count_trained += 1
                    count_liable += 1
                else:
                    period = get_training_period_years(row['program_id'], tab._b_period_3years)
                    if exam_year == year - period:
                        count_liable += 1
            except (ValueError, IndexError):
                count_liable += 1
                continue
        report_data[cat_name] = (count_liable, count_trained)

    def _pct(trained, liable):
        return round(trained / liable * 100, 1) if liable else 0.0

    dialog = BaseDialog(tab, f"Отчёт по обученным за {year} год", min_width=780, min_height=440)
    layout = dialog.body_layout()
    total_trained = sum(c[1] for c in report_data.values())
    log_audit("EXPORT_TRAINED_REPORT", f"employees={total_trained}")

    table = QTableWidget()
    table.setColumnCount(4)
    table.setHorizontalHeaderLabels(["Программа", "Подлежат обучению\nв текущем году", "Обучено\nв текущем году", "% выполнения"])
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setDefaultSectionSize(180)
    table.verticalHeader().setVisible(False)

    for cat_name, (count_liable, count_trained) in report_data.items():
        row = table.rowCount()
        table.insertRow(row)
        pct = _pct(count_trained, count_liable)
        for c, v in enumerate([cat_name, str(count_liable), str(count_trained), f"{pct:.1f}%"]):
            item = QTableWidgetItem(v)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, c, item)

    total_liable = sum(c[0] for c in report_data.values())
    total_trained_val = sum(c[1] for c in report_data.values())
    total_pct = _pct(total_trained_val, total_liable)
    row = table.rowCount()
    table.insertRow(row)
    total_font = QFont()
    total_font.setBold(True)
    for c, v in enumerate(["ИТОГО", str(total_liable), str(total_trained_val), f"{total_pct:.1f}%"]):
        item = QTableWidgetItem(v)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setFont(total_font)
        table.setItem(row, c, item)

    layout.addWidget(table)

    dialog.add_action_buttons("Экспорт в Excel",
                              lambda: tab._export_trained_report_xlsx(report_data, _pct, year, dialog),
                              secondary_text="Закрыть", on_secondary=dialog.close)
    dialog.exec()


def _export_trained_report_xlsx(tab, report_data: dict, pct_func, year: int, parent: QDialog):
    file_path, _ = QFileDialog.getSaveFileName(
        parent, "Сохранить XLSX", suggest_path(f"Отчет_по_обученным_{year}.xlsx"), "Excel Files (*.xlsx)"
    )
    if not file_path:
        return
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = "Отчет"
        headers = ["Программа", "Подлежат обучению\nв текущем году",
                    "Обучено\nв текущем году", "% выполнения"]
        ws.append(headers)
        hf = Font(bold=True, color="FFFFFF")
        hfill = PatternFill(start_color="4169E1", end_color="4169E1", fill_type="solid")
        for cell in ws[1]:
            cell.font = hf; cell.fill = hfill; cell.alignment = Alignment(horizontal="center")

        total_liable = 0
        total_trained = 0
        for cat_name, (count_liable, count_trained) in report_data.items():
            pct = pct_func(count_trained, count_liable)
            ws.append([cat_name, count_liable, count_trained, f"{pct:.1f}%"])
            total_liable += count_liable
            total_trained += count_trained

        total_pct = pct_func(total_trained, total_liable)
        ws.append(["ИТОГО", total_liable, total_trained, f"{total_pct:.1f}%"])

        for col in ws.columns:
            mx = max((len(str(c.value or "")) for c in col), default=0)
            ws.column_dimensions[col[0].column_letter].width = min(mx + 3, 50)

        wb.save(file_path)
        from utils.error_utils import safe_message_box
        safe_message_box(parent, QMessageBox.Icon.Information, "Успех", f"Файл сохранён:\n{file_path}")
    except Exception:
        logger.exception("Export trained report error")
        from utils.error_utils import show_error_dialog
        show_error_dialog(parent, "Ошибка экспорта", "Не удалось сохранить файл. Проверьте путь и права на запись", critical=False)
