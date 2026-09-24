# Logres Brain Connected Plugin Integration Design

Date: 2026-09-24
Project: Awakened Realms / Logres reconstruction
Integration branch: feat/logres-reconstruction
Design task: BRAIN-PLUGIN-INTEGRATION-SPEC-002
Baseline integration SHA: eb90cdfc52f6d4e0f24e5188f7540d31dc538ff7
Supersedes incomplete review candidate: caa8f9db16a2a2b7e615ba935873b9654497c4a4
Replaces integrated incomplete spec commit: eb90cdfc52f6d4e0f24e5188f7540d31dc538ff7

## Purpose

Connect the installed ChatGPT plugins and external services to the existing Logres Brain Network without creating competing sources of truth.

The VM control plane remains the canonical operational authority. External systems receive projections, artifacts, telemetry, documentation, or communication work according to their role. Connector-capable ChatGPT sessions execute plugin actions through a durable integration queue and return receipts to the Brain.

The end state is a project operating system where a new Logres chat registers itself, recovers relevant context, sees current ownership, avoids duplicate work, claims a safe task, uses the right external services, records results, and leaves complete durable state for the next chat.

## Existing System To Preserve

The current control plane already provides:

- SQLite WAL storage at the VM control plane.
- Brain membership and pull-based worker coordination.
- Atomic task leases.
- Task graph, dependencies, acceptance criteria, and file claims.
- Durable Brain events.
- Project journal and project decisions.
- Durable chat sessions and chat transcript messages.
- Transcript archive files.
- Evidence and knowledge graph state.
- Exact-SHA verification and integration queue state.
- Deployment/runtime helpers.
- Autonomous scheduling and reconciliation.
- One serialized integration authority.
- Git branch and worktree guardrails.

The plugin layer extends these mechanisms. It does not replace them.

## Authority Model

Each information class has one authoritative home.

| Domain | Authority |
| --- | --- |
| Operational coordination | VM Brain Network / SQLite |
| Code and immutable implementation history | GitHub |
| Work presentation for humans | Linear |
| Curated working knowledge | Notion |
| Stable technical documentation | GitBook |
| Large files and evidence blobs | Google Drive |
| Product and interface design | Figma |
| Player/product behavior | PostHog |
| Infrastructure telemetry | Datadog |
| Hosted runtime state | Railway / Render / Oracle |
| Agent-to-human or agent-to-agent email | AgentMail |
| Application transactional email | Resend |
| Company mail and calendar | Gmail / Google Calendar |
| Presentation outputs | Gamma |
| Research acquisition | Firecrawl / TinyFish / Context7 / Hugging Face |
| Generated media | OpenArt |
| Production game backend when needed | Supabase |
| Source implementation execution | VM workers / GitHub / approved hosted workers |

An external system never silently becomes authoritative because a connector changed its copy.

## Core Architectural Rule

The architecture is hub-and-spoke.

The VM Brain is the hub.

Every provider is an adapter.

There is no direct provider-to-provider synchronization.

For example:

Linear does not update Notion directly.
Notion does not update GitHub directly.
GitHub does not update Figma directly.
AgentMail does not execute arbitrary actions directly.

Every state transition passes through the Brain or is recorded back into it as an immutable receipt.

This prevents sync loops, stale overwrites, split ownership, and duplicate work.

## Connector Execution Constraint

ChatGPT plugins are available to connector-capable ChatGPT sessions. Their credentials are not assumed to exist on the VM.

Therefore the first implementation uses a durable connector bridge rather than embedding provider credentials into the control plane.

Flow:

1. The Brain creates an integration intent.
2. The intent is written to an integration outbox.
3. A connector-capable chat claims the intent.
4. The chat performs the external MCP/plugin action.
5. The chat writes a structured receipt to the Brain.
6. The Brain updates the binding/projection state.
7. Retries or reconciliation operate from durable Brain state.

Later, a provider may gain a direct server-side executor if a service account and explicit security policy exist. Direct execution must implement the same intent and receipt protocol.

## Restart-Safety Contract

After any chat restart, VM restart, connector disconnect, or provider timeout, the durable integration record must answer:

