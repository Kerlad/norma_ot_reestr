#!/usr/bin/env bash
# One command for the whole Linux release: PyInstaller build + tar.gz + .deb (+ .rpm if rpmbuild exists). L-06.
# Run on the OLDEST supported target OS (or any host: the bundle ships no host system libraries, so the
# glibc floor is set by PySide6/cryptography wheels, currently 2.34). Use a PORTABLE Python
# (e.g. `uv venv --python 3.12`), not the distro's: the distro Python's _decimal etc. raise the floor.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

bash tools/linux/build_linux.sh
bash tools/linux/make_deb.sh
if [ -n "${RPMBUILD:-}" ] || command -v rpmbuild >/dev/null; then
    bash tools/linux/make_rpm.sh
else
    echo "rpmbuild not found: skipping .rpm" >&2
fi
echo "--- artifacts"
ls -l dist/*.tar.gz dist/*.deb dist/*.rpm 2>/dev/null || true
(cd dist && cat *.sha256)
