# Logres AI + Copilot Autoflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Logres control plane so new evidence can be analyzed, routed, implemented, verified, and returned to Lead with OpenAI and Copilot as first-class bounded workers.

**Architecture:** Keep Brain Network and `control.sqlite` authoritative. Add durable route state, an evidence router, a Copilot router, and reconciliation around the existing `logres-autopilot-watch`, `logres-ai`, coordinator, verification farm, blocker router, and merge train. Version the changed control-plane source inside this repository and deploy it atomically to `/home/ubuntu/logres`.

**Tech Stack:** Python 3.12, SQLite WAL, Git/GitHub CLI, OpenAI Python SDK, existing Bash/Python Logres helpers, unittest, existing verification farm.

**Spec:** `docs/superpowers/specs/2026-09-23-logres-ai-copilot-autoflow-design.md`

## Global Constraints

- Never modify, merge, or target `main`.
- `feat/logres-reconstruction` remains the only integration branch.
- Lead remains the only integration authority.
- `control.sqlite` plus Brain Network remain the coordination source of truth.
- Global 3.0.24 evidence outranks later/current JP evidence where they conflict.
- AI analysis is advisory and cannot promote historical truth by itself.
- Copilot cannot self-merge and cannot bypass existing scope, verification, preflight, or merge-train checks.
- Automatic OpenAI dispatch must remain bounded, deduplicated, and fail-safe near budget uncertainty/exhaustion.
- Existing 5-minute `logres-autopilot-watch` cron remains the only periodic autoflow trigger.

## Review Focus

- Duplicate Brain events or restarted routers must not create duplicate API charges, GitHub issues, or Copilot assignments; Task 2 and Task 7 pin this.
- A SUPPORTED INFERENCE result with a strict evidence policy must not unlock implementation; Task 4 pins this.
- A Copilot PR based on stale integration or touching forbidden scope must be rejected before verification; Task 6 pins this.
- Missing/unknown model pricing must fail closed for automatic API spend rather than pretending cost is zero; Task 3 pins this.
- A VM restart between external dispatch and local state update must reconcile the external job instead of dispatching again; Task 7 pins this.

---
## File Structure

Versioned control-plane source will live under `ops/logres-control-plane/`:

- `ops/logres-control-plane/bin/logres-ai` — versioned OpenAI CLI wrapper.
- `ops/logres-control-plane/bin/logres-ai-router` — Brain evidence -> AI dispatch/result routing.
- `ops/logres-control-plane/bin/logres-copilot-router` — eligible task -> Copilot issue/assignment.
- `ops/logres-control-plane/bin/logres-route-reconcile` — restart/external-state reconciliation.
- `ops/logres-control-plane/bin/logres-autopilot-watch` — existing watcher plus router hooks.
- `ops/logres-control-plane/bin/logres-doctor` — existing health check plus autoflow checks.
- `ops/logres-control-plane/bin/logres-lead` — existing wrapper plus route/status commands.
- `ops/logres-control-plane/lib/logres_ai_common.py` — current pure AI helpers.
- `ops/logres-control-plane/lib/logres_ai_runner.py` — current bounded OpenAI runner plus usage capture.
- `ops/logres-control-plane/lib/logres_route_store.py` — schema, route state, transitions, lineage.
- `ops/logres-control-plane/lib/logres_route_policy.py` — classification, evidence-policy, budget/backpressure rules.
- `ops/logres-control-plane/lib/logres_ai_router.py` — testable evidence-event and AI-result routing cycle.
- `ops/logres-control-plane/lib/logres_copilot.py` — GitHub/Copilot payload and external-state adapter.
- `ops/logres-control-plane/lib/logres_copilot_router.py` — testable Copilot eligibility/dispatch/return cycle.
- `ops/logres-control-plane/lib/logres_reconcile.py` — restart reconciliation and backpressure evaluation.
- `ops/logres-control-plane/config/autoflow.default.json` — non-secret defaults.
- `ops/logres-control-plane/tests/` — offline unit/integration tests.
- `scripts/logres/deploy_control_plane.py` — atomic deploy/dry-run from repo source to live VM paths.

Runtime state remains under `/home/ubuntu/logres/control`; secrets remain outside the repository.

### Task 1: Version and Atomically Deploy the Control-Plane Source

**Files:**
- Create: `ops/logres-control-plane/README.md`
- Create: `ops/logres-control-plane/bin/logres-ai`
- Create: `ops/logres-control-plane/bin/logres-autopilot-watch`
- Create: `ops/logres-control-plane/bin/logres-doctor`
- Create: `ops/logres-control-plane/bin/logres-lead`
- Create: `ops/logres-control-plane/lib/logres_ai_common.py`
- Create: `ops/logres-control-plane/lib/logres_ai_runner.py`
- Create: `scripts/logres/deploy_control_plane.py`
- Create: `ops/logres-control-plane/tests/test_deploy_control_plane.py`

**Interfaces:**
- Consumes: current live files under `/home/ubuntu/logres/bin` and `/home/ubuntu/logres/lib` as the initial source snapshot.
- Produces: `deploy_control_plane.deploy(source_root: Path, target_root: Path, dry_run: bool) -> list[Deployment]`.

- [ ] **Step 1: Write a failing deployment test**

```python
def test_deploy_copies_only_manifested_files_and_preserves_modes(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    make_fixture_tree(source)
    deployed = deploy(source, target, dry_run=False)
    assert (target / "bin/logres-ai").read_text() == "#!/bin/sh\necho ai\n"
    assert (target / "lib/logres_ai_runner.py").is_file()
    assert stat.S_IMODE((target / "bin/logres-ai").stat().st_mode) == 0o700
    assert all("openai_api_key" not in str(x.destination) for x in deployed)
```

