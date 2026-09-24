# Logres Brain Connected Plugin Integration Design

Date: 2026-09-24
Project: Logres reconstruction
Repository: alfred092020-ux/awakened-realms
Integration branch: feat/logres-reconstruction
Status: Canonical design specification

## 1. Purpose

Define one canonical integration layer between connected plugins and the Logres Brain Network.

Plugins extend what a registered Brain chat can read or do in external systems. They do not become a second project brain, task database, evidence authority, or integration authority.

The design must preserve restart safety, task ownership, provenance, deterministic dedupe, bounded retries, chat history continuity, and the existing exact-SHA verification pipeline.

A successful plugin integration must answer five questions after any restart:

1. Which chat and session initiated the action?
2. Which task, if any, authorized project work?
3. Which plugin action ran against which external object and version?
4. What durable result or artifact was produced?
5. Which project decision, evidence record, or follow-up consumed the result?

## 2. Non-negotiable constraints

- Never modify, merge, or target `main`.
- `feat/logres-reconstruction` remains the only integration branch.
- Lead remains the only integration authority.
- Brain Network and `control.sqlite` remain the coordination source of truth.
- Existing task leases and claims remain the work-ownership authority.
- Existing exact-SHA verification, scope checks, merge preflight, regression capture, and merge train remain mandatory.
- Plugin provider state is external state, not canonical Logres task state.
- A successful plugin call cannot directly mark a task DONE, verified, integrated, or historically confirmed.
- No plugin output can promote current-JP evidence above Global 3.0.24 evidence.
- No OAuth token, API key, bearer token, cookie, refresh token, or provider secret may be written to Brain, chat memory, SQLite, logs, artifacts, or repository files.
- Large provider payloads are stored once as immutable artifacts when needed. Brain and chat memory keep pointers and hashes instead of duplicate bodies.
- Missing, disconnected, rate-limited, or permission-denied plugins must fail closed without corrupting project state.

## 3. Existing primitives to reuse

The implementation must extend the current control plane instead of introducing a competing orchestrator.

Reuse:
- `logres-chat-start` for automatic Brain registration and durable chat-session resume.
- `logres-chat-memory` for user, assistant, tool-summary, and system-note transcript records.
- `chat_sessions` and `chat_messages` for durable per-conversation history.
- `logres-brain` for events, leases, evidence, decisions, handoffs, cursors, and presence.
- `route_jobs` for restart-safe routing intent and external route ownership.
- `route_decisions` for append-only routing rationale.
- `project_journal` for durable project action lineage.
- `project_decisions` for durable decision records.
- `logres-coordinator` for atomic task acquisition and concurrency safety.
- `logres-finish-task`, merge preflight, and merge train for normal candidate integration.
- Artifact storage plus SHA-256 for large immutable evidence snapshots.

No new task table or alternate lease system is allowed.

## 4. Target architecture

```text
registered Brain chat
        |
   chat session
        |
 plugin request normalizer
        |
 durable route intent
        |
 permission + ownership policy
        |
 connected plugin/provider
        |
 result normalizer
   /          \
tool-summary   immutable artifact
   |               |
chat memory     SHA + provenance
   \               /
      Brain event / evidence
              |
        existing tasks
              |
      normal verification
              |
         merge preflight
              |
             Lead
```

The plugin layer is a transport and normalization boundary. It never replaces Brain state transitions.

## 5. Canonical plugin request envelope

Every plugin invocation must normalize to one durable envelope before external dispatch.

Required fields:

- `schema`: versioned envelope schema.
- `plugin_id`: stable ChatGPT/plugin identifier when available.
- `provider`: GitHub, Google Drive, Slack, Gmail, or other provider family.
- `action`: canonical action name.
- `action_class`: READ_ONLY, REVERSIBLE_WRITE, or IRREVERSIBLE_SIDE_EFFECT.
- `chat_id`: registered Brain chat.
- `session_id`: active durable chat-memory session.
- `task_id`: project task when the action performs project work.
- `actor`: initiating Brain member.
- `request_id`: locally generated immutable run identifier.
- `dedupe_key`: deterministic operation identity.
- `request_hash`: SHA-256 of the sanitized canonical request.
- `external_object_id`: provider object ID when known.
- `external_version`: commit SHA, ETag, revision, message ID, file version, or equivalent.
- `source_ref`: sanitized provider reference or URI when useful.
- `requested_at`: UTC timestamp.
- `metadata`: sanitized bounded metadata only.

Fields containing credentials or raw authorization headers are forbidden.

