# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for «Норма ОТ: Реестр обучения» on Linux (L-06).

Build (from the project root, Linux venv active) — see tools/linux/build_linux.sh:
    python -m PyInstaller NormaOT_Reestr_linux.spec --noconfirm

Result: dist/normaot-reestr/normaot-reestr + dist/normaot-reestr/_internal/ (onedir).
Build on the OLDEST supported target OS: the bundled libc symbols set the minimum glibc
(PySide6 wheels need glibc >= 2.28).

Same data layout as the Windows spec (schema/, templates/, resources/ in _internal/),
but no version resource, no icon resource, no pywin32. User data lives in
$XDG_DATA_HOME/NormaOT (utils.app_paths).
"""
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(SPECPATH)
APP_NAME = "normaot-reestr"

datas = [
    (os.path.join(ROOT, "schema", "educated_person_import_v1.0.9.xsd"), "schema"),
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "resources"), "resources"),
]

# keyring picks its backend at run time (entry points), so PyInstaller cannot see them;
# truststore is imported lazily inside utils.tls_context.
hiddenimports = (
    collect_submodules("keyring.backends")
    + ["secretstorage", "jeepney", "truststore"]
)

excludes = [
    # Windows-only modules and dev/test tooling the app never uses on Linux
    "win32crypt", "win32security", "ntsecuritycon", "win32api", "pywintypes",
    "win32com", "win32timezone", "winreg",
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