1. Which Brain chat and durable chat session initiated the operation?
2. Which Brain task or explicit user request authorized it?
3. Which provider action targeted which external object and version?
4. Did the provider operation definitely succeed, definitely fail, or enter an uncertain state?
5. Which receipt, artifact, Brain event, proposal, task, or decision consumed the result?

No mutating provider action is considered complete until enough local state exists to answer those questions.

## Canonical Connector Request Envelope

Every provider operation is normalized before dispatch.

Required fields:

- schema_version
- provider
- target_key
- operation
- action_class
- chat_id
- session_id
- task_id when project work is involved
- actor
- intent_id
- dedupe_key
- canonical_entity_type
- canonical_entity_id
- projection_hash or request_hash
- provider_entity_type when known
- provider_entity_id when known
- provider_version when known
- requested_at
- bounded sanitized metadata

Forbidden fields:

- OAuth access tokens
- refresh tokens
- API keys
- cookies
- bearer headers
- passwords
- private signing material

The durable envelope stores intent and provenance. Connector credentials remain in the connector/provider security boundary.

## Action Classes And Authorization

### READ_ONLY

Examples:

- fetch a GitHub file
- search Linear
- read Notion
- inspect Figma
- query Datadog
- read Drive metadata

Rules:

- require an available provider connection and provider permission
- record durable intent when the read materially affects project state or evidence
- require task ownership when the read is part of claimed project work
- never mutate canonical Brain state solely because external data was read

### REVERSIBLE_WRITE

Examples:

- create or update a managed Linear issue
- create a managed Notion page
- upload a Drive artifact
- create a draft
- update a managed GitBook page

Rules:

- require all READ_ONLY safeguards
- require an authorized Brain task or explicit user-directed operation
- persist intent before external dispatch
- use provider idempotency support when available
- reconcile provider state before retrying an uncertain write
- record a receipt after the provider response

### IRREVERSIBLE_SIDE_EFFECT

Examples:

- send external email
- publish externally
- delete nonrecoverable provider data
- trigger financial, legal, release, or other nonreplayable effects

Rules:

- require all REVERSIBLE_WRITE safeguards
- require explicit authority for the specific side effect
- never infer missing consent from prior unrelated approvals
- never blindly replay after timeout or process crash
- uncertain outcomes enter RECONCILING until provider state is checked
- high-risk actions remain human-gated

The integration layer never bypasses ChatGPT or provider permission controls.

## New Control-Plane Concepts

### Integration Target

A configured provider destination.

Fields:

- provider
- account/workspace identifier
- logical purpose
- enabled state
- execution mode
- read policy
- write policy
- metadata

Examples:

- linear:logres-workspace
- notion:logres-knowledge
- gitbook:logres-docs
- datadog:nexus-runtime

### Canonical Binding

Maps one Brain entity to one provider entity.

Fields:

- provider
- canonical entity type
- canonical entity ID
- provider entity type
- provider entity ID
- provider URL
- last projected canonical version/hash
- last observed provider version/hash
- sync state
- timestamps

Example:

task:MISSION-PERFORMANCE-001
→ Linear issue LOG-123

A binding is identity metadata, not authority transfer.

### Integration Intent

A durable request for an external action.

Fields:

- intent ID
- provider
- operation
- canonical entity type
- canonical entity ID
- payload
- payload hash
- dedupe key
- priority
- state
- attempt count
- required capability
- created by
- source Brain event or journal entry
- timestamps

States:

- NEW
- CLAIMED
- DISPATCHED
- RECONCILING
- SUCCEEDED
- RETRYABLE
- FAILED
- SUPERSEDED
- CANCELLED

DISPATCHED means the provider call may have taken effect.
RECONCILING is mandatory when a mutating call returned an uncertain outcome.
An irreversible side effect must not automatically transition from RECONCILING back to dispatch.

### Integration Claim

A bounded lease on an intent.

Fields:

- intent ID
- chat ID
- lease token
- claimed at
- lease expiry

The same race-safety principle as Brain task leases applies.

### Integration Receipt

Immutable result of one attempted provider action.

Fields:

- intent ID
- provider
- operation
- success/failure
- provider entity ID
- provider URL
- provider revision/version if available
- observed output hash
- safe compact response metadata
- error class
- error detail
- chat ID
- attempt number
- timestamp

Large provider responses are stored as artifacts and referenced by path/hash.

### Integration Cursor

Provider-specific read position for bounded inbound reconciliation.

Examples:

- last Linear update timestamp
- last AgentMail message/thread ID
- last deployment event cursor
- last Datadog incident time

A cursor is advisory. It never replaces canonical Brain event IDs.

### Integration Proposal

Inbound external changes that might affect canonical state are recorded as proposals.

Fields:

- provider
- provider entity ID
- proposed canonical entity ID
- change type
- observed value
- current canonical value
- risk class
- disposition
- reviewer/actor
- timestamp

Possible dispositions:

- ACCEPTED
- REJECTED
- NOOP
- SUPERSEDED
- NEEDS_HUMAN

External changes do not write directly into tasks, leases, evidence confidence, or integration authority.

## Database Design

Add focused tables to the existing SQLite WAL database.

### integration_targets

Primary key:
provider + target_key

Stores provider purpose and policy.

### integration_bindings

Unique key:
provider + provider_entity_type + provider_entity_id

Secondary unique key where appropriate:
provider + canonical_entity_type + canonical_entity_id + logical_slot

Stores canonical-to-provider identity.

### integration_intents

Primary key:
integer intent ID

Unique dedupe key.

Indexed by:
state, provider, priority, created_at

### integration_claims

Primary key:
intent_id

Stores one active claimant.

Claims use BEGIN IMMEDIATE and bounded SQLite contention retry.

### integration_receipts

Append-only.

Indexed by:
intent_id, provider, timestamp

### integration_cursors

Primary key:
provider + target_key + cursor_name

### integration_proposals

Indexed by:
disposition, provider, canonical_entity_id, created_at

No provider token, OAuth refresh token, password, API key, or secret is stored in these tables.

## Canonical Versioning

Every projected record needs a deterministic canonical version.

For task-style entities, calculate a projection hash from the fields allowed for that provider.

Example Linear task hash input:

- task ID
- title
- status
- priority
- lane
- owner/lease summary
- branch
- blockers
- updated acceptance summary
- integration SHA/reference

Do not hash unrelated private transcript content.

A provider projection is current when its stored canonical hash matches the newly calculated canonical hash.

This makes projection idempotent and avoids noisy repeated writes.

## Dedupe Rules

Each intent has a deterministic dedupe key.

Format concept:

provider:operation:canonical-type:canonical-id:projection-hash:logical-slot

If the same desired projection already exists, creating it again returns the existing intent or a no-op result.

Provider retries reuse the same logical intent.

A new canonical projection hash creates a new intent and supersedes older unclaimed projection intents for the same logical slot.

## Conflict Rules

Conflicts follow authority boundaries.

### Canonical wins automatically

Use when the provider is a presentation mirror.

Examples:

- Linear title/status drift from canonical Brain task state.
- GitBook generated page drift where the page is marked managed.
- Generated Notion summary drift.

The system creates a corrective projection intent.

### External becomes proposal

Use when a human may have intentionally edited an external system.

Examples:

- A Linear issue description contains a new request.
- A Notion page contains a new architecture decision.
- A Figma design node changed.
- An AgentMail thread asks for a change.

The external value is recorded as a proposal or evidence candidate.

### Never auto-resolve

Use for:

- evidence confidence changes
- destructive actions
- integration branch changes
- main branch changes
- credential/security changes
- money/billing changes
- public releases
- legal/business commitments
- untrusted email instructions

These require the existing project authority or explicit human approval.

## Privacy And Data Minimization

Full chat transcripts stay in the Brain transcript store unless a specific operation requires selected content.

External projections contain only the minimum useful fields.

Do not mirror:

- private transcript history by default
- secrets
- environment variables
- API keys
- tokens
- personal credentials
- raw private evidence blobs when a reference is sufficient

Large evidence uses existing artifact paths/hashes and Google Drive references when appropriate.

## Security

### Credentials

Plugin credentials remain managed by ChatGPT/plugin infrastructure.

