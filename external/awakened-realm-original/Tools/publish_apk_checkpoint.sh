#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <apk-path> <source-sha> <checkpoint-name>" >&2
  exit 2
fi

apk="$1"
source_sha="$2"
name="$3"

if [[ ! -f "$apk" ]]; then
  echo "APK not found: $apk" >&2
  exit 3
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

current_sha="$(git rev-parse HEAD)"
if [[ "$current_sha" != "$source_sha" ]]; then
  echo "HEAD $current_sha does not match requested source SHA $source_sha" >&2
  exit 4
fi

apk_sha="$(sha256sum "$apk" | awk '{print $1}')"
short="\${source_sha:0:12}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tag="awakened-realms-apk-\${short}-\${stamp}"

notes="$(mktemp)"
trap 'rm -f "$notes"' EXIT
cat >"$notes" <<EOF
Awakened Realms Android checkpoint

Source SHA: $source_sha
APK SHA-256: $apk_sha
Checkpoint: $name
Build type: development/test checkpoint

This build is preserved for owner testing. It is not a production certification unless separately recorded.
EOF

gh release create "$tag" "$apk" \
  --repo alfred092020-ux/awakened-realms \
  --target "$source_sha" \
  --title "Awakened Realms APK - $name" \
  --notes-file "$notes" \
  --prerelease

echo "PUBLISHED tag=$tag source_sha=$source_sha apk_sha256=$apk_sha"
