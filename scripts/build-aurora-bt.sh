#!/usr/bin/env bash
# Build on Apple Silicon or Linux using the official Aurora BT 5.2.1 image.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="${ARTIFACT_DIR:-$PROJECT_ROOT/artifacts/rpm}"
case "$(uname -m)" in
  arm64|aarch64)
    PLATFORM=linux/arm64
    DIGEST=ee8a3a16192c10ef3de252f9be13f93102db73a0c1ddbefe214a9b3c62553115
    ;;
  x86_64)
    PLATFORM=linux/amd64
    DIGEST=eaa0b8a79550c31c706dc100a2f7635a360cfcfc126ce83ff8a8f1fce19d4f4c
    ;;
  *) echo "Unsupported host architecture" >&2; exit 1 ;;
esac
case "${AURORA_ARCH:-arm64}" in
  arm64) TARGET_FLAG=--arm64 ;;
  arm32) TARGET_FLAG=--arm32 ;;
  x64) TARGET_FLAG=--x64 ;;
  *) echo "AURORA_ARCH must be arm64, arm32 or x64" >&2; exit 1 ;;
esac
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
BUILD_ROOT="$(mktemp -d "$OUTPUT_DIR/nirs-bt.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT
cp -R "$PROJECT_ROOT/aurora_client" "$BUILD_ROOT/source"
docker run --rm --platform "$PLATFORM" --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$BUILD_ROOT/source,dst=/sources" --workdir /sources \
  "hub.omp.ru/public/sdk-build-tools@sha256:$DIGEST" \
  apptool build "$TARGET_FLAG" 2>&1 | tee "$OUTPUT_DIR/build.log"
found=0
while IFS= read -r -d '' package; do
  cp "$package" "$OUTPUT_DIR/"
  found=1
done < <(find "$BUILD_ROOT/source/RPMS" -type f -name 'ru.nirs.Client-*.rpm' \
  ! -name '*debuginfo*' ! -name '*debugsource*' -print0)
if [[ "$found" != 1 ]]; then
  echo "Build finished without the expected client RPM" >&2
  exit 1
fi
printf 'Signed and validated RPM packages: %s\n' "$OUTPUT_DIR"