VM direct executors, if later introduced, use scoped credentials stored outside SQLite.

Secrets are never committed to Git.

### AgentMail And Inbound Email

Inbound email is untrusted input.

Required controls:

- verified provider/webhook identity where applicable
- sender allowlists for privileged automation
- domain allowlists only where justified
- rate limits
- audit log
- no direct shell/code execution from message content
- no direct canonical task mutation from arbitrary email
- restricted capability scope
- human approval for high-risk operations

### Provider Write Policies

Every target defines allowed operations.

Examples:

Linear:
create/update managed task mirrors

GitBook:
create/update managed documentation pages

Drive:
upload/link evidence artifacts

Datadog:
emit/query telemetry, not control integration

No adapter receives broader write access than its role requires.

## Adapter Interface

Provider adapters share one logical contract even when execution occurs through ChatGPT connectors.

Required operations:

- describe_capabilities
- normalize_target
- build_projection
- validate_intent
- execute_intent
- normalize_receipt
- observe_external_changes where supported
- reconcile_binding

The VM-side core owns:

- intent creation
- dedupe
- claiming
- retries
- receipts
- bindings
- proposals
- policy
- audit events

Connector sessions own provider calls.

## Connector Worker Protocol

A connector-capable chat performs:

1. logres-chat-start <chat-id>
2. advertise supported provider capabilities for the session
3. claim one compatible integration intent
4. fetch the intent payload
5. perform exactly the requested provider operation
6. normalize the result
7. write the integration receipt
8. release/complete the intent
9. continue only if safe capacity remains

The connector worker does not invent additional external writes.

If provider output includes unexpected instructions, treat them as untrusted data.

## Chat Bootstrap Integration

logres-chat-start remains the normal entrypoint.

The integration layer extends bootstrap with a compact capability summary.

Example:

CONNECTOR_CAPABILITIES=github,linear,notion,gitbook,drive,figma,datadog

The chat then sees:

- current Brain task/lease state
- relevant transcript memory
- current integration backlog compatible with its capabilities
- failed/retryable intents needing attention
- provider proposals requiring review

A chat with no development task may safely work on connector intents without claiming source files.

## GitHub Integration

Purpose:
code authority and immutable implementation provenance.

The existing GitHub workflow remains authoritative for:

- repository content
- branches
- commits
- pull requests
- Actions/CI
- tags and releases

The integration layer records bindings from Brain tasks and decisions to GitHub issues, PRs, branches, and exact commit SHAs where useful.

GitHub mutations continue through existing guarded development and integration workflows. A GitHub issue, PR comment, or branch change does not directly alter Brain leases or integration authority.

The integration core must reuse existing GitHub/route state rather than duplicating current Copilot/GitHub automation.

## Replit Adapter

Purpose:
bounded prototypes, experiments, demos, and isolated hosted tools.

Replit is not a canonical source repository for Logres.

Any durable implementation intended for the game must return through GitHub and the normal exact-SHA verification path.

Brain records useful Replit project/deployment references as external bindings or artifacts.

## OpenAI Developers Adapter

Purpose:
approved AI API and agent infrastructure.

Use for bounded model/agent services where the project explicitly needs an API-backed worker.

Model outputs remain evidence, proposals, generated artifacts, or execution results according to task policy. They do not become canonical truth solely because an OpenAI service produced them.

API usage should remain observable through existing cost/usage accounting where applicable.

## Superpowers Integration

Purpose:
development process policy.

Superpowers is not an external state store.

Connector-capable development chats use its skills for design, planning, worktree isolation, debugging, TDD, review, and verification. Specs and plans produced by the workflow live in Git and are linked to Brain tasks.

The Brain remains responsible for task authority and durable coordination.

## VM Execution Bridge

Nexus Commander remains the preferred VM execution path.

Remote Desktop Commander is a bootstrap, inspection, and emergency bridge when Nexus execution is unavailable or the task explicitly requires its capabilities.

Neither execution surface owns project state. Commands that materially change project state must leave normal Brain, Git, task, verification, and provenance records.

## Linear Adapter

Purpose:
human-readable work view.

Direction:
primarily Brain → Linear.