- [ ] **Step 2: Run the test and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_deploy_control_plane.py
```

Expected: FAIL because `deploy_control_plane` does not exist.
- [ ] **Step 3: Import the current live files unchanged into the versioned tree**

Copy the current live contents of:
```text
/home/ubuntu/logres/bin/logres-ai
/home/ubuntu/logres/bin/logres-autopilot-watch
/home/ubuntu/logres/bin/logres-doctor
/home/ubuntu/logres/bin/logres-lead
/home/ubuntu/logres/lib/logres_ai_common.py
/home/ubuntu/logres/lib/logres_ai_runner.py
```

Do not import `/home/ubuntu/.config/logres/openai_api_key`, logs, SQLite files, private evidence, or generated artifacts.

- [ ] **Step 4: Implement the deploy manifest**

```python
MANIFEST = {
    "bin/logres-ai": ("bin/logres-ai", 0o700),
    "bin/logres-autopilot-watch": ("bin/logres-autopilot-watch", 0o755),
    "bin/logres-doctor": ("bin/logres-doctor", 0o700),
    "bin/logres-lead": ("bin/logres-lead", 0o700),
    "lib/logres_ai_common.py": ("lib/logres_ai_common.py", 0o600),
    "lib/logres_ai_runner.py": ("lib/logres_ai_runner.py", 0o600),
}
```

Deployment must write each file to a sibling temp path, fsync, chmod, then `os.replace()` into the live destination. `--dry-run` prints the manifest and makes no changes.

- [ ] **Step 5: Run deployment tests**

Run:
```bash
python3 ops/logres-control-plane/tests/test_deploy_control_plane.py
python3 scripts/logres/deploy_control_plane.py --source ops/logres-control-plane --target /tmp/logres-control-plane-smoke
```

Expected: PASS; only manifested files exist under the temporary target.

- [ ] **Step 6: Commit**

```bash
git add ops/logres-control-plane scripts/logres/deploy_control_plane.py
git commit -m "chore: version Logres control-plane source"
```

### Task 2: Add Durable Route Schema, State Transitions, Dedupe, and Lineage

**Files:**
- Create: `ops/logres-control-plane/lib/logres_route_store.py`
- Create: `ops/logres-control-plane/lib/logres_route_policy.py`
- Create: `ops/logres-control-plane/tests/fixtures.py`
- Create: `ops/logres-control-plane/tests/test_route_store.py`
- Create: `ops/logres-control-plane/tests/test_route_policy.py`

**Interfaces:**
- Produces: `RouteSpec(dedupe_key, route_kind, source_event_id=None, task_id=None, artifact_sha=None, question_sha=None, base_sha=None, parent_route_id=None, resolution_type=None, meta=None)` and `RouteJob`.
- Produces: `ensure_route_schema(conn)`, `claim_route(conn, spec: RouteSpec) -> RouteJob`, `transition_route(conn, route_id: int, expected: str, new: str, **fields) -> RouteJob`.
- Produces: `append_decision(conn, route_job_id: int, decision: str, reason: str, source_event_id: int | None = None, task_id: str | None = None, meta: dict | None = None) -> int`.
- Produces: `find_active_child(conn, parent_route_id: int, resolution_type: str) -> RouteJob | None` and `classify_evidence_event(event, task, metadata, config) -> RouteDecision`.
- Test fixture API in `tests/fixtures.py`: `make_test_db() -> sqlite3.Connection`; `seed_task(conn, task_id="T1", priority=0, status="READY", work_type="implementation", evidence_policy="", concurrency_key="default", acceptance=("criterion",))`; `seed_event(conn, event_id=10, event_type="EVIDENCE", task_id="T1", artifact_path="/tmp/artifact.txt", artifact_sha="a"*64, meta=None)`; `seed_ai_run(conn, artifact_sha, question, status="PASS")`; `seed_route(conn, state, dedupe_key, route_kind="AI", task_id="T1", external_ref=None) -> int`; `seed_active_lease(conn, task_id, chat_id="worker", branch="worker/test")`; and `test_config() -> dict`.
- Consumes: existing `brain_events`, `tasks`, `task_metadata`, `task_acceptance`, `task_dependencies`, `brain_task_leases`, `verification`, `integration_queue`.

- [ ] **Step 1: Write schema/idempotency/dedupe tests**

```python
def test_claim_route_is_idempotent_for_dedupe_key():
    conn = make_test_db()
    ensure_route_schema(conn)
    a = claim_route(conn, RouteSpec(dedupe_key="e:10:ai", route_kind="AI", source_event_id=10))
    b = claim_route(conn, RouteSpec(dedupe_key="e:10:ai", route_kind="AI", source_event_id=10))
    assert a.id == b.id
    assert conn.execute("select count(*) from route_jobs").fetchone()[0] == 1

def test_find_active_child_prevents_unresolved_loop():
    conn = make_test_db()
    ensure_route_schema(conn)
    parent = claim_route(conn, RouteSpec(dedupe_key="parent", route_kind="AI", source_event_id=10))
    child = claim_route(conn, RouteSpec(dedupe_key="child", route_kind="RESEARCH", source_event_id=11,
                                       parent_route_id=parent.id, resolution_type="UNRESOLVED"))
    assert find_active_child(conn, parent.id, "UNRESOLVED").id == child.id
```
- [ ] **Step 2: Run tests and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_route_store.py
python3 ops/logres-control-plane/tests/test_route_policy.py
```

Expected: FAIL because route modules do not exist.

- [ ] **Step 3: Implement the four new tables idempotently**

```sql
create table if not exists route_jobs (
  id integer primary key autoincrement,
  dedupe_key text unique not null,
  source_event_id integer,
  task_id text,
  route_kind text not null,
  state text not null,
  attempt_count integer not null default 0,
  artifact_sha text,
  question_sha text,
  base_sha text,
  external_ref text,
  parent_route_id integer,
  resolution_type text,
  last_error text,
  meta_json text not null default '{}',
  created_at text not null,
  updated_at text not null
);

create table if not exists route_decisions (
  id integer primary key autoincrement,
  route_job_id integer not null,
  source_event_id integer,
  task_id text,
  decision text not null,
  reason text not null,
  meta_json text not null default '{}',
  created_at text not null
);

create table if not exists copilot_jobs (
  id integer primary key autoincrement,
  route_job_id integer unique not null,
  task_id text not null,
  issue_number integer,
  pr_number integer,
  branch text,
  base_sha text not null,
  candidate_sha text,
  state text not null,
  last_error text,
  created_at text not null,
  updated_at text not null
);

create table if not exists api_usage (
  id integer primary key autoincrement,
  route_job_id integer,
  ai_run_id integer,
  task_id text,
  artifact_sha text,
  model text not null,
  input_tokens integer not null default 0,
  cached_input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  reasoning_tokens integer not null default 0,
  estimated_cost_usd real,
  status text not null,
  created_at text not null
);
```

