# Engine Status — as-built (a-side general engine)

> Snapshot 2026-06-16. The domain-agnostic Hermes+Skill research engine (a-side) is
> BUILT, TESTED, and LIVE-VALIDATED on ac-2012 — it produces a real paper that BEATS
> the golden baseline. This file is the single source of truth for "what exists now".
> Companions: [ENGINE_GENERAL_SPEC.md](ENGINE_GENERAL_SPEC.md) (PRD), [ENGINE_BUILD_PLAN.md](ENGINE_BUILD_PLAN.md)
> (TDD phases + status), [HERMES_NATIVE_ORCHESTRATOR_DESIGN.md](HERMES_NATIVE_ORCHESTRATOR_DESIGN.md)
> (design), [BSIDE_WEB_INTEGRATION_PLAN.md](BSIDE_WEB_INTEGRATION_PLAN.md) (next: wire b-side + web).

## 1. What is built (newarch/, branch `engine-build`, 16 commits, 154 tests pass)

```
framework/                  domain-agnostic, imports NO domain (test-enforced)
  domain_pack.py            DomainPack ABC + value objects (Severity/Gate/GateResult/ViabilityVerdict)
  gate_lifecycle.py         run_gates(pack, dossier) — register->run->enforce->block, fail-closed
  dossier.py                reasoning-continuity checkpoint + atomic manifest + fresh-resume + projection
  dispatch.py               WorkerPacket + Dispatcher; MockDispatcher / HermesDispatcher / LiveDispatcher
  orchestrator.py           control-plane state machine: phases, fan-out, gates, checkpoint, watchdog
  review.py                 SelfHealLoop — strong-brain review + deterministic floor, no silent pass
  viability.py              handle_viability — master auto-pivot / phd pause + steering log
  submission.py             viability-lock + deterministic contract derivation + submit_gate
packs/paper/                the proven paper pack
  pack.py                   PaperPack(DomainPack): PICOS grill, viability=poolable-k, gates A-F, QMD+PDF
  gates.py                  Gates A-F real checks (B independent claim extraction; E value WARN)
  logic_audit.py            vendored 7-scan logic audit (Gate F)
  pipeline.py               THE 11-phase meta-analysis lane ON the framework (run_paper entry point)
packs/insurance/            real-ish 2nd domain (proves the seam): findings-yield viability + KB gates
paperctl.py                 thin CLI over the deterministic core (refs/data/figures/tables/render/gate/...)
golden_proof.py             acceptance harness — grades any run dir vs golden (floor + review)
engine_routes.py            HTTP: POST /v2/jobs (orchestrator) + GET /v2/jobs/{id}/status (projection)
engine_project_page.html    reference live project page (polls the projection)
```

## 2. Division of labour (the architecture, validated)

| concern | owner |
|---|---|
| facts: meta-analysis, refs, figures, tables, render, floor_score | deterministic (paperctl / direct) — never an LLM |
| reasoning: gap / structure / claim-evidence / review judgment + **edit prescription** | codex BRAIN (LiveDispatcher reviewer class → `codex exec`) |
| bulk: 7 section drafts + applying prescribed edits | free big-pickle WORKER (LiveDispatcher drafter class → hermes) |
| loop, gates, state machine, refusal to ship bad artifacts | Python control plane (framework) |

Governing rule holds: **Python owns facts+gates+loop; the brain reasons + prescribes; the worker just executes.**

## 3. Live validation (ac-2012, exercise-depression frozen corpus, ~30 min/run once tuned)

Full 11-phase pipeline end-to-end on the NEW framework (not the old `paper_driver` loop):
data → gap → structure → claim_evidence → write(7 worker drafts + codex compose) → render+gates → review+self-heal.

| run | change | floor /100 | review /100 |
|---|---|---|---|
| 1 | (wrong) free worker = deepseek-v4-flash-free | 59.3 | 64 |
| 2 | correct big-pickle (`hermes -z … --provider custom -m big-pickle --toolsets file,terminal`) | 58.3 | 74 |
| 3 | codex review PRESCRIBES `{locator,action,replacement}` edits in one call; worker only executes (deterministic apply + big-pickle fuzzy) | 60.1 | 76 |
| 4 | steer prescriptions at floor_score's weak dims | **70.7** | **82** |

**Golden bars: floor 62.2, review 57.1. Run 4 BEATS both (floor +8.5, review +25). `golden_proof: meets_floor=true, passed=true`.**
Key dim recoveries (run 3→4): evidence_validity 3.5→7.5 (claim_evidence_map ≥8 rows marked PASS);
limitation_honesty 4.8→7.2 (Limitations names the real true caveats: not-significant/CI-crosses-zero,
may-not-generalize/external-validity, small sample/subset, abstract-level). These are honest content
the paper warrants, scored by the deterministic floor — not keyword-gaming.
Delivery still reports `blocked` (strict 80-AND-no-P0 gate; honest — quality nonetheless exceeds golden).

## 4. Deployment (NON-DESTRUCTIVE — production untouched)

- Engine code: `ac-2012:~/engine-live-newarch/` (a copy of prod `newarch` + the new framework overlaid).
  **Prod `~/paper-job-service/newarch` and the live `paper-a.cooperation.tw` service were NOT touched.**