Project mapping:

- Brain milestones → Linear project/milestone
- Brain tasks → Linear issues
- status → issue state
- priority → issue priority
- current lease owner → assignee/delegate metadata when safe
- branch and exact SHA → issue links/details
- blocker → blocked state/comment
- integration completion → completed state with exact SHA reference

Inbound:

Human edits that differ from managed fields become integration proposals.

Linear is not allowed to steal Brain leases, alter integration authority, or mutate Git state.

## Notion Adapter

Purpose:
curated working knowledge.

Direction:
Brain knowledge → Notion, with bounded inbound proposals.

Publish:

- architecture decisions
- reverse-engineering findings
- system descriptions
- project history
- lessons from failed approaches
- canonical procedures
- high-value research summaries

Do not publish every transcript message.

Notion is a curated view over Brain knowledge, not transcript storage.

Human Notion edits to managed knowledge produce proposals for incorporation into Brain/project documentation.

## GitBook Adapter

Purpose:
stable technical documentation.

Direction:
canonical stable docs → GitBook.

Content is promoted only after it reaches a stable documentation state.

Examples:

- control-plane operator guide
- reconstruction bible
- map format
- protocol format
- asset pipeline
- battle system
- field architecture
- onboarding
- API references

GitBook publication does not alter implementation state.

## Google Drive Adapter

Purpose:
large artifact and evidence storage.

Existing Drive files remain valid.

Use for:

- APKs
- videos
- screenshots
- bug reports
- binary evidence
- archives
- large exports
- milestone reports
- backup artifacts

Brain records:

- Drive file ID
- URL
- content hash when known
- artifact type
- source task
- evidence label
- uploader/actor
- timestamp

The existing Awakened Realms Control sheet becomes legacy/reference. It does not compete with Brain task authority.

## Figma Adapter

Purpose:
visual source of truth for designed UI.

Bindings link:

Brain design task
→ Figma file/node
→ implementation task
→ commit SHA
→ verification evidence

Figma changes do not directly change product requirements.

Changed managed designs generate implementation/review proposals.

Generated concept work is distinguished from evidence-backed reconstruction.

## Datadog Adapter

Purpose:
infrastructure observability.

Inputs:

- VM/runtime metrics
- service logs
- traces
- incidents
- deployment failures
- worker health where appropriate

Brain links incidents or anomaly summaries back to tasks/deployments.

Datadog does not schedule development work directly.

An incident requiring code changes becomes a Brain proposal/task through normal policy.

## PostHog Adapter

Purpose:
player and product behavior.

Use for:

- onboarding funnel
- field traversal events
- battle entry/completion
- victory/reward flow
- errors
- session behavior
- feature flags
- experiments
- retention when applicable

PostHog data informs product/reconstruction decisions through evidence or proposals.

It does not own tasks or deployment state.

## Railway, Render, And Oracle

Purpose:
runtime execution and hosted services.

Deployment identity must include:

- source Git SHA
- environment
- service
- deployment ID
- timestamp
- status

Brain stores deployment bindings.

Datadog receives infrastructure telemetry.
PostHog receives product telemetry.
GitHub remains code authority.

Railway is preferred for simple managed services where already suitable.
Render is a secondary deployment option.
Oracle remains part of the existing execution infrastructure.

## AgentMail Adapter

Purpose:
agent communication identity.

Use for:

- bounded agent inboxes
- status messages
- external coordination
- attachments
- threaded communication

Each autonomous agent identity must have:

- purpose
- allowed senders/domains
- allowed action classes
- escalation rules

Inbound requests become proposals/intents, not arbitrary executable commands.

## Resend Adapter

Purpose:
application transactional email.

Use for:

- verification
- password reset
- beta invitations
- service alerts
- receipts
- system notifications

Resend is not the agent coordination bus.

## Gmail And Google Calendar

Purpose:
Nexus Core company operations.

They remain human/company systems.

Relevant mail or events may be referenced by Brain tasks after explicit retrieval or user-directed workflow.

Do not bulk ingest company email into project memory.

## Research Providers

### Context7

Use for current library and framework documentation.

Output:
source-backed technical guidance recorded as task evidence when material.

