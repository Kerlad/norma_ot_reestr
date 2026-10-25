import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QMessageBox, QFileDialog, QComboBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt
from protocol.programs_manager import ProgramsManager
from exporters.protocol_exporter import ProtocolExporter

logger = logging.getLogger(__name__)


class SingleWorkerProtocolTab(QWidget):
    def __init__(self, programs_manager: ProgramsManager, data_dir: str, parent=None):
        super().__init__(parent)
        self.programs = programs_manager
        self.data_dir = data_dir
        self.commission_data = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        layout.addWidget(self._build_commission_bar())

        cards = QHBoxLayout()
        cards.setSpacing(16)
        cards.addWidget(self._build_worker_card(), 1)
        cards.addWidget(self._build_exam_card(), 1)
        cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        form_wrap = QWidget()
        form_wrap.setMaximumWidth(1000)
        form_wrap.setLayout(cards)
        layout.addWidget(form_wrap)

        from utils.ui_helpers import set_role
        gen_row = QHBoxLayout()
        gen_row.setSpacing(12)
        self.generate_btn = QPushButton("Сформировать протокол")
        self.generate_btn.setObjectName("generateProtocolBtn")
        set_role(self.generate_btn, "primary")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._generate_protocol)
        gen_row.addWidget(self.generate_btn)
        gen_row.addWidget(self._build_preview(), 1)
        clear_btn = QPushButton("Очистить форму")
        set_role(clear_btn, "ghost")
        clear_btn.clicked.connect(self._clear_form)
        gen_row.addWidget(clear_btn)
        gen_wrap = QWidget()
        gen_wrap.setMaximumWidth(1000)
        gen_wrap.setLayout(gen_row)
        gen_row.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gen_wrap)
        layout.addStretch()

        self._update_preview()
        self._load_commission()

    def _clear_form(self):
        for edit in (self.last_name_input, self.first_name_input, self.middle_name_input, self.position_input,
                     self.programs_input, self.exam_date_input, self.protocol_input, self.base_no_input):
            edit.clear()
        self.result_combo.setCurrentIndex(0)
        self._update_preview()

    def _build_worker_card(self):
        from utils.ui_helpers import make_card
        card, lay = make_card("Работник")
        card.setObjectName("workerFormCard")
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.last_name_input = QLineEdit()
        self.last_name_input.setPlaceholderText("Иванов")
        self.last_name_input.textChanged.connect(self._update_preview)
        form.addRow("Фамилия", self.last_name_input)

        self.first_name_input = QLineEdit()
        self.first_name_input.setPlaceholderText("Иван")
        self.first_name_input.textChanged.connect(self._update_preview)
        form.addRow("Имя", self.first_name_input)

        self.middle_name_input = QLineEdit()
        self.middle_name_input.setPlaceholderText("Иванович")
        self.middle_name_input.textChanged.connect(self._update_preview)
        form.addRow("Отчество", self.middle_name_input)

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Слесарь")
        form.addRow("Должность", self.position_input)
        lay.addLayout(form)
        lay.addStretch()
        return card

    def _build_exam_card(self):
        from utils.ui_helpers import make_card, set_role, set_char_width
        card, lay = make_card("Проверка знаний")
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        prog_row = QHBoxLayout()
        self.programs_input = QLineEdit()
        self.programs_input.setPlaceholderText("1, 3, 18 (через запятую)")
        prog_row.addWidget(self.programs_input, 1)
        help_btn = QPushButton("Справочник")
        set_role(help_btn, "secondary")
        help_btn.setObjectName("programHelpBtn")
        help_btn.clicked.connect(self._show_programs_help)
        prog_row.addWidget(help_btn)
        form.addRow("Программы", prog_row)

        self.exam_date_input = QLineEdit()
        self.exam_date_input.setPlaceholderText("ДД.ММ.ГГГГ")
        set_char_width(self.exam_date_input, 12)
        form.addRow("Дата проверки", self.exam_date_input)

        self.protocol_input = QLineEdit()
        self.protocol_input.setPlaceholderText("1")
        set_char_width(self.protocol_input, 14)
        self.protocol_input.textChanged.connect(self._update_preview)
        form.addRow("Номер протокола", self.protocol_input)

        self.result_combo = QComboBox()
        self.result_combo.addItems(["Удовлетворительно", "Неудовлетворительно", "Не сдавал"])
        form.addRow("Результат", self.result_combo)

        self.base_no_input = QLineEdit()
        self.base_no_input.setPlaceholderText("если получен")
        form.addRow("Рег. номер", self.base_no_input)
        lay.addLayout(form)
        lay.addStretch()
        return card

    def _build_commission_bar(self):
        from utils.ui_helpers import set_role
        bar = QFrame()
        bar.setObjectName("commissionBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.commission_label = QLabel("не загружены")
        self.commission_label.setObjectName("commissionState")
        text.addWidget(self.commission_label)
        self.org_details_label = QLabel()
        self.org_details_label.setObjectName("hintLabel")
        self.org_details_label.setWordWrap(True)
        text.addWidget(self.org_details_label)
        row.addLayout(text, 1)

        load_btn = QPushButton("Подставить комиссию")
        set_role(load_btn, "secondary")
        load_btn.setObjectName("loadCommissionBtn")
        load_btn.setToolTip("Загрузить сохранённые данные комиссии")
        load_btn.clicked.connect(self._load_commission)
        row.addWidget(load_btn)
        self._commission_bar = bar
        return bar

    def _build_preview(self):
        self.preview_label = QLabel()
        self.preview_label.setObjectName("hintLabel")
        self.preview_label.setWordWrap(True)
        return self.preview_label

    def _update_preview(self):
        last = self.last_name_input.text().strip() or "одиночный"
        proto = self.protocol_input.text().strip() or "1"
        from utils.export_safe import safe_filename_part
        name = f"Протокол_{safe_filename_part(last, 'одиночный')}_№{safe_filename_part(proto, '1')}.docx"
        self.preview_label.setText(f"Файл: {name}")

    def _load_commission(self):
        from protocol.commission_manager import CommissionManager
        cm = CommissionManager(self.data_dir)
        self.commission_data = cm.load()
        org = self.commission_data.get("org_name", "").strip()
        if org:
            self.commission_label.setText(f"Комиссия загружена. Организация: {org}")
            self._set_commission_state("ok")
        else:
            self.commission_label.setText("Данные комиссии не заполнены: укажите их в разделе «Настройка протоколов»")
            self._set_commission_state("warn")

        details = []
        if org:
            details.append(f"Организация: {org}")
        if self.commission_data.get("order_number"):
            details.append(f"Приказ №{self.commission_data['order_number']}")
        if self.commission_data.get("chairman_fio"):
            details.append(f"Председатель: {self.commission_data['chairman_fio']}")
        self.org_details_label.setText(" | ".join(details) if details else "")

        if self.commission_data.get("exam_date"):
            self.exam_date_input.setText(self.commission_data["exam_date"])

    def _set_commission_state(self, state: str):
        for widget in (self._commission_bar, self.commission_label):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _show_programs_help(self):
        from PySide6.QtWidgets import QDialog
        from utils.programs_picker import ProgramsPickerDialog, merge_program_ids
        current = [p.strip() for p in self.programs_input.text().split(",") if p.strip()]
        items = [(pid, info.get("name", "")) for pid, info in self.programs.get_all_programs().items()]
        dlg = ProgramsPickerDialog(self, items, current)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.programs_input.setText(merge_program_ids(self.programs_input.text(), dlg.selected_ids()))

    def _generate_protocol(self):
        last = self.last_name_input.text().strip()
        first = self.first_name_input.text().strip()
        middle = self.middle_name_input.text().strip()
        position = self.position_input.text().strip()
        prog_str = self.programs_input.text().strip()
        exam_date = self.exam_date_input.text().strip()
        protocol = self.protocol_input.text().strip()
        result = self.result_combo.currentText()
        base_no = self.base_no_input.text().strip()

        if not last and not first and not position and not prog_str and not exam_date:
            QMessageBox.warning(self, "Ошибка", "Заполните хотя бы одно поле")
            return

        program_ids = [p.strip() for p in prog_str.split(",") if p.strip()]
        program_titles = []
        for pid in program_ids:
            prog = self.programs.get_program(pid)
            if prog:
                name = prog.get("name", f"Программа {pid}")
                hours = prog.get("hours", "")
                doc = prog.get("doc", "")
                title = name
                if hours:
                    title = f'{hours}-часовая программа {pid} "{name}"'
                elif doc:
                    title = f"{title} - {doc}"
            else:
                title = f"Программа {pid}"
            program_titles.append(title)

        worker_records = []
        for pid, ptitle in zip(program_ids, program_titles):
            worker_records.append({
                "last_name": last, "first_name": first, "middle_name": middle,
                "snils": "", "position": position,
                "employer_inn": "", "employer_title": "",
                "tc_inn": "", "tc_title": "",
                "result": result, "program": ptitle, "program_id": pid,
                "date": exam_date, "protocol": protocol, "base_no": base_no,
            })

        if not worker_records:
            worker_records.append({
                "last_name": last, "first_name": first, "middle_name": middle,
                "snils": "", "position": position,
                "employer_inn": "", "employer_title": "",
                "tc_inn": "", "tc_title": "",
                "result": result, "program": "", "program_id": "",
                "date": exam_date, "protocol": protocol, "base_no": base_no,
            })

        proto_num = protocol or "1"
        from utils.export_safe import safe_filename_part
        default_file = f"Протокол_{safe_filename_part(last, 'одиночный')}_№{safe_filename_part(proto_num, '1')}.docx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить протокол", default_file, "Word Files (*.docx)"
        )
        if not file_path:
            return

        from utils.app_paths import get_resource_dir
        template_path = os.path.join(
            get_resource_dir(), "templates",
            "Protokol_proverki_znanii_OT.docx"
        )

        success, msg = ProtocolExporter.generate_from_commission(
            commission_data=self.commission_data,
            protocol_number=proto_num,
            worker_records=worker_records,
            programs_manager=self.programs,
            output_path=file_path,
            template_path=template_path,
            data_dir=self.data_dir
        )

        if success:
            QMessageBox.information(self, "Успех", f"Протокол сохранён:\n{file_path}")
        else:
            QMessageBox.warning(self, "Ошибка", msg)