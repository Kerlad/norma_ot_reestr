#!/usr/bin/env bash
# Put libxcb-cursor.so.0 (needed by Qt's xcb plugin, missing on some distros) into build/extra_libs
# for the PyInstaller spec. Taken from Debian 12 (bookworm), not from the build host: the host's copy
# may need a newer glibc (Ubuntu 24.04 -> 2.38) and would raise the package's minimum OS version. L-06.
# Needs no root. The download is checked against a pinned SHA-256 (value from the signed bookworm index).
set -euo pipefail

DEB="libxcb-cursor0_0.1.4-1_amd64.deb"
URL="https://deb.debian.org/debian/pool/main/x/xcb-util-cursor/${DEB}"
SHA256="a4b3c32dc008275ffcacccc1c77c030f01aad38e232e05d5ad116b76656c607c"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/build/extra_libs"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

curl -fsSL -o "$TMP/$DEB" "$URL"
echo "$SHA256  $TMP/$DEB" | sha256sum -c - >/dev/null || { echo "SHA-256 mismatch for $DEB" >&2; exit 1; }
dpkg -x "$TMP/$DEB" "$TMP/x"
cp -a "$TMP"/x/usr/lib/*/libxcb-cursor.so.0* "$OUT/"
ls -l "$OUT"
