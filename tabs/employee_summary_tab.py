import os
import json
import time
import logging
from datetime import datetime
from typing import List
from dateutil.relativedelta import relativedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QCheckBox,
    QListWidget, QListWidgetItem, QMenu, QDialog
)
from utils.error_utils import safe_message_box
from utils.dialog_base import BaseDialog
from utils.field_validators import ValidatedLineEdit
from utils.constants import VALID_PROGRAMS, VALID_PROGRAMS_SET, DEFAULT_PROGRAMS, PROGRAM_TITLES
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRect
from PySide6.QtGui import QColor, QFont, QPalette, QBrush, QPainter

from db import (
    DatabaseManager, EmployeesRepo, EmployeeProgramsRepo
)
from api.mintrud_api import load_api_key, get_by_snils
from utils.proxy_manager import load_proxy_settings
from utils.app_paths import get_app_data_dir
from utils.training_rules import get_dynamic_status, compute_expiry_date, get_training_period_years
from utils.audit import log_audit
from utils.logger import filter_sensitive_text

from utils.toast import Toast
from utils.table_sort import SORT_ROLE

logger = logging.getLogger(__name__)


def _normalize_api_date(date_str: str) -> str:
    if not date_str:
        return ""
    date_str = date_str.strip()
    if '.' in date_str:
        parts = date_str.split()[0]
        if len(parts) == 10 and parts[2] == '.' and parts[5] == '.':
            return parts
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    if '-' in date_str:
        parts = date_str.split()[0]
        try:
            dt = datetime.strptime(parts, "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except (ValueError, IndexError):
            pass
    return date_str


def _dmy_gt(a: str, b: str) -> bool:
    """Compare two DD.MM.YYYY dates, returns True if a > b chronologically."""
    try:
        return datetime.strptime(a.strip(), '%d.%m.%Y') > datetime.strptime(b.strip(), '%d.%m.%Y')
    except (ValueError, AttributeError):
        return False


BASE_COLUMNS = 3
SUB_COLUMNS = 4


class ApiQueryThread(QThread):
    finished = Signal(int, int)
    error_signal = Signal(str)
    progress = Signal(int, int)

    def __init__(self, employees, api_key, proxy_settings=None):
        super().__init__()
        self.employees = employees
        self.api_key = api_key
        self.proxy_settings = proxy_settings or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.employees)
        updated = 0
        errors = 0
        for idx, emp in enumerate(self.employees):
            if self._cancelled:
                self.finished.emit(updated, errors)
                DatabaseManager.close_thread_connection()
                return
            try:
                snils_clean = emp['snils'].replace('-', '').replace(' ', '')
                result = get_by_snils(self.api_key, snils_clean, proxy_settings=self.proxy_settings)
                if result.get("success"):
                    records = result.get("records", [])
                    self._process_api_records(emp['id'], records)
                    updated += 1
                    now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
                    EmployeesRepo.update_sync(emp['id'], now)
                else:
                    errors += 1
                    err_msg = result.get('error', 'Неизвестная ошибка API')
                    logger.warning("API error: %s", filter_sensitive_text(str(err_msg)))
                    self.error_signal.emit(f"{emp.get('last_name','')} {emp.get('first_name','')}: {err_msg}")
            except Exception as e:
                errors += 1
                logger.exception("Registry API exception")
                self.error_signal.emit(f"{emp.get('last_name','')} {emp.get('first_name','')}: {e}")
            self.progress.emit(idx + 1, total)
            if idx < total - 1 and not self._cancelled:
                time.sleep(0.5)
        DatabaseManager.close_thread_connection()
        self.finished.emit(updated, errors)

    def _process_api_records(self, employee_id, records):
        seen_programs = {}
        for rec in records:
            prog_id = rec.get('learnProgramId', '')
            if not prog_id:
                continue
            exam_date = _normalize_api_date(rec.get('Date', ''))
            protocol = rec.get('ProtocolNumber', '')
            base_no = rec.get('baseNo', '')
            is_passed = rec.get('isPassed', '')
            result = 1 if is_passed and is_passed.lower() in ('true', '1', 'да', 'удовлетворительно') else 0
            if prog_id not in seen_programs or (exam_date and _dmy_gt(exam_date, seen_programs[prog_id].get('exam_date', ''))):
                seen_programs[prog_id] = { 'exam_date': exam_date,
                    'protocol': protocol, 'base_no': base_no, 'result': result,}
        for prog_id, data in seen_programs.items():
            try:
                EmployeeProgramsRepo.update_from_api(
                    employee_id, int(prog_id),
                    data['exam_date'], data['protocol'], data['base_no'], data['result']
                )
            except (ValueError, TypeError):
                pass
        if records:
            first_rec = records[0]
            emp = EmployeesRepo.get_by_id(employee_id)
            if emp:
                updates = {}
                if not emp.get('last_name'): updates['last_name'] = first_rec.get('LastName', '')
                if not emp.get('first_name'): updates['first_name'] = first_rec.get('FirstName', '')
                if not emp.get('middle_name'): updates['middle_name'] = first_rec.get('MiddleName', '')
                if not emp.get('position'): updates['position'] = first_rec.get('Position', '')
                if updates:
                    updates['snils'] = emp['snils']
                    EmployeesRepo.upsert(updates)