Do not alter existing authoritative tables.
- [ ] **Step 4: Implement compare-and-swap transitions**

```python
VALID_TRANSITIONS = {
    "NEW": {"ROUTED", "SKIPPED_DETERMINISTIC", "DUPLICATE_CACHE"},
    "ROUTED": {"AI_RUNNING", "ASSIGNING", "FAILED_BOUNDED"},
    "AI_RUNNING": {"AI_VALIDATED", "FAILED_BOUNDED"},
    "AI_VALIDATED": {"BRAIN_POSTED", "FAILED_BOUNDED"},
    "BRAIN_POSTED": {"COMPLETE"},
    "ASSIGNING": {"ACTIVE", "FAILED_BOUNDED"},
    "ACTIVE": {"PR_READY", "SUPERSEDED", "BLOCKED_EVIDENCE", "FAILED_BOUNDED"},
    "PR_READY": {"VERIFYING", "SCOPE_VIOLATION", "SUPERSEDED"},
    "VERIFYING": {"QUEUED", "FAILED_BOUNDED", "SCOPE_VIOLATION"},
}
```

`transition_route` must execute `UPDATE route_jobs SET state=?, updated_at=? WHERE id=? AND state=?` plus requested field updates inside an immediate transaction and raise `StateConflict` if rowcount is not exactly one.

- [ ] **Step 5: Implement provenance/evidence-policy guard**

```python
def implementation_allowed(canonical_confidence: str, evidence_policy: str, provenance: str) -> bool:
    if "current_jp" in provenance.lower() or "later_jp" in provenance.lower():
        return False
    if canonical_confidence == "CONFIRMED ORIGINAL":
        return True
    if canonical_confidence == "SUPPORTED INFERENCE":
        return "allow-supported-inference" in evidence_policy.lower()
    return False
```

The caller must pass canonical evidence status derived from project provenance, never the model-selected confidence field directly. Provenance that explicitly says current/later JP routes to `REVIEW_REQUIRED` when the task requires Global evidence.

- [ ] **Step 6: Run tests and commit**

```bash
python3 ops/logres-control-plane/tests/test_route_store.py
python3 ops/logres-control-plane/tests/test_route_policy.py
git add ops/logres-control-plane
git commit -m "feat: add durable autoflow route state"
```
### Task 3: Extend OpenAI Worker with Usage Telemetry and Fail-Closed Budget Policy

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_ai_runner.py`
- Modify: `ops/logres-control-plane/bin/logres-ai`
- Create: `ops/logres-control-plane/config/autoflow.default.json`
- Create: `ops/logres-control-plane/tests/test_ai_usage_budget.py`

**Interfaces:**
- `analyze_artifact(client, conn, path: Path, question: str, task_id: str | None = None, force: bool = False, route_job_id: int | None = None, rate_config: dict | None = None) -> dict` returns `cached`, `model`, `artifact_sha`, `result`, `usage`, and `ai_run_id`.
- `budget_state(conn, config, priority) -> "OPEN"|"THROTTLED"|"RESERVED"|"CLOSED"|"UNKNOWN"`.

- [ ] **Step 1: Write failing usage and fail-closed budget tests**

```python
def test_usage_records_reasoning_and_cached_tokens():
    usage = usage_from_response(SimpleNamespace(
        input_tokens=1000,
        output_tokens=300,
        input_tokens_details=SimpleNamespace(cached_tokens=400),
        output_tokens_details=SimpleNamespace(reasoning_tokens=50),
    ))
    assert usage.cached_input_tokens == 400
    assert usage.reasoning_tokens == 50

def test_unknown_model_rate_blocks_non_p0_auto_spend():
    cfg = config_with_budget(10.0, rates={})
    assert budget_state(conn_with_usage([]), cfg, priority=1, model="new-model") == "UNKNOWN"
    assert automatic_api_allowed("UNKNOWN", priority=1) is False
    assert automatic_api_allowed("UNKNOWN", priority=0) is False
```

- [ ] **Step 2: Run test and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_ai_usage_budget.py
```

- [ ] **Step 3: Add non-secret runtime defaults**

```json
{
  "routing": {
    "ai_dispatch_enabled": false,
    "copilot_dispatch_enabled": false,
    "copilot_mode": "report_only"
  },
  "openai": {
    "budget_usd": 10.0,
    "warn_fraction": 0.50,
    "throttle_fraction": 0.75,
    "reserve_fraction": 0.20,
    "max_active": 1,
    "max_active_hard": 2,
    "model_rates_per_million": {}
  },
  "copilot": {
    "max_active": 2,
    "max_queued": 1
  },
  "backpressure": {
    "ready_for_integration": 4,
    "verification_backlog": 3
  }
}
```

An empty rate map means estimated cost is unknown; automatic API routing must fail closed until a rate is configured. Manual `logres-ai` remains available.

- [ ] **Step 4: Capture response usage and store one `api_usage` row per real call**

Do not add usage rows for cache hits. Preserve `reasoning={"effort":"none"}`, strict JSON schema, bounded retry, and `store=False`.

- [ ] **Step 5: Add CLI output fields**

```json
{
  "cached": false,
  "model": "gpt-5.6-luna",
  "usage": {
    "input_tokens": 0,
    "cached_input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "estimated_cost_usd": null
  }
}
```

Never print the API key or environment contents.
- [ ] **Step 6: Run all AI tests**

Run:
```bash
python3 ops/logres-control-plane/tests/test_ai_usage_budget.py
python3 /home/ubuntu/logres/control/tests/test_logres_ai_common.py
python3 /home/ubuntu/logres/control/tests/test_logres_ai_runner.py
python3 /home/ubuntu/logres/control/tests/test_logres_ai_request_contract.py
python3 /home/ubuntu/logres/control/tests/test_logres_ai_worker.py
```

