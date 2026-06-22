# Engine v3 Implementation Spec

> Status: draft for owner alignment
> Date: 2026-06-22
> Scope decision: **Paper-first v3**, with a real `DomainPack` seam for future insurance / IFRS.
> Runtime decision: **runtime-pluggable v3**. Production target is Hermes-native, but `CodexCliRuntime`
> and `MockRuntime` are first-class for validation and development.

---

## 0. Purpose

Engine v3 rebuilds the a-side research engine so the implementation matches the intended
Hermes+Skill architecture instead of continuing the v2 hybrid drift.

The v3 target is:

> A general research engine core, proven first through the paper domain, where Hermes/Skill,
> DomainPack, Runtime, GatePolicy, and deterministic tools are first-class abstractions.

v3 must preserve the v2 proof assets where they are valuable:

- CrossRef / DOI verification
- meta-analysis and dataset lanes
- figure/table/render tools
- delivery audit
- floor scoring
- golden paper fixtures
- paper-mcp thin handoff and viability-lock concept

v3 must not preserve the v2 architectural drift:

- skill paths embedded ad hoc in phase prompts
- gate severity declared in `PaperPack` but enforced differently in `pipeline.py`
- core importing paper-specific modules
- runtime hard-coded to `codex exec` for brain and Hermes only for workers
- job submit endpoints without explicit server-side POST auth

---

## 1. Non-Goals

v3 MVP does not attempt to:

- Replace live production immediately.
- Build insurance / IFRS packs in the first implementation wave.
- Automate journal submission or rebuttal.
- Remove v2. v2 remains the rollback path until v3 beats the selected golden gates.
- Rewrite deterministic scientific logic that already works. v3 wraps it behind stable tool interfaces first.

---

## 2. Architecture Decisions

### AD-1: Paper-first, Not Paper-only

v3 starts with `PaperPack` because paper has real fixtures, real v2 artifacts, and a live b-side path.
However, `core/` must not import `packs.paper.*`.

Acceptance:

- `rg "packs\\.paper|paper_driver|format_repair|dataset_lane" engine_v3/core engine_v3/service`
  returns no matches, except comments in migration docs.
- `PaperPack` is loaded through a pack registry.

### AD-2: Runtime-Pluggable

v3 defines a runtime interface. Production target is Hermes-native; Codex CLI remains a fallback.

Required runtimes:

- `MockRuntime`: deterministic test runtime.
- `CodexCliRuntime`: development and golden-test fallback.
- `HermesCodexRuntime`: target production runtime. Brain uses Hermes with codex-capable provider;
  worker uses Hermes big-pickle / delegate path.

Acceptance:

- The same `PaperPack` golden fixture can run with `MockRuntime` for unit/integration tests.
- At least one smoke test proves `HermesCodexRuntime` can run one brain task and one worker task.
- Engine code does not branch on "codex" or "hermes" outside runtime classes.

### AD-3: Skill Bundle Is Configuration, Not Prompt Decoration

Domain packs declare skill bundles. Runtime decides how to load or inject those skills.

Acceptance:

- There is no `_skill("...")` helper inside paper pipeline phases.
- Phase prompts may reference "loaded skill requirements", but cannot list hard-coded filesystem paths.
- `PaperPack.skill_bundle()` is the single source for paper skill names.

### AD-4: GatePolicy Is the Single Enforcement Source

Gate definitions and enforcement policy must live in the pack/gate layer, not hidden in phase code.

Acceptance:

- Every gate result has `severity`: `BLOCK | WARN | RECORD`.
- Every gate has `applies_to`: lane, tier, and phase selectors.
- The orchestrator enforces gate reports generically.
- Pipeline phase handlers cannot manually decide "Gate C blocks but Gate B does not" except by returning
  structured gate inputs. Policy belongs to the gate registry.

### AD-5: Python Owns Loop; Agent Owns Thinking

Python remains the deterministic control plane:

- job lifecycle
- state machine
- checkpoint
- work queue
- fan-out
- gate enforcement
- artifact rendering and validation

