#!/usr/bin/env bash
set -euo pipefail

BASE="${LOGRES_REPO:-/home/ubuntu/logres/src/awakened-realms}"
CONTROL_DB="${LOGRES_CONTROL_DB:-/home/ubuntu/logres/control/control.sqlite}"
PRIVATE_ANCHOR="${LOGRES_PRIVATE_ANCHOR:-/home/ubuntu/logres/private/logres-private-cache.zip}"
GLOBAL_ARCHIVE="${LOGRES_GLOBAL_ARCHIVE:-/home/ubuntu/logres/private/global-files.zip}"
JP_CACHE="${LOGRES_JP_CACHE:-/home/ubuntu/logres/private/jp-live-patch-cache}"
CANONICAL_RUNTIME="${LOGRES_CANONICAL_RUNTIME:-$BASE/public/__logres_ref}"
ANDROID_SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/home/ubuntu/android-sdk}}"
ARTIFACT_DIR="${LOGRES_APK_ARTIFACT_DIR:-/home/ubuntu/logres/artifacts/apk}"
TMP_ROOT="${LOGRES_TMP_ROOT:-/home/ubuntu/logres/tmp}"

REF="origin/feat/logres-reconstruction"
LABEL="demo-0.2"
ALLOW_UNVERIFIED=0
SKIP_VERIFY=0
KEEP_WORKTREE=0

usage() {
  cat <<'EOF'
usage: build_android_checkpoint.sh [options]

Build a signed Android debug checkpoint from one exact Git SHA.

Options:
  --ref <branch-or-sha>       Source ref (default: origin/feat/logres-reconstruction)
  --label <artifact-label>    Artifact label (default: demo-0.2)
  --artifact-dir <path>       Output directory
  --allow-unverified          Permit build without a recorded full-e2e PASS;
                              manifest is marked UNVERIFIED
  --skip-verify               Do not invoke final gate when PASS cache is absent
  --keep-worktree             Preserve temporary detached worktree for debugging
  -h, --help                  Show this help

Default behavior is verified-only. If the exact SHA has no recorded full-e2e
PASS, the authoritative private final gate is run. Packaging aborts if the SHA
still has no PASS. The repository's main branch is never checked out or changed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      REF="${2:?--ref requires a value}"
      shift 2
      ;;
    --label)
      LABEL="${2:?--label requires a value}"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="${2:?--artifact-dir requires a value}"
      shift 2
      ;;
    --allow-unverified)
      ALLOW_UNVERIFIED=1
      shift
      ;;
    --skip-verify)
      SKIP_VERIFY=1
      shift
      ;;
    --keep-worktree)
      KEEP_WORKTREE=1
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

case "$REF" in
  main|refs/heads/main|origin/main|refs/remotes/origin/main)
    echo "Refusing symbolic main ref. Build an exact SHA or reconstruction branch instead." >&2
    exit 2
    ;;
esac

if [[ ! -d "$BASE/.git" && ! -f "$BASE/.git" ]]; then
  echo "Repository unavailable: $BASE" >&2
  exit 1
fi

git -C "$BASE" fetch origin --prune >/dev/null 2>&1 || true
SHA="$(git -C "$BASE" rev-parse "${REF}^{commit}")"
SHORT_SHA="${SHA:0:12}"
SOURCE_REF="$REF"

sanitize_label() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//'
}
LABEL="$(sanitize_label "$LABEL")"
[[ -n "$LABEL" ]] || LABEL="checkpoint"

verification_record() {
  python3 - "$CONTROL_DB" "$SHA" <<'PY'
import sqlite3,sys
db,sha=sys.argv[1:]
try:
    connection=sqlite3.connect(db)
    row=connection.execute(
        "select ref, ran_at, details from verification "
        "where sha=? and mode='full-e2e' and status='PASS' "
        "order by ran_at desc limit 1",
        (sha,),
    ).fetchone()
except Exception:
    row=None
if row:
    print("|".join("" if value is None else str(value) for value in row))
PY
}

VERIFY_RECORD="$(verification_record)"
if [[ -z "$VERIFY_RECORD" && "$SKIP_VERIFY" -eq 0 ]]; then
  echo "[verify] no cached full-e2e PASS for $SHORT_SHA; running authoritative final gate"
  /home/ubuntu/logres/bin/logres-gate final "$SHA"
  VERIFY_RECORD="$(verification_record)"
fi

