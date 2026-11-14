"""Start folder for «Save as» dialogs: never the program folder, never the app data folder."""
import os

from utils import xml_output


def default_save_dir() -> str:
    """The user's XML folder if set and usable, else «Документы\\Норма ОТ\\XML».

    Does not create the folder: the dialog opens in the nearest existing parent."""
    return xml_output.get_xml_dir()


def suggest_path(file_name: str) -> str:
    """Start path for a save dialog: default_save_dir() + file name."""
    return os.path.join(default_save_dir(), file_name)