Agents own:

- research positioning
- analysis spec reasoning
- prose writing
- review judgment
- edit prescription

Agents do not certify completion. Completion is a gate decision.

---

## 3. Target Directory Layout

```text
engine_v3/
  core/
    contracts.py          # typed core contracts and task/result objects
    dossier.py            # file-backed run state and checkpoint manifests
    gates.py              # generic gate lifecycle and policy enforcement
    orchestrator.py       # phase loop, reroute, checkpoint, resume
    packs.py              # DomainPack ABC and pack registry
    runtime.py            # Runtime ABC
    status.py             # domain-neutral status projection shape

  runtimes/
    mock.py               # deterministic tests
    codex_cli.py          # development fallback
    hermes_codex.py       # production target

  packs/
    paper/
      pack.py             # PaperPack implementation
      contract.py         # paper contract parsing/canonicalization
      skills.py           # paper skill bundle declaration
      tools.py            # PaperToolProvider wrapping v2 deterministic assets
      gates.py            # paper gate registry and checks
      pipeline.py         # paper pipeline plan and phase handlers
      schemas/
        contract_v3.schema.json

  service/
    auth.py               # POST Bearer auth / signed artifact policy
    http_app.py           # FastAPI app
    routes.py             # /v3/jobs routes
    job_store.py          # file-backed or sqlite-backed job store + locks

  tests/
    core/
    runtimes/
    packs/paper/
    service/
    golden/
```

The first implementation may live under `newarch/engine_v3/` to avoid moving v2. Once stable, it can
be promoted.

---

## 4. Core Interfaces

### 4.1 Runtime

```python
@dataclass(frozen=True)
class RuntimeContext:
    run_dir: Path
    dossier_path: Path
    skill_bundle: list[str]
    tool_manifest: dict[str, Any]
    timeout_s: int

@dataclass(frozen=True)
class BrainTask:
    task_id: str
    phase: str
    goal: str
    inputs: list[str]
    outputs: list[str]
    context: str
    acceptance_criteria: list[str]

@dataclass(frozen=True)
class WorkerTask:
    task_id: str
    phase: str
    worker_class: Literal["drafter", "fixer", "mechanical"]
    goal: str
    inputs: list[str]
    outputs: list[str]
    context: str
    acceptance_criteria: list[str]

@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: Literal["ok", "blocked", "error"]
    changed_files: list[str]
    blockers: list[str]
    stdout_tail: str = ""

class Runtime(Protocol):
    name: str

    def prepare(self, ctx: RuntimeContext) -> None: ...
    def run_brain(self, task: BrainTask, ctx: RuntimeContext) -> TaskResult: ...
    def run_worker(self, task: WorkerTask, ctx: RuntimeContext) -> TaskResult: ...
    def review(self, task: BrainTask, ctx: RuntimeContext) -> TaskResult: ...
```

Rules:

- Runtime must verify declared output files exist before returning `ok`.
- Runtime must classify quota/auth/provider failures as `error`, not `ok`.
- Runtime must not mutate dossier directly. It returns results; orchestrator records them.

### 4.2 DomainPack

```python
class DomainPack(Protocol):
    name: str

    def contract_schema(self) -> dict[str, Any]: ...
    def parse_contract(self, raw: dict[str, Any]) -> dict[str, Any]: ...
    def canonicalize_contract(self, contract: dict[str, Any]) -> dict[str, Any]: ...
    def contract_hash(self, contract: dict[str, Any]) -> str: ...

    def skill_bundle(self) -> list[str]: ...
    def tool_provider(self) -> ToolProvider: ...
    def pipeline_plan(self) -> list[PhaseSpec]: ...
    def gate_registry(self) -> list[GateSpec]: ...
    def status_projection(self, dossier: dict[str, Any], run_dir: Path) -> dict[str, Any]: ...
```

Rules:

- `core/` calls only `DomainPack`.
- Pack-specific typed fields must live under `dossier["pack"]`.
- Pack-specific artifacts must be described through tool outputs and status projection.

### 4.3 ToolProvider