Expected: all PASS after deploying versioned test-target files to a temporary root or setting `PYTHONPATH` to the versioned lib directory.

- [ ] **Step 7: Commit**

```bash
git add ops/logres-control-plane
git commit -m "feat: meter bounded OpenAI evidence analysis"
```

### Task 4: Build the Evidence -> OpenAI -> Brain Router

**Files:**
- Create: `ops/logres-control-plane/lib/logres_ai_router.py`
- Create: `ops/logres-control-plane/bin/logres-ai-router`
- Create: `ops/logres-control-plane/tests/test_ai_router.py`
- Modify: `ops/logres-control-plane/lib/logres_route_policy.py`

**Interfaces:**
- CLI: `logres-ai-router [--dry-run] [--limit N] [--since EVENT_ID]`.
- Library: `route_event(conn, source_event_id: int, config: dict, dry_run: bool, ai_runner) -> RouteJob`.
- Library: `route_ai_result(conn, route_job_id: int, result: dict, task_row: dict | None, metadata_row: dict | None, provenance: str) -> RouteDecision`.
- Library: `run_ai_cycle(conn, ai_runner, brain_runner, config: dict, limit: int = 10) -> CycleResult`, where `CycleResult` exposes `processed`, `api_calls`, `cache_hits`, and `created_research_tasks`.
- Test fake: `FakeAIRunner(result: dict | None = None)` exposes instance counter `calls` and returns the supplied validated result; `FakeBrainRunner()` records posted events without shelling out.
- Reads: new `brain_events` with artifact path/SHA and supported event types.
- Calls: deployed `logres-ai <artifact> --task <id> --question <bounded-question> --post-brain`.
- Produces: durable `route_jobs`, `route_decisions`, and focused research tasks through the existing DB/task conventions.

- [ ] **Step 1: Write failing classifier tests**

```python
def test_large_global_native_artifact_routes_to_ai():
    event_row = {"event_type": "EVIDENCE", "artifact_path": "/x/global-native.txt",
                 "artifact_sha256": "a" * 64,
                 "meta_json": '{"artifact_bytes":74000,"kind":"native_trace","provenance":"CONFIRMED_GLOBAL_2017"}'}
    task_row = {"id": "T1", "priority": 0}
    metadata_row = {"work_type": "research", "evidence_policy": "Global evidence required"}
    decision = classify_evidence_event(event_row, task_row, metadata_row, test_config())
    assert decision.route == "AI"

def test_one_line_symbol_lookup_stays_deterministic():
    event_row = {"event_type": "EVIDENCE", "artifact_path": "/x/symbol.txt",
                 "artifact_sha256": "a" * 64,
                 "meta_json": '{"artifact_bytes":80,"kind":"symbol_lookup"}'}
    task_row = {"id": "T1", "priority": 1}
    metadata_row = {"work_type": "research", "evidence_policy": "Global evidence required"}
    decision = classify_evidence_event(event_row, task_row, metadata_row, test_config())
    assert decision.route == "SKIP_DETERMINISTIC"

def test_duplicate_artifact_question_uses_cache_route():
    conn = make_test_db()
    ensure_route_schema(conn)
    seed_task(conn, task_id="T1", work_type="research")
    seed_event(conn, event_id=10, task_id="T1", artifact_path="/tmp/native.txt", artifact_sha="a" * 64,
               meta={"artifact_bytes": 74000, "kind": "native_trace", "provenance": "CONFIRMED_GLOBAL_2017"})
    seed_ai_run(conn, artifact_sha="a" * 64, question=DEFAULT_QUESTION, status="PASS")
    fake_ai = FakeAIRunner()
    job = route_event(conn, source_event_id=10, config=test_config(), dry_run=False, ai_runner=fake_ai)
    assert job.state == "DUPLICATE_CACHE"
    assert fake_ai.calls == 0
```

- [ ] **Step 2: Write failing AI-result routing tests**

```python
def test_supported_inference_does_not_unlock_strict_global_task():
    conn = make_test_db()
    ensure_route_schema(conn)
    task_row = {"id": "T1", "priority": 0}
    metadata_row = {"work_type": "implementation", "evidence_policy": "CONFIRMED ORIGINAL Global evidence required"}
    result = {"confidence": "SUPPORTED INFERENCE", "summary": "indirect", "findings": [],
              "contradictions": [], "unresolved": [], "recommended_next_search": "trace callback"}
    decision = route_ai_result(conn, route_job_id=1, result=result, task_row=task_row,
                               metadata_row=metadata_row, provenance="CONFIRMED_GLOBAL_2017")
    assert decision.route == "REVIEW_REQUIRED"

def test_version_sensitive_creates_one_crosscheck_child():
    conn = make_test_db()
    ensure_route_schema(conn)
    task_row = {"id": "T1", "priority": 0}
    metadata_row = {"work_type": "research", "evidence_policy": "Global evidence required"}
    result = {"confidence": "VERSION SENSITIVE", "summary": "JP-only", "findings": [],
              "contradictions": [], "unresolved": ["Global cross-check"],
              "recommended_next_search": "Global native xref"}
    first = route_ai_result(conn, 1, result, task_row, metadata_row, provenance="CONFIRMED_CURRENT_JP")
    second = route_ai_result(conn, 1, result, task_row, metadata_row, provenance="CONFIRMED_CURRENT_JP")
    assert first.child_task_id == second.child_task_id
```

