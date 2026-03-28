#!/usr/bin/env bash
# Clean rebuild of dist/YulangADB.app. Run from any cwd; requires repo venv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d venv ]]; then
  echo "Missing venv/ — create with: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$ROOT/venv/bin/activate"
pip install -q -r requirements.txt -r requirements-dev.txt
rm -rf build dist
pyinstaller yulang_gui.spec
echo "Built: $ROOT/dist/YulangADB.app"
