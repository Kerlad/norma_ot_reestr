#!/usr/bin/env bash
# Build an .rpm (ALT Linux / RED OS) from the PyInstaller output. L-06.
# Usage: tools/linux/make_rpm.sh    -> dist/normaot-reestr-<version>-alt1.x86_64.rpm
# rpmbuild is taken from $RPMBUILD or PATH (on Debian/Ubuntu: `apt install rpm`; without root,
# `apt-get download rpm librpm* ...` + `dpkg -x` into a directory, then set RPMBUILD and RPM_CONFIGDIR).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -x dist/normaot-reestr/normaot-reestr ] || { echo "Run PyInstaller first (build_linux.sh)" >&2; exit 1; }
RPMBUILD="${RPMBUILD:-$(command -v rpmbuild || true)}"
[ -x "$RPMBUILD" ] || { echo "rpmbuild not found (set RPMBUILD)" >&2; exit 1; }

VERSION="$(sed -n 's/^VERSION *= *"\([0-9.]*\)".*/\1/p' utils/about_dialog.py | head -1)"
GLIBC_FLOOR="$("$ROOT/tools/linux/glibc_floor.sh" dist/normaot-reestr)"
echo "glibc floor of this build: ${GLIBC_FLOOR}"

TOP="$ROOT/dist/rpm-top"
rm -rf "$TOP"
mkdir -p "$TOP"/{SOURCES,SPECS,BUILD,RPMS,SRPMS,BUILDROOT}
cp -a dist/normaot-reestr "$TOP/SOURCES/normaot-reestr"
cp tools/linux/normaot-reestr.desktop "$TOP/SOURCES/"
cp resources/icon.png "$TOP/SOURCES/normaot-reestr.png"
sed -e "s/@VERSION@/${VERSION}/" -e "s/@GLIBC@/${GLIBC_FLOOR}/" \
    tools/linux/normaot-reestr.spec.in > "$TOP/SPECS/normaot-reestr.spec"

# gzip payload: readable by the oldest rpm versions (zstd/xz are not available everywhere)
"$RPMBUILD" -bb --target x86_64 \
    --define "_topdir $TOP" \
    --define "_binary_payload w9.gzdio" \
    --define "_build_id_links none" \
    --define "_buildhost normaot" \
    "$TOP/SPECS/normaot-reestr.spec"

OUT="normaot-reestr-${VERSION}-alt1.x86_64.rpm"
cp "$TOP"/RPMS/x86_64/*.rpm "dist/${OUT}"
rm -rf "$TOP"
(cd dist && sha256sum "${OUT}" > "${OUT}.sha256")
echo "Built dist/${OUT}"
