#!/usr/bin/env bash
# Re-vendor bluetti-modbus-lib's device library (published on PyPI as
# bluetti-modbus) into custom_components/bluetti/vendor/bluetti_modbus_lib/.
#
# This integration bundles its own copy rather than depending on it via
# pip - see quality_scale.yaml's dependency-transparency comment. Run this
# after a bluetti-community/bluetti-modbus release to pick up changes.
set -euo pipefail

REF="${1:-main}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$ROOT_DIR/custom_components/bluetti/vendor/bluetti_modbus_lib"
CLONE_DIR="$(mktemp -d)"
trap 'rm -rf "$CLONE_DIR"' EXIT

echo "==> Cloning bluetti-modbus@$REF"
git clone -q --depth 1 --branch "$REF" \
    https://github.com/bluetti-community/bluetti-modbus.git "$CLONE_DIR"
COMMIT="$(git -C "$CLONE_DIR" rev-parse HEAD)"

echo "==> Replacing vendored copy"
rm -rf "$VENDOR_DIR"
cp -r "$CLONE_DIR/src/bluetti_modbus_lib" "$VENDOR_DIR"
find "$VENDOR_DIR" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

cat >"$VENDOR_DIR/VENDORED.md" <<EOF
Vendored from https://github.com/bluetti-community/bluetti-modbus
(published on PyPI as bluetti-modbus) at commit $COMMIT ($REF).

Re-vendor with: scripts/vendor_bluetti_modbus_lib.sh [ref]
EOF

echo "==> Vendored bluetti-modbus at $COMMIT"
