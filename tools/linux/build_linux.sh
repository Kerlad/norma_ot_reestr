#!/usr/bin/env bash
# Build the Linux release: PyInstaller onedir -> tar.gz (+ SHA-256). L-06.
# Run on the OLDEST supported target OS (glibc floor), from any directory, venv active:
#   tools/linux/build_linux.sh
# Result: dist/normaot-reestr-<version>-linux-<arch>.tar.gz and .sha256
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^VERSION *= *"\([0-9.]*\)".*/\1/p' utils/about_dialog.py | head -1)"
[ -n "$VERSION" ] || { echo "VERSION not found in utils/about_dialog.py" >&2; exit 1; }
ARCH="$(uname -m)"
NAME="normaot-reestr-${VERSION}-linux-${ARCH}"

rm -rf build/NormaOT_Reestr_linux "dist/normaot-reestr"
python -m PyInstaller NormaOT_Reestr_linux.spec --noconfirm

STAGE="dist/${NAME}"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -a dist/normaot-reestr "$STAGE/normaot-reestr"
cp tools/linux/normaot-reestr.desktop "$STAGE/"
cp resources/icon.png "$STAGE/normaot-reestr.png"
cp tools/linux/INSTALL.txt "$STAGE/"

tar -C dist -czf "dist/${NAME}.tar.gz" "${NAME}"
rm -rf "$STAGE"
(cd dist && sha256sum "${NAME}.tar.gz" > "${NAME}.tar.gz.sha256")

echo "Built dist/${NAME}.tar.gz"
cat "dist/${NAME}.tar.gz.sha256"
echo "glibc floor of the build (min target glibc): $(tools/linux/glibc_floor.sh dist/normaot-reestr || echo unknown)"
echo "glibc of this build host: $(ldd --version | head -1)"
