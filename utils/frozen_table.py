"""Table with frozen left columns and a two-level (grouped) header.

`FrozenColumnsTable` is the standard Qt "frozen column" technique: a second QTableView of the same
model/selection overlays the first N columns of the main view, so they stay put during horizontal
scrolling. The width of the frozen part is the sum of the real column widths, so resizing a frozen
column with the mouse works (and persists through HeaderStatePersistence on `horizontalHeader()`).
"""
from typing import List, Tuple

from PySide6.QtCore import QModelIndex, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPolygonF
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QTableView

LEVEL_HEIGHT = 28


def _colors():
    from utils.tahoe_style import get_colors, get_current_theme
    return get_colors(get_current_theme())


class GroupedHeaderView(QHeaderView):
    """Horizontal header: plain 12 px muted labels; optional group titles above sub-columns."""

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._groups = {}
        self._levels = 1
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setFixedHeight(LEVEL_HEIGHT)

    def set_levels(self, levels: int) -> None:
        self._levels = max(1, levels)
        self.setFixedHeight(LEVEL_HEIGHT * self._levels)

    def set_groups(self, groups: List[Tuple[int, int, str]]) -> None:
        """groups = [(first_column, column_count, title), ...]"""
        self._groups = {}
        for start, count, title in groups:
            for col in range(start, start + count):
                self._groups[col] = (start, count, title)
        self.set_levels(2 if groups else self._levels)
        self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        if not rect.isValid():
            return
        c = _colors()
        painter.save()
        painter.fillRect(rect, QColor(c.surface_subtle))
        painter.setPen(QColor(c.border))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        group = self._groups.get(logicalIndex)
        inside_group = group is not None and logicalIndex != group[0] + group[1] - 1
        # no vertical line through the group title, only between the sub-columns
        painter.drawLine(rect.topRight() + QPoint(0, rect.height() // 2 if inside_group else 0), rect.bottomRight())
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        model = self.model()
        label = str(model.headerData(logicalIndex, Qt.Orientation.Horizontal) or "") if model else ""
        pad = 8
        if group:
            start, count, title = group
            gx = self.sectionViewportPosition(start)
            gw = sum(self.sectionSize(i) for i in range(start, start + count))
            half = rect.height() // 2
            painter.save()
            painter.setClipRect(QRect(rect.x(), rect.y(), rect.width(), half))
            painter.setPen(QColor(c.text_secondary))
            painter.drawText(QRect(gx + pad, rect.y(), max(gw - 2 * pad, 0), half), int(Qt.AlignmentFlag.AlignCenter),
                             metrics.elidedText(title, Qt.TextElideMode.ElideRight, max(gw - 2 * pad, 0)))
            painter.restore()
            painter.setPen(QColor(c.border))
            painter.drawLine(rect.left(), rect.y() + half, rect.right(), rect.y() + half)
            text_rect = QRect(rect.x() + pad, rect.y() + half, max(rect.width() - 2 * pad, 0), rect.height() - half)
        else:
            text_rect = QRect(rect.x() + pad, rect.y(), max(rect.width() - 2 * pad, 0), rect.height())
        painter.setPen(QColor(c.text_muted))
        align = Qt.AlignmentFlag.AlignVCenter | (
            Qt.AlignmentFlag.AlignLeft if logicalIndex == 0 and not group else Qt.AlignmentFlag.AlignHCenter)
        reserve = 14 if (self.isSortIndicatorShown() and self.sortIndicatorSection() == logicalIndex) else 0
        painter.drawText(text_rect.adjusted(0, 0, -reserve, 0), int(align),
                         metrics.elidedText(label, Qt.TextElideMode.ElideRight, max(text_rect.width() - reserve, 0)))
        if reserve:
            cx, cy = rect.right() - 10, text_rect.center().y()
            up = self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
            tri = QPolygonF([QPointF(cx - 4, cy + (2 if up else -2)), QPointF(cx + 4, cy + (2 if up else -2)),
                             QPointF(cx, cy + (-3 if up else 3))])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c.link))
            painter.drawPolygon(tri)
        painter.restore()