- [ ] **Step 3: Run and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_ai_router.py
```
- [ ] **Step 4: Implement event eligibility and deterministic question generation**

Questions must be selected from a fixed template by artifact/event kind; do not use another model to decide what question to ask.

Example native template:
```text
Using only this artifact and its stated provenance, extract material Logres behavior,
contradictions, unresolved predicates, and the highest-value deterministic next search.
Do not promote later/current JP evidence to Global 2017 truth.
```

- [ ] **Step 5: Implement result routing**

Rules:
```text
CONFIRMED ORIGINAL + provenance compatible -> evidence packet / dependent readiness review
SUPPORTED INFERENCE + policy allows -> evidence packet / dependent readiness review
SUPPORTED INFERENCE + strict policy -> REVIEW_REQUIRED
UNRESOLVED -> focused research child
VERSION SENSITIVE -> target-version cross-check child
contradictions[] non-empty -> EVIDENCE_CONFLICT Brain event
```

Focused child tasks must reuse the blocker-router conventions: parent dependency, acceptance criteria, source event, artifact/hash, and explicit remaining uncertainty.

- [ ] **Step 6: Make dry-run the initial default**

Until rollout Task 8 explicitly enables dispatch, `logres-ai-router` must only print planned routes and append route decisions with state `NEW`; it must not call OpenAI.

Activation uses runtime config:
```json
{"routing": {"ai_dispatch_enabled": false}}
```

- [ ] **Step 7: Run tests and commit**

```bash
python3 ops/logres-control-plane/tests/test_ai_router.py
git add ops/logres-control-plane
git commit -m "feat: route Logres evidence through bounded AI analysis"
```

### Task 5: Build Copilot Eligibility, Dispatch, and Idempotent GitHub Assignment

**Files:**
- Create: `ops/logres-control-plane/lib/logres_copilot.py`
- Create: `ops/logres-control-plane/lib/logres_copilot_router.py`
- Create: `ops/logres-control-plane/bin/logres-copilot-router`
- Create: `ops/logres-control-plane/tests/test_copilot_router.py`

**Interfaces:**
- `CopilotPacket(task_id, title, base_sha, evidence_summary, allowed_files, forbidden_files, acceptance, tests)`.
- `copilot_eligibility(conn, task_id, integration_sha, config) -> Eligibility`.
- `build_issue_body(packet: CopilotPacket) -> str` and `build_assignment(packet: CopilotPacket, base_branch: str) -> dict`.
- `assign_copilot(repo, issue_number, base_branch, instructions, gh_runner) -> AssignmentResult`.
- `dispatch_task(conn, task_id: str, integration_sha: str, config: dict, gh_runner) -> DispatchResult`; `DispatchResult` exposes `route_job_id`, `job`, and `branch`.
- Test fake: `FakeGitHub()` records issue-creation calls, assignment payloads, and deterministic issue/PR query results.
- CLI: `logres-copilot-router [--dry-run] [--task TASK] [--limit N]`.

- [ ] **Step 1: Write failing eligibility tests**

```python
def test_research_task_is_not_copilot_eligible():
    conn = make_test_db()
    seed_task(conn, task_id="T1", work_type="research", status="READY")
    base_sha = "b" * 40
    assert copilot_eligibility(conn, "T1", base_sha, test_config()).allowed is False

def test_missing_acceptance_criteria_is_rejected():
    conn = make_test_db()
    seed_task(conn, task_id="T1", work_type="implementation", status="READY", acceptance=())
    base_sha = "b" * 40
    assert "acceptance" in copilot_eligibility(conn, "T1", base_sha, test_config()).reason

def test_active_overlap_is_rejected():
    conn = make_test_db()
    seed_task(conn, task_id="T1", concurrency_key="field")
    seed_task(conn, task_id="ACTIVE", status="ACTIVE", concurrency_key="field")
    seed_active_lease(conn, task_id="ACTIVE", chat_id="builder", branch="worker/active")
    base_sha = "b" * 40
    assert copilot_eligibility(conn, "T1", base_sha, test_config()).allowed is False

def test_main_can_never_be_target(self):
    packet = CopilotPacket(task_id="T1", title="Bounded helper", base_sha="b" * 40,
                           evidence_summary="CONFIRMED ORIGINAL: fixture", allowed_files=("src/a.ts",),
                           forbidden_files=("main",), acceptance=("unit test passes",),
                           tests=("npm test -- test-a",))
    with self.assertRaises(PolicyError):
        build_assignment(base_branch="main", packet=packet)
```
- [ ] **Step 2: Write failing GitHub payload/idempotency tests**

```python
def test_assignment_forces_integration_base_and_copilot_branch_policy():
    packet = CopilotPacket(task_id="T1", title="Implement bounded helper", base_sha="b" * 40,
                           evidence_summary="CONFIRMED ORIGINAL: fixture", allowed_files=("src/a.ts",),
                           forbidden_files=("main",), acceptance=("unit test passes",),
                           tests=("npm test -- test-a",))
    payload = build_assignment(packet, base_branch="feat/logres-reconstruction")
    assert payload["agent_assignment"]["base_branch"] == "feat/logres-reconstruction"
    assert "Never modify main" in payload["agent_assignment"]["custom_instructions"]

def test_same_task_revision_and_base_sha_reuses_existing_job():
    first = dispatch(conn, packet, fake_gh)
    second = dispatch(conn, packet, fake_gh)
    assert first.route_job_id == second.route_job_id
    assert fake_gh.issue_create_calls == 1
```

- [ ] **Step 3: Run and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_copilot_router.py
```

- [ ] **Step 4: Implement GitHub calls behind an injectable runner**

Production commands:
```bash
gh issue create --repo alfred092020-ux/awakened-realms --title "<title>" --body-file "<file>"
gh api --method POST   -H "Accept: application/vnd.github+json"   -H "X-GitHub-Api-Version: 2022-11-28"   /repos/alfred092020-ux/awakened-realms/issues/<N>/assignees   --input <assignment.json>
```

The assignment JSON must include `copilot-swe-agent[bot]`, target repo, base `feat/logres-reconstruction`, bounded custom instructions, and no main/integration self-merge permission.

- [ ] **Step 5: Build bounded packet content**

Issue body must include:
```text
Task ID
Base integration SHA
Evidence classification + artifact paths/hashes
Allowed files/scopes
Forbidden files/scopes
Acceptance criteria
Required tests
Definition of DONE
Instruction to open a draft PR against feat/logres-reconstruction
Instruction to stop and report BLOCKED_EVIDENCE if historical behavior is unresolved
```

- [ ] **Step 6: Keep production dispatch disabled by default**

Runtime config:
```json
{"routing": {"copilot_dispatch_enabled": false}}
```

Dry-run must show exactly which task would be dispatched and why.

- [ ] **Step 7: Run tests and commit**

