# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for «Норма ОТ: Реестр обучения».

Build (from the project root, venv active):
    py -m PyInstaller NormaOT_Reestr.spec --noconfirm

Result: dist/NormaOT_Reestr/NormaOT_Reestr.exe + dist/NormaOT_Reestr/_internal/
(onedir build: faster start and fewer antivirus false positives than onefile).

Runtime files are looked up via utils.app_paths.get_resource_dir(), which in a
frozen build resolves to _internal/, so schema/, templates/ and resources/ are
copied there. User data never goes here: it lives in %APPDATA%\\NormaOT.

The file version shown in Explorer is taken from utils/about_dialog.py:VERSION,
so it can no longer drift from the version displayed in the app.
"""
import os
import re

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = os.path.abspath(SPECPATH)
APP_NAME = "NormaOT_Reestr"


def _read_version():
    with open(os.path.join(ROOT, "utils", "about_dialog.py"), encoding="utf-8-sig") as f:
        m = re.search(r'^VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', f.read(), re.M)
    if not m:
        raise SystemExit("VERSION not found in utils/about_dialog.py")
    return tuple(int(x) for x in m.groups()) + (0,)


VERSION = _read_version()
VERSION_STR = ".".join(str(x) for x in VERSION)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=VERSION, prodvers=VERSION),
    kids=[
        StringFileInfo([StringTable("041904B0", [
            StringStruct("CompanyName", "Кривоносов Д.А."),
            StringStruct("FileDescription", "Норма ОТ: Реестр обучения"),
            StringStruct("FileVersion", VERSION_STR),
            StringStruct("InternalName", APP_NAME),
            StringStruct("LegalCopyright", "MIT License"),
            StringStruct("OriginalFilename", APP_NAME + ".exe"),
            StringStruct("ProductName", "Норма ОТ: Реестр обучения"),
            StringStruct("ProductVersion", VERSION_STR),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0419, 1200])]),
    ],
)

datas = [
    (os.path.join(ROOT, "schema", "educated_person_import_v1.0.9.xsd"), "schema"),
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "resources"), "resources"),
]

hiddenimports = [
    # pywin32 pieces imported lazily inside functions (DPAPI, ACLs, Outlook COM, WinINET)
    "win32crypt", "win32security", "ntsecuritycon", "win32api", "pywintypes",
    "win32com.client", "win32timezone",
]

excludes = [
    # dev/test tooling and toolkits the app never uses
    "tkinter", "pytest", "_pytest", "IPython", "matplotlib", "numpy",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed binaries trigger antivirus false positives
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "resources", "ico.ico"),
    version=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
