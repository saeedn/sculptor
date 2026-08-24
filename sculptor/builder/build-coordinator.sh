#!/usr/bin/env bash
# This script builds a standalone executable for the coordinator CLI using PyInstaller.
# We need to build for multiple architectures, so we accept a python key argument to select the architecture that uv will use. By default it will use the system default python.
set -euxo pipefail

# Resolve the script's own directory before changing into the project, so every
# path below is anchored to the repo rather than to the caller's cwd.
BUILDER_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$BUILDER_DIR/../../tools/coordinator"

PYKEY="${1:-}"

# Let's create a temporary virtual environment for the build process.
TEMP_ENV="$(mktemp -d -t coordinator-venv.XXXXXX)"
trap 'rm -rf "$TEMP_ENV"' EXIT

# If no PYKEY was provided, choose a deterministic default on macOS
if [[ -z "$PYKEY" && "$(uname -s)" == "Darwin" ]]; then
  PYKEY="cpython-3.14.4-macos-aarch64-none"
elif [[ -z "$PYKEY" ]]; then
  PYKEY="3.14.4"
fi

ARCH_PREFIX=""
if [[ "$(uname -s)" == "Darwin" ]]; then
  if [[ "$PYKEY" == *"-x86_64-"* ]]; then
    echo "==> Building for x86_64 architecture"
    ARCH_PREFIX="arch -x86_64"
  fi
else
  echo "==> Non-macOS-Intel build, using system default architecture"
fi

# Set the path correctly for brew-installed utils depending on if we are using arch or not
if [[ -n "$ARCH_PREFIX" ]]; then # if ARCH_PREFIX is set, we are on macOS and using arch
  export PATH="/usr/local/bin:/usr/local/sbin:$PATH"
else
    echo "==> Not using arch, leaving PATH alone"
fi

# Ensure the requested interpreter exists and create a nonce env with it
$ARCH_PREFIX uv python install "$PYKEY" >/dev/null
$ARCH_PREFIX uv venv -p "$PYKEY" "$TEMP_ENV" --clear

export UV_PROJECT_ENVIRONMENT="$TEMP_ENV"

echo "==> Using ARCH_PREFIX: ${ARCH_PREFIX:-<none>}"
echo "==> Using uv python key: ${PYKEY:-<default>}"
echo "==> Using UV_PROJECT_ENVIRONMENT: $UV_PROJECT_ENVIRONMENT"

# Install dependencies into the nonce env
$ARCH_PREFIX uv sync --no-dev --extra packaging

# Time to build. The coordinator reads its prompt templates and built-in worker
# registrations through `importlib.resources`, and textual loads its own widget
# styles and tree-sitter grammars the same way, so both packages need their data
# files collected — module-level imports alone would leave them out.
$ARCH_PREFIX uv run --no-dev --extra packaging \
pyinstaller --onedir --name coordinator \
  --collect-all coordinator \
  --copy-metadata coordinator \
  --collect-all textual \
  --noupx \
  --noconfirm \
  coordinator/main.py

# Copy the output to sculptor/dist/coordinator/ so Electron forge can find it
DEST_DIR="$BUILDER_DIR/../dist/coordinator"
rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
cp -R dist/coordinator/* "$DEST_DIR/"

# Verify the build was for the correct architecture.
if [[ "$(uname -s)" == "Darwin" ]]; then
   if [[ "$PYKEY" == *"-x86_64-"* ]]; then
    echo "==> Verifying x86_64 architecture for coordinator"
    file "$DEST_DIR/coordinator" | grep "x86_64" || (echo "ERROR: coordinator is not x86_64!" && exit 1)
   else
    echo "==> Verifying arm64 architecture for coordinator"
    file "$DEST_DIR/coordinator" | grep "arm64" || (echo "ERROR: coordinator is not arm64!" && exit 1)
   fi
else
   echo "==> Non-macOS build, skipping architecture verification"
fi
