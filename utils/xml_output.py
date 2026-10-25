"""Where generated XML files go and how they are named.

Default folder: «XML» inside the program folder when it is writable, otherwise
«Документы\\Норма ОТ\\XML». The user can pick their own folder in «Настройки и темы → Файлы».
File name: ДДММГГГГ-ЧЧ-ММ.xml; if it already exists, «-2», «-3», … is appended.
"""
import os
import sys
from datetime import datetime
from typing import Optional

PREF_XML_DIR = "xml_output_dir"
SUBFOLDER = "XML"
DOCS_SUBFOLDER = os.path.join("Норма ОТ", "XML")


def _program_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    from utils.app_paths import get_resource_dir
    return get_resource_dir()


def _documents_dir() -> str:
    try:
        from PySide6.QtCore import QStandardPaths
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if docs:
            return docs
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def is_writable_dir(path: str, create: bool = True) -> bool:
    """True if a file can really be created in `path` (os.access lies on Windows ACLs).

    create=False never creates folders: for a missing `path` the nearest existing parent is probed,
    so merely showing the folder in the settings does not litter the disk."""
    try:
        if create:
            os.makedirs(path, exist_ok=True)
        else:
            while path and not os.path.isdir(path):
                parent = os.path.dirname(path)
                if parent == path:
                    return False
                path = parent
        probe = os.path.join(path, ".write_test_%d" % os.getpid())
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(probe)
        return True
    except OSError:
        return False


def custom_xml_dir() -> str:
    """Folder chosen by the user ('' = default)."""
    from tabs.send_history_panel import load_ui_pref
    value = load_ui_pref(PREF_XML_DIR, "")
    return value if isinstance(value, str) else ""


def set_custom_xml_dir(path: str) -> None:
    from tabs.send_history_panel import save_ui_pref
    save_ui_pref(PREF_XML_DIR, path or "")


def default_xml_dir() -> str:
    program = os.path.join(_program_dir(), SUBFOLDER)
    if is_writable_dir(program, create=False):
        return program
    return os.path.join(_documents_dir(), DOCS_SUBFOLDER)


def get_xml_dir() -> str:
    """Folder for the next XML: the user's choice if it is usable, else the default."""
    custom = custom_xml_dir()
    if custom and is_writable_dir(custom, create=False):
        return custom
    return default_xml_dir()


def xml_file_name(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime("%d%m%Y-%H-%M") + ".xml"


def next_xml_path(now: Optional[datetime] = None, directory: Optional[str] = None) -> str:
    """Free path for a new XML. Creates the folder; raises OSError if it cannot be created."""
    folder = directory or get_xml_dir()
    os.makedirs(folder, exist_ok=True)
    base = xml_file_name(now)
    stem, ext = os.path.splitext(base)
    candidate = os.path.join(folder, base)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, "%s-%d%s" % (stem, n, ext))
        n += 1
    return candidate