```bash
python3 ops/logres-control-plane/tests/test_copilot_router.py
git add ops/logres-control-plane
git commit -m "feat: add safe Copilot task dispatch"
```
### Task 6: Adopt Copilot PRs into Existing Scope, Verification, and Integration Flow

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_copilot.py`
- Modify: `ops/logres-control-plane/bin/logres-copilot-router`
- Create: `ops/logres-control-plane/tests/test_copilot_return_path.py`

**Interfaces:**
- `CopilotJobRecord(route_job_id, task_id, issue_number, pr_number, branch, base_sha, candidate_sha, state)`.
- `reconcile_copilot_job(job, gh_runner, command_runner, current_integration_sha: str, conn=None) -> ReconcileResult`.
- Test fake: `FakeCommandRunner(scope_rc: int, gate_rc: int)` records `gate_calls`; `FakeGitHub()` returns deterministic issue/PR data.
- Calls existing commands only: `logres-scope-check`, `logres-gate fast <ref>`, `logres-coordinator reconcile`, existing immutable integration-queue logic.
- Must never call `git merge` or `logres-merge-train apply*`.

- [ ] **Step 1: Write failing stale-base/scope tests**

```python
def test_stale_base_requires_revalidation_not_auto_queue():
    job = CopilotJobRecord(route_job_id=1, task_id="T1", issue_number=7, pr_number=9,
                           branch="copilot/t1", base_sha="a" * 40, candidate_sha="c" * 40,
                           state="PR_READY")
    result = reconcile_copilot_job(job, gh_runner=FakeGitHub(),
                                   command_runner=FakeCommandRunner(scope_rc=0, gate_rc=0),
                                   current_integration_sha="b" * 40)
    assert result.state == "VERIFYING"
    assert result.revalidation_required is True

def test_forbidden_scope_is_terminal_scope_violation():
    job = CopilotJobRecord(route_job_id=1, task_id="T1", issue_number=7, pr_number=9,
                           branch="copilot/t1", base_sha="b" * 40, candidate_sha="c" * 40,
                           state="PR_READY")
    commands = FakeCommandRunner(scope_rc=1, gate_rc=0)
    result = reconcile_copilot_job(job, gh_runner=FakeGitHub(), command_runner=commands,
                                   current_integration_sha="b" * 40)
    assert result.state == "SCOPE_VIOLATION"
    assert commands.gate_calls == []
```

- [ ] **Step 2: Write failing verification/queue test**

```python
def test_green_copilot_candidate_uses_existing_fast_gate_then_queue():
    conn = make_test_db()
    seed_task(conn, task_id="T1")
    job = CopilotJobRecord(route_job_id=1, task_id="T1", issue_number=7, pr_number=9,
                           branch="copilot/t1", base_sha="b" * 40, candidate_sha="c" * 40,
                           state="PR_READY")
    commands = FakeCommandRunner(scope_rc=0, gate_rc=0)
    result = reconcile_copilot_job(job, gh_runner=FakeGitHub(), command_runner=commands,
                                   current_integration_sha="b" * 40, conn=conn)
    assert commands.gate_calls == [["logres-gate", "fast", "copilot/t1"]]
    assert result.state == "QUEUED"
    assert conn.execute("select count(*) from integration_queue where task_id=? and sha=?", ("T1", "c" * 40)).fetchone()[0] == 1
```

- [ ] **Step 3: Run and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_copilot_return_path.py
```

- [ ] **Step 4: Implement PR discovery and candidate immutability**

Use:
```bash
gh pr list --repo alfred092020-ux/awakened-realms   --state open --json number,headRefName,headRefOid,baseRefName,isDraft,body
```

Match the task by issue linkage/job metadata. Record the first accepted candidate SHA immutably. If the branch later moves, create a new route/candidate rather than mutating the queued SHA.

- [ ] **Step 5: Route scope and verification failures through existing systems**

- Scope failure -> Brain `CONFLICT`, route state `SCOPE_VIOLATION`.
- Fast gate failure -> existing `logres-regression-capture`; route state `FAILED_BOUNDED`.
- Evidence ambiguity noted by Copilot -> parent task `BLOCKED_EVIDENCE` and focused research route.
- Green candidate -> existing coordinator/queue path; do not insert a special Copilot-only merge status.

- [ ] **Step 6: Run tests and commit**

```bash
python3 ops/logres-control-plane/tests/test_copilot_return_path.py
git add ops/logres-control-plane
git commit -m "feat: feed Copilot candidates into normal verification"
```
### Task 7: Add Restart Reconciliation, Backpressure, Health, and Lead Status

**Files:**
- Create: `ops/logres-control-plane/lib/logres_reconcile.py`
- Create: `ops/logres-control-plane/bin/logres-route-reconcile`
- Modify: `ops/logres-control-plane/bin/logres-autopilot-watch`
- Modify: `ops/logres-control-plane/bin/logres-doctor`
- Modify: `ops/logres-control-plane/bin/logres-lead`
- Create: `ops/logres-control-plane/tests/test_route_reconcile.py`
- Create: `ops/logres-control-plane/tests/test_autoflow_health.py`

**Interfaces:**
- `reconcile_routes(conn, ai_cache, github, command_runner, config: dict, current_integration_sha: str) -> list[ReconcileResult]`.
- Test fake: `FakeAICache(dedupe_key=None, status=None)` exposes `openai_calls`; `FakeGitHub()` exposes mutable `search_issue.return_value` and `create_issue_calls`.
- `backpressure(conn, config: dict) -> BackpressureState`.
- `logres-route-reconcile [--dry-run]` repairs local state from cached AI results, Brain, GitHub, and integration state.
- `logres-lead routes` prints compact route/OpenAI/Copilot status.
- Existing `logres-autopilot-watch` invokes reconcile, AI router, Copilot router once per existing 5-minute cron cycle.

- [ ] **Step 1: Write failing crash-window reconciliation tests**

