#!/bin/bash
# Compile the microphone helper. No model download.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/helper/BlaBla.app"
BIN="$APP/Contents/MacOS/BlaBlaBin"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -whole-module-optimization \
  -framework AVFoundation \
  -o "$BIN" \
  "$ROOT/helper/RequestMicAndRun.swift"
chmod +x "$APP/Contents/MacOS/BlaBla"
codesign --force --sign - "$BIN"
codesign --force --deep --sign - "$APP"
echo "Built $APP"