if [[ -n "$VERIFY_RECORD" ]]; then
  VERIFICATION_STATUS="PASS"
  VERIFICATION_REF="${VERIFY_RECORD%%|*}"
  VERIFY_REST="${VERIFY_RECORD#*|}"
  VERIFICATION_RAN_AT="${VERIFY_REST%%|*}"
  VERIFICATION_DETAIL="${VERIFY_REST#*|}"
else
  VERIFICATION_STATUS="UNVERIFIED"
  VERIFICATION_REF=""
  VERIFICATION_RAN_AT=""
  VERIFICATION_DETAIL=""
  if [[ "$ALLOW_UNVERIFIED" -ne 1 ]]; then
    echo "Refusing unverified SHA $SHA. Use --allow-unverified only for explicit diagnostic builds." >&2
    exit 1
  fi
  echo "[verify] WARNING: building explicitly UNVERIFIED source $SHORT_SHA" >&2
fi

mkdir -p "$ARTIFACT_DIR" "$TMP_ROOT"
WT="$(mktemp -d "$TMP_ROOT/apk-checkpoint.${SHORT_SHA}.XXXXXX")"
rmdir "$WT"
HYDRATION_DIR="$WT/.apk-hydration"
BUILD_STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cleanup() {
  rc=$?
  trap - EXIT INT TERM
  if [[ "$KEEP_WORKTREE" -eq 1 ]]; then
    echo "[cleanup] preserving worktree: $WT"
  else
    git -C "$BASE" worktree remove --force "$WT" >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

echo "[source] $SOURCE_REF -> $SHA"
git -C "$BASE" worktree add --detach "$WT" "$SHA" >/dev/null
ACTUAL_SHA="$(git -C "$WT" rev-parse HEAD)"
[[ "$ACTUAL_SHA" == "$SHA" ]] || {
  echo "Detached worktree SHA mismatch" >&2
  exit 1
}

mkdir -p "$HYDRATION_DIR" "$WT/public/__logres_ref"

tree_digest() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    printf ''
    return
  fi
  (
    cd "$path"
    find . -type f -print0 | sort -z | xargs -0 sha256sum
  ) | sha256sum | awk '{print $1}'
}

hydrate_copy_dir() {
  local name="$1"
  local src="$2"
  local dst="$3"
  if [[ -d "$src" ]]; then
    echo "[hydrate] canonical $name"
    mkdir -p "$(dirname "$dst")"
    rm -rf "$dst"
    cp -a "$src" "$dst"
    printf '%s\n' "$(tree_digest "$dst")" > "$HYDRATION_DIR/${name}.tree.sha256"
  fi
}

# Canonical private UI/config derivatives have no single source hydrator yet.
# Copy them as explicit, hashed build inputs; specialized packages below are
# regenerated from their private source archives whenever the target SHA
# provides the corresponding hydrator.
hydrate_copy_dir "global-runtime" "$CANONICAL_RUNTIME/global" "$WT/public/__logres_ref/global"
hydrate_copy_dir "config-runtime" "$CANONICAL_RUNTIME/config" "$WT/public/__logres_ref/config"

run_hydrator() {
  local name="$1"
  shift
  echo "[hydrate] $name"
  "$@"
}

if [[ -f "$WT/scripts/logres/hydrate_global_renderer_candidate.py" ]]; then
  [[ -f "$PRIVATE_ANCHOR" ]] || { echo "Missing private anchor: $PRIVATE_ANCHOR" >&2; exit 1; }
  run_hydrator "Global playable map 002_000_00001"     python3 "$WT/scripts/logres/hydrate_global_renderer_candidate.py"       "$PRIVATE_ANCHOR"       --map-id 002_000_00001       --output-root "$WT/public/__logres_ref/renderer-proof"       --profile linear       --summary "$HYDRATION_DIR/renderer-candidate.json"
fi

if [[ -f "$WT/scripts/logres/hydrate_global_tutorial_hud.py" ]]; then
  [[ -f "$GLOBAL_ARCHIVE" ]] || { echo "Missing Global archive: $GLOBAL_ARCHIVE" >&2; exit 1; }
  run_hydrator "Global tutorial HUD"     python3 "$WT/scripts/logres/hydrate_global_tutorial_hud.py"       "$GLOBAL_ARCHIVE"       --output-root "$WT/public/__logres_ref/global/tutorial-hud"       --summary "$HYDRATION_DIR/tutorial-hud.json"
fi