## 6. Action classes and authorization

### 6.1 READ_ONLY

Examples include fetching a GitHub file, reading a Drive document, searching messages, or inspecting metadata.

Requirements:

- active plugin connection and provider permission;
- durable request intent before result publication;
- task lease is required when the read is part of owned project work;
- no task mutation occurs from the read alone.

### 6.2 REVERSIBLE_WRITE

Examples include creating a draft, comment, issue, branch, or provider object that has a clear compensating delete/archive operation.

Requirements:

- all READ_ONLY requirements;
- active task ownership for project-directed work;
- durable write intent before dispatch;
- deterministic idempotency key when the provider supports one;
- provider reconciliation before any retry after an uncertain outcome.
### 6.3 IRREVERSIBLE_SIDE_EFFECT

Examples include sending a message, publishing externally, deleting nonrecoverable data, or other actions whose effects cannot be safely replayed.

Requirements:

- all REVERSIBLE_WRITE requirements;
- explicit product/provider authorization must already be present;
- the plugin layer must not infer missing user consent;
- no automatic replay after timeout or process crash;
- uncertain outcomes enter RECONCILING until provider state is checked.

Brain never bypasses ChatGPT or provider permission controls.

## 7. Durable execution ledger

Routing intent continues to use `route_jobs`. Plugin execution needs a provider-facing run ledger inside the same `control.sqlite`, not a second database.

Proposed `plugin_runs` fields:

- `run_id` primary key;
- `dedupe_key` unique;
- `route_job_id`;
- `chat_id`;
- `session_id`;
- `task_id`;
- `plugin_id`;
- `provider`;
- `connection_alias_hash`;
- `action`;
- `action_class`;
- `state`;
- `request_hash`;
- `response_hash`;
- `external_ref`;
- `external_object_id`;
- `external_version`;
- `artifact_path`;
- `artifact_sha256`;
- `attempt_count`;
- `last_error`;
- `created_at`;
- `updated_at`.

The ledger stores identity and provenance only. It never stores provider credentials.

## 8. Plugin run state machine

Normal path:

`PLANNED -> AUTHORIZED -> DISPATCHED -> SUCCEEDED -> PUBLISHED`

Bounded alternatives:

- `NEEDS_USER_ACTION`
- `PERMISSION_DENIED`
- `FAILED_BOUNDED`
- `SUPERSEDED`
- `RECONCILING`

Rules:

- PLANNED is durable before any mutating external dispatch.
- AUTHORIZED means local policy and provider permission checks passed.
- DISPATCHED means the external call may have taken effect.
- SUCCEEDED requires a normalized provider result.
- PUBLISHED means chat memory and required Brain/project lineage are durable.
- RECONCILING is mandatory when a write outcome is uncertain.
- FAILED_BOUNDED is terminal unless a new explicit route is created.
## 9. Deterministic dedupe

Read dedupe key:

`provider + connection_alias_hash + action + external_object_id + external_version_or_query_hash`

Write dedupe key:

`task_or_chat + provider + action + target_identity + canonical_request_hash + idempotency_token`

Rules:

- equivalent requests reuse the existing durable run when safe;
- a repeated write must not create a second external side effect;
- provider version changes produce a new read identity;
- mutable objects without a stable version require a fresh snapshot before evidence use;
- dedupe keys are recorded before external dispatch.

The existing `route_jobs.dedupe_key` remains the routing-level duplicate guard. `plugin_runs.dedupe_key` protects external execution.

## 10. Chat-memory binding

Every chat-initiated plugin run belongs to the current `chat_sessions.session_id`.

After the provider result is normalized, append one bounded `tool-summary` through `logres-chat-memory`.

The tool-summary metadata should contain:

- plugin run ID;
- plugin/provider/action;
- task ID if present;
- external object ID and version if safe;
- request and response hashes;
- artifact path and SHA when a snapshot exists;
- final run state.

Use a stable `external_id` derived from the plugin run ID so transcript replay cannot duplicate the summary.
Do not append large raw provider payloads to chat memory.

A final assistant response can refer to the summarized result. It must not become the only durable record of an external action.

## 11. Brain event mapping

Plugin outcomes enter Brain only when they affect project coordination.

Examples:

- evidence-bearing read -> EVIDENCE with task ID, artifact path, SHA, provenance metadata;
- project discovery -> DISCOVERY;
- provider conflict or changed source -> EVIDENCE_CONFLICT or BLOCKER;
- completed external project step -> PROGRESS or HANDOFF;
- permission or account problem that blocks a task -> BLOCKER;
- normal conversational read with no project impact -> chat-memory tool-summary only.

