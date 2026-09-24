# Logres Android release candidate

`RELEASE-1.0` is packaged from one exact `feat/logres-reconstruction` SHA. The
release process does not modify `main` and does not publish automatically.

## Build

```bash
SHA="$(git rev-parse feat/logres-reconstruction)"
scripts/logres/build_release_candidate.sh --sha "$SHA"
```

The command fails closed unless:

- the supplied SHA is the current reconstruction integration SHA;
- the integration worktree is clean;
- every earlier milestone is `DONE` with a valid `PASS` certificate whose
  artifact hash still matches;
- the exact SHA has an authoritative `full-e2e` `PASS`;
- private runtime inputs hydrate successfully;
- the Android debug APK builds and its signature verifies;
- the checkpoint manifest and APK hashes agree.

Artifacts are written under:

```text
/home/ubuntu/logres/artifacts/releases/release-1.0/<short-sha>/
```

The release-candidate manifest uses
`logres-android-release-candidate-v1` and binds the exact source SHA, APK hash,
checkpoint-manifest hash, full-E2E verification record, and prerequisite
milestone certificates.

Reproducibility is **exact-input/process reproducibility**. The manifest does
not claim that APK ZIP bytes will be bit-identical across different build
hosts or toolchain timestamps.

## Verify

```bash
scripts/logres/verify_release_candidate.py \
  /home/ubuntu/logres/artifacts/releases/release-1.0/<short-sha>/release-candidate.manifest.json
```

Verification rejects stale SHAs, tampered APKs/manifests, missing milestone
certificates, invalid certificate hashes, and non-PASS checkpoint verification.

## Publish

Packaging never publishes. After release certification and exact-current-SHA
real-device proof are satisfied, publication remains an explicit action:

```bash
scripts/logres/publish_android_checkpoint.sh \
  --manifest /home/ubuntu/logres/artifacts/releases/release-1.0/<short-sha>/checkpoint/Awakened-Realms-release-1.0-<short-sha>.manifest.json \
  --tag release-1.0-<short-sha> \
  --title "Awakened Realms RELEASE-1.0 @ <short-sha>"
```

The publisher rechecks APK hash, signature attestation, and verification status
before creating the GitHub prerelease.
