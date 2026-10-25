import logging
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QMessageBox, QInputDialog, QLineEdit, QFileDialog
)
from PySide6.QtCore import Qt
from utils.dialog_base import BaseDialog
from utils.app_paths import get_app_data_dir, get_resource_dir
from utils.crypto import (
    check_master_key_security, create_master_key_backup,
    is_passphrase_protected, set_passphrase, remove_passphrase,
    verify_passphrase, get_key_fingerprint, CryptoPassphraseRequiredError,
    CryptoError
)
from utils.error_utils import safe_message_box

logger = logging.getLogger(__name__)


class SecurityDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Безопасность", min_width=820, min_height=360, scrollable=True)

        bl = self.body_layout()
        from utils.ui_helpers import make_card, notice_label, set_role, hint_label
        self.set_subtitle("Защита ключа шифрования и данных на этом компьютере")

        # card 1: master key status
        key_card, kl = make_card("Мастер-ключ", "Им шифруются ФИО, СНИЛС, API-ключ и настройки прокси.")
        self._security_status_label = QLabel()
        self._security_status_label.setWordWrap(True)
        kl.addWidget(self._security_status_label)
        bl.addWidget(key_card)

        # card 2: passphrase
        pass_card, pl = make_card("Парольная фраза",
                                  "Дополнительная защита ключа и условие для блокировки сеанса.")
        self._passphrase_notice = notice_label(
            '<b>Рекомендуется установить парольную фразу.</b> '
            '<b>Обязательно запишите или запомните её</b> — '
            'при утере восстановить данные будет невозможно.', "warn")
        pl.addWidget(self._passphrase_notice)
        pass_row = QHBoxLayout()
        self._set_passphrase_btn = QPushButton("Установить парольную фразу")
        set_role(self._set_passphrase_btn, "dark")
        self._set_passphrase_btn.clicked.connect(self._set_passphrase)
        pass_row.addWidget(self._set_passphrase_btn)
        self._remove_passphrase_btn = QPushButton("Снять парольную фразу")
        set_role(self._remove_passphrase_btn, "danger")
        self._remove_passphrase_btn.clicked.connect(self._remove_passphrase)
        pass_row.addWidget(self._remove_passphrase_btn)
        pass_row.addStretch()
        pl.addLayout(pass_row)
        bl.addWidget(pass_card)

        # card 3: key backup
        backup_card, bl3 = make_card(
            "Резервная копия ключа",
            "Без файла master.key зашифрованные данные не восстановить: придётся вводить сотрудников, "
            "API-ключ и настройки заново. Копия создаётся с паролем, производным от ключа. "
            "Храните её отдельно от программы.")
        backup_btn = QPushButton("Создать защищённый бэкап master.key")
        set_role(backup_btn, "secondary")
        backup_btn.clicked.connect(self._create_key_backup)
        row3 = QHBoxLayout()
        row3.addWidget(backup_btn)
        row3.addStretch()
        bl3.addLayout(row3)
        bl.addWidget(backup_card)

        # card 4: session lock
        lock_card, ll = make_card("Блокировка при бездействии",
                                  "Требует парольную фразу. Время бездействия задаётся в «Настройках и темах».")
        host = self.parent()
        if host is not None and hasattr(host, "_manual_lock"):
            row4 = QHBoxLayout()
            lock_now = QPushButton("Заблокировать сейчас")
            set_role(lock_now, "secondary")
            lock_now.clicked.connect(lambda: (self.close(), host._manual_lock()))
            row4.addWidget(lock_now)
            row4.addStretch()
            ll.addLayout(row4)
        bl.addWidget(lock_card)

        # card 5: danger zone
        danger_card, dl = make_card("Опасная зона")
        danger_card.setObjectName("dangerCard")
        dl.addWidget(hint_label(
            "Удаляет все файлы приложения: сотрудников, программы, журнал, API-ключ, мастер-ключ, "
            "настройки и логи. Приложение будет немедленно закрыто. Действие необратимо."))
        delete_btn = QPushButton("Удалить все данные приложения")
        set_role(delete_btn, "danger")
        delete_btn.clicked.connect(self._delete_all_data)
        row5 = QHBoxLayout()
        row5.addWidget(delete_btn)
        row5.addStretch()
        dl.addLayout(row5)
        bl.addWidget(danger_card)
        bl.addStretch()

        self.add_close_button("Закрыть")

        self._update_security_status()

    def _update_security_status(self):
        mode, msg = check_master_key_security()
        pp = is_passphrase_protected()
        from utils.tahoe_style import get_colors, get_current_theme
        c = get_colors(get_current_theme())
        if mode in ('dpapi', 'dpapi_passphrase', 'secret_service', 'secret_service_passphrase', 'passphrase_file', 'passphrase_file_passphrase'):
            html = f'<span style="color:{c.ok_text};"><b>Безопасность:</b> {msg}</span>'
        elif mode == 'raw_passphrase':
            html = f'<span style="color:{c.ok_text};"><b>Безопасность:</b> {msg}</span>'
        elif mode == 'raw':
            html = f'<span style="color:{c.err_text};"><b>ВНИМАНИЕ!</b> {msg}</span>'
        else:
            html = f'<span style="color:{c.warn_text};"><b>Внимание:</b> {msg}</span>'
        fingerprint = get_key_fingerprint()
        html += f'<br><span style="font-size:11px;color:{c.text_muted};">Отпечаток ключа: {fingerprint}</span>'
        self._security_status_label.setText(html)
        self._set_passphrase_btn.setVisible(not pp)
        self._remove_passphrase_btn.setVisible(pp)
        self._passphrase_notice.setVisible(not pp)

    def _set_passphrase(self):
        pp, ok = QInputDialog.getText(
            self, "Установка парольной фразы",
            "Введите парольную фразу для дополнительной защиты мастер-ключа:",
            QLineEdit.EchoMode.Password
        )
        if not ok or not pp:
            return
        confirm, ok = QInputDialog.getText(
            self, "Подтверждение парольной фразы",
            "Повторите парольную фразу:",
            QLineEdit.EchoMode.Password
        )
        if not ok or pp != confirm:
            QMessageBox.warning(self, "Ошибка", "Парольные фразы не совпадают")
            return
        try:
            set_passphrase(pp)
            QMessageBox.information(self, "Успех", "Парольная фраза установлена")
            self._update_security_status()
        except CryptoError as e:
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Не удалось установить парольную фразу:\n{e}")

    def _remove_passphrase(self):
        pp, ok = QInputDialog.getText(
            self, "Снятие парольной фразы",
            "Введите текущую парольную фразу:",
            QLineEdit.EchoMode.Password
        )
        if not ok or not pp:
            return
        try:
            verify_passphrase(pp)
            remove_passphrase(pp)
            QMessageBox.information(self, "Успех", "Парольная фраза снята")
            self._update_security_status()
        except CryptoPassphraseRequiredError:
            QMessageBox.warning(self, "Ошибка", "Неверная парольная фраза")
        except CryptoError as e:
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Не удалось снять парольную фразу:\n{e}")

    def _create_key_backup(self):
        backup_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для бэкапа master.key")
        if not backup_dir:
            return
        ok, result = create_master_key_backup(backup_dir)
        if ok:
            safe_message_box(self, QMessageBox.Icon.Information, "Успех", f"Бэкап создан:\n{result}")
        else:
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка", f"Не удалось создать бэкап:\n{result}")

    def _delete_all_data(self):
        from utils.app_paths import get_app_data_dir
        import os, shutil, logging
        logger = logging.getLogger(__name__)
        parent = self.parent()
        reply = QMessageBox.critical(
            self, "Удаление всех данных",
            "Это удалит ВСЕ данные приложения:\n\n"
            "• Всех сотрудников и программы обучения\n"
            "• Журнал проверки знаний\n"
            "• API ключ и настройки прокси\n"
            "• Мастер-ключ шифрования\n"
            "• Все настройки и логи\n\n"
            "Приложение будет немедленно закрыто.\n"
            "Данные будут удалены безвозвратно!\n\n"
            "Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        confirm, ok = QInputDialog.getText(self, "Подтверждение", "Введите 'УДАЛИТЬ' для подтверждения:")
        if not ok or confirm.strip() != 'УДАЛИТЬ':
            QMessageBox.warning(self, "Отмена", "Удаление отменено")
            return
        try:
            data_dir = get_app_data_dir()
            logger.warning("Deleting all app data in %s", data_dir)
            from utils.audit import log_audit
            log_audit("FACTORY_RESET", "All application data deleted via Security dialog")
            from utils.crypto import forget_master_key
            forget_master_key()
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
            self.close()
            if parent and hasattr(parent, 'close'):
                parent.close()
        except Exception as e:
            logger.exception("Delete all data failed")
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка",
                           f"Не удалось удалить данные: {e}")