Brain events must reference the plugin run ID in metadata.

A plugin success never emits DONE unless the owning task's acceptance path separately determines the task is complete.

## 12. Artifact and snapshot policy

Provider data becomes project evidence only after a stable evidence identity exists.

Preferred order:

1. provider immutable object/version already exists;
2. record provider object ID and immutable version;
3. if content is material, snapshot once to project artifact storage;
4. compute SHA-256;
5. publish Brain evidence using path/hash/provenance;
6. keep the provider reference as supporting provenance.

For mutable external documents, message threads, dashboards, or pages, a later provider state does not silently rewrite prior evidence.
A new provider version produces a new snapshot and new evidence event.

## 13. Evidence authority and provenance

Plugin retrieval does not change the Logres evidence hierarchy.

The normalized provenance record must identify:

- provider;
- external object ID;
- version or ETag;
- retrieval timestamp;
- content SHA or artifact SHA;
- source classification;
- target-version relevance;
- plugin run ID.

Historical rules remain unchanged:

- recovered Global 3.0.24 evidence outranks later/current JP evidence for the Global target;
- current-JP-only data cannot establish Global historical truth;
- model or plugin summaries are not primary evidence by themselves;
- unsupported claims remain SUPPORTED_INFERENCE, VERSION_SENSITIVE, or UNKNOWN as required by task policy.

A plugin result can satisfy a dependency only after deterministic evidence mapping and the existing task evidence policy accepts it.

## 14. Task ownership and concurrency

Project-directed plugin work must honor the same ownership system as repository work.

Before dispatch:

- task is active and owned by the initiating chat, or the action is an explicitly allowed read used to evaluate whether work is claimable;
- hard dependencies are satisfied;
- no conflicting claim or lease exists;
- action scope matches the task;
- integration work is never delegated through a normal plugin route.
If the lease expires or ownership changes before a mutating dispatch, the run is blocked or superseded.

If ownership changes after DISPATCHED, reconciliation records the external result, but the old worker cannot continue project mutation.

No plugin action may steal, force-release, or bypass another live lease.

## 15. Provider capability discovery

Plugin availability must be discovered at runtime.

Do not hard-code an assumption that a specific provider is always connected.

The capability record should expose only safe metadata:

- plugin ID;
- provider;
- connection alias or nonsecret connection hash;
- supported actions;
- granted scope summary when available;
- observed health;
- last successful use.

When a required plugin is unavailable, the route enters NEEDS_USER_ACTION or a policy-approved deterministic fallback. It does not fabricate provider data.

## 16. Secret and privacy boundary

Forbidden durable content:

- OAuth access or refresh tokens;
- API keys;
- cookies;
- bearer headers;
- passwords;
- provider session secrets;
- raw connector credentials.

Allowed durable content:

- provider/plugin IDs;
- connection alias hash;
- granted scope names without tokens;
- external object IDs;
- commit SHAs, revisions, ETags, message IDs, file IDs;
- sanitized request/response hashes;
- artifact paths and hashes;
- bounded nonsecret result metadata.

Logs and tool-summary records must redact secret-like fields before persistence.

## 17. Retry and reconciliation policy

READ_ONLY transient failure:

- one bounded retry when provider semantics make retry safe;
- then FAILED_BOUNDED or NEEDS_USER_ACTION.

REVERSIBLE_WRITE transient failure before DISPATCHED:

- one bounded retry is allowed.

Any write failure after DISPATCHED:

1. enter RECONCILING;
2. query provider state using the run's external reference or idempotency key;
3. if effect exists, adopt it and continue;
4. if effect definitely does not exist, a bounded retry may run;
5. if outcome remains ambiguous, stop and surface NEEDS_USER_ACTION.

IRREVERSIBLE_SIDE_EFFECT never auto-replays after an ambiguous dispatch.

Restart reconciliation scans nonterminal `plugin_runs` and existing `route_jobs` before creating new external work.

## 18. Integration and repository authority

Plugins do not receive a privileged repository path.

GitHub-connected actions must still obey:

- no automated target or push to `main`;
- worker branches only for normal implementation;
- candidate SHA remains immutable after queueing;
- scope check and verification remain mandatory;
- merge preflight tests the exact combined result SHA;
- Lead remains the only integration authority.
Drive, Slack, Gmail, or other plugins cannot redefine repository truth, task state, or acceptance criteria.

External provider completion does not substitute for `logres-finish-task`, verification, or merge-train state.

