#!/usr/bin/env bash
# Print the highest GLIBC_x.y symbol version required by a PyInstaller onedir build (the real glibc floor).
# Usage: tools/linux/glibc_floor.sh [dir]   (default dist/normaot-reestr)
set -euo pipefail
DIR="${1:-dist/normaot-reestr}"
command -v objdump >/dev/null || { echo "objdump (binutils) not found" >&2; exit 1; }
find "$DIR" -type f \( -name '*.so' -o -name '*.so.*' -o -perm -u+x \) -print0 \
  | xargs -0 -r -n1 sh -c 'file -b "$0" | grep -q ELF && objdump -T "$0" 2>/dev/null | grep -o "GLIBC_[0-9][0-9.]*"' \
  | sort -uV | tail -1 | sed 's/GLIBC_//'
