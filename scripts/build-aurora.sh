#!/usr/bin/env bash
# Run on a Linux self-hosted Azure agent with Aurora SDK already configured.
set -euo pipefail
: "${AURORA_TARGET:?Set the installed target from sfdk tools list}"
: "${AURORA_WORKSPACE:?Set the workspace selected when installing Aurora SDK}"
SFDK_BIN="${SFDK_BIN:-sfdk}"
command -v "$SFDK_BIN" >/dev/null || { echo "Aurora SDK sfdk not found" >&2; exit 1; }
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${ARTIFACT_DIR:-$PROJECT_ROOT/artifacts/aurora}"
mkdir -p "$OUTPUT_DIR"
BUILD_ROOT="$(mktemp -d "$AURORA_WORKSPACE/nirs-build.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT
cp -R "$PROJECT_ROOT/aurora_client" "$BUILD_ROOT/source"
mkdir "$BUILD_ROOT/build"
cd "$BUILD_ROOT/build"
"$SFDK_BIN" config "target=$AURORA_TARGET"
"$SFDK_BIN" build ../source
"$SFDK_BIN" check
found=0
while IFS= read -r -d '' package; do
  cp "$package" "$OUTPUT_DIR/"
  found=1
done < <(find "$BUILD_ROOT" -type f -name 'ru.nirs.Client-*.rpm' ! -name '*debuginfo*' ! -name '*debugsource*' -print0)
if [[ "$found" != 1 ]]; then
  echo "Build finished without the expected client RPM" >&2
  exit 1
fi
printf 'RPM packages published to %s\n' "$OUTPUT_DIR"
