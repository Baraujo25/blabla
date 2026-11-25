#!/bin/bash
# simple-bar right-click — reset stuck state and cancel transcription.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export BLABLA_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Run scripts/setup.sh" >&2
  exit 1
fi
exec "$ROOT/.venv/bin/python" -m blabla reset