### Firecrawl

Use for web research, archived pages, structured extraction, and monitored public sources.

Output:
artifact/source references and evidence summaries.

### TinyFish

Use for bounded interactive browser workflows.

Output:
receipts and selected evidence, not browser history dumps.

### Hugging Face

Use for model, dataset, Space, and AI research.

Output:
model/dataset references, evaluation artifacts, or task evidence.

Research providers never self-promote findings to CONFIRMED ORIGINAL without project evidence policy.

## OpenArt Adapter

Purpose:
generated media and visual experimentation.

Generated output is labeled as generated/reconstructed.

It is never classified as original Logres evidence solely because it resembles the target.

Artifacts link to the requesting Brain task and generation metadata.

## Gamma Adapter

Purpose:
presentation output.

Source material comes from canonical Brain/Notion/GitBook state.

Use for:

- investor decks
- publisher pitches
- milestone reviews
- technical reports

Presentation edits do not mutate canonical engineering state.

## Supabase Policy

Do not create Supabase infrastructure only to duplicate Brain SQLite state.

Reserve Supabase for production game/backend needs such as:

- authentication
- player data
- storage
- realtime
- production APIs
- server functions

If a future production requirement needs shared cloud state, define it separately from project control-plane state.

## Failure Handling

Failures are classified.

### RETRYABLE

Examples:

- temporary 5xx before a write was dispatched
- rate limit with a known safe retry condition
- connector transient failure before an irreversible side effect
- network error on an idempotent read

Use bounded exponential backoff and provider-specific retry-after data.

A timeout after a mutating dispatch is not automatically RETRYABLE. It becomes RECONCILING until the external object or provider operation is checked. This prevents duplicate issues, duplicate uploads, duplicate messages, and duplicate irreversible side effects.

### FAILED

Examples:

- invalid target
- missing permission
- malformed payload
- policy violation
- deleted provider workspace
- unsupported operation

Record receipt and require corrective action.

### SUPERSEDED

A newer canonical projection replaced the old unexecuted intent.

### Provider drift

Reconciliation compares canonical projection hash and last observed provider hash.

Drift produces either:

- corrective projection
- proposal
- no-op

according to policy.

## Observability

Every integration action emits:

- provider
- operation
- intent ID
- canonical entity
- duration
- outcome
- attempt
- error class
- provider entity reference when safe

The Brain keeps durable audit state.

Datadog receives operational metrics/logs after the integration core is stable.

Suggested metrics:

- integration_intents_new
- integration_intents_succeeded
- integration_intents_retryable
- integration_intents_failed
- integration_queue_depth
- integration_oldest_age_seconds
- integration_provider_latency_ms
- integration_proposals_open
- integration_drift_detected

## Reconciliation

Reconciliation is pull-based and bounded.

It does not continuously poll every service.

Triggers:

- chat bootstrap
- explicit operator command
- scheduled low-frequency reconciliation for selected providers
- provider webhook/event where securely supported
- post-write verification

The system compares only managed bindings and bounded provider windows.

## Scheduling

Do not create a new high-frequency daemon for every provider.

Use the existing supervisor model for lightweight local maintenance.

Connector-dependent work remains queued until a capable chat is active.

Direct provider executors added later may run under the existing supervisor with bounded cadence and rate limits.

## Provider Capability Registry

The Brain stores provider capability declarations separately from credentials.

Examples:

linear.read
linear.write
notion.read
notion.write
gitbook.write
drive.read
drive.write
figma.read
figma.write
datadog.read
agentmail.send
agentmail.read

A connector worker may claim only intents requiring capabilities it currently advertises.

Capability declarations expire with the chat/session unless registered as a durable direct executor.

## Auditability

For every external object we should answer:

- Which canonical Brain entity caused it?
- Which intent created or updated it?
- Which chat/direct executor performed the action?
- What provider ID was returned?
- What canonical projection hash was used?
- What exact source Git SHA applied where relevant?
- Was the action retried?
- What changed externally afterward?
- Was external drift accepted, rejected, or corrected?

This is required for autonomous operation.

## CLI Surface

The implementation should expose a compact CLI, likely through a dedicated integration helper and logres-lead routing.

