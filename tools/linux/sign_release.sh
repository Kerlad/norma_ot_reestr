#!/usr/bin/env bash
# Detached GPG signature (.asc) for release artifacts. L-06.
# The private key is NEVER in the repo: pass the key id/fingerprint in NORMAOT_GPG_KEY.
# Usage: NORMAOT_GPG_KEY=<fingerprint> tools/linux/sign_release.sh dist/<file> [...]
# Exit code 2 = no key configured (artifacts stay unsigned, only SHA-256 is published).
set -euo pipefail
[ $# -ge 1 ] || { echo "usage: $0 <file>..." >&2; exit 1; }
if [ -z "${NORMAOT_GPG_KEY:-}" ]; then
    echo "NORMAOT_GPG_KEY is not set: skipping signature" >&2
    exit 2
fi
for f in "$@"; do
    gpg --batch --yes --local-user "$NORMAOT_GPG_KEY" --armor --detach-sign --output "$f.asc" "$f"
    gpg --verify "$f.asc" "$f"
    echo "Signed $f.asc"
done
