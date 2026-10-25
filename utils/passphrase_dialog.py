import os
import sys
import shutil
import logging
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialog,
    QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, QProcess
from PySide6.QtGui import QPixmap, QIcon
from utils.crypto import verify_passphrase, CryptoPassphraseRequiredError
from utils.app_paths import get_resource_dir
from utils.about_dialog import VERSION
from utils.audit import log_audit


logger = logging.getLogger(__name__)


class PassphraseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подтверждение парольной фразы")
        self.setMinimumSize(460, 360)
        self.setMaximumSize(640, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        icon_path = os.path.join(get_resource_dir(), "resources", "ico.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        from utils.ui_helpers import make_dark_plate, set_role, mark_invalid, hint_label
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        plate_icon = os.path.join(get_resource_dir(), "resources", "icon.png")
        if not os.path.exists(plate_icon):
            plate_icon = icon_path
        plate, _ = make_dark_plate("Норма ОТ: Реестр обучения", f"Версия {VERSION}", plate_icon, 56)
        outer.addWidget(plate)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        outer.addLayout(layout)

        prompt = QLabel("Для доступа к зашифрованным данным требуется парольная фраза.")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        layout.addWidget(hint_label(
            "Мастер-ключ зашифрован парольной фразой (PBKDF2, 600 000 итераций). "
            "Без неё расшифровать сохранённые персональные данные невозможно."))

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("Введите парольную фразу")
        self.pwd_input.setMinimumHeight(38)
        self.pwd_input.returnPressed.connect(self._on_accept)
        layout.addWidget(self.pwd_input)

        btn_row = QHBoxLayout()

        forgot_btn = QPushButton("Не помню парольную фразу…")
        set_role(forgot_btn, "ghost")
        forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        forgot_btn.setToolTip(
            "Удалить все данные приложения, чтобы войти без парольной фразы"
        )
        forgot_btn.clicked.connect(self._reset_all_data)
        btn_row.addWidget(forgot_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        set_role(cancel_btn, "secondary")
        cancel_btn.setMinimumHeight(38)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Разблокировать")
        set_role(ok_btn, "primary")
        ok_btn.setMinimumHeight(38)
        ok_btn.setMinimumWidth(140)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

        self._wrong_attempts: int = 0
        self._MAX_ATTEMPTS: int = 5
        self._BASE_DELAY_MS: int = 1000
        self.ok_btn = ok_btn

        self.pwd_input.setFocus()

    def _on_accept(self):
        from utils.ui_helpers import mark_invalid
        pp = self.pwd_input.text()
        if not pp:
            mark_invalid(self.pwd_input)
            self.pwd_input.setPlaceholderText("Введите парольную фразу (обязательно)")
            return
        try:
            if verify_passphrase(pp):
                logger.info("Passphrase verified at startup")
                self.accept()
            else:
                self._show_wrong()
        except CryptoPassphraseRequiredError:
            self._show_wrong()

    def _show_wrong(self):
        from utils.ui_helpers import mark_invalid
        self._wrong_attempts += 1
        log_audit("SESSION_LOCK",
                  f"Wrong passphrase attempt {self._wrong_attempts}/{self._MAX_ATTEMPTS}")
        if self._wrong_attempts >= self._MAX_ATTEMPTS:
            log_audit("SECURITY_WARNING",
                      f"Max passphrase attempts ({self._MAX_ATTEMPTS}) reached — forcing exit")
            QMessageBox.critical(
                self, "Превышено число попыток",
                f"Введено {self._MAX_ATTEMPTS} неверных парольных фраз.\n"
                "Приложение будет закрыто в целях безопасности."
            )
            self.reject()
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        delay_ms = self._BASE_DELAY_MS * (2 ** (self._wrong_attempts - 1))
        delay_ms = min(delay_ms, 30_000)
        self.ok_btn.setEnabled(False)
        self.pwd_input.setEnabled(False)
        mark_invalid(self.pwd_input)
        self.pwd_input.setPlaceholderText(
            f"Неверно. Подождите {delay_ms // 1000} сек..."
        )
        QTimer.singleShot(delay_ms, self._restore_after_delay)

    def _restore_after_delay(self):
        from utils.ui_helpers import mark_invalid
        self.pwd_input.setEnabled(True)
        self.ok_btn.setEnabled(True)
        mark_invalid(self.pwd_input, False)
        self.pwd_input.clear()
        self.pwd_input.setPlaceholderText("Введите парольную фразу")
        self.pwd_input.setFocus()

    def _on_cancel(self):
        logger.warning("Passphrase prompt cancelled at startup")
        QMessageBox.information(
            self, "Завершение работы",
            "Приложение не может работать без расшифровки данных.\n\n"
            "Программа будет закрыта."
        )
        self.reject()

    def _reset_all_data(self):
        """Аварийный сброс при забытой парольной фразе.

        Парольную фразу невозможно восстановить, а без неё расшифровать данные
        нельзя. Единственный способ снова войти в программу — удалить все данные
        приложения (включая мастер-ключ и саму парольную фразу) и запустить
        программу с чистого состояния.
        """
        reply = QMessageBox.critical(
            self, "Сброс данных для входа",
            "Вы забыли парольную фразу?\n\n"
            "Восстановить её или расшифровать ранее сохранённые данные без неё "
            "НЕВОЗМОЖНО.\n\n"
            "Единственный способ войти в программу — удалить все данные приложения "
            "и начать с чистого состояния. Будут удалены:\n\n"
            "• Все сотрудники и программы обучения\n"
            "• Журнал проверки знаний\n"
            "• API-ключ и настройки прокси\n"
            "• Мастер-ключ шифрования и парольная фраза\n"
            "• Все настройки и логи\n\n"
            "Действие необратимо. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        confirm, ok = QInputDialog.getText(
            self, "Подтверждение сброса",
            "Введите 'УДАЛИТЬ' для подтверждения удаления всех данных:"
        )
        if not ok or confirm.strip() != "УДАЛИТЬ":
            QMessageBox.information(self, "Отмена", "Сброс отменён.")
            return

        if not self._perform_reset():
            return

        QMessageBox.information(
            self, "Данные удалены",
            "Все данные приложения удалены. Программа будет перезапущена "
            "и откроется без парольной фразы."
        )
        self._restart_application()

    def _perform_reset(self) -> bool:
        try:
            from utils.app_paths import get_app_data_dir
            try:
                from db import DatabaseManager
                DatabaseManager.close_all()
            except Exception:
                logger.debug("DatabaseManager.close_all() skipped during reset", exc_info=True)
            log_audit(
                "FACTORY_RESET",
                "All application data deleted from unlock screen (forgotten passphrase)"
            )
            from utils.crypto import forget_master_key
            forget_master_key()
            data_dir = get_app_data_dir()
            logger.warning("Resetting all app data from unlock screen: %s", data_dir)
            if os.path.exists(data_dir):
                for entry in os.listdir(data_dir):
                    entry_path = os.path.join(data_dir, entry)
                    try:
                        if os.path.isfile(entry_path) or os.path.islink(entry_path):
                            os.remove(entry_path)
                        elif os.path.isdir(entry_path):
                            shutil.rmtree(entry_path)
                    except Exception as e:
                        logger.error("Failed to delete %s: %s", entry, e)
            return True
        except Exception as e:
            logger.exception("Reset from unlock screen failed")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось удалить данные:\n{e}"
            )
            return False

    def _restart_application(self):
        from PySide6.QtWidgets import QApplication
        try:
            program = sys.executable
            if getattr(sys, "frozen", False):
                args = sys.argv[1:]
            else:
                args = sys.argv
            QProcess.startDetached(program, args)
        except Exception:
            logger.exception("Failed to schedule application restart")
        self.reject()
        app = QApplication.instance()
        if app is not None:
            app.quit()
