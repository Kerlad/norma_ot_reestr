"""
Worker-классы для длительных операций в фоновых QThread.
Safe exception handling - no PII in error messages.
"""
import logging
from PySide6.QtCore import Signal, QObject

logger = logging.getLogger(__name__)


def _safe_error_msg(msg: str, exc: BaseException) -> str:
    """Create a safe error message without PII."""
    from utils.logger import filter_sensitive_text
    exc_type = type(exc).__name__
    safe_str = filter_sensitive_text(str(exc)[:200])
    return f"{msg}: [{exc_type}] {safe_str}"


class ExcelImportWorker(QObject):
    progress = Signal(int, int)
    status_message = Signal(str)
    finished = Signal(list, int, list, str)
    error = Signal(str)
    cancelled = Signal()

    def __init__(self, file_path: str, password: str = ""):
        super().__init__()
        self.file_path = file_path
        self.password = password
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            from importers.xlsx_importer import load_xlsx

            self.status_message.emit("Открытие файла...")
            self.progress.emit(0, 0)

            if self._cancelled:
                self.cancelled.emit()
                return

            def on_progress(current, total):
                self.progress.emit(current, total)
                if current % 1000 == 0:
                    self.status_message.emit(f"Обработано строк: {current}")

            def on_cancel():
                return self._cancelled

            records, error_details, error_rows_set, error_msg = load_xlsx(
                self.file_path, self.password,
                progress_callback=on_progress,
                cancel_check=on_cancel
            )

            if self._cancelled:
                self.status_message.emit("Импорт отменён")
                from utils.audit import log_audit
                log_audit("IMPORT_CANCELLED", "XLSX import cancelled")
                self.cancelled.emit()
                return

            error_count = len(error_details)
            self.status_message.emit("Импорт завершён")
            self.finished.emit(records, error_count, error_details, error_msg)

        except Exception as e:
            logger.exception("Excel import failed")
            self.error.emit(_safe_error_msg("Ошибка импорта", e))