class PlanDialog(BaseDialog):
    def __init__(self, plan_data: list, plan_title: str, parent=None):
        super().__init__(parent, title=plan_title, min_width=1000, min_height=600)
        from utils.constants import PROGRAM_TITLES

        bl = self.body_layout()

        stats_layout = QHBoxLayout()
        total = len(plan_data)
        high = sum(1 for p in plan_data if p['priority'] == 'Высокий')
        medium = sum(1 for p in plan_data if p['priority'] == 'Средний')
        low = sum(1 for p in plan_data if p['priority'] == 'Низкий')

        for label, value, color in [
            ("Всего в плане", str(total), "#4169E1"),
            ("Высокий", str(high), "#dc3545"),
            ("Средний", str(medium), "#ffc107"),
            ("Низкий", str(low), "#28a745"),
        ]:
            card = QFrame()
            card.setObjectName("planStatCard")
            card.setStyleSheet(f"""
                QFrame {{ border: 2px solid {color}; border-radius: 8px;
                    padding: 10px;}}
            """)
            card_layout = QVBoxLayout(card)
            val_label = QLabel(value)
            val_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color}; background-color: transparent;")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label = QLabel(label)
            desc_label.setStyleSheet("font-size: 12px; background-color: transparent;")
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(val_label)
            card_layout.addWidget(desc_label)
            stats_layout.addWidget(card)
        bl.addLayout(stats_layout)

        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels([
            "№", "ФИО", "СНИЛС", "Должность", "Программа", "Название",
            "Последняя\nдата\nобучения", "Дата\nокончания\nдействия",
            "Основание", "Приоритет"
        ])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for col, width in enumerate((40, 220, 120, 160, 80, 260, 110, 110, 200, 90)):
            table.setColumnWidth(col, width)
        table.verticalHeader().setVisible(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setWordWrap(True)

        for i, p in enumerate(plan_data, 1):
            row = table.rowCount()
            table.insertRow(row)
            prog_name = PROGRAM_TITLES.get(p['program']) if p['program'] else ''
            items = [
                str(i),
                f"{p['last_name']} {p['first_name']} {p['middle_name']}".strip(),
                p['snils'], p['position'], p['program'], prog_name,
                p['last_exam_date'], p['expiry_date'],
                p['reason'], p['priority'],
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 9:
                    color_map = {'Высокий': '#dc3545', 'Средний': '#ffc107', 'Низкий': '#28a745'}
                    item.setForeground(QColor(color_map.get(text, '#E0E0E0')))
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setData(SORT_ROLE, {'Высокий': 0, 'Средний': 1, 'Низкий': 2}.get(text, 3))
                elif col == 4:
                    item.setData(SORT_ROLE, p['program'])
                table.setItem(row, col, item)

        from utils.ui_helpers import HeaderStatePersistence
        self._header_persistence = HeaderStatePersistence(header, "plan_dialog")
        self._resize_rows_timer = QTimer(self)
        self._resize_rows_timer.setSingleShot(True)
        self._resize_rows_timer.setInterval(100)
        self._resize_rows_timer.timeout.connect(table.resizeRowsToContents)
        header.sectionResized.connect(lambda *_: self._resize_rows_timer.start())
        table.resizeRowsToContents()
        self.table = table
        from utils.table_sort import install_widget_sort
        install_widget_sort(table, skip_columns=(0,))
        table._tristate_sort.on_sorted = table.resizeRowsToContents

        bl.addWidget(table)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Экспорт XLSX")
        export_btn.setObjectName("planExportBtn")
        export_btn.clicked.connect(lambda: self._export_plan(plan_data, plan_title))
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("planCloseBtn")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        bl.addLayout(btn_layout)

    def _export_plan(self, plan_data: list, plan_title: str):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить XLSX", f"{plan_title}.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            from utils.constants import PROGRAM_TITLES
            wb = Workbook()
            ws = wb.active
            ws.title = "План"
            headers = ["№", "ФИО", "СНИЛС", "Должность", "Программа", "Название",
                "Последняя\nдата\nобучения", "Дата\nокончания\nдействия", "Основание", "Приоритет"]
            ws.append(headers)
            hf = Font(bold=True, color="FFFFFF")
            hfill = PatternFill(start_color="4169E1", end_color="4169E1", fill_type="solid")
            for cell in ws[1]:
                cell.font = hf; cell.fill = hfill; cell.alignment = Alignment(horizontal="center")
            for i, p in enumerate(plan_data, 1):
                prog_name = PROGRAM_TITLES.get(p['program']) if p['program'] else ''
                ws.append([i, f"{p['last_name']} {p['first_name']} {p['middle_name']}".strip(),
                    p['snils'], p['position'], p['program'], prog_name,
                    p['last_exam_date'], p['expiry_date'], p['reason'], p['priority']])
            ws2 = wb.create_sheet("Сводка")
            ws2.append(["Программа", "Название", "Кол-во"])
            from collections import Counter
            prog_counts = Counter(p['program'] for p in plan_data)
            for prog, cnt in sorted(prog_counts.items()):
                prog_name = PROGRAM_TITLES.get(prog) if prog else ''
                ws2.append([prog, prog_name, cnt])
            for cell in ws2[1]:
                cell.font = hf; cell.fill = hfill; cell.alignment = Alignment(horizontal="center")
            wb.save(file_path)
            safe_message_box(self, QMessageBox.Icon.Information, "Успех", f"Файл сохранён:\n{file_path}")
        except Exception as e:
            logger.exception("Export error")
            from utils.error_utils import show_error_dialog
            show_error_dialog(self, "Ошибка экспорта", str(e), critical=False)


# ──────── EmployeeAddDialog ────────

class EmployeeAddDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Добавление сотрудника", min_width=520, min_height=400)

        bl = self.body_layout()
        form = QFormLayout()
        form.setSpacing(8)

        from utils.field_validators import validate_snils, validate_name

        self.last_name = ValidatedLineEdit(validator=validate_name)
        self.last_name.setPlaceholderText("Иванов")
        form.addRow("Фамилия:", self.last_name)

        self.first_name = ValidatedLineEdit(validator=validate_name)
        self.first_name.setPlaceholderText("Иван")
        form.addRow("Имя:", self.first_name)

        self.middle_name = ValidatedLineEdit(validator=validate_name)
        self.middle_name.setPlaceholderText("Иванович")
        form.addRow("Отчество:", self.middle_name)

        self.snils = ValidatedLineEdit(validator=validate_snils)
        self.snils.setPlaceholderText("123-456-789 00")
        self.register_field(self.snils)
        form.addRow("СНИЛС:", self.snils)

        self.position = ValidatedLineEdit()
        self.position.setPlaceholderText("Слесарь")
        form.addRow("Должность:", self.position)

        prog_row = QHBoxLayout()
        self.programs = QLineEdit()
        self.programs.setPlaceholderText("1, 2, 3")
        prog_row.addWidget(self.programs, 1)
        help_btn = QPushButton("Справка")
        help_btn.setObjectName("programHelpBtn")
        help_btn.setToolTip("Открыть справочник номеров программ обучения")
        help_btn.clicked.connect(self._show_programs_help)
        prog_row.addWidget(help_btn)
        form.addRow("Программы:", prog_row)

        bl.addLayout(form)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Добавить"); save_btn.setObjectName("dialogPrimaryBtn")
        save_btn.clicked.connect(self._validate_and_accept)
        cancel_btn = QPushButton("Отмена"); cancel_btn.setObjectName("dialogDangerBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn); btn_row.addStretch(); btn_row.addWidget(cancel_btn)
        bl.addLayout(btn_row)

    def _validate_and_accept(self):
        from utils.field_validators import validate_program_id
        if not self.validate_fields():
            return
        prog_text = self.programs.text().strip()
        if prog_text:
            pids = [p.strip() for p in prog_text.split(",") if p.strip()]
            for pid in pids:
                err = validate_program_id(pid)
                if err:
                    from utils.ui_helpers import mark_invalid
                    mark_invalid(self.programs)
                    self.programs.setToolTip(f"Некорректная программа: {pid}")
                    self.programs.setFocus()
                    return
        from utils.ui_helpers import mark_invalid
        mark_invalid(self.programs, False)
        self.accept()

    def _show_programs_help(self):
        from PySide6.QtGui import QPalette
        d = QDialog(self)
        d.setWindowTitle("Программы обучения"); d.setMinimumSize(600, 500)
        dl = QVBoxLayout(d)
        lw = QListWidget(); lw.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        current = [p.strip() for p in self.programs.text().split(",") if p.strip()]
        blue = {"1", "2", "3", "4", "18", "23"}

        pal = d.palette()
        primary = pal.color(QPalette.ColorRole.Highlight)
        current_bg = QColor(primary.red(), primary.green(), primary.blue(), 35)

        for pid in VALID_PROGRAMS:
            title = PROGRAM_TITLES.get(pid, "")
            item = QListWidgetItem(f"{pid}: {title}")
            item.setData(Qt.ItemDataRole.UserRole, pid)
            if pid in current:
                item.setBackground(current_bg)
            if pid in blue:
                item.setForeground(primary)
            lw.addItem(item)
        def add_sel():
            sel = lw.selectedItems()
            if not sel: return
            new_set = set(current)
            for it in sel: new_set.add(it.data(Qt.ItemDataRole.UserRole))
            self.programs.setText(", ".join(sorted(new_set, key=lambda x: int(x) if x.isdigit() else 0)))
            d.accept()
        lw.itemDoubleClicked.connect(lambda item: (
            current.append(item.data(Qt.ItemDataRole.UserRole))
            or self.programs.setText(", ".join(current))))
        dl.addWidget(lw)
        br = QHBoxLayout()
        ab = QPushButton("Добавить выбранные"); ab.setObjectName("dialogPrimaryBtn"); ab.clicked.connect(add_sel)
        br.addWidget(ab); br.addStretch()
        cb = QPushButton("Отмена"); cb.setObjectName("dialogDangerBtn"); cb.clicked.connect(d.reject)
        br.addWidget(cb); dl.addLayout(br)
        d.exec()


# ──────── EmployeeEditDialog ────────

class EmployeeEditDialog(BaseDialog):
    def __init__(self, emp: dict, progs: list, parent=None):
        super().__init__(parent, title="Редактирование сотрудника", min_width=520, min_height=400)
        self.emp = emp
        self.progs = progs

        bl = self.body_layout()
        form = QFormLayout(); form.setSpacing(8)

        from utils.field_validators import validate_required, validate_snils, validate_name

        self.last_name = ValidatedLineEdit(emp['last_name'],
            validator=lambda t: validate_required(t, "Фамилия") or validate_name(t))
        self.register_field(self.last_name)
        form.addRow("Фамилия:", self.last_name)

        self.first_name = ValidatedLineEdit(emp['first_name'],
            validator=lambda t: validate_required(t, "Имя") or validate_name(t))
        self.register_field(self.first_name)
        form.addRow("Имя:", self.first_name)

        self.middle_name = ValidatedLineEdit(emp['middle_name'], validator=validate_name)
        form.addRow("Отчество:", self.middle_name)

        self.snils = ValidatedLineEdit(emp['snils'], validator=validate_snils)
        form.addRow("СНИЛС:", self.snils)

        self.position = ValidatedLineEdit(emp['position'],
            validator=lambda t: validate_required(t, "Должность"))
        self.register_field(self.position)
        form.addRow("Должность:", self.position)

        prog_ids = [str(p['program_id']) for p in progs if p.get('need_training') == 1]
        self.programs = QLineEdit(",".join(prog_ids))
        form.addRow("Программы:", self.programs)

        bl.addLayout(form)
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Сохранить"); save_btn.setObjectName("dialogPrimaryBtn")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена"); cancel_btn.setObjectName("dialogDangerBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn); btn_row.addStretch(); btn_row.addWidget(cancel_btn)
        bl.addLayout(btn_row)


# ──────── QueryProgressDialog ────────

class QueryProgressDialog(QDialog):
    cancelled = Signal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновление данных работников")
        self.setMinimumSize(480, 260)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Обновление данных работников")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self._info_label = QLabel(f"Происходит запрос данных по {total} работникам.")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        est = total * 0.5
        self._est_label = QLabel(
            f"Примерное время ожидания: {est:.0f} секунд"
            if est >= 1.0 else "Примерное время ожидания: менее 1 секунды"
        )
        self._est_label.setStyleSheet("color: #666;")
        layout.addWidget(self._est_label)

        self._progress_label = QLabel("Получено данных по 0 из 0 работников.")
        self._progress_label.setWordWrap(True)
        layout.addWidget(self._progress_label)

        self._timer_label = QLabel("Прошло 0 секунд.")
        self._timer_label.setStyleSheet("color: #666;")
        layout.addWidget(self._timer_label)

        # UX-16: support/licence block while the user waits; no timer, closes any time
        self._support_box = self._build_support_box()
        layout.addWidget(self._support_box)

        layout.addStretch()

        cancel_btn = QPushButton("Отмена операции")
        cancel_btn.setObjectName("dialogDangerBtn")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._total = total
        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _build_support_box(self):
        from utils.donation_dialog import SupportPanel
        box = QFrame()
        box.setObjectName("supportBox")
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)
        panel = SupportPanel(box, compact=True)
        box_layout.addWidget(panel)
        hide_row = QHBoxLayout()
        hide_row.addStretch()
        hide_btn = QPushButton("Скрыть")
        hide_btn.clicked.connect(box.hide)
        hide_row.addWidget(hide_btn)
        box_layout.addLayout(hide_row)
        panel.activated.connect(lambda _lic: panel.refresh())
        return box

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(1000)

    def _tick(self):
        self._elapsed += 1
        self._timer_label.setText(f"Прошло {self._elapsed} секунд.")

    def update_progress(self, current: int, total: int):
        self._progress_label.setText(f"Получено данных по {current} из {total} работников.")

    def _on_cancel(self):
        self._timer.stop()
        self.cancelled.emit()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


ROLE_EMP_ID = Qt.ItemDataRole.UserRole
ROLE_FIO = Qt.ItemDataRole.UserRole + 10
ROLE_POSITION = Qt.ItemDataRole.UserRole + 11
FG_ROLE = Qt.ItemDataRole.UserRole + 100     # text colour token name ("err_text", "warn_text", ...)
BG_ROLE = Qt.ItemDataRole.UserRole + 101     # background token name ("surface_subtle")
STATUS_KIND = {'trained': 'ok', 'expired': 'warn', 'not_trained': 'not_trained'}
STATUS_TEXT = {'trained': 'Обучен', 'expired': 'Просрочено', 'not_trained': 'Не обучен'}
STATUS_RANK = {'not_trained': 0, 'expired': 1, 'trained': 2}


class SummaryCellDelegate(QStyledItemDelegate):
    """Paints cells itself: the global stylesheet overrides item colours, so token colours are
    applied here. First column is two-line (name + position), status column is an icon only."""

    def paint(self, painter, option, index):
        from utils.tahoe_style import get_colors, get_current_theme
        c = get_colors(get_current_theme())
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect
        bg_token = index.data(BG_ROLE)
        if selected:
            bg = QColor(c.selection_row)
        elif bg_token:
            bg = QColor(getattr(c, bg_token))
        else:
            bg = QColor(c.surface)
        painter.save()
        painter.fillRect(rect, bg)
        painter.setPen(QColor(c.divider_row))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if icon is not None and not text:
            size = 18
            icon.paint(painter, QRect(rect.center().x() - size // 2, rect.center().y() - size // 2, size, size))
            painter.restore()
            return
        fg_token = index.data(FG_ROLE)
        main_color = QColor(getattr(c, fg_token)) if fg_token else QColor(c.text)
        font = painter.font()
        font.setPixelSize(13)
        font.setBold(False)
        painter.setFont(font)
        inner = rect.adjusted(10, 0, -10, 0)
        left = index.column() == 0
        align = int((Qt.AlignmentFlag.AlignLeft if left else Qt.AlignmentFlag.AlignHCenter)
                    | Qt.AlignmentFlag.AlignVCenter)
        lines = str(text).split("\n")
        metrics = painter.fontMetrics()
        if len(lines) == 1:
            painter.setPen(main_color)
            painter.drawText(inner, align, metrics.elidedText(lines[0], Qt.TextElideMode.ElideRight, inner.width()))
        else:
            half = rect.height() // 2
            painter.setPen(main_color)
            painter.drawText(QRect(inner.x(), rect.y() + 2, inner.width(), half), align,
                             metrics.elidedText(lines[0], Qt.TextElideMode.ElideRight, inner.width()))
            small = painter.font()
            small.setPixelSize(12)
            painter.setFont(small)
            painter.setPen(QColor(c.text_muted))
            painter.drawText(QRect(inner.x(), rect.y() + half - 2, inner.width(), half), align,
                             painter.fontMetrics().elidedText(lines[1], Qt.TextElideMode.ElideRight, inner.width()))
        painter.restore()


class ShareBar(QWidget):
    """Thin bar showing the shares of trained / expired / not trained employees."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = (0, 0, 0)
        self.setFixedHeight(10)
        self.setMinimumWidth(120)

    def set_values(self, trained: int, expired: int, not_trained: int):
        self._values = (trained, expired, not_trained)
        self.update()

    def paintEvent(self, event):
        from utils.icons import STATUS_GREEN, STATUS_YELLOW, STATUS_RED
        from utils.tahoe_style import get_colors, get_current_theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(get_colors(get_current_theme()).segment_bg))
        painter.drawRoundedRect(rect, 5, 5)
        total = sum(self._values)
        if total:
            painter.setClipPath(self._clip(rect))
            x = 0.0
            for value, color in zip(self._values, (STATUS_GREEN, STATUS_YELLOW, STATUS_RED)):
                w = rect.width() * value / total
                if w > 0:
                    painter.setBrush(QColor(color))
                    painter.drawRect(int(x), 0, int(w + 1), rect.height())
                x += w

    @staticmethod
    def _clip(rect):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(rect, 5, 5)
        return path


# ──────── EmployeeSummaryTab ────────

class EmployeeSummaryTab(QWidget):
    _programs_cache = None

    @classmethod
    def _load_saved_settings(cls, data_dir):
        path = os.path.join(data_dir, "summary_programs.json")
        result = {'programs': None}
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                result['programs'] = [p for p in data.get('programs', []) if p in VALID_PROGRAMS]
                # 'b_period_3years' from older versions is ignored: programs В (№6-29)
                # always use the 3-year period (UX-04).
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to load summary_programs.json: %s", e)
        return result

    @classmethod
    def _save_settings(cls, data_dir, programs):
        path = os.path.join(data_dir, "summary_programs.json")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'programs': programs}, f)
        except OSError as e:
            logger.debug("Failed to save summary_programs.json: %s", e)

    def __init__(self, parent=None):
        super().__init__(parent)
        from utils.app_paths import get_app_data_dir
        from utils.org_profiles import get_org_data_dir
        self.data_dir = get_org_data_dir()
        saved = self._load_saved_settings(self.data_dir)
        self._selected_programs = saved['programs'] if saved['programs'] else DEFAULT_PROGRAMS.copy()
        self._b_period_3years = True
        self._current_filter_status = "all"
        self._current_filter_program = "all"
        self._current_filter_position = ""
        self._problem_only = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 12)
        main_layout.setSpacing(12)

        main_layout.addWidget(self._build_stats())
        main_layout.addWidget(self._build_filters())
        main_layout.addWidget(self._build_actions())
        main_layout.addWidget(self._build_table_widget(), 1)

        self.refresh_table()

    # ── Stats Cards ────────────────────────────────────────

    def _build_stats(self):
        from utils.ui_helpers import make_card
        card, lay = make_card()
        lay.setContentsMargins(18, 12, 18, 12)
        row = QHBoxLayout()
        row.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(0)
        self.stat_total = QLabel("0")
        self.stat_total.setObjectName("statBigNumber")
        caption = QLabel("подлежат обучению")
        caption.setObjectName("hintLabel")
        self.stat_total_info = QLabel("всего 0 сотрудников")
        self.stat_total_info.setObjectName("hintLabel")
        left.addWidget(self.stat_total)
        left.addWidget(caption)
        row.addLayout(left)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        self.share_bar = ShareBar()
        mid.addWidget(self.share_bar)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self._chips = {}
        for key, kind, text in (("Обучен", "ok", "Обучены"), ("Не обучен", "err", "Не обучены"),
                                ("Просрочено", "warn", "Просрочено")):
            chip = QPushButton()
            chip.setObjectName("chip")
            chip.setProperty("kind", kind)
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip("Показать только: %s (повторный щелчок снимает фильтр)" % text.lower())
            chip.clicked.connect(lambda checked=False, k=key: self._on_chip_clicked(k))
            self._chips[key] = (chip, text)
            chips.addWidget(chip)
        chips.addStretch()
        mid.addLayout(chips)
        row.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)
        sync_caption = QLabel("Данные из реестра")
        sync_caption.setObjectName("hintLabel")
        sync_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.stat_sync = QLabel("нет")
        self.stat_sync.setAlignment(Qt.AlignmentFlag.AlignRight)
        right.addWidget(sync_caption)
        right.addWidget(self.stat_sync)
        row.addLayout(right)
        lay.addLayout(row)
        self._set_chip_counts(0, 0, 0)
        return card

    def _set_chip_counts(self, trained: int, not_trained: int, expired: int):
        counts = {"Обучен": trained, "Не обучен": not_trained, "Просрочено": expired}
        for key, (chip, text) in self._chips.items():
            chip.setText("%s · %d" % (text, counts[key]))
        self.share_bar.set_values(trained, expired, not_trained)

    def _on_chip_clicked(self, key: str):
        current = self.filter_status.currentText()
        self.filter_status.setCurrentText("Все" if current == key else key)

    def _sync_chips(self):
        current = self.filter_status.currentText()
        for key, (chip, _) in self._chips.items():
            chip.setChecked(key == current)

    # ── Filters / actions ──────────────────────────────────

    def _build_filters(self):
        from utils.icons import themed_icon
        w = QWidget(); w.setObjectName("filterContainer")
        layout = QHBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(10)

        self.filter_position = QLineEdit(); self.filter_position.setObjectName("filterInput")
        self.filter_position.setPlaceholderText("Поиск по должности")
        self.filter_position.setClearButtonEnabled(True)
        self.filter_position.setFixedHeight(34)
        self.filter_position.setMaximumWidth(260)
        self.filter_position.addAction(themed_icon("search", "text_muted", 16), QLineEdit.ActionPosition.LeadingPosition)
        self.filter_position.textChanged.connect(self._apply_filters)
        layout.addWidget(self.filter_position)

        self.filter_program = QComboBox(); self.filter_program.setObjectName("filterCombo")
        self.filter_program.addItem("Все программы", "all")
        for p in VALID_PROGRAMS:
            self.filter_program.addItem(f"Программа {p}", p)
        self.filter_program.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.filter_program)

        self.filter_status = QComboBox(); self.filter_status.setObjectName("filterCombo")
        self.filter_status.addItems(["Все", "Обучен", "Не обучен", "Просрочено"])
        self.filter_status.setToolTip("Статус сотрудника")
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.filter_status)

        self.problem_cb = QCheckBox("Только проблемные"); self.problem_cb.setObjectName("filterCheck")
        self.problem_cb.setToolTip("Показывать только сотрудников с просроченным или отсутствующим обучением")
        self.problem_cb.toggled.connect(self._apply_filters)
        layout.addWidget(self.problem_cb)

        layout.addStretch()

        prog_btn = QPushButton("Программы")
        prog_btn.setProperty("role", "secondary")
        prog_btn.setToolTip("Выбрать программы, показываемые в таблице")
        prog_btn.clicked.connect(self._show_program_selector)
        layout.addWidget(prog_btn)
        return w

    REGISTRY_TEXT = "Реестр"

    def _build_actions(self):
        from utils.icons import themed_icon
        from utils.ui_helpers import set_role
        w = QWidget(); w.setObjectName("toolbarContainer")
        layout = QHBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(8)

        reports_btn = QPushButton("Отчёты и планы")
        set_role(reports_btn, "dark")
        reports_menu = QMenu(reports_btn)
        reports_menu.addAction("План на текущий год", lambda: self._generate_plan(current_year=True))
        reports_menu.addAction("План на следующий год", lambda: self._generate_plan(current_year=False))
        reports_menu.addAction("Текущая ситуация", self._show_current_snapshot)
        reports_menu.addSeparator()
        reports_menu.addAction("Отчёт по обученным", self._generate_trained_report)
        reports_btn.setMenu(reports_menu)
        layout.addWidget(reports_btn)

        self.query_btn = QPushButton(self.REGISTRY_TEXT)
        set_role(self.query_btn, "dark")
        self.query_btn.setToolTip("Данные из реестра обученных Минтруда")
        reg_menu = QMenu(self.query_btn)
        reg_menu.addAction("Запросить из реестра", self._query_reestr)
        self.query_selected_action = reg_menu.addAction("Обновить выбранные", self._update_selected)
        reg_menu.addSeparator()
        self.import_report_action = reg_menu.addAction("Импорт отчёта из реестра…", self._import_registry_report)
        self.import_report_action.setToolTip("Файл-ответ по SetId (XLSX), сохранённый на вкладке «Передача данных»")
        self.query_btn.setMenu(reg_menu)
        layout.addWidget(self.query_btn)

        layout.addStretch()

        import_btn = QPushButton("Импорт XLSX")
        set_role(import_btn, "secondary")
        import_btn.setIcon(themed_icon("download", "text", 16))
        import_btn.clicked.connect(self._import_xlsx)
        layout.addWidget(import_btn)

        export_btn = QPushButton("Экспорт")
        set_role(export_btn, "secondary")
        export_btn.setIcon(themed_icon("upload", "text", 16))
        export_menu = QMenu(export_btn)
        export_menu.addAction("Экспорт в XLSX (как в таблице)", lambda: self._export_xlsx(filtered=True))
        export_menu.addAction("Экспорт всех программ", lambda: self._export_xlsx(filtered=False))
        export_btn.setMenu(export_menu)
        layout.addWidget(export_btn)

        more_btn = QPushButton()
        set_role(more_btn, "ghost")
        more_btn.setIcon(themed_icon("more", "text", 18))
        more_btn.setToolTip("Ещё")
        more_menu = QMenu(more_btn)
        more_menu.addAction("Удалить выбранные", self._delete_selected)
        more_menu.addAction("Удалить все", self._delete_all_data)
        more_btn.setMenu(more_menu)
        layout.addWidget(more_btn)

        add_btn = QPushButton("Добавить сотрудника")
        set_role(add_btn, "primary")
        add_btn.setIcon(themed_icon("plus", "on_cta", 16))
        add_btn.setFixedHeight(38)
        add_btn.clicked.connect(self._add_employee_dialog)
        layout.addWidget(add_btn)
        return w

    # ── Table ─────────────────────────────────────────────

    def _build_table_widget(self):
        from PySide6.QtGui import QStandardItemModel
        from utils.frozen_table import FrozenColumnsTable
        from utils.table_sort import SmartSortProxyModel, TriStateSort, SORT_ROLE
        self._model = QStandardItemModel(self)
        self._proxy = SmartSortProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)

        self.table = FrozenColumnsTable(BASE_COLUMNS)
        self.table.setObjectName("summaryTable")
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.set_row_height(42)
        self.table.set_item_delegate(SummaryCellDelegate(self.table))
        self.table.set_header_levels(2)
        self.table.context_menu_requested.connect(self._show_context_menu)
        self.table.cell_double_clicked.connect(self._on_item_double_click)

        self._sorter = TriStateSort(self.table.horizontalHeader(), self._apply_sort)
        self.table.frozen_header().sectionClicked.connect(self._sorter.on_clicked)
        self._header_persistence = None
        return self.table

    def _apply_sort(self, column, order):
        self.table.set_sort_indicator(column, order or Qt.SortOrder.AscendingOrder)
        self._proxy.sort(column, order if order is not None else Qt.SortOrder.AscendingOrder)

    def _emp_id_at(self, proxy_row: int):
        return self._proxy.index(proxy_row, 0).data(ROLE_EMP_ID)

    def _selected_emp_ids(self) -> list:
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            eid = idx.data(ROLE_EMP_ID)
            if eid and eid not in ids:
                ids.append(eid)
        return ids

    def refresh_table(self):
        from utils.ui_helpers import busy_cursor
        with busy_cursor():
            data_map = EmployeesRepo.get_all_with_programs()
            employees = [v['emp'] for v in data_map.values()]
            self._build_table(employees, data_map)
            self._update_stats(employees, data_map)

    def _build_table(self, employees: List[dict], progs_by_employee: dict = None):
        from PySide6.QtGui import QStandardItem
        from utils.icons import status_icon
        from utils.table_sort import SORT_ROLE

        programs = self._selected_programs
        model = self._model
        model.clear()
        num_cols = BASE_COLUMNS + len(programs) * SUB_COLUMNS
        model.setColumnCount(num_cols)

        labels = ["Сотрудник", "СНИЛС", "Статус"]
        sub_labels = ["Потребность", "Дата", "Протокол", "Рег.№"]
        for col, label in enumerate(labels):
            model.setHeaderData(col, Qt.Orientation.Horizontal, label)
        groups = []
        for pi, p in enumerate(programs):
            start = BASE_COLUMNS + pi * SUB_COLUMNS
            groups.append((start, SUB_COLUMNS, "№%s · %s" % (p, PROGRAM_TITLES.get(p, ''))))
            for j, label in enumerate(sub_labels):
                model.setHeaderData(start + j, Qt.Orientation.Horizontal, label)
        self.table.horizontalHeader().set_groups(groups)
        self.table.frozen_header().set_levels(2)

        status_filter = self.filter_status.currentText()
        prog_filter = self.filter_program.currentData()
        pos_filter = self.filter_position.text().strip().lower()
        problem_only = self.problem_cb.isChecked()

        for emp in employees:
            if pos_filter:
                if pos_filter not in emp['position'].lower():
                    continue

            eid = emp['id']
            progs = progs_by_employee[eid]['programs'] if progs_by_employee and eid in progs_by_employee else \
                    EmployeeProgramsRepo.get_by_employee(eid)
            if prog_filter != "all":
                has_prog = any(str(p['program_id']) == prog_filter and p.get('need_training') == 1 for p in progs)
                if not has_prog:
                    continue
            prog_map = {str(p['program_id']): p for p in progs}

            row_programs = {}
            overall_status = None
            for p in programs:
                pd = prog_map.get(p)
                if not pd or pd.get('need_training') != 1:
                    row_programs[p] = {'need_training': 0, 'exam_date': '', 'protocol': '', 'base_no': '', 'status': ''}
                    continue
                stored_status = pd.get('status', 'not_trained')
                prog_id = int(p)
                effective_status = get_dynamic_status(
                    stored_status, pd.get('exam_date', ''),
                    prog_id, self._b_period_3years, result=pd.get('result')
                )
                row_programs[p] = { 'need_training': pd.get('need_training', 0),
                    'exam_date': pd.get('exam_date', ''), 'protocol': pd.get('protocol', ''),
                    'base_no': pd.get('base_no', ''), 'status': effective_status,}
                if effective_status == 'not_trained':
                    overall_status = 'not_trained'
                elif effective_status == 'expired' and overall_status != 'not_trained':
                    overall_status = 'expired'
                elif effective_status == 'trained' and overall_status is None:
                    overall_status = 'trained'

            if status_filter != "Все":
                status_map = {"Обучен": "trained", "Не обучен": "not_trained", "Просрочено": "expired"}
                mapped = status_map.get(status_filter, "")
                if overall_status != mapped:
                    continue

            if problem_only and overall_status in (None, 'trained'):
                continue

            fio = f"{emp['last_name']} {emp['first_name']} {emp['middle_name']}".strip()
            position = emp['position'] or ''

            name_item = QStandardItem(fio + ("\n" + position if position else ""))
            name_item.setData(emp['id'], ROLE_EMP_ID)
            name_item.setData(fio, ROLE_FIO)
            name_item.setData(position, ROLE_POSITION)
            name_item.setData(fio.lower(), SORT_ROLE)
            name_item.setToolTip(fio + ("\n" + position if position else ""))
            snils_item = QStandardItem(str(emp['snils'] or ''))
            snils_item.setData(emp['id'], ROLE_EMP_ID)
            status_item = QStandardItem("")
            status_item.setData(emp['id'], ROLE_EMP_ID)
            if overall_status:
                text = STATUS_TEXT[overall_status]
                status_item.setData(status_icon(STATUS_KIND[overall_status]), Qt.ItemDataRole.DecorationRole)
                status_item.setToolTip(text)
                status_item.setData(text, Qt.ItemDataRole.AccessibleTextRole)
                status_item.setData(STATUS_RANK[overall_status], SORT_ROLE)
            else:
                status_item.setToolTip("Нет программ, требующих обучения")
            row_items = [name_item, snils_item, status_item]

            for p in programs:
                pd = row_programs.get(p, {})
                if pd.get('need_training', 0) != 1:
                    cells = [QStandardItem("Нет")]
                    for _ in range(SUB_COLUMNS - 1):
                        dash = QStandardItem("—")
                        dash.setData("surface_subtle", BG_ROLE)
                        dash.setData("text_faint", FG_ROLE)
                        cells.append(dash)
                    cells[0].setData("surface_subtle", BG_ROLE)
                    cells[0].setData("text_faint", FG_ROLE)
                    row_items.extend(cells)
                    continue
                s_prog = pd.get('status', 'not_trained')
                date_text = pd.get('exam_date', '')
                need_item = QStandardItem("Да")
                date_item = QStandardItem(date_text if date_text else "нет")
                if not date_text:
                    date_item.setData("err_text", FG_ROLE)
                elif s_prog == 'expired':
                    date_item.setData("warn_text", FG_ROLE)
                    date_item.setToolTip("Срок действия обучения истёк")
                date_item.setData(date_text, SORT_ROLE)
                row_items.extend([need_item, date_item, QStandardItem(pd.get('protocol', '') or ''),
                                  QStandardItem(pd.get('base_no', '') or '')])
            for item in row_items:
                item.setEditable(False)
            model.appendRow(row_items)

        self.table.sync_frozen()
        self._restore_column_layout(num_cols)
        self._sorter.reapply()

    def _restore_column_layout(self, num_cols: int):
        """Frozen column widths + remembered widths (state is skipped if the column count changed)."""
        from utils.ui_helpers import HeaderStatePersistence
        header = self.table.horizontalHeader()
        for col, width in enumerate((230, 130, 70)):
            self.table.setColumnWidth(col, width)
        for col in range(BASE_COLUMNS, num_cols):
            self.table.setColumnWidth(col, 110 if (col - BASE_COLUMNS) % SUB_COLUMNS else 100)
        if self._header_persistence is None:
            self._header_persistence = HeaderStatePersistence(header, "summary_table")
        else:
            self._header_persistence.restore()
        self.table.sync_frozen()

    def _get_employee_status(self, programs) -> str:
        has_trained = False
        has_expired = False
        for p in programs:
            if p.get('need_training') != 1:
                continue
            stored_status = p.get('status', 'not_trained')
            s = get_dynamic_status(
                stored_status, p.get('exam_date', ''),
                p.get('program_id', 0), self._b_period_3years, result=p.get('result')
            )
            if s == 'not_trained':
                return 'not_trained'
            if s == 'expired':
                has_expired = True
            elif s == 'trained':
                has_trained = True
        if has_expired:
            return 'expired'
        if has_trained:
            return 'trained'
        return 'not_trained'

    def _update_stats(self, employees: List[dict] = None, progs_by_employee: dict = None):
        trained = not_trained = expired = 0
        emp_count = 0
        emp_list = employees if employees is not None else EmployeesRepo.get_all()
        for emp in emp_list:
            eid = emp['id']
            progs = progs_by_employee[eid]['programs'] if progs_by_employee and eid in progs_by_employee else \
                    EmployeeProgramsRepo.get_by_employee(eid)
            need_progs = [p for p in progs if p.get('need_training') == 1]
            if not need_progs:
                continue
            emp_count += 1
            status = self._get_employee_status(progs)
            if status == 'trained':
                trained += 1
            elif status == 'expired':
                expired += 1
            else:
                not_trained += 1
        self.stat_total.setText(str(emp_count))
        self._set_chip_counts(trained, not_trained, expired)

        total_all = len(emp_list)
        self.stat_total_info.setText(f"всего {total_all} сотрудников")

        last_sync = ""
        rows = DatabaseManager.get_instance().fetchone(
            "SELECT MAX(last_sync) as ls FROM employees WHERE last_sync IS NOT NULL"
        )
        if rows and rows['ls']:
            parts = rows['ls'].split(' ', 1)
            last_sync = '\n'.join(parts) if len(parts) > 1 else rows['ls']
        self.stat_sync.setText(last_sync or "нет")

    def _apply_filters(self):
        self._sync_chips()
        self.refresh_table()

    # ── Context menu ───────────────────────────────────────

    def _show_context_menu(self, global_pos, idx):
        if not idx.isValid():
            return
        emp_id = idx.sibling(idx.row(), 0).data(ROLE_EMP_ID)

        menu = QMenu(self)
        menu.setObjectName("summaryCtxMenu")

        selected_rows = len(self.table.selectionModel().selectedRows())

        edit_action = menu.addAction("Редактировать")
        query_action = menu.addAction("Запросить из реестра")
        delete_action = menu.addAction("Удалить")
        if selected_rows > 1:
            menu.addSeparator()
            menu.addAction("Удалить выбранные", self._delete_selected)
            menu.addAction("Обновить выбранные", self._update_selected)

        action = menu.exec(global_pos)

        if action == edit_action:
            if emp_id:
                self._edit_employee(emp_id)
        elif action == query_action:
            if emp_id:
                self._query_single(emp_id)
        elif action == delete_action:
            if emp_id:
                reply = QMessageBox.question(
                    self, "Подтверждение", "Удалить сотрудника из сводки?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    EmployeesRepo.delete(emp_id)
                    self.refresh_table()

    def _on_item_double_click(self, idx):
        """Double click on «Потребность» toggles whether the program is required."""
        if not idx.isValid():
            return
        col = idx.column()
        for pi, p in enumerate(self._selected_programs):
            if col == BASE_COLUMNS + pi * SUB_COLUMNS:
                emp_id = idx.sibling(idx.row(), 0).data(ROLE_EMP_ID)
                if not emp_id:
                    return
                current = idx.data(Qt.ItemDataRole.DisplayRole) or "Нет"
                need = 0 if current == "Да" else 1
                EmployeeProgramsRepo.update_need_training(emp_id, int(p), need)
                self.refresh_table()
                return

    # ── Dialogs ────────────────────────────────────────────

    def _add_employee_dialog(self):
        dialog = EmployeeAddDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            last_name = dialog.last_name.text().strip()
            first_name = dialog.first_name.text().strip()
            middle_name = dialog.middle_name.text().strip()
            snils = dialog.snils.text().strip()
            position = dialog.position.text().strip()
            programs_str = dialog.programs.text().strip()

            if not snils:
                QMessageBox.warning(self, "Ошибка", "Заполните СНИЛС")
                return

            snils_clean = snils.replace('-', '').replace(' ', '')
            if not snils_clean.isdigit() or len(snils_clean) != 11:
                QMessageBox.warning(self, "Ошибка", "СНИЛС должен содержать 11 цифр")
                return

            snils_fmt = f"{snils_clean[:3]}-{snils_clean[3:6]}-{snils_clean[6:9]} {snils_clean[9:]}"
            programs = [p.strip() for p in programs_str.split(',') if p.strip() and p.strip() in VALID_PROGRAMS]

            emp_data = { 'snils': snils_fmt, 'last_name': last_name, 'first_name': first_name,
                'middle_name': middle_name, 'position': position,
                'required_programs': ';'.join(programs),}
            emp_id = EmployeesRepo.upsert(emp_data)

            for p in programs:
                EmployeeProgramsRepo.upsert(emp_id, {'program_id': int(p), 'need_training': 1})

            self.refresh_table()
            Toast.success(self, "Сотрудник добавлен")

    def _edit_employee(self, emp_id):
        emp = EmployeesRepo.get_by_id(emp_id)
        if not emp:
            return
        progs = EmployeeProgramsRepo.get_by_employee(emp_id)
        old_progs = {str(p['program_id']): p for p in progs}
        dialog = EmployeeEditDialog(emp, progs, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_progs = [p.strip() for p in dialog.programs.text().split(',') if p.strip() in VALID_PROGRAMS]
            EmployeesRepo.upsert({ 'snils': dialog.snils.text().strip(),
                'last_name': dialog.last_name.text().strip(), 'first_name': dialog.first_name.text().strip(),
                'middle_name': dialog.middle_name.text().strip(), 'position': dialog.position.text().strip(),
                'required_programs': ';'.join(new_progs),})
            EmployeeProgramsRepo.delete_by_employee(emp_id)
            for p in new_progs:
                old = old_progs.get(p, {})
                EmployeeProgramsRepo.upsert(emp_id, {
                    'program_id': int(p),
                    'need_training': 1,
                    'exam_date': old.get('exam_date'),
                    'protocol': old.get('protocol'),
                    'base_no': old.get('base_no'),
                    'result': old.get('result'),
                })
            self.refresh_table()

    def _delete_all_data(self):
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить ВСЕ данные из сводки по сотрудникам?\nЭто действие необратимо.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            EmployeesRepo.clear()
            self.refresh_table()
            Toast.success(self, "Все данные удалены")

    # ── Program selector ───────────────────────────────────

    def _show_program_selector(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Выбор программ для отображения")
        dialog.setMinimumSize(500, 500)

        lw = QListWidget()
        selected = set(self._selected_programs)
        for p in VALID_PROGRAMS:
            item = QListWidgetItem(f"{p}: {PROGRAM_TITLES.get(p, '')}")
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if p in selected else Qt.CheckState.Unchecked)
            lw.addItem(item)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Отметьте программы для отображения:"))
        layout.addWidget(lw)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Применить"); ok_btn.setObjectName("dialogPrimaryBtn")
        def apply():
            checked = []
            for i in range(lw.count()):
                item = lw.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    checked.append(item.data(Qt.ItemDataRole.UserRole))
            if not checked:
                QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну программу")
                return
            self._selected_programs = checked
            self._save_settings(self.data_dir, checked)
            dialog.accept()
            self.refresh_table()
        ok_btn.clicked.connect(apply)
        cancel_btn = QPushButton("Отмена"); cancel_btn.setObjectName("dialogDangerBtn")
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(ok_btn); btn_row.addStretch(); btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        dialog.exec()

    # ── Import / Export ────────────────────────────────────

    # ── UX-14: импорт отчёта реестра (ответ по SetId) ──────

    def _import_registry_report(self):
        """Обновляет справочник по файлу-ответу реестра: сопоставление по СНИЛС."""
        from utils.constants import MAX_XLSX_FILE_SIZE_MB

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Файл-ответ реестра (SetId)", "", "Excel Files (*.xlsx)")
        if not file_path:
            return
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
        except OSError as e:
            safe_message_box(self, QMessageBox.Icon.Warning, "Импорт отчёта",
                             "Не удалось прочитать файл: %s" % type(e).__name__)
            return
        if size_mb > MAX_XLSX_FILE_SIZE_MB:
            safe_message_box(self, QMessageBox.Icon.Warning, "Импорт отчёта",
                             "Файл превышает лимит %d МБ (%.1f МБ)" % (MAX_XLSX_FILE_SIZE_MB, size_mb))
            return

        from journal.registry_sync import is_api_xlsx_headers
        from journal.summary_sync import describe_summary_merge, merge_summary_records
        from utils.ui_helpers import busy_cursor

        try:
            with busy_cursor():
                from openpyxl import load_workbook
                wb = load_workbook(file_path, data_only=True, read_only=True)
                try:
                    rows = list(wb.active.values)
                finally:
                    wb.close()
        except Exception as e:
            logger.exception("Registry report could not be read")
            safe_message_box(self, QMessageBox.Icon.Warning, "Импорт отчёта",
                             "Не удалось прочитать файл: %s" % type(e).__name__)
            return

        if not rows:
            safe_message_box(self, QMessageBox.Icon.Warning, "Импорт отчёта", "Файл пуст")
            return
        headers = list(rows[0])
        if not is_api_xlsx_headers(headers):
            safe_message_box(
                self, QMessageBox.Icon.Warning, "Импорт отчёта",
                "Это не файл-ответ реестра.\n\n"
                "Ожидаются столбцы: «Номер записи в реестре», «СНИЛС», "
                "«Номер программы», «Номер протокола», «Дата».\n"
                "Такой файл сохраняется на вкладке «Передача данных» после запроса по SetId.\n\n"
                "Для загрузки списка работников используйте «Импорт из XLSX».")
            return

        known = {e.get('snils', '') for e in EmployeesRepo.get_all()}
        with busy_cursor():
            res = merge_summary_records(headers, rows[1:], known)

        if not res.employees and not res.errors:
            safe_message_box(self, QMessageBox.Icon.Information, "Импорт отчёта",
                             "В файле нет записей для импорта")
            return

        add_new = False
        skipped_new = 0
        if res.new:
            names = "\n".join("• %s" % (e.full_name or e.snils) for e in res.new[:15])
            if len(res.new) > 15:
                names += "\n• …и ещё %d" % (len(res.new) - 15)
            reply = QMessageBox.question(
                self, "Новые работники",
                "В отчёте есть работники, которых нет в справочнике (%d):\n\n%s\n\n"
                "Добавить их в справочник?" % (len(res.new), names),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            add_new = reply == QMessageBox.StandardButton.Yes
            if not add_new:
                skipped_new = len(res.new)

        targets = list(res.existing) + (list(res.new) if add_new else [])
        added = 0
        failed = 0
        with busy_cursor():
            for emp in targets:
                try:
                    emp_id = EmployeesRepo.upsert({
                        'snils': emp.snils,
                        'last_name': emp.last_name,
                        'first_name': emp.first_name,
                        'middle_name': emp.middle_name,
                        'position': emp.position,
                    })
                    if emp.is_new:
                        added += 1
                    for prog in emp.programs.values():
                        EmployeeProgramsRepo.update_from_api(
                            emp_id, prog.program_id, prog.exam_date,
                            prog.protocol, prog.base_no, prog.result)
                except Exception:
                    logger.exception("Registry report: employee update failed")
                    failed += 1

        log_audit("IMPORT_XLSX", "registry report: employees=%d programs=%d added=%d errors=%d" % (
            len(targets), res.program_count, added, len(res.errors) + failed))
        from utils.cache import invalidate_summary_cache
        invalidate_summary_cache()
        self.refresh_table()

        text = describe_summary_merge(res, added=added, skipped_new=skipped_new)
        if failed:
            text += "\nНе удалось сохранить работников: %d" % failed
        safe_message_box(self, QMessageBox.Icon.Information, "Импорт отчёта завершён", text)

    def _import_xlsx(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите XLSX файл", "", "Excel Files (*.xlsx)")
        if not file_path:
            return
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, data_only=True)
            ws = wb.active

            headers = [str(ws.cell(row=1, column=c).value or '').strip() for c in range(1, ws.max_column + 1)]
            col_map = {h: i for i, h in enumerate(headers)}

            if 'СНИЛС' not in col_map:
                QMessageBox.warning(self, "Ошибка", "Не найден столбец 'СНИЛС'")
                return

            snils_col = col_map['СНИЛС']
            last_name_col = col_map.get('Фамилия')
            first_name_col = col_map.get('Имя')
            middle_name_col = col_map.get('Отчество')
            position_col = col_map.get('Должность')
            fio_col = col_map.get('ФИО')

            program_cols = {}
            for p in VALID_PROGRAMS:
                need_key = f"программа #{p} Потребность"
                date_key = f"программа #{p} Дата обучения"
                proto_key = f"программа #{p} Протокол"
                reg_key = f"программа #{p} Рег.№"
                if need_key in col_map:
                    program_cols[p] = { 'need': col_map[need_key],
                        'date': col_map.get(date_key), 'protocol': col_map.get(proto_key),
                        'reg': col_map.get(reg_key),}

            hidden_col = col_map.get('Потребность в обучении по программам')

            if not program_cols and hidden_col is None:
                QMessageBox.warning(self, "Ошибка", "Не найдены столбцы с потребностью в обучении по программам.\n\nОжидаются заголовки вида: 'программа #N Потребность' или 'Потребность в обучении по программам'")
                return

            imported = 0
            for row_num in range(2, ws.max_row + 1):
                snils_raw = str(ws.cell(row=row_num, column=snils_col + 1).value or '').strip()
                if not snils_raw:
                    continue
                snils_clean = snils_raw.replace('-', '').replace(' ', '')
                if not snils_clean.isdigit() or len(snils_clean) != 11:
                    logger.info("Import: row %d skipped — invalid SNILS", row_num)
                    continue
                snils_fmt = f"{snils_clean[:3]}-{snils_clean[3:6]}-{snils_clean[6:9]} {snils_clean[9:]}"

                last_name = str(ws.cell(row=row_num, column=(last_name_col if last_name_col is not None else 0) + 1).value or '').strip() if last_name_col is not None else ''
                first_name = str(ws.cell(row=row_num, column=(first_name_col if first_name_col is not None else 0) + 1).value or '').strip() if first_name_col is not None else ''
                middle_name = str(ws.cell(row=row_num, column=(middle_name_col if middle_name_col is not None else 0) + 1).value or '').strip() if middle_name_col is not None else ''
                position = str(ws.cell(row=row_num, column=(position_col if position_col is not None else 0) + 1).value or '').strip() if position_col is not None else ''
                if (not last_name or not first_name) and fio_col is not None:
                    fio_raw = str(ws.cell(row=row_num, column=fio_col + 1).value or '').strip()
                    if fio_raw:
                        parts = fio_raw.split()
                        if len(parts) >= 1: last_name = parts[0]
                        if len(parts) >= 2: first_name = parts[1]
                        if len(parts) >= 3: middle_name = ' '.join(parts[2:])

                required_programs = set()
                if hidden_col is not None:
                    hidden_val = str(ws.cell(row=row_num, column=hidden_col + 1).value or '').strip()
                    if hidden_val:
                        parts = [p.strip() for p in hidden_val.replace(';', ',').split(',')]
                        for p in parts:
                            if p in VALID_PROGRAMS:
                                required_programs.add(p)

                for p, cols in program_cols.items():
                    val = str(ws.cell(row=row_num, column=cols['need'] + 1).value or '').strip().lower()
                    if val in ('1', 'да', 'true', 'yes'):
                        required_programs.add(p)

                emp_id = EmployeesRepo.upsert({ 'snils': snils_fmt,
                    'last_name': last_name, 'first_name': first_name, 'middle_name': middle_name,
                    'position': position,
                    'required_programs': ';'.join(sorted(required_programs)),})
                for p in required_programs:
                    prog_data = {'program_id': int(p), 'need_training': 1}
                    if p in program_cols:
                        cols = program_cols[p]
                        if cols['date'] is not None:
                            date_val = ws.cell(row=row_num, column=cols['date'] + 1).value
                            if date_val is not None:
                                from datetime import datetime as _dt
                                if isinstance(date_val, _dt):
                                    prog_data['exam_date'] = date_val.strftime('%d.%m.%Y')
                                else:
                                    prog_data['exam_date'] = str(date_val).strip()
                        if cols['protocol'] is not None:
                            pval = ws.cell(row=row_num, column=cols['protocol'] + 1).value
                            if pval is not None: prog_data['protocol'] = str(pval).strip()
                        if cols['reg'] is not None:
                            rval = ws.cell(row=row_num, column=cols['reg'] + 1).value
                            if rval is not None: prog_data['base_no'] = str(rval).strip()
                    EmployeeProgramsRepo.upsert(emp_id, prog_data)
                imported += 1

            if imported == 0:
                msg = "Не найдено сотрудников для импорта."
                safe_message_box(self, QMessageBox.Icon.Information, "Результат", msg)
            else:
                safe_message_box(self, QMessageBox.Icon.Information, "Успех", f"Импортировано: {imported} сотрудников")
            self.refresh_table()
        except Exception as e:
            logger.exception("Ошибка импорта XLSX")
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Ошибка импорта: {e}")

    def _export_xlsx(self, filtered=True):
        reply = QMessageBox.warning(
            self, "Экспорт данных",
            "Файл будет содержать персональные данные (ФИО, СНИЛС).\n"
            "Убедитесь, что файл сохраняется на зашифрованном диске (BitLocker).",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Ok:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить XLSX", "Сводка_сотрудников.xlsx", "Excel Files (*.xlsx)")
        if not file_path:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment

            log_audit("EXPORT_XLSX", f"table_rows={self._proxy.rowCount()}")
            wb = Workbook()
            ws = wb.active
            ws.title = "Сводка"

            programs = self._selected_programs if filtered else VALID_PROGRAMS

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

            for r in range(self._proxy.rowCount()):
                name_idx = self._proxy.index(r, 0)
                row_data = [name_idx.data(ROLE_FIO) or '',
                            self._proxy.index(r, 1).data(Qt.ItemDataRole.DisplayRole) or '',
                            name_idx.data(ROLE_POSITION) or '']
                for p in programs:
                    pos = self._selected_programs.index(p) if p in self._selected_programs else -1
                    col_start = BASE_COLUMNS + pos * SUB_COLUMNS
                    for sub in range(SUB_COLUMNS):
                        if pos < 0:
                            row_data.append('')
                            continue
                        text = self._proxy.index(r, col_start + sub).data(Qt.ItemDataRole.DisplayRole) or ''
                        row_data.append('' if text in ('—', 'нет') and sub else text)
                ws.append(row_data)

            for col in ws.columns:
                max_len = 0
                for cell in col:
                    if cell.value: max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

            wb.save(file_path)
            safe_message_box(self, QMessageBox.Icon.Information, "Успех", f"Файл сохранён:\n{file_path}")
        except Exception as e:
            logger.exception("Export error")
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Ошибка экспорта: {e}")

    # ── API ──────────────────────────────────────────────

    def _query_reestr(self):
        api_key = load_api_key(self.data_dir)
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не найден. Сохраните ключ на вкладке 'Передача данных'")
            return
        employees = EmployeesRepo.get_all()
        if not employees:
            Toast.info(self, "Нет сотрудников для запроса")
            return
        proxy_settings = load_proxy_settings(get_app_data_dir())

        self.query_btn.setEnabled(False)
        self.query_btn.setText("Запрос...")

        self._query_errors = []

        dialog = QueryProgressDialog(len(employees), self)

        self._api_thread = ApiQueryThread(employees, api_key, proxy_settings)
        self._api_thread.finished.connect(self._on_query_finished)
        self._api_thread.finished.connect(dialog.accept)
        self._api_thread.error_signal.connect(self._on_query_error)
        self._api_thread.progress.connect(dialog.update_progress)
        dialog.cancelled.connect(self._api_thread.cancel)
        dialog.cancelled.connect(dialog.reject)
        dialog.rejected.connect(self._api_thread.cancel)
        self._api_thread.start()

        dialog.exec()

    def _on_query_error(self, msg):
        logger.error("%s", filter_sensitive_text(str(msg)))
        self._query_errors.append(msg)

    def _on_query_finished(self, updated, errors):
        self.query_btn.setEnabled(True)
        self.query_btn.setText(self.REGISTRY_TEXT)
        if errors > 0:
            detail = "\n".join(self._query_errors[:20])
            if len(self._query_errors) > 20:
                detail += f"\n... и ещё {len(self._query_errors) - 20} ошибок"
            safe_message_box(self, QMessageBox.Icon.Warning, "Результат",
                             f"Обновлено: {updated}\nОшибок: {errors}\n\nПодробности:\n{detail}")
        else:
            safe_message_box(self, QMessageBox.Icon.Information, "Успех",
                             f"Обновлено: {updated} сотрудников")
        self.refresh_table()

    def _delete_selected(self):
        emp_ids = set(self._selected_emp_ids())
        if not emp_ids:
            Toast.info(self, "Выберите сотрудников для удаления")
            return
        if QMessageBox.question(
            self, "Подтверждение",
            f"Удалить выбранных сотрудников ({len(emp_ids)} шт.)?\nДанные удалятся безвозвратно.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        ) != QMessageBox.StandardButton.Ok:
            return
        for eid in emp_ids:
            EmployeesRepo.delete(eid)
        DatabaseManager.get_instance().secure_vacuum()
        self.refresh_table()
        Toast.success(self, "Выбранные сотрудники удалены")

    def _update_selected(self):
        emp_ids = set(self._selected_emp_ids())
        if not emp_ids:
            Toast.info(self, "Выберите сотрудников для обновления")
            return
        api_key = load_api_key(self.data_dir)
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не найден. Сохраните ключ на вкладке 'Передача данных'")
            return
        employees = [e for e in EmployeesRepo.get_all() if e['id'] in emp_ids]
        if not employees:
            return
        proxy_settings = load_proxy_settings(get_app_data_dir())
        self.query_btn.setEnabled(False)
        self.query_btn.setText("Обновление...")
        self._query_errors = []
        dialog = QueryProgressDialog(len(employees), self)
        self._api_thread = ApiQueryThread(employees, api_key, proxy_settings)
        self._api_thread.finished.connect(self._on_query_finished)
        self._api_thread.finished.connect(dialog.accept)
        self._api_thread.error_signal.connect(self._on_query_error)
        self._api_thread.progress.connect(dialog.update_progress)
        dialog.cancelled.connect(self._api_thread.cancel)
        dialog.cancelled.connect(dialog.reject)
        dialog.rejected.connect(self._api_thread.cancel)
        self._api_thread.start()
        dialog.exec()

    def _query_single(self, emp_id):
        api_key = load_api_key(self.data_dir)
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "API ключ не найден")
            return
        emp = EmployeesRepo.get_by_id(emp_id)
        if not emp:
            return
        proxy_settings = load_proxy_settings(get_app_data_dir())
        snils_clean = emp['snils'].replace('-', '').replace(' ', '')
        try:
            result = get_by_snils(api_key, snils_clean, proxy_settings=proxy_settings)
            if result.get("success"):
                records = result.get("records", [])
                best = {}
                for rec in records:
                    prog_id = rec.get('learnProgramId', '')
                    if not prog_id: continue
                    exam_date = _normalize_api_date(rec.get('Date', ''))
                    if prog_id not in best or (exam_date and _dmy_gt(exam_date, _normalize_api_date(best[prog_id].get('Date', '')))):
                        best[prog_id] = rec
                updated = 0
                for prog_id, rec in best.items():
                    is_passed = rec.get('isPassed', '')
                    result_val = 1 if is_passed and is_passed.lower() in ('true', '1', 'да') else 0
                    try:
                        EmployeeProgramsRepo.update_from_api(
                            emp_id, int(prog_id),
                            _normalize_api_date(rec.get('Date', '')), rec.get('ProtocolNumber', ''),
                            rec.get('baseNo', ''), result_val)
                        updated += 1
                    except (ValueError, TypeError): pass
                if records:
                    first_rec = records[0]
                    if not emp.get('last_name') or not emp.get('first_name') or not emp.get('position'):
                        updates = {}
                        if not emp.get('last_name'): updates['last_name'] = first_rec.get('LastName', '')
                        if not emp.get('first_name'): updates['first_name'] = first_rec.get('FirstName', '')
                        if not emp.get('middle_name'): updates['middle_name'] = first_rec.get('MiddleName', '')
                        if not emp.get('position'): updates['position'] = first_rec.get('Position', '')
                        if updates:
                            updates['snils'] = emp['snils']
                            EmployeesRepo.upsert(updates)
                EmployeesRepo.update_sync(emp_id, datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
                safe_message_box(self, QMessageBox.Icon.Information, "Успех", f"Обновлено программ: {updated}")
                self.refresh_table()
            else:
                safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", result.get("error", "Неизвестная ошибка"))
        except Exception as e:
            logger.exception("Registry query error")
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Ошибка запроса: {e}")

    # ── Reports ──────────────────────────────────────────

    def _show_current_snapshot(self):
        today = datetime.now()
        plan_data = []

        for emp in EmployeesRepo.get_all():
            progs = EmployeeProgramsRepo.get_by_employee(emp['id'])
            need_progs = [p for p in progs if p.get('need_training') == 1]
            if not need_progs:
                continue

            for p in need_progs:
                prog_id = p.get('program_id', 0)
                last_exam = p.get('exam_date', '')
                stored_status = p.get('status', 'not_trained')
                effective_status = get_dynamic_status(stored_status, last_exam, prog_id, self._b_period_3years,
                                                      result=p.get('result'))

                if effective_status == 'not_trained':
                    reason = 'Не обучен'
                    priority = 'Высокий'
                    expiry = (today + relativedelta(days=60)).strftime('%d.%m.%Y')
                elif effective_status == 'expired':
                    reason = 'Просрочено'
                    priority = 'Высокий'
                    try:
                        ed = compute_expiry_date(last_exam, prog_id, self._b_period_3years)
                        expiry = ed.strftime('%d.%m.%Y')
                    except (ValueError, IndexError):
                        expiry = ''
                else:
                    reason = 'Обучен'
                    priority = 'Низкий'
                    try:
                        ed = compute_expiry_date(last_exam, prog_id, self._b_period_3years)
                        expiry = ed.strftime('%d.%m.%Y')
                    except (ValueError, IndexError):
                        expiry = ''

                plan_data.append({
                    'last_name': emp['last_name'], 'first_name': emp['first_name'],
                    'middle_name': emp['middle_name'], 'snils': emp['snils'],
                    'position': emp['position'], 'program': str(prog_id),
                    'last_exam_date': last_exam, 'expiry_date': expiry,
                    'reason': reason,
                    'priority': priority,
                })

        plan_data.sort(key=lambda x: (
            {"Высокий": 0, "Средний": 1, "Низкий": 2}.get(x['priority'], 3), x['last_name']))

        if not plan_data:
            Toast.info(self, "Нет данных для отображения")
            return

        log_audit("EXPORT_SNAPSHOT", f"rows={len(plan_data)}")

        title = f"Текущая ситуация на {today.strftime('%d.%m.%Y')}"
        plan_dlg = PlanDialog(plan_data, title, self)
        plan_dlg.exec()

    def _generate_trained_report(self):
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
                        period = get_training_period_years(row['program_id'], self._b_period_3years)
                        if exam_year == year - period:
                            count_liable += 1
                except (ValueError, IndexError):
                    count_liable += 1
                    continue
            report_data[cat_name] = (count_liable, count_trained)

        def _pct(trained, liable):
            return round(trained / liable * 100, 1) if liable else 0.0

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Отчет по обученным за {year} год")
        dialog.setMinimumSize(750, 400)

        layout = QVBoxLayout(dialog)
        total_trained = sum(c[1] for c in report_data.values())
        log_audit("EXPORT_TRAINED_REPORT", f"employees={total_trained}")

        title = QLabel(f"Отчет по обученным за {year} год")
        title.setObjectName("reportTitleLabel")
        layout.addWidget(title)

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

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Экспорт в Excel")
        export_btn.setObjectName("dialogPrimaryBtn")
        export_btn.clicked.connect(lambda: self._export_trained_report_xlsx(report_data, _pct, year, dialog))
        btn_layout.addWidget(export_btn)
        close_btn = QPushButton("Закрыть"); close_btn.setObjectName("dialogDangerBtn")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addStretch(); btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dialog.exec()

    def _export_trained_report_xlsx(self, report_data: dict, pct_func, year: int, parent: QDialog):
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "Сохранить XLSX", f"Отчет_по_обученным_{year}.xlsx", "Excel Files (*.xlsx)"
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
        except Exception as e:
            logger.exception("Export trained report error")
            from utils.error_utils import show_error_dialog
            show_error_dialog(parent, "Ошибка экспорта", str(e), critical=False)

    def _generate_plan(self, current_year=True):
        year = datetime.now().year if current_year else datetime.now().year + 1
        plan_year = year
        today = datetime.now()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Параметры формирования плана на {plan_year} год")
        dialog.setMinimumSize(400, 250)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Параметры формирования плана на {plan_year} год:"))

        cb_not_trained = QCheckBox("Включать не обученных"); cb_not_trained.setChecked(True)
        layout.addWidget(cb_not_trained)
        cb_expired = QCheckBox("Включать просроченных"); cb_expired.setChecked(True)
        layout.addWidget(cb_expired)
        cb_expiring = QCheckBox("Включать истекающих в планируемом году"); cb_expiring.setChecked(True)
        layout.addWidget(cb_expiring)
        cb_failed = QCheckBox("Включать неуспешно прошедших"); cb_failed.setChecked(True)
        layout.addWidget(cb_failed)

        btn_layout = QHBoxLayout()
        generate_btn = QPushButton("Сформировать"); generate_btn.setObjectName("dialogPrimaryBtn")
        cancel_btn = QPushButton("Отмена"); cancel_btn.setObjectName("dialogDangerBtn")
        cancel_btn.clicked.connect(dialog.reject)

        plan_data = []

        def do_generate():
            nonlocal plan_data
            employees = EmployeesRepo.get_all()
            for emp in employees:
                progs = EmployeeProgramsRepo.get_by_employee(emp['id'])
                need_progs = [p for p in progs if p.get('need_training') == 1]
                if not need_progs:
                    continue

                status = self._get_employee_status(progs)

                if status == 'not_trained' and cb_not_trained.isChecked():
                    for p in need_progs:
                        prog_id = p.get('program_id', 0)
                        last_exam = p.get('exam_date', '')
                        plan_data.append({
                            'last_name': emp['last_name'], 'first_name': emp['first_name'],
                            'middle_name': emp['middle_name'], 'snils': emp['snils'],
                            'position': emp['position'], 'program': str(prog_id),
                            'last_exam_date': last_exam,
                            'expiry_date': (today + relativedelta(days=60)).strftime('%d.%m.%Y'),
                            'reason': 'Не обучен', 'priority': 'Высокий',
                        })

                elif status == 'expired' and cb_expired.isChecked():
                    for p in need_progs:
                        prog_id = p.get('program_id', 0)
                        last_exam = p.get('exam_date', '')
                        plan_data.append({
                            'last_name': emp['last_name'], 'first_name': emp['first_name'],
                            'middle_name': emp['middle_name'], 'snils': emp['snils'],
                            'position': emp['position'], 'program': str(prog_id),
                            'last_exam_date': last_exam,
                            'expiry_date': (today + relativedelta(days=30)).strftime('%d.%m.%Y'),
                            'reason': 'Просрочено', 'priority': 'Высокий',
                        })

                else:
                    if cb_expiring.isChecked():
                        for p in need_progs:
                            pid = p.get('program_id', 0)
                            last_exam = p.get('exam_date', '')
                            if not last_exam:
                                continue
                            try:
                                expiry_date = compute_expiry_date(last_exam, pid, self._b_period_3years)
                                if expiry_date.year == plan_year:
                                    plan_data.append({
                                        'last_name': emp['last_name'], 'first_name': emp['first_name'],
                                        'middle_name': emp['middle_name'], 'snils': emp['snils'],
                                        'position': emp['position'], 'program': str(pid),
                                        'last_exam_date': last_exam,
                                        'expiry_date': expiry_date.strftime('%d.%m.%Y'),
                                        'reason': 'Истекает срок действия', 'priority': 'Средний',
                                    })
                            except (ValueError, IndexError):
                                pass

                    if cb_failed.isChecked():
                        failed_progs = [p for p in need_progs if p.get('result') == 0]
                        for p in failed_progs:
                            prog_id = p.get('program_id', 0)
                            last_exam = p.get('exam_date', '')
                            plan_data.append({
                                'last_name': emp['last_name'], 'first_name': emp['first_name'],
                                'middle_name': emp['middle_name'], 'snils': emp['snils'],
                                'position': emp['position'], 'program': str(prog_id),
                                'last_exam_date': last_exam,
                                'expiry_date': (today + relativedelta(days=60)).strftime('%d.%m.%Y'),
                                'reason': 'Неудовлетворительный результат', 'priority': 'Высокий',
                            })

            n = sum(1 for x in plan_data if x['reason'] == 'Не обучен')
            e = sum(1 for x in plan_data if x['reason'] == 'Просрочено')
            t = sum(1 for x in plan_data if x['reason'] == 'Истекает срок действия')
            log_audit("EXPORT_PLAN", f"rows={len(plan_data)}, not_trained={n}, expired={e}, trained={t}")

            plan_data.sort(key=lambda x: (
                {"Высокий": 0, "Средний": 1, "Низкий": 2}.get(x['priority'], 3), x['last_name']))
            dialog.accept()

        generate_btn.clicked.connect(do_generate)
        btn_layout.addWidget(generate_btn); btn_layout.addStretch(); btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.DialogCode.Rejected or not plan_data:
            if not plan_data:
                Toast.info(self, "Нет сотрудников для включения в план")
            return

        title = f"План обучения на {plan_year} год"
        plan_dlg = PlanDialog(plan_data, title, self)
        plan_dlg.exec()
