#!/bin/bash
# Build BlaBla on a clean Apple Silicon Mac.
# Prerequisites: Xcode Command Line Tools, ffmpeg, Python 3.11+, git, curl.
# CMake is downloaded only when the system does not already have it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WHISPER_CPP_TAG="v1.9.6"
CMAKE_VERSION="3.31.8"
SRC="$ROOT/.tools/whisper.cpp"
SUPPORT="${BLABLA_SUPPORT_DIR:-$HOME/Library/Application Support/BlaBla}"
BIN_DIR="$SUPPORT/bin"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing $1. $2" >&2
    exit 1
  fi
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "BlaBla setup targets macOS." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This setup is tested on Apple Silicon. Continuing anyway." >&2
fi

need git "Install Xcode Command Line Tools: xcode-select --install"
need clang "Install Xcode Command Line Tools: xcode-select --install"
need curl "curl is part of macOS; reinstall the Command Line Tools if it is missing."
need python3 "Install Python 3.11 or newer from https://www.python.org/downloads/macos/"
if ! command -v ffmpeg >/dev/null 2>&1 && [[ ! -x /opt/homebrew/bin/ffmpeg ]] && [[ ! -x /usr/local/bin/ffmpeg ]]; then
  echo "ffmpeg is required. Install it with Homebrew (brew install ffmpeg) or from https://ffmpeg.org/download.html" >&2
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ is required, found {sys.version.split()[0]}")
PY

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT/.venv"
fi

bash "$ROOT/scripts/build-helper.sh"

find_cmake() {
  if command -v cmake >/dev/null 2>&1; then
    command -v cmake
    return
  fi
  local bundled="$ROOT/.tools/cmake-${CMAKE_VERSION}-macos-universal/CMake.app/Contents/bin/cmake"
  if [[ -x "$bundled" ]]; then
    echo "$bundled"
    return
  fi
  echo "Downloading CMake ${CMAKE_VERSION}…" >&2
  mkdir -p "$ROOT/.tools"
  curl -L --fail --retry 3 -o "$ROOT/.tools/cmake.tar.gz" \
    "https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-macos-universal.tar.gz"
  tar -xzf "$ROOT/.tools/cmake.tar.gz" -C "$ROOT/.tools"
  echo "$bundled"
}

CMAKE="$(find_cmake)"

if [[ ! -d "$SRC/.git" ]]; then
  git clone --depth 1 --branch "$WHISPER_CPP_TAG" https://github.com/ggml-org/whisper.cpp.git "$SRC"
fi

python3 - "$SRC/examples/server/server.cpp" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text()
old = "    int32_t read_timeout  = 600;\n    int32_t write_timeout = 600;\n"
new = "    int32_t read_timeout  = 3600;\n    int32_t write_timeout = 3600;\n"
if old in text:
    path.write_text(text.replace(old, new, 1))
    print("Raised whisper-server socket timeouts to 3600s")
elif "write_timeout = 3600" in text:
    print("whisper-server timeouts already raised")
else:
    raise SystemExit("Could not find whisper-server timeout defaults. The pinned revision may have changed.")
PY

"$CMAKE" -S "$SRC" -B "$SRC/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_METAL=ON \
  -DGGML_METAL_EMBED_LIBRARY=ON \
  -DWHISPER_BUILD_EXAMPLES=ON \
  -DWHISPER_BUILD_TESTS=OFF
"$CMAKE" --build "$SRC/build" --config Release --parallel "$(sysctl -n hw.ncpu)" \
  --target whisper-cli whisper-server

mkdir -p "$BIN_DIR"
cp -R "$SRC/build/bin/." "$BIN_DIR/"
python3 - "$SRC/build/bin" "$BIN_DIR" <<'PY'
import os, subprocess, sys
source, dest = sys.argv[1], sys.argv[2]
for name in os.listdir(dest):
    path = os.path.join(dest, name)
    if not os.path.isfile(path) or os.path.islink(path):
        continue
    info = subprocess.run(["file", "-b", path], capture_output=True, text=True).stdout
    if "Mach-O" not in info:
        continue
    subprocess.run(["install_name_tool", "-add_rpath", "@loader_path", path], check=False)
    subprocess.run(["install_name_tool", "-delete_rpath", source, path], check=False)
    subprocess.run(["codesign", "--force", "--sign", "-", path], check=False)
PY

"$ROOT/.venv/bin/python" -m blabla download-model
echo
echo "BlaBla is ready."
echo "  ./scripts/blabla doctor"
echo "  ./scripts/blabla warmup"
echo "Point simple-bar at scripts/status.sh, scripts/toggle.sh, and scripts/reset.sh."