class FrozenColumnsTable(QTableView):
    """QTableView whose first `frozen_columns` columns do not scroll horizontally."""

    header_clicked = Signal(int)
    cell_double_clicked = Signal(QModelIndex)
    context_menu_requested = Signal(QPoint, QModelIndex)

    def __init__(self, frozen_columns: int = 3, parent=None):
        super().__init__(parent)
        self._n = frozen_columns
        self.setHorizontalHeader(GroupedHeaderView(self))
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(False)

        self._frozen = QTableView(self)
        self._frozen.setObjectName("frozenColumns")
        self._frozen.setHorizontalHeader(GroupedHeaderView(self._frozen))
        self._frozen.verticalHeader().hide()
        self._frozen.setShowGrid(False)
        self._frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._frozen.setFrameShape(QFrame.Shape.NoFrame)
        self._frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._frozen.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._frozen.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._frozen.viewport().setAutoFillBackground(True)
        self._divider = QFrame(self)
        self._divider.setObjectName("frozenDivider")
        self._divider.setFixedWidth(1)

        self._frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.verticalScrollBar().valueChanged.connect(self._frozen.verticalScrollBar().setValue)
        self.horizontalHeader().sectionResized.connect(self._on_main_section_resized)
        self._frozen.horizontalHeader().sectionResized.connect(self._on_frozen_section_resized)
        self.horizontalHeader().sectionClicked.connect(self.header_clicked)
        self._frozen.horizontalHeader().sectionClicked.connect(self.header_clicked)
        self._frozen.doubleClicked.connect(self.cell_double_clicked)
        self.doubleClicked.connect(self.cell_double_clicked)
        for view in (self, self._frozen):
            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.customContextMenuRequested.connect(lambda pos, v=view: self._emit_context(v, pos))

    # -- model ---------------------------------------------------------------

    def setModel(self, model):
        super().setModel(model)
        self._frozen.setModel(model)
        self._frozen.setSelectionModel(self.selectionModel())
        for signal in (model.modelReset, model.columnsInserted, model.columnsRemoved, model.layoutChanged):
            signal.connect(lambda *a: self.sync_frozen())
        self.sync_frozen()

    def set_item_delegate(self, delegate):
        self.setItemDelegate(delegate)
        self._frozen.setItemDelegate(delegate)

    def set_row_height(self, height: int):
        self.verticalHeader().setDefaultSectionSize(height)
        self._frozen.verticalHeader().setDefaultSectionSize(height)

    def frozen_columns(self) -> int:
        return self._n

    def frozen_view(self) -> QTableView:
        return self._frozen

    def frozen_header(self) -> GroupedHeaderView:
        return self._frozen.horizontalHeader()

    def set_sort_indicator(self, column: int, order: Qt.SortOrder) -> None:
        self.horizontalHeader().setSortIndicator(column, order)
        self._frozen.horizontalHeader().setSortIndicator(column, order)
        self.viewport().update()
        self._frozen.viewport().update()

    def set_header_levels(self, levels: int) -> None:
        self.horizontalHeader().set_levels(levels)
        self._frozen.horizontalHeader().set_levels(levels)

    # -- frozen geometry -------------------------------------------------------

    def sync_frozen(self) -> None:
        model = self.model()
        if model is None:
            return
        for col in range(model.columnCount()):
            self._frozen.setColumnHidden(col, col >= self._n)
        for col in range(min(self._n, model.columnCount())):
            self._frozen.setColumnWidth(col, self.columnWidth(col))
        self._frozen.horizontalHeader().setSortIndicatorShown(self.horizontalHeader().isSortIndicatorShown())
        self._update_frozen_geometry()

    def _on_main_section_resized(self, column, old, new):
        if column < self._n:
            self._frozen.setColumnWidth(column, new)
            self._update_frozen_geometry()

    def _on_frozen_section_resized(self, column, old, new):
        if column < self._n and self.columnWidth(column) != new:
            self.setColumnWidth(column, new)
            self._update_frozen_geometry()

    def _update_frozen_geometry(self) -> None:
        if getattr(self, "_divider", None) is None:
            return  # called by Qt while the widget is still being constructed
        model = self.model()
        count = min(self._n, model.columnCount()) if model else 0
        width = sum(self.columnWidth(c) for c in range(count))
        fw = self.frameWidth()
        x = self.verticalHeader().width() + fw
        height = self.viewport().height() + self.horizontalHeader().height()
        self._frozen.setGeometry(x, fw, width, height)
        self._divider.setGeometry(x + width - 1, fw, 1, height)
        self._frozen.setVisible(count > 0)
        self._divider.setVisible(count > 0)
        self._divider.raise_()

    def updateGeometries(self):
        super().updateGeometries()
        self._update_frozen_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_frozen_geometry()

    # -- navigation ----------------------------------------------------------------

    def moveCursor(self, action, modifiers):
        current = super().moveCursor(action, modifiers)
        if (action == QAbstractItemView.CursorAction.MoveLeft and current.column() >= self._n
                and self.visualRect(current).topLeft().x() < self._frozen.width()):
            shift = self.visualRect(current).topLeft().x() - self._frozen.width()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + shift)
        return current

    def scrollTo(self, index, hint=QAbstractItemView.ScrollHint.EnsureVisible):
        if index.column() >= self._n:
            super().scrollTo(index, hint)

    def _emit_context(self, view, pos):
        self.context_menu_requested.emit(view.viewport().mapToGlobal(pos), view.indexAt(pos))
