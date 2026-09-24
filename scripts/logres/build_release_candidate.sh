#!/usr/bin/env bash
set -euo pipefail

BASE="${LOGRES_REPO:-/home/ubuntu/logres/src/awakened-realms}"
CONTROL_DB="${LOGRES_CONTROL_DB:-/home/ubuntu/logres/control/control.sqlite}"
ARTIFACT_ROOT="${LOGRES_RELEASE_ARTIFACT_ROOT:-/home/ubuntu/logres/artifacts/releases}"
SHA=""

usage() {
  cat <<'USAGE'
usage: build_release_candidate.sh --sha <40-char-integration-sha> [options]

Build and verify a RELEASE-1.0 Android candidate from the exact current
feat/logres-reconstruction SHA. This command packages only; it never publishes.

Options:
  --sha <sha>              Exact current integration SHA (required)
  --artifact-root <path>   Release artifact root
  -h, --help               Show help

The command fails closed unless:
- the requested SHA equals current feat/logres-reconstruction HEAD,
- the integration worktree is clean,
- every milestone before RELEASE-1.0 is DONE and has a PASS certificate,
- the exact SHA has full-e2e PASS,
- the signed checkpoint APK and all referenced hashes verify.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sha)
      SHA="${2:?--sha requires a value}"
      shift 2
      ;;
    --artifact-root)
      ARTIFACT_ROOT="${2:?--artifact-root requires a value}"
      shift 2
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

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "--sha must be an exact lowercase 40-character Git SHA" >&2
  exit 2
}

CURRENT_SHA="$(git -C "$BASE" rev-parse 'feat/logres-reconstruction^{commit}')"
[[ "$SHA" == "$CURRENT_SHA" ]] || {
  echo "Refusing stale/non-current release SHA: requested=$SHA current=$CURRENT_SHA" >&2
  exit 1
}

git -C "$BASE" diff --quiet
git -C "$BASE" diff --cached --quiet

SHORT_SHA="${SHA:0:12}"
OUT_DIR="$ARTIFACT_ROOT/release-1.0/$SHORT_SHA"
CHECKPOINT_DIR="$OUT_DIR/checkpoint"
PREREQ_JSON="$OUT_DIR/prerequisite-certificates.json"
RELEASE_MANIFEST="$OUT_DIR/release-candidate.manifest.json"
RELEASE_MANIFEST_SHA="$RELEASE_MANIFEST.sha256"

mkdir -p "$CHECKPOINT_DIR"

python3 - "$CONTROL_DB" "$PREREQ_JSON" <<'PY'
import hashlib
import json
import pathlib
import sqlite3
import sys

db_path, output = sys.argv[1:]
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

release = conn.execute(
    "select sort_order from milestones where id='RELEASE-1.0'"
).fetchone()
if release is None:
    raise SystemExit("RELEASE-1.0 milestone missing")

required = list(
    conn.execute(
        """select id,status from milestones
             where sort_order < ?
             order by sort_order,id""",
        (int(release["sort_order"]),),
    )
)

records = []
for milestone in required:
    milestone_id = str(milestone["id"])
    if str(milestone["status"]) != "DONE":
        raise SystemExit(f"prerequisite milestone not DONE: {milestone_id}")

    cert = conn.execute(
        """select id,milestone_id,integration_sha,contract_fingerprint,status,
                  artifact_path,artifact_sha256,created_at
             from milestone_certificates
            where milestone_id=? and status='PASS'
            order by id desc limit 1""",
        (milestone_id,),
    ).fetchone()
    if cert is None:
        raise SystemExit(f"PASS certificate missing: {milestone_id}")

    artifact = pathlib.Path(str(cert["artifact_path"]))
    if not artifact.is_file():
        raise SystemExit(f"certificate artifact missing: {artifact}")
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    expected = str(cert["artifact_sha256"])
    if actual != expected:
        raise SystemExit(
            f"certificate artifact hash mismatch {milestone_id}: "
            f"expected={expected} actual={actual}"
        )

    payload = json.loads(artifact.read_text())
    if (
        payload.get("milestone_id") != milestone_id
        or payload.get("status") != "PASS"
        or payload.get("valid") is not True
    ):
        raise SystemExit(f"certificate payload invalid: {milestone_id}")

    records.append(dict(cert))

path = pathlib.Path(output)
path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
print(f"[prerequisites] {len(records)} milestone certificates verified")
PY

