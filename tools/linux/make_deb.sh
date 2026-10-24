#!/usr/bin/env bash
# Build a .deb from the PyInstaller output (run build_linux.sh's PyInstaller step first). L-06.
# Usage: tools/linux/make_deb.sh   -> dist/normaot-reestr_<version>_<debarch>.deb
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -x dist/normaot-reestr/normaot-reestr ] || { echo "Run PyInstaller first (build_linux.sh)" >&2; exit 1; }

VERSION="$(sed -n 's/^VERSION *= *"\([0-9.]*\)".*/\1/p' utils/about_dialog.py | head -1)"
DEBARCH="$(dpkg --print-architecture)"
PKG="dist/deb-root"
rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/normaot-reestr" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/pixmaps"

cp -a dist/normaot-reestr/. "$PKG/opt/normaot-reestr/"
ln -s /opt/normaot-reestr/normaot-reestr "$PKG/usr/bin/normaot-reestr"
cp tools/linux/normaot-reestr.desktop "$PKG/usr/share/applications/"
cp resources/icon.png "$PKG/usr/share/pixmaps/normaot-reestr.png"

GLIBC_FLOOR="$("$ROOT/tools/linux/glibc_floor.sh" dist/normaot-reestr || true)"
echo "glibc floor of this build: ${GLIBC_FLOOR:-unknown}"
chmod 644 "$PKG/usr/share/applications/normaot-reestr.desktop"
SIZE_KB="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<CTRL
Package: normaot-reestr
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: ${DEBARCH}
Installed-Size: ${SIZE_KB}
Maintainer: Кривоносов Д.А. <denis.krv@yandex.ru>
Depends: libc6 (>= ${GLIBC_FLOOR:-2.34}), libstdc++6 (>= 11), libgcc-s1, zlib1g, libegl1, libgl1, libglx0, libx11-6, libx11-xcb1, libxcb1, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render0, libxcb-render-util0, libxcb-shape0, libxcb-shm0, libxcb-sync1, libxcb-util1, libxcb-xfixes0, libxcb-xkb1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libfreetype6, libdbus-1-3, libglib2.0-0, libpng16-16, libwayland-client0, libwayland-cursor0
Recommends: gnome-keyring | kwalletmanager, fonts-liberation2 | fonts-liberation
Description: Норма ОТ: Реестр обучения
 Реестр обучения по охране труда и обмен данными с реестром Минтруда.
 Данные хранятся локально, мастер-ключ защищён связкой ключей ОС или парольной фразой.
CTRL

dpkg-deb --root-owner-group --build "$PKG" "dist/normaot-reestr_${VERSION}_${DEBARCH}.deb"
rm -rf "$PKG"
(cd dist && sha256sum "normaot-reestr_${VERSION}_${DEBARCH}.deb" > "normaot-reestr_${VERSION}_${DEBARCH}.deb.sha256")
echo "Built dist/normaot-reestr_${VERSION}_${DEBARCH}.deb"
