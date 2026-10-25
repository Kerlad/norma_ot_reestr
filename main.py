"""
Main application entry point.
Security audit and safe initialization for ISPDn.
"""
import sys
import os
import json
import logging
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QVBoxLayout, QHBoxLayout, QDialog, QWidget, QPushButton, QStackedWidget
from PySide6.QtCore import Qt, QTimer, QByteArray
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from tabs.data_entry_tab import DataEntryTab
from tabs.data_view_tab import DataViewTab
from tabs.data_transfer_tab import DataTransferTab
from tabs.exam_journal_tab import ExamJournalTab
from tabs.protocol_tab import ProtocolTab
from tabs.single_worker_protocol_tab import SingleWorkerProtocolTab
from tabs.employee_summary_tab import EmployeeSummaryTab
from journal.journal_manager import JournalManager
from protocol.commission_manager import CommissionManager
from protocol.programs_manager import ProgramsManager
from utils import platform_info
from utils.logger import setup_logging, filter_sensitive_text
from utils.audit import setup_audit_log, log_audit
from utils.tahoe_style import get_global_stylesheet, create_palette, apply_mica, load_theme, save_theme, load_app_fonts, THEME_ORDER, THEME_LABELS
from utils.app_paths import get_app_data_dir, get_app_log_dir, get_resource_dir
from utils.org_profiles import get_org_data_dir
from utils.about_dialog import AboutDialog, VERSION
from utils.help_dialog import HelpDialog
from utils.sidebar import Sidebar, PageHeader, TODAY_REFRESH_MS
from utils.settings_dialog import SettingsDialog
from utils.programs_reference_dialog import ProgramsReferenceWindow
from utils.log_viewer_dialog import LogViewerDialog
from utils.crypto import check_master_key_security, check_environment
from utils.clipboard_guard import ClipboardGuard
from utils.auto_lock import AutoLockManager
from db import DatabaseManager, create_schema
from db.employees_repo import EmployeesRepo
from api.mintrud_api import load_api_key
from utils.error_utils import safe_message_box

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    # (title, subtitle) of the pages, in sidebar order
    PAGE_TEXTS = [
        ("Внесение данных", "Загрузка списков работников из XLSX и XML, ручной ввод"),
        ("Просмотр данных", "Все внесённые записи: поиск, правка, экспорт"),
        ("Передача данных", "Отправка наборов в реестр обученных Минтруда и история отправок"),
        ("Журнал проверки знаний", "Протоколы и результаты проверок"),
        ("Сводка по сотрудникам", "Статус обучения, планы и отчёты"),
        ("Настройка протоколов", "Данные организации, комиссия, программы обучения"),
        ("Быстрый протокол", "Протокол для одного работника"),
    ]

    def __init__(self, app=None):
        super().__init__()
        self.app = app
        self.current_theme = load_theme(get_app_data_dir())
        self.setWindowTitle("Норма ОТ: Реестр обучения")
        org_name = ""
        try:
            from utils import org_profiles
            org_name = org_profiles.get_active_org().name
            if org_profiles.has_multiple_orgs():
                self.setWindowTitle("Норма ОТ: Реестр обучения — %s" % org_name)
        except Exception as e:
            logger.debug("Organization title unavailable: %s", type(e).__name__)
        self.setMinimumSize(1000, 640)
        self.resize(1280, 760)
        self._last_page = 0
        self._restore_window_geometry()

        icon_path = _app_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        data_dir = get_org_data_dir()

        self.data_entry_tab = DataEntryTab()
        self.data_view_tab = DataViewTab()
        self.data_transfer_tab = DataTransferTab()

        self.journal_manager = JournalManager(data_dir)
        self.exam_journal_tab = ExamJournalTab(self.journal_manager, data_dir)

        self.commission_manager = CommissionManager(data_dir)
        self.programs_manager = ProgramsManager(data_dir)
        self.protocol_tab = ProtocolTab(self.commission_manager, self.programs_manager, data_dir, self.journal_manager)
        self.protocol_tab.set_data_source(self.data_view_tab)

        self.single_worker_tab = SingleWorkerProtocolTab(self.programs_manager, data_dir)

        self.employee_summary_tab = EmployeeSummaryTab()

        self.auto_lock = AutoLockManager(self)

        central = QWidget()
        frame = QHBoxLayout(central)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setSpacing(0)
        self.sidebar = Sidebar(VERSION, org_name, icon_path if os.path.exists(icon_path) else "")
        self.stack = QStackedWidget()
        frame.addWidget(self.sidebar)
        frame.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._setup_pages()

        self.data_entry_tab.data_loaded.connect(self.data_view_tab.add_data)
        self.data_entry_tab.data_loaded.connect(lambda *_: self.sidebar.refresh_counts())
        self.data_entry_tab.get_existing_keys_callback = self.data_view_tab.get_existing_keys

        self.data_transfer_tab.set_journal_callback(self.exam_journal_tab.add_records_to_journal, self.exam_journal_tab.update_base_no)

        self.sidebar.page_selected.connect(self._show_page)
        self.sidebar.settings_requested.connect(self.open_settings)
        self.sidebar.help_requested.connect(self.show_help)
        self.sidebar.org_switch_requested.connect(self._switch_org)
        self.sidebar.org_add_requested.connect(self._add_org)
        self.sidebar.org_delete_requested.connect(self._delete_org)
        self._setup_shortcuts()

        self._today_timer = QTimer(self)
        self._today_timer.setInterval(TODAY_REFRESH_MS)
        self._today_timer.timeout.connect(self.sidebar.refresh_counts)
        self._today_timer.start()

        self._show_page(min(max(self._last_page, 0), self.stack.count() - 1))

        if self.app:
            self.app.installEventFilter(self.auto_lock)

    def _setup_pages(self):
        """Sidebar order; every page = 60 px header + the existing tab widget."""
        self._tab_widgets = [
            self.data_entry_tab, self.data_view_tab, self.data_transfer_tab, self.exam_journal_tab,
            self.employee_summary_tab, self.protocol_tab, self.single_worker_tab,
        ]
        for tab, (title, subtitle) in zip(self._tab_widgets, self.PAGE_TEXTS):
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            header = PageHeader(title, subtitle)
            if tab is self.data_entry_tab:
                header.add_action(self._header_button("Шаблон XLSX", self._create_template, "Ctrl+T"))
            elif tab is self.data_view_tab:
                header.add_action(self._header_button("Экспорт XLSX", self._export_all, "Ctrl+E"))
            lay.addWidget(header)
            lay.addWidget(tab, 1)
            self.stack.addWidget(page)

    def _header_button(self, text: str, handler, shortcut: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("role", "secondary")
        btn.setToolTip("%s (%s)" % (text, shortcut))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False: handler())
        return btn

    def _show_page(self, index: int):
        if index < 0 or index >= self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index)
        self._last_page = index
        w = self._tab_widgets[index]
        if hasattr(w, 'refresh_table'):
            try: w.refresh_table()
            except Exception as e:
                logger.debug("Tab refresh_table failed: %s", e)
        elif hasattr(w, 'refresh_data'):
            try: w.refresh_data()
            except Exception as e:
                logger.debug("Tab refresh_data failed: %s", e)
        self.sidebar.refresh_counts()

    def _setup_shortcuts(self):
        """Ctrl+1..7 - sections; F1, Ctrl+L/Q/E/T/D - as in the former menu bar."""
        for i in range(self.stack.count()):
            QShortcut(QKeySequence("Ctrl+%d" % (i + 1)), self).activated.connect(
                lambda idx=i: self._show_page(idx))
        for keys, handler in (
            ("F1", self.show_help), ("Ctrl+L", self._manual_lock), ("Ctrl+Q", self.close),
            ("Ctrl+E", self._export_all), ("Ctrl+T", self._create_template),
            ("Ctrl+D", self._cycle_theme),
        ):
            QShortcut(QKeySequence(keys), self).activated.connect(handler)

    def open_settings(self, section: str = "appearance"):
        dlg = SettingsDialog(self)
        dlg.show_section(section if isinstance(section, str) else "appearance")
        self._settings_dialog = dlg
        dlg.exec()
        self._settings_dialog = None
        self.auto_lock.refresh()

    def _create_template(self):
        self._show_page(0)
        self.data_entry_tab.create_template()

    def _export_all(self):
        self._show_page(1)
        self.data_view_tab._export_xlsx()

    def _open_proxy_settings(self):
        self.data_transfer_tab.open_proxy_settings_window()

    def _open_security(self):
        from utils.security_dialog import SecurityDialog
        dialog = SecurityDialog(self)
        dialog.exec()
        self.auto_lock.refresh()

    def _apply_theme(self, theme: str):
        self.current_theme = theme
        save_theme(get_app_data_dir(), theme)
        if self.app:
            self.app.setPalette(create_palette(theme))
            self.app.setStyleSheet(get_global_stylesheet(theme))
            self._refresh_styles()
        self.sidebar.apply_theme_colors()
        dlg = getattr(self, "_settings_dialog", None)
        if dlg is not None:
            dlg.refresh_theme_cards()
        dt = getattr(self, "data_transfer_tab", None)
        if dt is not None and hasattr(dt, "on_theme_changed"):
            try:
                dt.on_theme_changed()
            except Exception:
                logging.getLogger(__name__).debug("transfer theme refresh failed", exc_info=True)
        jt = getattr(self, "exam_journal_tab", None)
        if jt is not None and hasattr(jt, "on_theme_changed"):
            try:
                jt.on_theme_changed()
            except Exception:
                logging.getLogger(__name__).debug("journal theme refresh failed", exc_info=True)

    def _refresh_styles(self):
        for w in self.findChildren(QWidget):
            w.style().unpolish(w)
            w.style().polish(w)
        self.style().unpolish(self)
        self.style().polish(self)

    def _select_theme(self, theme: str):
        if theme == self.current_theme:
            return
        self._apply_theme(theme)

    def _cycle_theme(self):
        try:
            idx = THEME_ORDER.index(self.current_theme)
        except ValueError:
            idx = 0
        self._select_theme(THEME_ORDER[(idx + 1) % len(THEME_ORDER)])

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def show_programs_reference(self):
        from PySide6.QtWidgets import QApplication
        anchor = (
            QApplication.activeModalWidget()
            or QApplication.activeWindow()
            or self
        )
        existing = getattr(self, "_programs_ref_window", None)
        if existing is not None and existing.parent() is not anchor:
            existing.close()
            existing.deleteLater()
            self._programs_ref_window = None
        if getattr(self, "_programs_ref_window", None) is None:
            self._programs_ref_window = ProgramsReferenceWindow(anchor)
        self._programs_ref_window.show()
        self._programs_ref_window.raise_()
        self._programs_ref_window.activateWindow()

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()
        self.auto_lock.refresh()

    def show_log_viewer(self):
        dialog = LogViewerDialog(self)
        dialog.exec()

    def _delete_all_app_data(self):
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
        reply2 = QMessageBox.critical(
            self, "Подтверждение",
            "Введите 'УДАЛИТЬ' в поле ниже для подтверждения:",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if reply2 != QMessageBox.StandardButton.Ok:
            return
        from PySide6.QtWidgets import QInputDialog
        confirm, ok = QInputDialog.getText(self, "Подтверждение", "Введите 'УДАЛИТЬ' для подтверждения:")
        if not ok or confirm.strip() != 'УДАЛИТЬ':
            QMessageBox.warning(self, "Отмена", "Удаление отменено")
            return
        self._perform_factory_reset()

    def _perform_factory_reset(self):
        """Delete everything in the data dir (all organizations). Caller confirms."""
        try:
            DatabaseManager.close_all()
            data_dir = get_app_data_dir()
            logger.warning("Deleting all app data in %s", data_dir)
            log_audit("FACTORY_RESET", "All application data deleted")
            from utils.crypto import forget_master_key
            forget_master_key()
            import shutil
            if os.path.exists(data_dir):
                for entry in os.listdir(data_dir):
                    entry_path = os.path.join(data_dir, entry)
                    try:
                        if os.path.isfile(entry_path) or os.path.islink(entry_path):
                            os.unlink(entry_path)
                        elif os.path.isdir(entry_path):
                            shutil.rmtree(entry_path)
                    except Exception as e:
                        logger.error("Failed to delete %s: %s", entry, e)
            QMessageBox.information(self, "Готово", "Все данные приложения удалены.\nПриложение будет закрыто.")
            self.close()
        except Exception as e:
            logger.exception("Delete all data failed")
            safe_message_box(self, QMessageBox.Icon.Warning, "Ошибка",
                           f"Не удалось удалить данные: {e}")

    def _manual_lock(self):
        self.auto_lock.force_lock()

    def _configure_lock_timeout(self):
        from PySide6.QtWidgets import QInputDialog
        current = self.auto_lock.timeout_minutes
        value, ok = QInputDialog.getInt(
            self, "Таймаут блокировки",
            "Минуты бездействия до блокировки сессии (1-120):",
            value=current, minValue=1, maxValue=120, step=1
        )
        if ok:
            self.auto_lock.timeout_minutes = value
            logger.info("Auto-lock timeout set to %d min", value)

    def _window_settings_path(self):
        return os.path.join(get_app_data_dir(), "window_settings.json")

    def _save_window_geometry(self):
        geo = self.saveGeometry()
        b64 = geo.toBase64().data().decode('ascii')
        data = {"window_geometry": b64, "last_page": self._last_page}
        try:
            with open(self._window_settings_path(), 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except OSError as e:
            logger.debug("Failed to save window geometry: %s", e)

    def _restore_window_geometry(self):
        path = self._window_settings_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            last = data.get("last_page", 0)
            self._last_page = last if isinstance(last, int) else 0
            b64 = data.get("window_geometry", "")
            if b64:
                self.restoreGeometry(QByteArray.fromBase64(b64.encode('ascii')))
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to restore window geometry: %s", e)

    # --- UX-10: organizations -------------------------------------------------

    def _switch_org(self):
        from utils import org_profiles
        from tabs.org_dialogs import OrgSelectDialog
        current = org_profiles.get_active_org_id()
        dlg = OrgSelectDialog(self, current_id=current, on_delete_all=self._perform_factory_reset)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        target = dlg.selected_id if accepted else None
        if dlg.deleted_current and not target:
            target = org_profiles.get_last_active_id()
        if not target or (target == current and not dlg.deleted_current):
            return
        if not dlg.deleted_current:
            from utils.donation_dialog import ORG_SWITCH_SECONDS, show_support_if_needed
            show_support_if_needed(
                self, seconds=ORG_SWITCH_SECONDS, require_org=True,
                reason="Смена организации. С лицензией «Организация» — без ожидания.")
        self._relaunch_with_org(target)

    def _add_org(self):
        from tabs.org_dialogs import ask_new_org
        org = ask_new_org(self)
        if org is None:
            return
        reply = QMessageBox.question(
            self, "Организация добавлена",
            "Организация «%s» добавлена.\nПерейти к ней сейчас? Программа перезапустится." % org.name)
        if reply == QMessageBox.StandardButton.Yes:
            self._relaunch_with_org(org.id)

    def _delete_org(self):
        from utils import org_profiles
        from tabs.org_dialogs import OrgDeleteDialog
        org = org_profiles.get_active_org()
        dlg = OrgDeleteDialog(self, org, can_delete_one=org_profiles.has_multiple_orgs())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.choice == OrgDeleteDialog.ALL:
            self._perform_factory_reset()
            return
        self._stop_background_threads()
        try:
            org_profiles.delete_org(org.id)
        except (org_profiles.OrgError, OSError) as e:
            logger.error("Failed to delete organization: %s", type(e).__name__)
            safe_message_box(self, QMessageBox.Icon.Warning, "Удаление организации",
                             str(e) if isinstance(e, org_profiles.OrgError)
                             else "Не удалось удалить данные организации")
            return
        QMessageBox.information(self, "Удаление организации",
                                "Организация «%s» удалена. Программа перезапустится." % org.name)
        self._relaunch_with_org(org_profiles.get_last_active_id())

    def _relaunch_with_org(self, org_id: str):
        """Restart the app with another organization (started after this process exits)."""
        _RELAUNCH["args"] = ["--org=%s" % org_id, "--no-splash"]
        log_audit("ORG_SWITCHED", "id=%s" % org_id)
        self.close()

    def closeEvent(self, event):
        self._save_window_geometry()
        self._stop_background_threads()
        log_audit("SHUTDOWN", "Application shutdown")
        super().closeEvent(event)

    def _stop_background_threads(self):
        """Останавливает фоновые потоки вкладок, чтобы ни один QThread не был уничтожен во время работы."""
        tab = getattr(self, "data_transfer_tab", None)
        if tab is not None and hasattr(tab, "cleanup_threads"):
            try:
                tab.cleanup_threads()
            except Exception:
                logging.getLogger(__name__).debug("thread cleanup failed", exc_info=True)


def global_exception_handler(exc_type, exc_value, exc_tb):
    """Safe global exception handler - no PII in crash dialog."""
    _logger = logging.getLogger(__name__)
    _logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    log_audit("CRASH", f"Type: {exc_type.__name__}")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is not None:
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Icon.Critical)
            error_box.setWindowTitle("Критическая ошибка")
            error_box.setText(
                "Произошла неожиданная ошибка. Приложение будет закрыто.\n\n"
                "Подробности записаны в лог-файл."
            )
            error_box.setDetailedText(
                f"Тип: {exc_type.__name__}\n"
                f"Описание: {filter_sensitive_text(str(exc_value)[:200])}\n"
                f"Подробности см. в error.log"
            )
            error_box.exec()
    except Exception as e:
        _logger.critical("Crash dialog failed: %s", e)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = global_exception_handler


def _report_data_dir_migration():
    """Log/audit the Excel_to_XML -> NormaOT data dir migration.
    Returns a message for the user, or None if nothing needs attention."""
    from utils.app_paths import (
        get_migration_status, MIGRATION_DONE, MIGRATION_FAILED, MIGRATION_SKIPPED,
    )
    info = get_migration_status()
    status, error = info.get('status'), info.get('error')
    if status == MIGRATION_DONE:
        logger.info("Data directory migrated: Excel_to_XML -> NormaOT")
        log_audit("DATA_DIR_MIGRATED", "Excel_to_XML -> NormaOT")
        return None
    if status == MIGRATION_FAILED:
        logger.warning("Data directory migration failed (%s), using legacy directory", error)
        log_audit("DATA_DIR_MIGRATION_FAILED", "rename failed: %s" % error)
        return ("Не удалось перенести данные приложения из папки\n"
                "%APPDATA%\\Excel_to_XML в %APPDATA%\\NormaOT.\n\n"
                "Скорее всего, открыта другая копия программы. В этом сеансе "
                "используется старая папка, данные не потеряны.\n"
                "Закройте все копии программы и запустите её снова — перенос "
                "будет выполнен автоматически.")
    if status == MIGRATION_SKIPPED:
        logger.warning("Both legacy and new data directories exist, legacy left untouched")
        log_audit("DATA_DIR_MIGRATION_FAILED", "skipped: both directories exist")
        return ("Обнаружены две папки данных: %APPDATA%\\NormaOT (используется) и\n"
                "старая %APPDATA%\\Excel_to_XML (не используется).\n\n"
                "Старая папка может содержать персональные данные. Если нужные "
                "данные есть в программе, удалите старую папку вручную.")
    return None


_RELAUNCH = {"args": None}


def _start_relaunch():
    """Start a new instance after an organization switch (MainWindow._relaunch_with_org)."""
    args = _RELAUNCH.get("args")
    if not args:
        return
    from PySide6.QtCore import QProcess
    if getattr(sys, "frozen", False):
        ok = QProcess.startDetached(sys.executable, args)
    else:
        ok = QProcess.startDetached(sys.executable, [os.path.abspath(__file__)] + args)
    if not ok:
        logger.error("Relaunch after organization switch failed")


def _choose_org(org_arg):
    """--org=<id> from a relaunch, the only organization, or the startup dialog."""
    from utils import org_profiles
    ids = [o.id for o in org_profiles.list_orgs()]
    if org_arg in ids:
        return org_arg
    if len(ids) == 1:
        return ids[0]
    from tabs.org_dialogs import OrgSelectDialog
    dlg = OrgSelectDialog(None, startup=True)
    if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_id:
        logger.info("Organization selection cancelled")
        sys.exit(0)
    return dlg.selected_id


def _app_icon_path():
    """Windows: ico.ico. Elsewhere: PNG (not every Qt build ships the ICO plugin)."""
    name = "ico.ico" if platform_info.IS_WINDOWS else "icon.png"
    return os.path.join(get_resource_dir(), "resources", name)


def _unlock_keystore_if_needed():
    """Linux without Secret Service: the master key is wrapped by a passphrase asked at startup."""
    from PySide6.QtWidgets import QInputDialog, QLineEdit
    from utils.crypto import (keystore_needs_passphrase, unlock_keystore, _key_dir,
                              CryptoError)
    if not keystore_needs_passphrase():
        return
    first_run = not (_key_dir() / 'master.key').exists()
    while True:
        if first_run:
            text = ("Хранилище ключей ОС недоступно. Задайте парольную фразу для защиты "
                    "мастер-ключа. Без неё данные расшифровать невозможно, восстановления нет:")
        else:
            text = "Введите парольную фразу для доступа к мастер-ключу:"
        phrase, ok = QInputDialog.getText(None, "Парольная фраза", text, QLineEdit.EchoMode.Password)
        if not ok or not phrase:
            sys.exit(0)
        if first_run:
            again, ok = QInputDialog.getText(None, "Парольная фраза", "Повторите парольную фразу:",
                                             QLineEdit.EchoMode.Password)
            if not ok or again != phrase:
                QMessageBox.warning(None, "Ошибка", "Парольные фразы не совпадают")
                continue
        try:
            unlock_keystore(phrase)
            return
        except CryptoError:
            QMessageBox.warning(None, "Ошибка", "Неверная парольная фраза")


def _show_first_about(window, flag_path):
    try:
        from utils.about_dialog import AboutDialog
        dialog = AboutDialog(window)
        dialog.exec()
        with open(flag_path, 'w', encoding='utf-8') as f:
            f.write('shown')
    except Exception as e:
        logging.getLogger(__name__).debug("First-launch About dialog failed: %s", e)


if __name__ == "__main__":
    _profile_flag = '--profile' in sys.argv
    if _profile_flag:
        sys.argv.remove('--profile')

    log_dir = get_app_log_dir()
    setup_logging(log_dir)
    setup_audit_log(log_dir)
    logger.info("=== Application started ===")
    _migration_message = _report_data_dir_migration()

    app_dir = get_app_data_dir()
    data_dir = app_dir  # replaced by the active organization's dir below
    _org_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--org=")), None)
    _no_splash = "--no-splash" in sys.argv
    sys.argv = [a for a in sys.argv if not (a.startswith("--org=") or a == "--no-splash")]

    _first_launch_flag = os.path.join(app_dir, ".about_shown")
    _is_first_launch = not os.path.exists(_first_launch_flag)

    def security_audit():
        audit_logger = logging.getLogger(__name__)

        env_ok, env_msg = check_environment()
        if not env_ok:
            audit_logger.warning("Security audit - environment: FAIL - %s", env_msg)
        else:
            audit_logger.info("Security audit - environment: OK")

        mode, msg = check_master_key_security()
        audit_logger.info("Security audit - master.key: [%s] %s", mode, msg)
        if mode in ('raw',):
            audit_logger.warning(
                "SECURITY: master.key stored as plaintext! "
                "Consider setting a passphrase via 'About' dialog."
            )
            log_audit("SECURITY_WARNING", "Master key is plaintext")
        elif mode == 'raw_passphrase':
            audit_logger.info("Security audit - master.key: plaintext but passphrase protected (PBKDF2)")
        elif mode == 'none':
            audit_logger.error("SECURITY: Master key not found!")
            log_audit("SECURITY_WARNING", "Master key not found")
        elif mode in ('dpapi', 'dpapi_passphrase', 'secret_service', 'secret_service_passphrase', 'passphrase_file', 'passphrase_file_passphrase'):
            audit_logger.info("Security audit - master.key protection: OK (%s)", mode)

        from api.mintrud_api import load_api_key
        api_key = load_api_key(data_dir)
        if api_key:
            audit_logger.info("Security audit - API key: present (encrypted)")
        else:
            audit_logger.info("Security audit - API key: not set")

        try:
            from db.employees_repo import EmployeesRepo
            sample = EmployeesRepo.get_all(limit=1)
            if sample:
                audit_logger.info("Security audit - DB encryption: OK (field-level Fernet)")
        except Exception as e:
            audit_logger.warning("Security audit - DB encryption check: %s", e)

    theme = load_theme(app_dir)

    app = QApplication(sys.argv)

    if platform_info.IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("excelxml.mintrud.3.1")
        except Exception:
            pass
    else:
        app.setDesktopFileName("normaot-reestr")

    icon_path = _app_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    load_app_fonts(os.path.join(get_resource_dir(), "resources", "fonts"))
    app.setPalette(create_palette(theme))
    app.setStyle("Fusion")
    app.setStyleSheet(get_global_stylesheet(theme))

    _unlock_keystore_if_needed()

    from utils.crypto import is_passphrase_protected
    if is_passphrase_protected():
        from utils.passphrase_dialog import PassphraseDialog
        passphrase_dialog = PassphraseDialog()
        if passphrase_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    # UX-10: organization is chosen before any DB/tab is created
    from utils import org_profiles
    org_profiles.set_active_org(_choose_org(_org_arg))
    data_dir = org_profiles.get_org_data_dir()
    db = DatabaseManager.get_instance(os.path.join(data_dir, "app_data.db"))
    db.initialize()
    create_schema()
    logger.info("Database initialized")
    db.create_backup()
    log_audit("STARTUP", "Application started")
    security_audit()

    window = MainWindow(app=app)
    window.show()
    ClipboardGuard.start()

    apply_mica(window)
    logger.info("Window displayed, theme: %s", theme)

    if _migration_message:
        QTimer.singleShot(300, lambda: QMessageBox.warning(
            window, "Папка данных", _migration_message))

    if _is_first_launch:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, lambda: _show_first_about(window, _first_launch_flag))
    elif not _no_splash:
        # UX-10/UX-16: support splash, once per calendar day (skipped on first launch,
        # after an organization switch and with an active license)
        from utils.donation_dialog import maybe_show_startup_splash
        QTimer.singleShot(500, lambda: maybe_show_startup_splash(window))

    if _profile_flag:
        import cProfile
        profiler = cProfile.Profile()
        profiler.runcall(app.exec)
        profiler.dump_stats(os.path.join(log_dir, "profile.prof"))
        logger.info("Profile saved")
        _start_relaunch()
    else:
        _exit_code = app.exec()
        _start_relaunch()
        sys.exit(_exit_code)