echo "[checkpoint] build exact SHA $SHA"
LOGRES_REPO="$BASE" \
LOGRES_CONTROL_DB="$CONTROL_DB" \
LOGRES_APK_ARTIFACT_DIR="$CHECKPOINT_DIR" \
  "$BASE/scripts/logres/build_android_checkpoint.sh" \
    --ref "$SHA" \
    --label release-1.0 \
    --artifact-dir "$CHECKPOINT_DIR"

BASENAME="Awakened-Realms-release-1.0-${SHORT_SHA}"
APK="$CHECKPOINT_DIR/$BASENAME.apk"
CHECKPOINT_MANIFEST="$CHECKPOINT_DIR/$BASENAME.manifest.json"
[[ -f "$APK" && -f "$CHECKPOINT_MANIFEST" ]] || {
  echo "Expected checkpoint artifacts missing" >&2
  exit 1
}

echo "[publication] validate checkpoint publication without publishing"
"$BASE/scripts/logres/publish_android_checkpoint.sh" \
  --manifest "$CHECKPOINT_MANIFEST" \
  --tag "release-1.0-$SHORT_SHA" \
  --title "Awakened Realms RELEASE-1.0 @ $SHORT_SHA" \
  --dry-run

python3 - \
  "$CONTROL_DB" "$SHA" "$APK" "$CHECKPOINT_MANIFEST" "$PREREQ_JSON" \
  "$RELEASE_MANIFEST" <<'PY'
import hashlib
import json
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

db_path, sha, apk_raw, checkpoint_raw, prereq_raw, output_raw = sys.argv[1:]
apk = pathlib.Path(apk_raw)
checkpoint_path = pathlib.Path(checkpoint_raw)
prereq_path = pathlib.Path(prereq_raw)
output = pathlib.Path(output_raw)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checkpoint = json.loads(checkpoint_path.read_text())
prereqs = json.loads(prereq_path.read_text())
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
verify = conn.execute(
    """select ref,ran_at,details,duration_sec
         from verification
        where sha=? and mode='full-e2e' and status='PASS'
        order by ran_at desc limit 1""",
    (sha,),
).fetchone()
if verify is None:
    raise SystemExit(f"full-e2e PASS missing for release SHA {sha}")

manifest = {
    "schema": "logres-android-release-candidate-v1",
    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "release": {
        "milestone_id": "RELEASE-1.0",
        "publication_state": "PACKAGED_NOT_PUBLISHED",
        "tag": f"release-1.0-{sha[:12]}",
    },
    "source": {
        "sha": sha,
        "integration_branch": "feat/logres-reconstruction",
        "main_branch_modified": False,
    },
    "verification": {
        "status": "PASS",
        "mode": "full-e2e",
        "ref": verify["ref"],
        "ran_at": verify["ran_at"],
        "details": verify["details"],
        "duration_sec": verify["duration_sec"],
    },
    "apk": {
        "path": str(apk),
        "sha256": digest(apk),
        "bytes": apk.stat().st_size,
        "package_name": checkpoint["apk"].get("package_name"),
        "version_code": checkpoint["apk"].get("version_code"),
        "version_name": checkpoint["apk"].get("version_name"),
        "signature_verified": bool(checkpoint["apk"].get("signature_verified")),
        "certificate_sha256": checkpoint["apk"].get("certificate_sha256"),
    },
    "checkpoint_manifest": {
        "path": str(checkpoint_path),
        "sha256": digest(checkpoint_path),
        "schema": checkpoint.get("schema"),
    },
    "milestone_certificates": prereqs,
    "reproducibility": {
        "class": "EXACT_INPUT_PROCESS_REPRODUCIBLE",
        "bit_for_bit_apk_claim": False,
        "note": (
            "The candidate is reproducible from the exact Git SHA, recorded "
            "verification, hashed private hydration summaries, Android toolchain "
            "steps and signing provenance in the checkpoint manifest. No claim "
            "is made that ZIP/APK bytes are bit-identical across build hosts."
        ),
    },
}
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(f"[manifest] {output}")
PY

"$BASE/scripts/logres/verify_release_candidate.py" \
  "$RELEASE_MANIFEST" \
  --repo "$BASE" \
  --control-db "$CONTROL_DB"

sha256sum "$RELEASE_MANIFEST" > "$RELEASE_MANIFEST_SHA"

echo "[release] PASS"
echo "RELEASE_SHA=$SHA"
echo "APK=$APK"
echo "CHECKPOINT_MANIFEST=$CHECKPOINT_MANIFEST"
echo "RELEASE_MANIFEST=$RELEASE_MANIFEST"
echo "RELEASE_MANIFEST_SHA256=$(awk '{print $1}' "$RELEASE_MANIFEST_SHA")"
