#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/home/ubuntu/android-sdk}}"
OUT="${1:-/home/ubuntu/logres/artifacts/nexus-command-center}"
mkdir -p "$OUT"
printf 'sdk.dir=%s\n' "$SDK" > "$HERE/local.properties"

cd "$HERE"
./gradlew --no-daemon clean assembleDebug

APK="$HERE/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$OUT/nexus-command-center-$STAMP.apk"
cp "$APK" "$DEST"
SHA="$(sha256sum "$DEST" | awk '{print $1}')"
printf '%s  %s\n' "$SHA" "$DEST"