```python
def test_ai_completed_before_brain_post_is_recovered_without_second_call():
    conn = make_test_db()
    ensure_route_schema(conn)
    seed_route(conn, state="AI_RUNNING", dedupe_key="x", route_kind="AI")
    seed_ai_run(conn, artifact_sha="a" * 64, question="q", status="PASS")
    ai_cache = FakeAICache(dedupe_key="x", status="PASS")
    result = reconcile_routes(conn, ai_cache=ai_cache, github=FakeGitHub(),
                              command_runner=FakeCommandRunner(scope_rc=0, gate_rc=0),
                              config=test_config(), current_integration_sha="b" * 40)[0]
    assert result.state == "BRAIN_POSTED"
    assert ai_cache.openai_calls == 0

def test_existing_copilot_issue_is_adopted_after_crash():
    conn = make_test_db()
    ensure_route_schema(conn)
    seed_route(conn, state="ASSIGNING", dedupe_key="copilot:T1", route_kind="COPILOT", external_ref=None)
    fake_gh = FakeGitHub()
    fake_gh.search_issue.return_value = {"number": 42, "state": "open", "title": "T1"}
    result = reconcile_routes(conn, ai_cache=FakeAICache(), github=fake_gh,
                              command_runner=FakeCommandRunner(scope_rc=0, gate_rc=0),
                              config=test_config(), current_integration_sha="b" * 40)[0]
    assert result.state == "ACTIVE"
    assert result.issue_number == 42
    assert fake_gh.create_issue_calls == 0
```

- [ ] **Step 2: Write failing backpressure tests**

```python
def test_four_ready_merges_pause_new_copilot_dispatch():
    conn = make_test_db()
    for i in range(5):
        conn.execute("insert into integration_queue(task_id,sha,branch,status,queued_at,updated_at,note) values(?,?,?,?,datetime('now'),datetime('now'),'')",
                     (f"T{i}", f"{i:040d}", f"worker/t{i}", "READY_FOR_INTEGRATION"))
    conn.commit()
    assert backpressure(conn, test_config()).copilot_paused is True

def test_verification_backlog_pauses_implementation_but_not_research():
    conn = make_test_db()
    for i in range(4):
        conn.execute("insert into route_jobs(dedupe_key,route_kind,state,created_at,updated_at) values(?,?,?,datetime('now'),datetime('now'))",
                     (f"verify:{i}", "VERIFY", "VERIFYING"))
    conn.commit()
    state = backpressure(conn, test_config())
    assert state.copilot_paused is True
    assert state.ai_research_paused is False
```

- [ ] **Step 3: Run and verify RED**

Run:
```bash
python3 ops/logres-control-plane/tests/test_route_reconcile.py
python3 ops/logres-control-plane/tests/test_autoflow_health.py
```

- [ ] **Step 4: Implement reconciler**

Reconciliation order:
```text
1. expire/renew normal Brain leases using existing behavior
2. recover AI routes from ai_runs cache
3. recover Copilot issue/PR state from GitHub
4. compare candidate base SHA to current integration SHA
5. mark superseded/cancelled task routes
6. enforce lineage dedupe
7. append route decision for every repair
```
- [ ] **Step 5: Hook into the existing 5-minute watcher**

Append in `logres-autopilot-watch`, after existing lease/integration refresh and before safe-wave notification:
```python
run_helper("logres-route-reconcile")
run_helper("logres-ai-router")
run_helper("logres-copilot-router")
```

Each helper must hold its own non-blocking file lock or durable claim so a slow cycle cannot overlap the next cron invocation.

- [ ] **Step 6: Extend doctor**

Add checks:
```text
route_schema
route_cursor
route_failures
openai_recent_success
openai_budget_state
copilot_auth
copilot_active_jobs
copilot_base_policy
autoflow_source_deployed
```

No check may print token/key values.

- [ ] **Step 7: Extend lead status**

Add:
```bash
logres-lead routes
```

Expected compact output:
```text
ROUTER cursor=742 lag=0 active=2 failed=0
OPENAI healthy active=1 cache_hits=3 budget=OPEN
COPILOT healthy active=1 queued=0 prs=1
BACKPRESSURE copilot=OPEN ai=OPEN
```

- [ ] **Step 8: Run tests and commit**

```bash
python3 ops/logres-control-plane/tests/test_route_reconcile.py
python3 ops/logres-control-plane/tests/test_autoflow_health.py
git add ops/logres-control-plane
git commit -m "feat: reconcile and monitor autoflow routes"
```

### Task 8: Deploy in Stages, Prove No Regression, Then Enable Bounded Production Autoflow

**Files:**
- Modify: `ops/logres-control-plane/config/autoflow.default.json`
- Modify: `ops/logres-control-plane/README.md`
- Create: `ops/logres-control-plane/tests/test_autoflow_integration.py`

**Interfaces:**
- Uses: `scripts/logres/deploy_control_plane.py`, existing `logres-doctor`, `logres-autopilot-watch`, `logres-gate`, Brain, GitHub CLI.
- Produces: live deployed helpers plus one Brain rollout event containing deployed commit/hash and enabled feature flags.

- [ ] **Step 1: Write synthetic end-to-end tests before live activation**

```python
def test_synthetic_artifact_to_cached_ai_to_research_child():
    conn = make_test_db()
    ensure_route_schema(conn)
    seed_task(conn, task_id="RE1", priority=0, status="ACTIVE", work_type="research",
              evidence_policy="Global evidence required")
    seed_event(conn, event_id=100, task_id="RE1", artifact_path="/tmp/global-native.txt",
               artifact_sha="a" * 64,
               meta={"artifact_bytes": 74000, "kind": "native_trace",
                     "provenance": "CONFIRMED_GLOBAL_2017"})
    fake_ai = FakeAIRunner(result={"confidence": "UNRESOLVED", "summary": "missing branch",
                                   "findings": [], "contradictions": [],
                                   "unresolved": ["callback target"],
                                   "recommended_next_search": "xref callback"})
    first = run_ai_cycle(conn, fake_ai, FakeBrainRunner(), test_config(), limit=10)
    second = run_ai_cycle(conn, fake_ai, FakeBrainRunner(), test_config(), limit=10)
    assert first.created_research_tasks == 1
    assert second.created_research_tasks == 0
    assert fake_ai.calls == 1

def test_synthetic_eligible_task_to_copilot_then_queue():
    conn = make_test_db()
    ensure_route_schema(conn)
    seed_task(conn, task_id="IMP1", priority=0, status="READY", work_type="implementation",
              evidence_policy="CONFIRMED ORIGINAL Global evidence required",
              acceptance=("targeted test passes",))
    github = FakeGitHub()
    dispatch = dispatch_task(conn, "IMP1", "b" * 40, test_config(), github)
    github.list_prs_result = [{"number": 9, "headRefName": dispatch.branch,
                               "headRefOid": "c" * 40,
                               "baseRefName": "feat/logres-reconstruction",
                               "isDraft": True}]
    result = reconcile_copilot_job(dispatch.job, github,
                                   FakeCommandRunner(scope_rc=0, gate_rc=0),
                                   current_integration_sha="b" * 40, conn=conn)
    assert result.state == "QUEUED"
    assert conn.execute("select count(*) from integration_queue where task_id=? and sha=?",
                        ("IMP1", "c" * 40)).fetchone()[0] == 1
```

