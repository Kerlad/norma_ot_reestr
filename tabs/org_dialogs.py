"""
Organization selection / add / delete dialogs (UX-10, step 5).

Without an «Организация» license adding an organization shows the support
splash for 60 s and switching for 30 s (see utils/donation_dialog.py).
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QButtonGroup, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QRadioButton,
)

from utils.dialog_base import BaseDialog
from utils.donation_dialog import ORG_ADD_SECONDS, show_support_if_needed
from utils import org_profiles as orgs

logger = logging.getLogger(__name__)

CONFIRM_WORD = "УДАЛИТЬ"


def ask_new_org(parent) -> Optional[orgs.Org]:
    """Name prompt → (60 s splash without org license) → create. None if cancelled."""
    name, ok = QInputDialog.getText(parent, "Добавить организацию",
                                    "Название организации (как в реестре / протоколах):")
    if not ok:
        return None
    try:
        orgs._clean_name(name)  # validate before the wait
    except orgs.OrgError as e:
        QMessageBox.warning(parent, "Добавить организацию", str(e))
        return None
    show_support_if_needed(
        parent, seconds=ORG_ADD_SECONDS, require_org=True,
        reason="Добавление организации. С лицензией «Организация» — без ожидания.")
    try:
        return orgs.add_org(name)
    except orgs.OrgError as e:
        QMessageBox.warning(parent, "Добавить организацию", str(e))
    except OSError as e:
        logger.error("Failed to add organization: %s", type(e).__name__)
        QMessageBox.warning(parent, "Добавить организацию", "Не удалось создать папку организации")
    return None


class OrgDeleteDialog(BaseDialog):
    """Choice: delete one organization or everything; confirmed by typing УДАЛИТЬ."""

    ONE, ALL = 1, 2

    def __init__(self, parent, org: orgs.Org, can_delete_one: bool, allow_all: bool = True):
        super().__init__(parent, title="Удаление данных", min_width=540, min_height=300,
                         subtitle="Данные будут удалены безвозвратно")
        bl = self.body_layout()
        self.choice = None
        self.one_rb = QRadioButton("Удалить организацию «%s» и все её данные" % org.name)
        self.all_rb = QRadioButton("Удалить все организации и все данные приложения "
                                   "(мастер-ключ, лицензию, настройки, логи); программа закроется")
        self.one_rb.setEnabled(can_delete_one)
        self.all_rb.setEnabled(allow_all)
        if not allow_all:
            self.all_rb.setToolTip("Доступно в программе: «Настройки и темы → Безопасность → Опасная зона»")
        if not can_delete_one:
            self.one_rb.setToolTip("Это единственная организация — удалите все данные")
        group = QButtonGroup(self)
        group.addButton(self.one_rb, self.ONE)
        group.addButton(self.all_rb, self.ALL)
        (self.one_rb if can_delete_one else self.all_rb).setChecked(True)
        for rb in (self.one_rb, self.all_rb):
            bl.addWidget(rb)
        warn = QLabel("Данные будут удалены безвозвратно. Для подтверждения введите «%s»:" % CONFIRM_WORD)
        warn.setWordWrap(True)
        bl.addWidget(warn)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setPlaceholderText(CONFIRM_WORD)
        self.confirm_edit.textChanged.connect(self._update_ok)
        bl.addWidget(self.confirm_edit)
        bl.addStretch()
        self.ok_btn, _ = self.add_action_buttons("Удалить", self._on_ok, primary_role="danger")
        self._group = group
        self._update_ok()

    def _update_ok(self):
        self.ok_btn.setEnabled(self.confirm_edit.text().strip() == CONFIRM_WORD)

    def _on_ok(self):
        if self.confirm_edit.text().strip() != CONFIRM_WORD:
            return
        self.choice = self._group.checkedId()
        self.accept()


class OrgSelectDialog(BaseDialog):
    """List of organizations: open / add / rename / delete.

    startup=True: «Выход» instead of «Отмена».
    on_delete_all: callback for the «delete everything» choice (factory reset).
    """

    def __init__(self, parent=None, startup: bool = False, current_id: Optional[str] = None,
                 on_delete_all=None):
        super().__init__(parent, title="Выбор организации", min_width=780, min_height=440)
        from utils.ui_helpers import make_dark_plate
        from utils.app_paths import get_resource_dir
        import os
        icon = os.path.join(get_resource_dir(), "resources", "icon.png")
        plate, _ = make_dark_plate("Выбор организации", "У каждой организации свои данные", icon, 44)
        self._header.setVisible(False)
        self.layout().insertWidget(0, plate)
        self._current_id = current_id
        self._on_delete_all = on_delete_all
        self.selected_id: Optional[str] = None
        self.deleted_current = False
        bl = self.body_layout()
        hint = QLabel("Выберите организацию, с данными которой будете работать:")
        hint.setWordWrap(True)
        bl.addWidget(hint)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._open())
        bl.addWidget(self.list, 1)

        self.add_footer_button("Добавить организацию…", self._add, "secondary")
        self.add_footer_button("Переименовать…", self._rename, "ghost")
        self.add_footer_button("Удалить…", self._delete, "ghost")
        self.open_btn, _ = self.add_action_buttons("Открыть", self._open, "Выход" if startup else "Отмена")
        self.open_btn.setDefault(True)
        self._reload(select_id=current_id or orgs.get_last_active_id())

    def _reload(self, select_id: Optional[str] = None):
        self.list.clear()
        for org in orgs.list_orgs():
            label = org.name + ("  (текущая)" if org.id == self._current_id else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, org.id)
            item.setSizeHint(QSize(0, 44))
            self.list.addItem(item)
            if org.id == select_id:
                self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)

    def _selected(self) -> Optional[orgs.Org]:
        item = self.list.currentItem()
        if item is None:
            return None
        oid = item.data(Qt.ItemDataRole.UserRole)
        return next((o for o in orgs.list_orgs() if o.id == oid), None)

    def _open(self):
        org = self._selected()
        if org is not None:
            self.selected_id = org.id
            self.accept()

    def _add(self):
        org = ask_new_org(self)
        if org is not None:
            self._reload(select_id=org.id)

    def _rename(self):
        org = self._selected()
        if org is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать организацию", "Новое название:", text=org.name)
        if not ok:
            return
        try:
            orgs.rename_org(org.id, name)
        except orgs.OrgError as e:
            QMessageBox.warning(self, "Переименовать организацию", str(e))
            return
        self._reload(select_id=org.id)

    def _delete(self):
        org = self._selected()
        if org is None:
            return
        can_one = len(orgs.list_orgs()) > 1
        if not can_one and self._on_delete_all is None:
            QMessageBox.information(self, "Удаление организации",
                                    "Это единственная организация. Удалить все данные можно в программе: "
                                    "«Настройки и темы → Безопасность → Опасная зона».")
            return
        dlg = OrgDeleteDialog(self, org, can_delete_one=can_one, allow_all=self._on_delete_all is not None)
        if dlg.exec() != BaseDialog.DialogCode.Accepted:
            return
        if dlg.choice == OrgDeleteDialog.ALL:
            if self._on_delete_all is not None:
                self.reject()
                self._on_delete_all()
            return
        try:
            orgs.delete_org(org.id)
        except (orgs.OrgError, OSError) as e:
            logger.error("Failed to delete organization: %s", type(e).__name__)
            QMessageBox.warning(self, "Удаление организации",
                                str(e) if isinstance(e, orgs.OrgError) else "Не удалось удалить данные организации")
            return
        if org.id == self._current_id:
            self.deleted_current = True
            self._current_id = None
        self._reload()
