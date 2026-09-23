#!/usr/bin/env bash
set -euo pipefail

REPO="${LOGRES_GITHUB_REPO:-alfred092020-ux/awakened-realms}"
MANIFEST=""
TAG=""
TITLE=""
NOTES=""
DRY_RUN=0
CLOBBER=0
ALLOW_UNVERIFIED=0

usage() {
  cat <<'EOF'
usage: publish_android_checkpoint.sh --manifest <manifest.json> [options]

Publish a verified Android checkpoint as a GitHub prerelease.

Options:
  --manifest <path>       Manifest produced by build_android_checkpoint.sh
  --tag <tag>             Release tag (default: demo-0.2-<shortsha>)
  --title <title>         Release title
  --notes <text>          Additional release notes
  --repo <owner/name>     GitHub repository
  --clobber               Replace same-named release assets if tag exists
  --allow-unverified      Explicitly permit an UNVERIFIED manifest
  --dry-run               Validate everything but do not create/upload release
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST="${2:?--manifest requires a value}"
      shift 2
      ;;
    --tag)
      TAG="${2:?--tag requires a value}"
      shift 2
      ;;
    --title)
      TITLE="${2:?--title requires a value}"
      shift 2
      ;;
    --notes)
      NOTES="${2:?--notes requires a value}"
      shift 2
      ;;
    --repo)
      REPO="${2:?--repo requires a value}"
      shift 2
      ;;
    --clobber)
      CLOBBER=1
      shift
      ;;
    --allow-unverified)
      ALLOW_UNVERIFIED=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "$MANIFEST" ]] || {
  echo "--manifest is required" >&2
  exit 2
}
[[ -f "$MANIFEST" ]] || {
  echo "Manifest unavailable: $MANIFEST" >&2
  exit 1
}

eval "$(
python3 - "$MANIFEST" <<'PY'
import json,pathlib,shlex,sys
m=json.loads(pathlib.Path(sys.argv[1]).read_text())
if m.get("schema")!="logres-android-checkpoint-v1":
    raise SystemExit("Unsupported checkpoint manifest schema")
fields={
  "SOURCE_SHA":m["source"]["sha"],
  "SHORT_SHA":m["source"]["short_sha"],
  "LABEL":m["build"]["label"],
  "VERIFY_STATUS":m["verification"]["status"],
  "APK_PATH":m["apk"]["path"],
  "APK_SHA":m["apk"]["sha256"],
  "SIGNATURE_VERIFIED":"1" if m["apk"].get("signature_verified") else "0",
  "VERSION_CODE":m["apk"].get("version_code",""),
  "VERSION_NAME":m["apk"].get("version_name",""),
}
for key,value in fields.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)"

[[ -f "$APK_PATH" ]] || {
  echo "APK unavailable: $APK_PATH" >&2
  exit 1
}
ACTUAL_APK_SHA="$(sha256sum "$APK_PATH" | awk '{print $1}')"
[[ "$ACTUAL_APK_SHA" == "$APK_SHA" ]] || {
  echo "APK hash mismatch: manifest=$APK_SHA actual=$ACTUAL_APK_SHA" >&2
  exit 1
}
[[ "$SIGNATURE_VERIFIED" == "1" ]] || {
  echo "Manifest does not attest successful APK signature verification" >&2
  exit 1
}

if [[ "$VERIFY_STATUS" != "PASS" && "$ALLOW_UNVERIFIED" -ne 1 ]]; then
  echo "Refusing to publish checkpoint with verification status $VERIFY_STATUS" >&2
  exit 1
fi

[[ -n "$TAG" ]] || TAG="${LABEL}-${SHORT_SHA}"
[[ -n "$TITLE" ]] || TITLE="Awakened Realms ${LABEL} @ ${SHORT_SHA}"

DEFAULT_NOTES="$(
  printf '%s\n' \
    'Exact-SHA Android checkpoint.' \
    '' \
    "- Source: \`$SOURCE_SHA\`" \
    "- Verification: \`$VERIFY_STATUS\`" \
    "- Android version: \`$VERSION_NAME\` (code \`$VERSION_CODE\`)" \
    "- APK SHA256: \`$APK_SHA\`" \
    '- Signature: verified' \
    '' \
    'This is a test prerelease for reconstruction QA.'
)"
if [[ -n "$NOTES" ]]; then
  RELEASE_NOTES="$DEFAULT_NOTES

$NOTES"
else
  RELEASE_NOTES="$DEFAULT_NOTES"
fi

echo "[publish] repo=$REPO"
echo "[publish] tag=$TAG"
echo "[publish] target=$SOURCE_SHA"
echo "[publish] apk=$APK_PATH"
echo "[publish] manifest=$MANIFEST"
echo "[publish] verification=$VERIFY_STATUS"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[publish] DRY RUN PASS"
  exit 0
fi

gh auth status >/dev/null

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "[publish] release exists: $TAG"
  args=(gh release upload "$TAG" "$APK_PATH" "$MANIFEST" --repo "$REPO")
  if [[ "$CLOBBER" -eq 1 ]]; then
    args+=(--clobber)
  fi
  "${args[@]}"
else
  gh release create "$TAG"     "$APK_PATH"     "$MANIFEST"     --repo "$REPO"     --target "$SOURCE_SHA"     --title "$TITLE"     --notes "$RELEASE_NOTES"     --prerelease
fi

echo "[publish] PASS tag=$TAG"
