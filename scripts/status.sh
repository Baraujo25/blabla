#!/bin/bash
# simple-bar refresh — prints a short status label.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export BLABLA_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Run scripts/setup.sh" >&2
  exit 1
fi
exec "$ROOT/.venv/bin/python" -m blabla status