```python
class ToolProvider(Protocol):
    name: str

    def capabilities(self) -> dict[str, Any]: ...
    def run(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]: ...
```

Paper v3 can initially implement `PaperToolProvider` by wrapping existing v2 modules rather than shelling
out to a CLI. A CLI façade can be added without changing pack/core contracts.

Required paper tools:

- `refs.build`
- `refs.audit`
- `data.meta_analysis`
- `data.dataset_analysis`
- `figures.generate`
- `tables.inject`
- `render.pdf`
- `review.floor_score`
- `delivery.audit`

---

## 5. Dossier v3

Required core shape:

```json
{
  "schema_version": 3,
  "run": {
    "job_id": "...",
    "pack": "paper",
    "runtime": "hermes-codex|codex-cli|mock",
    "created_at": "...",
    "updated_at": "..."
  },
  "contract": {},
  "status": {
    "state": "accepted|running|blocked|failed|done",
    "phase": "data|gap|...",
    "checkpoint": null,
    "blockers": [],
    "next_action": null
  },
  "phases": [],
  "delegations": [],
  "gates": [],
  "artifacts": [],
  "revision_loop": {},
  "pack": {}
}
```

Rules:

- Every phase completion writes a checkpoint manifest with artifact hashes.
- Every runtime delegation is recorded with task id, runtime, class, status, declared outputs.
- Gate decisions are append-only records. The latest gate report can be projected, but history is retained.
- `status.state = done` is allowed only after final delivery gate passes.

---

## 6. Gate System

### 6.1 GateSpec

```python
@dataclass(frozen=True)
class GateSpec:
    name: str
    phase: str
    severity: Literal["BLOCK", "WARN", "RECORD"]
    applies_to: GateSelector
    check: Callable[[GateInput], GateResult]
```

### 6.2 GateSelector

```python
@dataclass(frozen=True)
class GateSelector:
    lanes: set[str] | None = None
    tiers: set[str] | None = None
    levels: set[str] | None = None
```

### 6.3 Enforcement Rule

The orchestrator runs all gates whose `phase` matches the completed phase and whose selector matches
the current contract/dossier. It enforces:

- `BLOCK` + `passed=false` -> terminal `blocked`, unless phase explicitly requests bounded reroute.
- `WARN` -> recorded in dossier and surfaced in status.
- `RECORD` -> recorded only; never blocks.

Pipeline code must not override severity after the gate report.

### 6.4 Paper v3 Gate Plan

| Gate | Phase | Severity | Applies | Meaning |
|---|---|---:|---|---|
| A.refs | data | BLOCK | all paper lanes | refs >= 35 and DOI real-rate >= 0.80 |
| B.claim_evidence | claim_evidence | BLOCK | meta lane | matrix rows exact-match claims |
| B.dataset_qualitative | render_gates | WARN | dataset lane | candidate qualitative overclaim for reviewer |
| C.figures | render_gates | BLOCK | all lanes with figures | SVG/PNG pair, no dupes, figure numbers trace |
| D.readability | render_gates | BLOCK | all lanes | no placeholders, render ok, body complete |
| E.value | data/gap | WARN | all lanes | value steering; never hard-block |
| F.logic | render_gates | BLOCK | all lanes | contradiction / logic audit |
| N.number_trace | render_gates | BLOCK | dataset lane | manuscript numbers trace to real_results |
| R.review | review_heal | BLOCK/WARN by tier | all lanes | no P0 + floor ok + review threshold |
| Z.delivery | format_repair | BLOCK | all lanes | PDF and final artifact deliverable |

If a gate is intentionally advisory for a lane, that must be represented here, not in phase code.

---

## 7. PaperPack v3 Pipeline

MVP phases:

1. `data`
   - Meta lane: build corpus, run meta-analysis, build refs, generate figures.
   - Dataset lane: resolve/fetch dataset, brain writes spec, worker/brain writes analysis code, run real analysis, build refs, generate figures.
   - Gates: `A.refs`, `E.value` as applicable.

