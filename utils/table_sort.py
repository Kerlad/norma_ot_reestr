"""Shared table sorting: header click cycles ascending -> descending -> off (natural order).

Dates (ДД.ММ.ГГГГ) and numbers compare by value, empty cells go last in both directions.
"""
import re
from typing import Callable, Optional

from PySide6.QtCore import QObject, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget

NATURAL_ROLE = Qt.ItemDataRole.UserRole + 301   # original row position (QTableWidget helper)
SORT_ROLE = Qt.ItemDataRole.UserRole + 302      # optional explicit sort key on an item / model index

_DATE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s.*)?$")
_NUMBER = re.compile(r"^\s*-?\d+(?:[.,]\d+)?\s*$")


def smart_key(value) -> tuple:
    """Sort key: empties last, dates by date, numbers by value, text case-insensitive."""
    if value is None:
        return (3, 0, "")
    if isinstance(value, (int, float)):
        return (1, float(value), "")
    text = str(value).strip()
    if not text or text in ("—", "-"):
        return (3, 0, "")
    m = _DATE.match(text)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        return (0, y * 10000 + mo * 100 + d, "")
    if _NUMBER.match(text):
        return (1, float(text.replace(",", ".")), "")
    return (2, 0, text.lower())


def _ordered(keys_rows, order: Qt.SortOrder):
    """Sort (key, payload) pairs; empty cells (group 3) stay last for both directions."""
    filled = [kr for kr in keys_rows if kr[0][0] != 3]
    empty = [kr for kr in keys_rows if kr[0][0] == 3]
    filled.sort(key=lambda kr: kr[0], reverse=(order == Qt.SortOrder.DescendingOrder))
    return filled + empty


class TriStateSort(QObject):
    """Connects a header to a sort callback with three states.

    apply(column, order) is called with order=None to restore the natural order.
    """

    def __init__(self, header: QHeaderView, apply: Callable[[int, Optional[Qt.SortOrder]], None],
                 skip_columns=()):
        super().__init__(header)
        self._header = header
        self._apply = apply
        self._skip = set(skip_columns)
        self.column = -1
        self.order: Optional[Qt.SortOrder] = None
        self.on_sorted: Optional[Callable[[], None]] = None
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self.on_clicked)

    def on_clicked(self, column: int) -> None:
        if column in self._skip:
            return
        if column != self.column:
            self.column, self.order = column, Qt.SortOrder.AscendingOrder
        elif self.order == Qt.SortOrder.AscendingOrder:
            self.order = Qt.SortOrder.DescendingOrder
        else:
            self.column, self.order = -1, None
        self._header.setSortIndicator(self.column, self.order or Qt.SortOrder.AscendingOrder)
        self._apply(self.column, self.order)
        if self.on_sorted:
            self.on_sorted()

    def reapply(self) -> None:
        """Re-sort after the data was reloaded (keeps the user's current sort)."""
        if self.column >= 0 and self.order is not None:
            self._apply(self.column, self.order)

    def reset(self) -> None:
        self.column, self.order = -1, None
        self._header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)


def install_model_sort(view, skip_columns=()) -> TriStateSort:
    """For QTableView whose (proxy) model implements sort(); column -1 means natural order."""
    view.setSortingEnabled(False)
    header = view.horizontalHeader()

    def apply(column, order):
        view.model().sort(column, order if order is not None else Qt.SortOrder.AscendingOrder)

    sorter = TriStateSort(header, apply, skip_columns)
    view._tristate_sort = sorter
    return sorter


def mark_natural_order(table: QTableWidget) -> None:
    """Remember the current row order as the natural one (call after the table is filled)."""
    for r in range(table.rowCount()):
        for c in range(table.columnCount()):
            item = table.item(r, c)
            if item is not None:
                item.setData(NATURAL_ROLE, r)
                break


def _row_natural(items) -> int:
    for item in items:
        if item is not None:
            v = item.data(NATURAL_ROLE)
            if v is not None:
                return int(v)
    return 0


def sort_table_widget(table: QTableWidget, column: int, order: Optional[Qt.SortOrder]) -> None:
    """Sort plain-item QTableWidget rows; order None restores the natural order."""
    rows = table.rowCount()
    cols = table.columnCount()
    data = []
    for r in range(rows):
        items = [table.takeItem(r, c) for c in range(cols)]
        data.append(items)
    if column < 0 or order is None:
        data.sort(key=_row_natural)
    else:
        def key_of(items):
            item = items[column] if column < len(items) else None
            if item is None:
                return smart_key(None)
            explicit = item.data(SORT_ROLE)
            return smart_key(explicit if explicit is not None else item.text())
        data = [p for _, p in _ordered([(key_of(items), items) for items in data], order)]
    table.setUpdatesEnabled(False)
    for r, items in enumerate(data):
        for c, item in enumerate(items):
            if item is not None:
                table.setItem(r, c, item)
    table.setUpdatesEnabled(True)


def install_widget_sort(table: QTableWidget, skip_columns=()) -> TriStateSort:
    """Three-state sorting for a plain QTableWidget. Call sorter.reload_done() after refilling."""
    table.setSortingEnabled(False)

    def apply(column, order):
        sort_table_widget(table, column, order)

    sorter = TriStateSort(table.horizontalHeader(), apply, skip_columns)

    def reload_done():
        mark_natural_order(table)
        sorter.reapply()

    sorter.reload_done = reload_done
    mark_natural_order(table)
    table._tristate_sort = sorter
    return sorter


class SmartSortProxyModel(QSortFilterProxyModel):
    """Proxy that sorts by smart_key of SORT_ROLE (falls back to the display text)."""

    def lessThan(self, left, right):
        lv = left.data(SORT_ROLE)
        rv = right.data(SORT_ROLE)
        if lv is None:
            lv = left.data(Qt.ItemDataRole.DisplayRole)
        if rv is None:
            rv = right.data(Qt.ItemDataRole.DisplayRole)
        kl, rk = smart_key(lv), smart_key(rv)
        left_empty, right_empty = kl[0] == 3, rk[0] == 3
        if left_empty != right_empty and self.sortOrder() == Qt.SortOrder.DescendingOrder:
            # Qt reverses lessThan for descending order; keep empty cells last anyway
            return left_empty
        return kl < rk