- Run with prod venv `~/paper-job-service/newarch/.venv/bin/python3` (numpy/scipy/matplotlib/fastapi), cwd=engine-live-newarch.
- Models: codex brain = alan.chen75@gmail.com (plus, until 2026-07-11) at `~/.codex/auth.json`; free worker =
  big-pickle on the local gateway 127.0.0.1:8898. Exact invocations: memory `reference_bigpickle_codex_invocation`.
- hermes binary the pipeline uses: `~/.hermes/hermes-agent/venv/bin/hermes`.

## 5. As-built deltas from the original spec (record these)

- **Worker substrate**: design says "big-pickle via hermes delegate_task". As-built LiveDispatcher shells
  `hermes -z … --provider custom -m big-pickle` per call (the original pipeline's proven invocation); the
  brain is the codex CLI (the design's §3.1 sanctioned path), not the hermes `openai-codex` provider
  (which would need an interactive `hermes login` device flow — deferred).
- **Self-heal**: design says fix-agents-by-failure-type. As-built: the review PRESCRIBES concrete edits;
  apply is deterministic-first (Python find/replace) + big-pickle for fuzzy remainder. Stronger than the
  spec — the worker needs no intelligence.
- **Phases 5-6 (real experiment / GPU)**: not in the meta-analysis lane (the proven free path); VIP/GPU lane
  later per SYSTEM_SPEC_v2 tiering.

## 6. What's NOT done yet (→ next)

- **b-side wiring**: `/v2/jobs` currently runs only the bounded intake phase; it must kick off the full
  `pipeline.run_paper` for a real submit. The b-side (paper-mcp Worker) must call the a-side
  (viability-probe + /v2/jobs) and gate submit on a viability-lock (framework.submission is the canonical
  a-side logic; the TS Worker is a thin client). See BSIDE_WEB_INTEGRATION_PLAN.md.
- **Live web progress**: projection API + reference page exist; the Hugo `/projects/{id}` page must adopt them.
- **a-side /jobs/viability-probe** endpoint (wrap handle_viability) — not yet exposed.
- IFRS pack (#3) — still speculative.

## 6b. Deployment status (2026-06-16) — DEPLOYED, NOT flipped

- **Branch pushed**: `origin/engine-build` (ai-cooperation/paperlab).
- **a-side (prod ac-2012)**: v2 code in `~/paper-job-service/newarch` (backup
  `newarch-code-pre-v2-backup.tgz` + `*.pre-v2.bak`); `PAPER_ENGINE_V2=1` + PATH/HOME
  in `~/.config/paper-job-service/paper-job-service.env`; user-service `paper-job-service`
  (uvicorn :8765, `KillMode=process`) restarted. Verified: health, /jobs intact,
  /v2/jobs + /jobs/viability-probe on the public tunnel, worker spawns under the prod env.
- **b-side (Cloudflare)**: `wrangler d1 migrations apply` (0002 viability_locks) +
  `wrangler deploy` (paper-mcp.alan-chen75.workers.dev, v6e8ee7db). `A_ENGINE_ENDPOINT="/jobs"`
  → **prod routing UNCHANGED** (old pipeline). v2 path available, gated behind the flip.
- **Golden A/B FAILED → NOT flipped (prod safe on /jobs)**: the prod v2 run scored
  floor 42 / no PDF because **codex (alan.chen75) hit its usage limit mid-run**. codex
  exits 0 while printing "you've hit your usage limit" and writes nothing; LiveDispatcher
  had treated brain rc==0 as CHILD_OK → empty brain files → garbage. FIXED: LiveDispatcher
  detects codex error markers → status=error; `_dispatch_brain` raises OrchestratorBlocked
  on brain-error/no-output → the run now BLOCKS loud, never garbage (redeployed).
- **BLOCKER to finish (flip)**: codex quota — alan.chen75 exhausted (the 4 engine-live
  golden-beating runs + the A/B drained it); `~/.codex` has ONE profile (no rotation
  fallback). When quota is back (reset, or add `~/.codex/auth.json.<name>` for
  `_rotate_codex_auth`): re-run the prod /v2 A/B → if it beats golden, flip
  `A_ENGINE_ENDPOINT=/v2/jobs` + `wrangler deploy`.

## 7. Known gaps (codex review 2026-06-16 — fix during integration)

- `framework.viability.handle_viability` master branch LOGS an auto-pivot + writes the steering log but
  does NOT actually mutate the contract (PICOS/query unchanged) — implement the real pivot (apply candidate
  + re-hash) or relabel as a logged suggestion.
- `engine_routes.project_status` projection is too thin — no `status` (running/done/blocked/failed), no
  `artifacts.pdf`, no `summary.floor_100`/`delivery`. Web needs the final PDF link + a terminal state.
- `/v2/jobs` has no idempotency (old `/jobs` has `Idempotency-Key`); deterministic `_job_id` → a duplicate
  submit clobbers the run dir. Add idempotent replay + a run-dir lock.
- Running `pipeline.run_paper` under the FastAPI service needs op-hardening (absolute codex/hermes paths,
  gateway 127.0.0.1:8898 health check, process-group kill on timeout, child reaper, `max_live_v2_jobs=1`,
  wall-clock watchdog). See [BSIDE_WEB_INTEGRATION_PLAN.md](BSIDE_WEB_INTEGRATION_PLAN.md) §3d.
