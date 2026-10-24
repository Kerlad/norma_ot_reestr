"""
Общие UI-хелперы (без хардкод-цветов): пометка полей через тему,
курсор ожидания для длительных операций и заглушка пустой таблицы.
"""
import base64
import json
import logging
import os
from contextlib import contextmanager

from PySide6.QtCore import Qt, QEvent, QObject, QTimer, QByteArray
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QLabel

logger = logging.getLogger(__name__)


def set_field_state(widget, state=None):
    """Пометить поле как 'invalid'/'warning' или сбросить (None).
    Цвет берётся из глобальной темы (см. tahoe_style), без хардкода."""
    try:
        widget.setProperty("fieldState", state or "")
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
    except Exception:
        logger.exception("set_field_state failed")


def mark_invalid(widget, invalid=True):
    set_field_state(widget, "invalid" if invalid else None)


def mark_warning(widget, warning=True):
    set_field_state(widget, "warning" if warning else None)


@contextmanager
def busy_cursor():
    """Курсор ожидания на время длительной синхронной операции."""
    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    try:
        QApplication.processEvents()
        yield
    finally:
        QApplication.restoreOverrideCursor()


class EmptyStateOverlay(QLabel):
    """Подсказка по центру таблицы, когда в ней нет строк."""

    def __init__(self, table, text):
        super().__init__(text, table.viewport())
        self._table = table
        self.setObjectName("tableEmptyState")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        table.viewport().installEventFilter(self)
        model = table.model()
        if model is not None:
            for sig in ("modelReset", "rowsInserted", "rowsRemoved", "layoutChanged"):
                try:
                    getattr(model, sig).connect(self._refresh)
                except Exception:
                    pass
        self._refresh()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
        return False

    def _row_count(self):
        model = self._table.model()
        return model.rowCount() if model is not None else 0

    def _refresh(self, *args):
        try:
            self.setGeometry(self._table.viewport().rect())
            self.setVisible(self._row_count() == 0)
            self.raise_()
        except Exception:
            pass


TABLE_LAYOUTS_FILE = "table_layouts.json"


class HeaderStatePersistence(QObject):
    """Сохраняет ширину/порядок/видимость столбцов таблицы между запусками.

    Состояние QHeaderView.saveState() (base64) хранится в
    %APPDATA%/NormaOT/table_layouts.json под ключом `key`. ПДн не содержит.
    Состояние не восстанавливается, если число столбцов изменилось.
    """

    SAVE_DELAY_MS = 500

    def __init__(self, header, key, data_dir=None):
        super().__init__(header)
        self._header = header
        self._key = key
        if data_dir is None:
            from utils.app_paths import get_app_data_dir
            data_dir = get_app_data_dir()
        self._path = os.path.join(data_dir, TABLE_LAYOUTS_FILE)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.SAVE_DELAY_MS)
        self._timer.timeout.connect(self.save)
        self.restored = self.restore()
        header.sectionResized.connect(self.schedule_save)
        header.sectionMoved.connect(self.schedule_save)

    def _read_all(self) -> dict:
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def restore(self) -> bool:
        entry = self._read_all().get(self._key)
        if not isinstance(entry, dict) or entry.get('columns') != self._header.count():
            return False
        try:
            state = QByteArray(base64.b64decode(entry.get('state', '')))
        except (ValueError, TypeError):
            return False
        return bool(self._header.restoreState(state))

    def schedule_save(self, *args):
        self._timer.start()

    def save(self):
        self._timer.stop()
        data = self._read_all()
        data[self._key] = {
            'columns': self._header.count(),
            'state': base64.b64encode(bytes(self._header.saveState())).decode('ascii'),
        }
        tmp = self._path + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
        except OSError as e:
            logger.debug("Failed to save table layout '%s': %s", self._key, e)


def set_char_width(edit, chars: int, sample: str = "0") -> int:
    """Фиксированная ширина поля ввода под `chars` символов текущего шрифта
    (с учётом рамки и отступов стиля). Возвращает установленную ширину."""
    from PySide6.QtWidgets import QStyle, QStyleOptionFrame
    edit.ensurePolished()
    fm = edit.fontMetrics()
    text_w = fm.horizontalAdvance(sample * chars)
    margins = edit.textMargins()
    opt = QStyleOptionFrame()
    edit.initStyleOption(opt)
    from PySide6.QtCore import QSize
    size = edit.style().sizeFromContents(
        QStyle.ContentsType.CT_LineEdit, opt,
        QSize(text_w + margins.left() + margins.right() + 4, fm.height()), edit)
    edit.setFixedWidth(size.width())
    return size.width()


def open_folder(path: str, select_file: str = None) -> None:
    """Show a folder in the file manager. Windows: Explorer (selecting the file if given);
    elsewhere: the desktop's default handler for the folder."""
    import subprocess
    from utils import platform_info
    if platform_info.IS_WINDOWS:
        if select_file:
            subprocess.Popen(f'explorer /select,"{select_file}"')
        else:
            subprocess.Popen(['explorer', path])
        return
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    folder = os.path.dirname(select_file) if select_file else path
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


def monospace_font(point_size: int = 10):
    """Windows keeps Consolas; elsewhere the system fixed font."""
    from PySide6.QtGui import QFont, QFontDatabase
    from utils import platform_info
    if platform_info.IS_WINDOWS:
        return QFont("Consolas", point_size)
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(point_size)
    return font
