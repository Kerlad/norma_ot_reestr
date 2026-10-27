"""«Что нового»: the CHANGELOG.md section of the running version (click on the version in the sidebar)."""
import os
import re

from PySide6.QtWidgets import QTextBrowser

from utils.app_paths import get_resource_dir
from utils.dialog_base import BaseDialog
from utils.about_dialog import VERSION


_HEADINGS = {"Added": "Добавлено", "Changed": "Изменено", "Fixed": "Исправлено", "Removed": "Удалено",
             "Security": "Безопасность", "Deprecated": "Устарело"}


def read_version_notes(version: str = VERSION) -> str:
    """Section of CHANGELOG.md for `version` (Markdown), or a short fallback."""
    path = os.path.join(get_resource_dir(), "CHANGELOG.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return "Описание изменений недоступно."
    sections = re.split(r"(?m)^(?=## v)", text)
    for sec in sections:
        if sec.startswith("## v%s " % version) or sec.startswith("## v%s\n" % version):
            # CHANGELOG headings are English (Keep a Changelog); the dialog is for users
            for en, ru in _HEADINGS.items():
                sec = re.sub(r"(?m)^### %s\s*$" % en, "### " + ru, sec)
            return sec.strip()
    return "Для версии %s описание изменений не найдено." % version


class WhatsNewDialog(BaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Что нового в версии %s" % VERSION, min_width=720, min_height=480)
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setMarkdown(read_version_notes())
        self.body_layout().addWidget(view)
        self.add_close_button()
