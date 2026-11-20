#!/usr/bin/env bash
# Usage: build.sh [OUT_DIR] [--since 180d]   -> collect + render, prints index.html path
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$(dirname "$HERE")/out}"
shift || true
python3 "$HERE/collect.py" --out "$OUT" "$@"
python3 "$HERE/render.py" --out "$OUT"
echo "$OUT/index.html"