2. `gap`
   - Brain writes `phase3_positioning.md`.
   - Must consume contract framing when present.
   - Store structured gap rows in dossier.

3. `structure`
   - Brain writes `phase4_structure.md`.

4. `claim_evidence`
   - Brain writes `claim_evidence_map.md`.
   - Gate B runs where applicable.

5. `write`
   - Workers draft isolated `sections/*.md`.
   - Brain composes `paper_draft_v0.qmd`.

6. `render_gates`
   - ToolProvider renders PDF.
   - Gate C/D/F/N runs by policy.

7. `review_heal`
   - Reviewer brain produces review JSON and edit prescriptions.
   - Exact locator edits are applied deterministically.
   - Remaining fuzzy edits go to worker.
   - VIP can trigger one bounded reroute to `data` for analysis-level findings.

8. `format_repair`
   - ToolProvider runs final render and delivery audit.
   - Gate Z runs.

Rules:

- Phase handlers may produce gate inputs, but cannot decide gate enforcement.
- Worker outputs are isolated. Only composition/review phases merge into main draft.
- Every number in final manuscript must be either from `real_results`, a verified reference/context matrix,
  or explicitly whitelisted as a method/rule constant.

---

## 8. HTTP Service v3

### 8.1 Routes

```text
GET  /v3/health
GET  /v3/capabilities
GET  /v3/schema/{pack}/contract_v3.schema.json
POST /v3/jobs/viability-probe
POST /v3/jobs
GET  /v3/jobs/{job_id}/status
GET  /v3/jobs/{job_id}/artifact/{artifact_id}
```

### 8.2 Auth

All POST routes require:

```text
Authorization: Bearer <PAPER_JOB_SERVICE_TOKEN>
```

Validation rules:

- Missing token -> 401.
- Invalid token -> 403.
- Compare using constant-time comparison.
- GET status may be public only if job id is unguessable or signed by b-side. Otherwise use signed URL.

### 8.3 Job Store

MVP can be file-backed, but must implement:

- idempotent submit by request hash
- atomic job creation lock
- max live jobs
- terminal state recording on worker crash
- artifact index

Acceptable MVP implementation:

- SQLite job index + file artifacts, or
- lock files created with exclusive open mode plus JSON state.

Non-acceptable:

- only scanning `dossier.json` to infer concurrency
- creating run dir before claiming an atomic lock

---

## 9. Runtime Details

### 9.1 MockRuntime

Purpose:

- core tests
- gate tests
- service tests

Behavior:

- Writes declared fixtures.
- Returns deterministic `ok` / `blocked`.
- Never calls external model.

### 9.2 CodexCliRuntime

Purpose:

- local development
- golden proof before Hermes substrate is fully stable

Rules:

- Must use the same `Runtime` interface.
- Must load pack skill bundle by reading skill files into bounded context.
- Must classify quota/auth/rate-limit text as `error`.
- Must verify output files exist.

### 9.3 HermesCodexRuntime

Purpose:

- production target for Hermes+Skill.

Rules:

- Brain uses Hermes codex-capable provider when available.
- Workers use Hermes big-pickle / delegate path.
- Skill bundle is installed/loaded through Hermes skill mechanism.
- Parent-level fan-out only. Child workers cannot delegate.
- If Hermes-native codex provider is unavailable, runtime may fail fast or explicitly fall back to
  `CodexCliRuntime` only when configured by feature flag.

Required smoke tests:

- Hermes loads paper skill bundle.
- Brain task writes one declared file.
- Worker task writes one declared file.
- Quota/auth/provider failure is classified as `error`.

---

## 10. b-side Compatibility

v3 must not require immediate changes to `paper-mcp`.

Compatibility layer:

- v3 accepts the existing paper-mcp research contract shape where possible.
- v3 returns `job_id`, `status_url`, and `artifact` fields compatible with current project page assumptions.
- v3 exposes `/v3/jobs/viability-probe`, but b-side can continue using v2 until feature flag changes.

Cutover plan:

1. Deploy v3 a-side behind `/v3`.
2. Run golden tests directly against `/v3`.
3. Add `A_ENGINE_ENDPOINT="/v3/jobs"` option to paper-mcp only after v3 passes acceptance.
4. Keep `/v2/jobs` as rollback.

---

## 11. Acceptance Tests

### 11.1 Core

- `test_pack_registry_no_core_domain_imports`
- `test_dossier_checkpoint_hashes_artifacts`
- `test_orchestrator_resume_skips_completed_phases`
- `test_gate_policy_blocks_warns_records_generically`
- `test_runtime_errors_do_not_mark_task_ok`

### 11.2 Paper Pack

- `test_paper_pack_declares_full_skill_bundle`
- `test_paper_gate_plan_has_single_policy_source`
- `test_refs_gate_blocks_under_35`
- `test_claim_evidence_gate_catches_unlisted_claim`
- `test_dataset_number_trace_blocks_untraced_numbers`
- `test_delivery_gate_blocks_missing_pdf`

### 11.3 Service

- `test_post_jobs_requires_bearer_token`
- `test_invalid_bearer_rejected`
- `test_submit_idempotent_replay_same_hash`
- `test_submit_conflict_different_hash`
- `test_concurrent_submit_lock`
- `test_worker_crash_sets_failed_state`

### 11.4 Golden

Golden proof target for first v3 paper:

- Same frozen corpus as v2 golden proof.
- `delivery=pass`.
- no P0.
- DOI real-rate >= 0.80.
- refs >= 35.
- no broken `?@` crossrefs.
- floor score must be at least v2 rollback threshold selected for the test.

The first v3 milestone may pass with `CodexCliRuntime`; Hermes acceptance requires the same test or
a bounded smoke+single-phase proof with `HermesCodexRuntime`.

---

## 12. Migration Plan

### M0: Spec Lock

- Owner approves this implementation spec.
- Create a task list from sections 3-11.

### M1: Core Skeleton

- Add `engine_v3/core`.
- Implement `MockRuntime`.
- Implement `DomainPack` interface.
- Unit tests pass without paper imports.

### M2: PaperPack Wrapper

- Wrap v2 deterministic assets behind `PaperToolProvider`.
- Move paper skill bundle declaration into `PaperPack`.
- Implement gate registry and policy.

### M3: Paper Pipeline on CodexCliRuntime

- Run one bounded golden fixture through v3.
- Ensure v3 dossier/status/artifact shape is stable.

### M4: Service v3

- Add `/v3` routes.
- Add Bearer POST auth.
- Add job locking/idempotency.
- Verify no impact to `/v2`.

### M5: Hermes Runtime

- Implement `HermesCodexRuntime`.
- Smoke test skill load + brain + worker.
- Run partial pipeline or full golden if stable.

### M6: b-side Feature Flag

- Add `A_ENGINE_ENDPOINT="/v3/jobs"` option.
- Shadow-run selected contracts.
- Flip only after golden and live smoke pass.

---

## 13. Open Decisions Before Coding

1. Job store implementation:
   - Option A: SQLite index + file artifacts.
   - Option B: file-only lock files + JSON.
   - Default recommendation: SQLite index for v3 service, file artifacts for large outputs.

2. Hermes provider policy:
   - Option A: Hermes-native codex required for production.
   - Option B: Codex CLI fallback allowed in production behind explicit feature flag.
   - Default recommendation: A for production, B only for emergency/manual operator mode.

3. First golden threshold:
   - Option A: equal v2 clean A/B threshold.
   - Option B: lower first milestone threshold, then raise.
   - Default recommendation: two-stage threshold: architecture milestone first, quality milestone second.

---

## 14. Definition of Done for v3 MVP

v3 MVP is done only when:

- `engine_v3/core` has no paper-specific imports.
- `PaperPack` runs through the `DomainPack` interface.
- Runtime selection is config-driven.
- Skill bundle is pack-declared.
- Gate policy is the only enforcement source.
- POST routes require auth.
- Job creation is locked and idempotent.
- One paper golden run completes with documented score/delivery result.
- v2 remains deployable as rollback.

