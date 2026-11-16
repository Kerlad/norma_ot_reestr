"""«Истекает скоро»: employees whose training ends within N days (C4).

Counting rule (shared by the sidebar line and the «Сводка» chip): an employee counts when
every program with need_training=1 is currently 'trained' and at least one of them has
0 <= days_to_expiry <= N. Employees that are already «Не обучен» or «Просрочено» are
excluded: they are counted by their own cards. (An exam whose period ends today is already
'expired' by get_dynamic_status, so the 0-day edge is reported there, not here.)
"""
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from utils.training_rules import days_to_expiry, get_dynamic_status

PERIOD_CHOICES = (30, 60, 90)
DEFAULT_PERIOD = 60
SIDEBAR_PERIOD = 60
PREF_PERIOD = "summary_expiry_days"


def employee_expires_within(programs: Iterable[dict], days: int, b_period_3years: bool = True) -> bool:
    """True if the employee is fully trained and some program expires within `days` days."""
    soonest: Optional[int] = None
    found = False
    for pr in programs:
        if pr.get("need_training") != 1:
            continue
        found = True
        exam_date = pr.get("exam_date", "")
        pid = pr.get("program_id", 0)
        status = get_dynamic_status(pr.get("status", "not_trained"), exam_date, pid,
                                    b_period_3years, result=pr.get("result"))
        if status != "trained":
            return False
        d = days_to_expiry(exam_date, pid, b_period_3years)
        if d is not None and (soonest is None or d < soonest):
            soonest = d
    return found and soonest is not None and 0 <= soonest <= days


def load_period() -> int:
    from tabs.send_history_panel import load_ui_pref
    try:
        value = int(load_ui_pref(PREF_PERIOD, DEFAULT_PERIOD))
    except (TypeError, ValueError):
        return DEFAULT_PERIOD
    return value if value in PERIOD_CHOICES else DEFAULT_PERIOD


class ExpiryFilter(QWidget):
    """Chip «Истекает скоро · N» plus a 30/60/90 days combo; `changed` fires on any change."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.chip = QPushButton()
        self.chip.setObjectName("chip")
        self.chip.setProperty("kind", "warn")
        self.chip.setCheckable(True)
        self.chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chip.setToolTip("Показать только сотрудников, у которых обучение истекает в выбранный срок "
                             "(повторный щелчок снимает фильтр)")
        self.combo = QComboBox()
        self.combo.setObjectName("filterCombo")
        for d in PERIOD_CHOICES:
            self.combo.addItem("%d дн." % d, d)
        self.combo.setCurrentIndex(PERIOD_CHOICES.index(load_period()))
        self.combo.setToolTip("За сколько дней до окончания срока обучения")
        lay.addWidget(self.chip)
        lay.addWidget(self.combo)
        self._count = 0
        self._refresh_text()
        self.chip.clicked.connect(lambda *_: self.changed.emit())
        self.combo.currentIndexChanged.connect(self._on_period)

    def _on_period(self, _index: int) -> None:
        from tabs.send_history_panel import save_ui_pref
        save_ui_pref(PREF_PERIOD, self.days())
        self.changed.emit()

    def days(self) -> int:
        return int(self.combo.currentData() or DEFAULT_PERIOD)

    def active(self) -> bool:
        return self.chip.isChecked()

    def set_count(self, count: int) -> None:
        self._count = count
        self._refresh_text()

    def _refresh_text(self) -> None:
        self.chip.setText("Истекает скоро · %d" % self._count)