if [[ -f "$WT/scripts/logres/hydrate_global_title_effects.py" ]]; then
  [[ -f "$GLOBAL_ARCHIVE" ]] || { echo "Missing Global archive: $GLOBAL_ARCHIVE" >&2; exit 1; }
  run_hydrator "Global title effects"     python3 "$WT/scripts/logres/hydrate_global_title_effects.py"       "$GLOBAL_ARCHIVE"       --output-root "$WT/public/__logres_ref/global/gui/title/effect/png"       --summary "$HYDRATION_DIR/title-effects.json"
fi

if [[ -f "$WT/scripts/logres/hydrate_tutorial_pointer.py" ]]; then
  [[ -d "$JP_CACHE" ]] || { echo "Missing current-JP cache: $JP_CACHE" >&2; exit 1; }
  run_hydrator "current-JP tutorial field references"     python3 "$WT/scripts/logres/hydrate_tutorial_pointer.py"       "$JP_CACHE"       --output-root "$WT/public/__logres_ref/current-jp/tutorial-field"       --summary "$HYDRATION_DIR/tutorial-field.json"
fi

if [[ -f "$WT/scripts/logres/inspect_avatar_resource_paths.py" ]]; then
  [[ -d "$JP_CACHE" ]] || { echo "Missing current-JP cache: $JP_CACHE" >&2; exit 1; }
  run_hydrator "current-JP player avatar references"     python3 "$WT/scripts/logres/inspect_avatar_resource_paths.py"       "$JP_CACHE"       --output-root "$WT/public/__logres_ref/current-jp/player-avatar-reference"       --summary "$HYDRATION_DIR/player-avatar.json"
fi

base_lock="$(sha256sum "$BASE/package-lock.json" | awk '{print $1}')"
ref_lock="$(sha256sum "$WT/package-lock.json" | awk '{print $1}')"
if [[ "$base_lock" == "$ref_lock" && -d "$BASE/node_modules" ]]; then
  ln -s "$BASE/node_modules" "$WT/node_modules"
  DEPS_MODE="shared-canonical-node-modules"
  echo "[deps] shared canonical node_modules"
else
  DEPS_MODE="npm-ci"
  echo "[deps] lockfile differs; npm ci"
  (cd "$WT" && npm ci --prefer-offline --no-audit --no-fund)
fi

echo "[web] npm run build"
(cd "$WT" && npm run build)

echo "[capacitor] sync android"
(cd "$WT" && npx cap sync android)

if [[ ! -d "$ANDROID_SDK" ]]; then
  echo "Android SDK unavailable: $ANDROID_SDK" >&2
  exit 1
fi
printf 'sdk.dir=%s\n' "$ANDROID_SDK" > "$WT/android/local.properties"
chmod +x "$WT/android/gradlew"

KEYSTORE="${LOGRES_ANDROID_DEBUG_KEYSTORE:-$HOME/.android/debug.keystore}"
if [[ ! -f "$KEYSTORE" ]]; then
  echo "Stable Android debug keystore unavailable: $KEYSTORE" >&2
  exit 1
fi

echo "[android] assembleDebug"
(
  cd "$WT/android"
  ./gradlew assembleDebug --no-daemon
)

BUILT_APK="$WT/android/app/build/outputs/apk/debug/app-debug.apk"
[[ -f "$BUILT_APK" ]] || {
  echo "Gradle completed without expected APK: $BUILT_APK" >&2
  exit 1
}

APKSIGNER="$(find "$ANDROID_SDK/build-tools" -type f -name apksigner | sort -V | tail -1)"
AAPT="$(find "$ANDROID_SDK/build-tools" -type f -name aapt | sort -V | tail -1)"
[[ -x "$APKSIGNER" ]] || { echo "apksigner unavailable" >&2; exit 1; }
[[ -x "$AAPT" ]] || { echo "aapt unavailable" >&2; exit 1; }

SIGNATURE_REPORT="$HYDRATION_DIR/apksigner.txt"
"$APKSIGNER" verify --verbose --print-certs "$BUILT_APK" | tee "$SIGNATURE_REPORT"
grep -q '^Verifies' "$SIGNATURE_REPORT" || {
  echo "APK signature verification did not report success" >&2
  exit 1
}

BADGING="$HYDRATION_DIR/aapt-badging.txt"
"$AAPT" dump badging "$BUILT_APK" > "$BADGING"

