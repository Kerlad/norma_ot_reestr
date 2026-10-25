"""«Справочник» программ обучения: список с множественным выбором, один вид для всех форм."""
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from utils.dialog_base import BaseDialog
from utils.ui_helpers import hint_label


class ProgramsPickerDialog(BaseDialog):
    """Выбор номеров программ. После accept() результат в selected_ids()."""

    def __init__(self, parent, items: List[Tuple[str, str]], current: Optional[List[str]] = None,
                 title: str = "Программы обучения", accept_text: str = "Добавить выбранные"):
        super().__init__(parent, title, min_width=640, min_height=560,
                         subtitle="Отметьте программы. Двойной щелчок добавляет одну программу сразу.")
        current = set(current or [])
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for pid, label in items:
            item = QListWidgetItem("%s: %s" % (pid, label))
            item.setData(Qt.ItemDataRole.UserRole, pid)
            item.setToolTip(label)
            self._list.addItem(item)
            if pid in current:
                item.setSelected(True)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self.body_layout().addWidget(self._list, 1)
        self.body_layout().addWidget(hint_label("Выбранные ранее программы уже отмечены."))
        self._chosen: List[str] = []
        self.add_action_buttons(accept_text, self._accept_selected)

    def _accept_selected(self):
        self._chosen = [it.data(Qt.ItemDataRole.UserRole) for it in self._list.selectedItems()]
        if not self._chosen:
            return
        self.accept()

    def _on_double_click(self, item):
        self._chosen = [item.data(Qt.ItemDataRole.UserRole)]
        self.accept()

    def selected_ids(self) -> List[str]:
        """Номера в порядке справочника."""
        order = {self._list.item(i).data(Qt.ItemDataRole.UserRole): i for i in range(self._list.count())}
        return sorted(self._chosen, key=lambda p: order.get(p, 0))


def merge_program_ids(existing_text: str, chosen: List[str]) -> str:
    """Добавляет номера к тексту поля («1, 3») без повторов, по возрастанию."""
    ids = {p.strip() for p in existing_text.split(",") if p.strip()}
    ids.update(chosen)
    return ", ".join(sorted(ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x)))