- [ ] **Step 2: Run full offline control-plane suite**

Run:
```bash
python3 -m unittest discover -s ops/logres-control-plane/tests -p 'test_*.py'
```

Expected: PASS.
- [ ] **Step 3: Dry-run deploy and compare manifest**

Run:
```bash
python3 scripts/logres/deploy_control_plane.py   --source ops/logres-control-plane   --target /home/ubuntu/logres   --dry-run
```

Verify no secret, SQLite DB, private evidence, game asset, or unrelated helper appears in the manifest.

- [ ] **Step 4: Deploy atomically with dispatch disabled**

Runtime config after first deploy:
```json
{
  "routing": {
    "ai_dispatch_enabled": false,
    "copilot_dispatch_enabled": false
  }
}
```

Run:
```bash
python3 scripts/logres/deploy_control_plane.py   --source ops/logres-control-plane   --target /home/ubuntu/logres
/home/ubuntu/logres/bin/logres-doctor
/home/ubuntu/logres/bin/logres-autopilot-watch
/home/ubuntu/logres/bin/logres-lead routes
```

Expected: existing Brain/worker/merge checks remain PASS; routers report dry-run/planned state only.

- [ ] **Step 5: Verify existing gameplay/integration gates are unaffected**

Run:
```bash
/home/ubuntu/logres/bin/logres-lead verify-all origin/feat/logres-reconstruction
```

Expected: exact existing project gate PASS. This control-plane rollout must not require gameplay changes.

- [ ] **Step 6: Configure current model rate from an official current OpenAI pricing source**

Populate the runtime-only `/home/ubuntu/logres/control/autoflow.json` rate entry for every automatically selected model. If a selected model lacks a configured rate, leave automatic AI dispatch disabled for that model. Do not commit pricing secrets or account data.

Then verify:
```bash
/home/ubuntu/logres/bin/logres-lead routes
```

Expected: `budget=OPEN` with `budget_usd=10.0`.

- [ ] **Step 7: Enable AI routing only**

Set:
```json
{"routing": {"ai_dispatch_enabled": true, "copilot_dispatch_enabled": false}}
```

Use one fresh, substantive Global RE artifact. Verify:
- exactly one `route_jobs` row;
- at most one real API call;
- `api_usage` row exists;
- result appears in Brain;
- duplicate run uses cache;
- no implementation task is unlocked contrary to evidence policy.

Observe at least one normal 5-minute cron cycle.

- [ ] **Step 8: Enable Copilot report/review mode**

Set Copilot mode to `report_only`. Dispatch one eligible review task. Verify:
- one GitHub issue/assignment;
- base branch `feat/logres-reconstruction`;
- draft PR only;
- no main target;
- restart/reconcile adopts the same issue/PR without duplication.

- [ ] **Step 9: Enable bounded Copilot implementation**

Change Copilot mode to `bounded_implementation` only after Step 8 passes. Dispatch one implementation task with explicit file scope and tests. Verify it flows through scope check, fast gate, and the existing integration queue without automatic merge.
- [ ] **Step 10: Exercise backpressure deliberately**

In a temporary test DB, seed:
- five READY_FOR_INTEGRATION rows;
- four verification-pending items;
- an unknown model rate.

Verify new Copilot implementation dispatch pauses, noncritical AI auto-spend closes, and deterministic research/Lead operations continue.

- [ ] **Step 11: Record rollout evidence in Brain**

Post one HIGH INFO/EVIDENCE event containing:
```text
deployed repo commit
deployed helper manifest SHA256
route schema version
AI routing enabled state
Copilot mode
doctor result
full verification result
known remaining limitations
```

Do not include API keys, tokens, GitHub credentials, or private artifact bytes.

- [ ] **Step 12: Commit rollout docs/config defaults**

```bash
git add ops/logres-control-plane
git commit -m "docs: document staged autoflow rollout"
```

## Final Whole-Branch Verification

After Tasks 1-8:

```bash
python3 -m unittest discover -s ops/logres-control-plane/tests -p 'test_*.py'
python3 scripts/logres/deploy_control_plane.py --source ops/logres-control-plane --target /tmp/logres-control-plane-final
git diff --check "$(git merge-base origin/feat/logres-reconstruction HEAD)" HEAD
/home/ubuntu/logres/bin/logres-doctor
/home/ubuntu/logres/bin/logres-lead routes
/home/ubuntu/logres/bin/logres-lead verify-all origin/feat/logres-reconstruction
```

Expected:
- all control-plane tests PASS;
- deployment manifest contains only approved helpers/config;
- doctor has no new FAIL caused by autoflow;
- routes report no duplicate/stuck jobs;
- gameplay/integration gate remains PASS;
- no branch or PR targets `main`;
- no code path integrates without Lead-controlled existing merge machinery.

## Execution Notes

Implement tasks in order. Each task ends with a commit so review can reject or revert one capability independently.

Do not enable automatic external dispatch until Task 8. The first seven tasks must be safe to deploy with both routing feature flags false.

The rollout must prefer fail-closed behavior: uncertainty about budget, evidence sufficiency, task eligibility, scope, or candidate identity stops automatic dispatch while leaving deterministic/manual project work available.
