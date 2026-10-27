# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for «Норма ОТ: Реестр обучения» on Linux (L-06).

Build (from the project root, Linux venv active) — see tools/linux/build_linux.sh:
    python -m PyInstaller NormaOT_Reestr_linux.spec --noconfirm

Result: dist/normaot-reestr/normaot-reestr + dist/normaot-reestr/_internal/ (onedir).
Build with a PORTABLE Python (uv), not the distro one. The bundle ships no host system libraries
(see the filter below), so the minimum glibc is set by the PySide6/cryptography wheels (2.34 now);
check with tools/linux/glibc_floor.sh.

Same data layout as the Windows spec (schema/, templates/, resources/ in _internal/),
but no version resource, no icon resource, no pywin32. User data lives in
$XDG_DATA_HOME/NormaOT (utils.app_paths).
"""
import glob
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(SPECPATH)
APP_NAME = "normaot-reestr"

datas = [
    (os.path.join(ROOT, "schema", "educated_person_import_v1.0.9.xsd"), "schema"),
    (os.path.join(ROOT, "CHANGELOG.md"), "."),
    (os.path.join(ROOT, "templates"), "templates"),
    (os.path.join(ROOT, "resources"), "resources"),
]

# keyring picks its backend at run time (entry points), so PyInstaller cannot see them;
# truststore is imported lazily inside utils.tls_context.
hiddenimports = (
    collect_submodules("keyring.backends")
    + ["secretstorage", "jeepney", "truststore"]
)

# Extra libraries not present on older target distros (tools/linux/fetch_extra_libs.sh puts them here).
binaries = [(f, ".") for f in sorted(glob.glob(os.path.join(ROOT, "build", "extra_libs", "*.so*")))]

excludes = [
    # Windows-only modules and dev/test tooling the app never uses on Linux
    "win32crypt", "win32security", "ntsecuritycon", "win32api", "pywintypes",
    "win32com", "win32timezone", "winreg",
    "tkinter", "pytest", "_pytest", "IPython", "matplotlib", "numpy",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Do NOT ship the build host's system libraries (libstdc++, libsystemd, libxkbcommon, libpango, ...):
# they were built against the host's glibc (Ubuntu 24.04 -> glibc 2.38) and would raise the minimum
# OS version. The target OS provides them (package dependencies). Libraries from the portable Python,
# the PySide6/cryptography wheels and build/extra_libs are kept.
_SYSTEM_DIRS = ("/usr/lib/x86_64-linux-gnu/", "/lib/x86_64-linux-gnu/", "/usr/lib64/", "/lib64/",
                "/usr/lib/aarch64-linux-gnu/", "/lib/aarch64-linux-gnu/")
a.binaries = TOC([b for b in a.binaries if not os.path.realpath(b[1]).startswith(_SYSTEM_DIRS)
                  or os.path.dirname(b[1]) == os.path.join(ROOT, "build", "extra_libs")])
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
