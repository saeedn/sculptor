#!/usr/bin/env bash
# Run integration tests against the packaged Sculptor application.
# Unlike acceptance tests, failures here block the release (no || true).
#
# Usage: test-sculptor-desktop-packaged.sh <platform> <architecture>
set -euo pipefail
set -x

# Extract the packaged binary based on platform
if [[ "$1" == "darwin" ]]; then
    # Use the DMG since that's the only macOS artifact published in TARGET_TO_FILES.
    dmg_path="../dist/Sculptor.dmg"
    mount_dir="/Volumes/Sculptor"
    hdiutil attach "$dmg_path" -nobrowse -noautoopen
    cp -R "$mount_dir/Sculptor.app" ../dist/Sculptor.app
    hdiutil detach "$mount_dir"
    xattr -d com.apple.quarantine ../dist/Sculptor.app 2>/dev/null || true
    BINARY_PATH="../dist/Sculptor.app/Contents/Resources/sculptor_backend/sculptor_backend"
    LAUNCH_MODE="packaged-backend"
elif [[ "$1" == "linux" ]]; then
    img="../dist/AppImage/$2/Sculptor.AppImage"
    chmod +x "$img"
    pushd "$(dirname "$img")" >/dev/null
    rm -rf squashfs-root
    "./$(basename "$img")" --appimage-extract
    popd >/dev/null
    BINARY_PATH="../dist/AppImage/$2/squashfs-root/usr/bin/Sculptor"
    LAUNCH_MODE="packaged-electron"
else
    echo "FAIL: Unsupported platform: $1"
    exit 1
fi

if [ ! -x "$BINARY_PATH" ]; then
    echo "FAIL: Packaged binary not found or not executable at $BINARY_PATH"
    exit 1
fi
echo "Binary found at: $BINARY_PATH"

# Wrap pytest in a bash timeout so a hung test cannot consume the entire CI job
# timeout. Defaults to 900s; override with PACKAGED_TEST_TIMEOUT_SECONDS. Keep
# it under the CI job timeout so there is room for the SIGINT (+60s kill-after)
# and the artifact upload that follows.
pytest_timeout_seconds="${PACKAGED_TEST_TIMEOUT_SECONDS:-900}"
timeout_cmd="timeout"
if [[ "$1" == "darwin" ]] && ! command -v timeout &>/dev/null; then
    timeout_cmd="gtimeout"  # coreutils on macOS
fi

set +eo pipefail
${timeout_cmd} --signal=INT --kill-after=60s "${pytest_timeout_seconds}" \
uv run --project sculptor pytest ./tests/integration \
    --sculptor-launch-mode="$LAUNCH_MODE" \
    --packaged-binary-path="$BINARY_PATH" \
    --tracing=retain-on-failure \
    --screenshot=only-on-failure \
    --junitxml=packaged_tests_junit.xml \
    --timeout=120 \
    -v -ra -s \
    "${@:3}" \
    2>&1 | tee packaged_tests.log
TEST_EXIT_CODE=${PIPESTATUS[0]}
set -eo pipefail
exit "$TEST_EXIT_CODE"
