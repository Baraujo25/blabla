#!/bin/bash
# simple-bar on-click — launch BlaBla.app (owns mic permission).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/helper/BlaBla.app"
mkdir -p "${BLABLA_HOME:-$HOME/.blabla}"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP" >>"${BLABLA_HOME:-$HOME/.blabla}/blabla.log"
  exit 1
fi

# -n: new instance each click so start and stop toggles reliably.
open -n "$APP"