## 19. Failure isolation

A plugin outage must not stall deterministic work that does not require the plugin.

Failure classes:

- connection missing;
- permission denied;
- rate limited;
- provider unavailable;
- object not found;
- version changed;
- response invalid;
- side-effect outcome uncertain;
- local persistence failure;
- provenance insufficient.

Each failure records a bounded reason in the plugin run and route job.

Only failures that block project progress emit Brain BLOCKER events.

Repeated identical failures update existing lineage rather than spawning an unbounded task chain.

## 20. Testing strategy

Unit tests:

- envelope normalization;
- secret redaction;
- action classification;
- deterministic read/write dedupe;
- task ownership guard;
- evidence-policy guard;
- state-transition validity;
- provider capability handling;
- retry ceilings.

Integration tests:

- registered chat -> plugin read -> tool-summary;
- plugin read -> immutable artifact -> Brain EVIDENCE;
- duplicate read -> one durable result;
- duplicate write -> one external side effect;
- crash after provider success before local publish -> reconciliation adopts result;
- crash before dispatch -> safe bounded retry;
- permission denial -> NEEDS_USER_ACTION with no task corruption;
- provider version change -> new snapshot and evidence identity;
- lease loss before write -> dispatch refused;
- mutable source changes after snapshot -> prior evidence remains immutable;
- disconnected plugin -> fail closed;
- secret-shaped values -> absent from SQLite, logs, chat archive, and artifacts;
- large result -> pointer/hash in Brain and chat memory, not duplicated body;
- GitHub target `main` -> hard rejection;
- plugin success -> no automatic DONE or integration state.

Regression requirements:

- Brain health remains PASS;
- chat-memory resume and append dedupe remain PASS;
- coordinator acquisition remains atomic;
- blocker/regression routing remains unchanged;
- exact-SHA merge preflight remains mandatory.

## 21. Rollout

Phase 1: schema and dry-run normalization.

- Add plugin run ledger.
- Normalize plugin capabilities and request envelopes.
- Record no external writes.

Phase 2: read-only providers.

- Enable bounded reads for a narrow allowlist.
- Append chat-memory tool summaries.
- Snapshot evidence-bearing results.
- Validate dedupe and restart reconciliation.

Phase 3: project evidence bridge.

- Publish accepted artifact references to Brain.
- Enforce evidence-policy and target-version rules.
Phase 4: reversible writes.

- Require active task ownership.
- Persist write intent before dispatch.
- Enforce idempotency and reconciliation.

Phase 5: guarded irreversible actions.

- Require explicit provider/product authorization.
- Disable automatic ambiguous replay.
- Add health and audit reporting.

## 22. Acceptance criteria

The design is implemented when:

- any registered Brain chat can use an available connected plugin without becoming a separate coordination island;
- each plugin run has durable chat/session identity, task ownership when applicable, deterministic dedupe, and sanitized provenance;
- a restart can reconcile every nonterminal write without duplicating side effects;
- evidence-bearing provider results are immutable or snapshotted before they influence project truth;
- large payloads are referenced by artifact path/hash instead of copied into Brain or chat history;
- plugin outages fail closed and do not block unrelated deterministic work;
- current-JP/provider data cannot override Global evidence rules;
- plugin completion cannot bypass task acceptance, verification, merge preflight, or Lead;
- no credential or provider secret is persisted;
- `main` remains unreachable from automated plugin routing.

## 23. Explicit non-goals

- replacing Brain Network or `control.sqlite`;
- using provider state as the project task database;
- automatic historical-truth promotion from connector output;
- automatic integration or merging;
- storing complete external inboxes, drives, or workspaces in project state;
- polling external services without a concrete task or unresolved dependency;
- retrying uncertain irreversible actions until one appears successful.

## 24. Success metric

Primary metric: useful plugin work reaches durable Brain/chat lineage without duplicate external effects or manual reconstruction after restart.
Secondary metrics:

- duplicate plugin runs prevented;
- external writes reconciled without replay;
- evidence snapshots with complete provenance;
- plugin-triggered blocker resolution time;
- plugin permission/error recovery time;
- percentage of plugin results represented by bounded tool summaries instead of raw duplicated payloads;
- zero secret-persistence incidents;
- zero plugin-driven bypasses of task ownership or exact-SHA integration.

The operating rule is:

Plugins retrieve or act. Chat memory preserves conversation lineage. Brain owns coordination. Evidence policy owns truth. Verification owns acceptance. Lead owns integration.