PACKAGE_NAME="$(sed -n "s/^package: name='\([^']*\)'.*/\1/p" "$BADGING" | head -1)"
VERSION_CODE="$(sed -n "s/^package:.*versionCode='\([^']*\)'.*/\1/p" "$BADGING" | head -1)"
VERSION_NAME="$(sed -n "s/^package:.*versionName='\([^']*\)'.*/\1/p" "$BADGING" | head -1)"
CERT_SHA256="$(sed -n 's/^Signer #1 certificate SHA-256 digest: //p' "$SIGNATURE_REPORT" | head -1)"
if [[ -z "$CERT_SHA256" ]]; then
  CERT_SHA256="$(sha256sum "$KEYSTORE" | awk '{print $1}')"
fi

ARTIFACT_BASENAME="Awakened-Realms-${LABEL}-${SHORT_SHA}"
APK_OUT="$ARTIFACT_DIR/${ARTIFACT_BASENAME}.apk"
MANIFEST_OUT="$ARTIFACT_DIR/${ARTIFACT_BASENAME}.manifest.json"
cp "$BUILT_APK" "$APK_OUT"

APK_SHA256="$(sha256sum "$APK_OUT" | awk '{print $1}')"
APK_BYTES="$(stat -c '%s' "$APK_OUT")"
KEYSTORE_SHA256="$(sha256sum "$KEYSTORE" | awk '{print $1}')"
BUILD_FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 -   "$MANIFEST_OUT" "$SOURCE_REF" "$SHA" "$SHORT_SHA" "$LABEL"   "$VERIFICATION_STATUS" "$VERIFICATION_REF" "$VERIFICATION_RAN_AT" "$VERIFICATION_DETAIL"   "$APK_OUT" "$APK_SHA256" "$APK_BYTES" "$PACKAGE_NAME" "$VERSION_CODE" "$VERSION_NAME"   "$CERT_SHA256" "$KEYSTORE_SHA256" "$DEPS_MODE" "$BUILD_STARTED" "$BUILD_FINISHED"   "$HYDRATION_DIR" "$WT" <<'PY'
import hashlib,json,pathlib,sys
(
 manifest_path,source_ref,sha,short_sha,label,
 verification_status,verification_ref,verification_ran_at,verification_detail,
 apk_path,apk_sha256,apk_bytes,package_name,version_code,version_name,
 cert_sha256,keystore_sha256,deps_mode,started,finished,
 hydration_dir,worktree,
)=sys.argv[1:]

hydration_root=pathlib.Path(hydration_dir)
hydration=[]
for path in sorted(hydration_root.iterdir()):
    if not path.is_file():
        continue
    data=path.read_bytes()
    entry={
        "name":path.name,
        "sha256":hashlib.sha256(data).hexdigest(),
        "bytes":len(data),
    }
    if path.suffix==".json":
        try:
            entry["summary"]=json.loads(data)
        except Exception:
            pass
    hydration.append(entry)

manifest={
    "schema":"logres-android-checkpoint-v1",
    "source":{
        "ref":source_ref,
        "sha":sha,
        "short_sha":short_sha,
        "detached_worktree":True,
        "main_branch_modified":False,
    },
    "verification":{
        "status":verification_status,
        "mode":"full-e2e",
        "record_ref":verification_ref or None,
        "ran_at":verification_ran_at or None,
        "detail":verification_detail or None,
    },
    "build":{
        "label":label,
        "started_utc":started,
        "finished_utc":finished,
        "dependency_mode":deps_mode,
        "steps":[
            "private-runtime-hydration",
            "npm run build",
            "npx cap sync android",
            "gradle assembleDebug",
            "apksigner verify",
            "aapt badging",
            "sha256",
        ],
    },
    "apk":{
        "path":apk_path,
        "sha256":apk_sha256,
        "bytes":int(apk_bytes),
        "package_name":package_name,
        "version_code":version_code,
        "version_name":version_name,
        "certificate_sha256":cert_sha256,
        "debug_keystore_sha256":keystore_sha256,
        "signature_verified":True,
    },
    "hydration":hydration,
}
pathlib.Path(manifest_path).write_text(
    json.dumps(manifest,indent=2,sort_keys=True,allow_nan=False)+"\n"
)
PY

MANIFEST_SHA256="$(sha256sum "$MANIFEST_OUT" | awk '{print $1}')"
cat <<EOF
[checkpoint] PASS
source_sha=$SHA
verification=$VERIFICATION_STATUS
apk=$APK_OUT
apk_sha256=$APK_SHA256
manifest=$MANIFEST_OUT
manifest_sha256=$MANIFEST_SHA256
package=$PACKAGE_NAME
versionCode=$VERSION_CODE
versionName=$VERSION_NAME
EOF
