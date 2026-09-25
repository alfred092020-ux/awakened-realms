# Brain Plugin Integration Core — Phase 1 Implementation Plan

Date: 2026-09-24
Task: BRAIN-PLUGIN-INTEGRATION-CORE-001
Branch: worker/plugins-brain-plugin-integration-core-001
Base integration SHA: 5b687cbe143a6c574ea533751577d405b5b83b68
Spec authority: worker/plugins-brain-plugin-integration-spec-002 @ 59c80f62dfb8d28a2ea979c94736eb938ccfc938
Spec path: docs/superpowers/specs/2026-09-24-logres-brain-plugin-integration-design.md

## Goal

Implement the provider-agnostic Phase 1 integration core as isolated new control-plane files, without touching active workers' files.

## Global Constraints

- Do not touch main.
- Do not modify existing claimed files in this task.
- Additive SQLite schema only.
- No provider credentials or secrets in SQLite.
- No external provider calls in Phase 1.
- No provider API call while holding a SQLite write transaction.
- All mutating behavior developed RED -> GREEN.
- Every uncertain mutating provider outcome must support RECONCILING.
- Irreversible side effects cannot be blindly retried.
- Brain remains the operational authority.

## Files

Create:
- ops/logres-control-plane/lib/logres_integration.py
- ops/logres-control-plane/bin/logres-integration
- ops/logres-control-plane/tests/test_integration.py

This task intentionally does NOT modify:
- logres-chat-start
- deployment manifest
- logres-brain
- coordinator
- existing route store

Those hooks are deferred to a follow-up task after active claims clear.

## Task 1 — Schema, canonical JSON, hashing, and secret rejection

Tests first:
- schema creation is idempotent
- required integration tables and indexes exist
- canonical hash is deterministic across dict key order
- secret-like keys are rejected recursively

Implement minimum helpers:
- ensure_schema
- canonical_json
- canonical_hash
- validate_sanitized_payload

Verification:
python3 -m unittest ops/logres-control-plane/tests/test_integration.py -v

## Task 2 — Targets and capabilities

Tests first:
- register target idempotently
- target update changes policy metadata without duplicating identity
- session capabilities are replaceable and expire by timestamp
- capability matching returns only compatible live sessions

Implement:
- register_target
- list_targets
- set_capabilities
- list_capabilities
- compatible_capabilities

## Task 3 — Durable intents and deterministic dedupe

Tests first:
- create intent is idempotent by dedupe key
- payload hash stored deterministically
- newer logical-slot projection supersedes older unclaimed intent
- claimed/dispatched intent is not silently superseded

Implement:
- create_intent
- get_intent
- list_intents
- supersede stale unclaimed projection intents

## Task 4 — Atomic claims and lease recovery

Tests first:
- one live claimant wins
- duplicate claimant gets same owned lease only when token matches
- expired claim can be recovered
- concurrent claim race yields exactly one owner

Implement bounded BEGIN IMMEDIATE helper and:
- claim_intent
- renew_claim
- release_claim

## Task 5 — State machine and uncertain-write safety

Tests first:
- valid state transitions succeed
- stale CAS transitions fail
- mutating DISPATCHED timeout moves to RECONCILING
- irreversible RECONCILING cannot transition directly to CLAIMED/DISPATCHED
- read-only retry path is allowed

Implement:
- transition_intent
- classify_uncertain_failure
- retry eligibility guard

## Task 6 — Immutable receipts and bindings

Tests first:
- receipts append without overwrite
- duplicate receipt dedupes by deterministic receipt key
- successful receipt can upsert canonical binding
- provider identity uniqueness prevents two canonical entities binding same provider object
- projection/observed hashes retained independently

Implement:
- append_receipt
- list_receipts
- upsert_binding
- get_binding
- list_bindings

## Task 7 — Cursors and inbound proposals

Tests first:
- cursor upsert is monotonic when requested
- proposal creation is idempotent
- proposal disposition CAS prevents double review
- accepted proposal does not itself mutate arbitrary canonical tables

Implement:
- set_cursor
- get_cursor
- create_proposal
- disposition_proposal
- list_proposals

## Task 8 — CLI

Tests first using subprocess:
- status JSON
- queue filtering by capability/provider/state
- claim returns lease token
- receipt command records result
- proposal listing works
- secret-bearing payload is rejected

Implement executable:
ops/logres-control-plane/bin/logres-integration

CLI subcommands:
- status
- targets
- capabilities
- intent-create
- queue
- claim
- renew
- transition
- receipt
- bindings
- proposals
- proposal-disposition
- cursor-get
- cursor-set

Human-readable by default; --json supported.

## Task 9 — Whole-module verification

Run:
- python3 -m unittest ops/logres-control-plane/tests/test_integration.py -v
- existing route-store tests
- existing journal tests
- python3 -m compileall ops/logres-control-plane/lib/logres_integration.py ops/logres-control-plane/bin/logres-integration
- git diff --check
- npm test
- npm run build

Then perform whole-branch self-review because no separate subagent tool is available in this harness.

## Completion Contract

This task is ready for normal logres-finish-task only when:
- every new behavior has a test observed failing before implementation
- all focused tests pass
- existing relevant control-plane tests pass
- full project test command and build are green or any unrelated failures are explicitly reported
- no secrets are persisted
- no existing worker-owned file changed
- branch diff is limited to the four claimed paths