Required operator actions:

- status
- targets
- capabilities
- queue
- claim
- show-intent
- receipt
- fail
- bindings
- proposals
- accept-proposal
- reject-proposal
- reconcile
- provider-status

Human-readable output is required.
JSON output should be available for agents.

## Brain Events

Meaningful integration transitions publish deduplicated Brain events.

Examples:

- INTEGRATION_INTENT
- INTEGRATION_SUCCEEDED
- INTEGRATION_FAILED
- INTEGRATION_DRIFT
- INTEGRATION_PROPOSAL
- INTEGRATION_PROPOSAL_ACCEPTED
- INTEGRATION_PROPOSAL_REJECTED

Do not flood Brain with every low-level provider response.

## Knowledge Graph Integration

Bindings and receipts should contribute selected nodes/edges to the existing knowledge graph.

Useful relations:

task → mirrored_as → linear_issue
decision → documented_in → notion_page
spec → published_as → gitbook_page
task → design_ref → figma_node
artifact → stored_as → drive_file
commit → deployed_as → deployment
deployment → observed_by → datadog_service
feature → observed_by → posthog_event

Provider metadata must not inflate reconstruction evidence confidence.

## Implementation Planning Boundary

This is an umbrella architecture specification.

Do not implement every provider in one branch or one implementation plan.

After user approval, implementation is decomposed into independently verifiable plans:

1. Core integration ledger, queue, claims, receipts, bindings, proposals, capability registry, CLI, Brain events, and fake-adapter tests.
2. Linear managed work projection and drift/proposal canary.
3. Notion curated knowledge plus GitBook stable documentation promotion.
4. Google Drive artifact binding plus Figma design references.
5. Datadog/PostHog telemetry plus Railway/Render/Oracle deployment references.
6. AgentMail/Resend communication workflows and untrusted-input controls.
7. Research/generation provider normalization for Context7, Firecrawl, TinyFish, Hugging Face, OpenArt, Gamma, Replit, and OpenAI Developers where durable receipts are useful.

Each plan has its own task ownership, file scopes, TDD cycle, review, verification, and exact-SHA integration candidate.

## First Rollout

Phase 1 builds the generic integration core only.

Includes:

- schema
- intent queue
- leases
- receipts
- bindings
- proposals
- capability registry
- CLI
- Brain events
- tests
- deployment manifest integration

Phase 2 adds Linear as the first real adapter.

Reason:
Linear is currently empty and is the cleanest test of one-way managed projection from canonical Brain work state.

Phase 3 adds Notion and GitBook.

Reason:
they exercise curated knowledge and stable documentation without affecting code authority.

Phase 4 adds Google Drive and Figma references.

Reason:
they introduce artifact and design bindings.

Phase 5 adds Datadog/PostHog and deployment references.

Reason:
they validate observability and runtime linkage.

Phase 6 adds AgentMail/Resend security-aware workflows.

Reason:
inbound communication requires stricter untrusted-input handling.

Research and generation providers remain tool workers that publish evidence/artifacts through the generic core rather than each receiving custom canonical state.

## Linear Initial Migration

Do not import stale task state from the existing Google control sheet into Linear as authority.

Instead:

1. Read current Brain canonical tasks.
2. Select current active/ready/recently completed high-value tasks.
3. Project them into a new Linear project.
4. Store bindings.
5. Verify issue state.
6. Expand historical projection only if useful.

This avoids filling Linear with obsolete recursive/superseded historical tasks.

## Notion Initial Migration

Notion is currently treated as empty for Logres.

Create a minimal top-level structure after the generic core exists:

- Logres Project Home
- Architecture
- Reconstruction Knowledge
- Decisions
- Operations
- Milestones

Populate only canonical high-value summaries.

Do not migrate entire chat transcripts.

## GitBook Initial Publication

Publish stable documentation only after Notion/Brain knowledge has a canonical version.

Initial candidates:

- Logres Brain Network
- Lead Start Here
- Control Plane Architecture
- Reconstruction Evidence Policy
- Developer/Agent Workflow

## Backward Compatibility

Existing commands keep working.

Required:

- logres-chat-start remains valid.
- logres-brain commands remain valid.
- logres-control remains valid.
- logres-worker-start and logres-finish-task remain valid.
- integration branch rules remain unchanged.
- current SQLite tables remain intact.
- existing route_jobs external_ref behavior remains intact.
- existing transcript archive paths remain intact.
- no migration deletes or renames existing tables.

New schema creation must be additive and idempotent.

## Performance

The integration layer must stay lightweight.

Requirements:

- no full-provider scans on chat start
- no provider API call required for ordinary Brain task claims
- no blocking external call inside SQLite transaction
- SQLite write locks held only for local state transition
- payloads compact
- large results stored by reference
- bounded retries
- indexed queue lookup
- connector intents dormant when no capable worker is active

## Testing Strategy

### Unit tests

Test:

- schema idempotency
- deterministic hashes
- dedupe
- claiming races
- lease expiry
- receipt validation
- superseding intents
- retry policy
- proposal rules
- capability matching
- conflict policy
- sensitive-field filtering

### Integration tests

Use fake adapters to test:

Brain change
→ intent
→ claim
→ fake provider result
→ receipt
→ binding
→ reconciliation

Test failure, retry, duplicate, and provider drift paths.

### Provider contract tests

Each real adapter receives mocked connector responses and verifies normalization.

Do not make live destructive provider writes in the default test suite.

### Rollout canary

Linear is the first live canary.

Project a small bounded task set.
Verify exact provider IDs and state.
Change one canonical field.
Verify one idempotent update.
Introduce one external drift.
Verify proposal/correction policy.

Only then expand.

## Verification

Implementation must pass:

- focused control-plane tests
- existing control-plane deployment manifest tests
- npm run test
- npm run build
- existing fast worker gate
- exact-SHA candidate gate before integration

Provider live canaries remain separately recorded evidence and do not weaken code verification.

## Review And Canonicalization Rule

This document becomes canonical only after:

1. the user reviews the written specification,
2. requested corrections are incorporated,
3. the approved spec is integrated through the normal exact-SHA path,
4. the implementation plan references the integrated spec path.

A prior incomplete spec branch must not be treated as canonical merely because it passed a documentation-only worker gate.

## Success Criteria

The design is successful when:

1. The VM Brain remains the only operational source of truth.
2. External providers receive useful synchronized views without becoming competing authorities.
3. Any connector-capable chat can safely claim and execute compatible provider intents.
4. Every external write is idempotent, attributable, and auditable.
5. External edits become controlled proposals or corrective projections.
6. No provider credential is stored in the Brain SQLite database.
7. Existing Logres workers continue operating without plugin dependencies.
8. A new chat can recover canonical state and see relevant integration work through logres-chat-start.
9. Linear provides a current human-readable work view.
10. Notion and GitBook provide curated knowledge and stable documentation without transcript duplication.
11. Drive, Figma, deployments, telemetry, and communications are linked by canonical Brain IDs.
12. Provider outages do not stop normal game development.
13. Duplicate chats cannot create duplicate provider objects for the same canonical projection.
14. All integration changes remain additive, testable, and deployable through the existing exact-SHA control-plane workflow.

## Non-Goals

This project does not:

- replace SQLite with Supabase
- replace Brain tasks with Linear
- replace Brain knowledge with Notion
- replace Git with cloud documents
- mirror all chat content everywhere
- make email a command shell
- let providers write directly to main
- auto-publish public releases
- auto-approve financial/legal/security actions
- create direct sync links between external providers
- require every plugin to be online for normal development

## Selected Design

Use the existing VM Brain as the canonical event/state hub.

Add an additive integration ledger, outbox, receipts, bindings, proposals, and capability registry to the same SQLite control plane.

Use connector-capable ChatGPT sessions as the initial external-action executors.

Project outward according to strict provider roles.

Treat inbound changes as bounded proposals unless the provider has an explicitly safe reconciliation policy.

Add direct server-side provider executors only later, behind the same protocol, when scoped credentials and a clear operational need exist.

This gives the project one durable memory, one work authority, one audit trail, and many specialized external surfaces without turning the system into a fragile synchronization mesh.
