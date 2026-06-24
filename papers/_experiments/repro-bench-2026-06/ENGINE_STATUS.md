# Engine Status — as-built (a-side general engine)

> Snapshot 2026-06-16. The domain-agnostic Hermes+Skill research engine (a-side) is
> BUILT, TESTED, and LIVE-VALIDATED on ac-2012 — it produces a real paper that BEATS
> the golden baseline. This file is the single source of truth for "what exists now".
> Companions: [ENGINE_GENERAL_SPEC.md](ENGINE_GENERAL_SPEC.md) (PRD), [ENGINE_BUILD_PLAN.md](ENGINE_BUILD_PLAN.md)
> (TDD phases + status), [HERMES_NATIVE_ORCHESTRATOR_DESIGN.md](HERMES_NATIVE_ORCHESTRATOR_DESIGN.md)
> (design), [BSIDE_WEB_INTEGRATION_PLAN.md](BSIDE_WEB_INTEGRATION_PLAN.md) (next: wire b-side + web).

## 0. Engine v3 rebuild status (2026-06-24)

Engine v3 now exists beside the proven v2 stack under `newarch/engine_v3/`. It is a
paper-first rebuild of the intended Hermes+Skill architecture, with a generic core seam
kept separate from `PaperPack`.

Implemented and locally verified:

- Core contracts, dossier store, generic gates, runtime protocol, orchestrator, and mock runtime.
- `PaperPack` wrapper over existing deterministic v2 paper assets, with pack-declared skills and gates A/E/B/C/D/F/R/Z.
- `CodexCliRuntime` plus output verification and provider-failure classification.
- `HermesCodexRuntime` seam with injectable runner and runtime delegation records.
- Full paper pipeline phases: data, gap, structure, write, claim_evidence, render_gates, review_heal, format_repair.
- `/v3` HTTP routes: health, capabilities, contract schema, viability-probe, authenticated submit, status, artifact download.
- POST auth, idempotency-key replay/conflict, per-job creation locks, failed-job dossier state, max-live-job cap.
- b-side `paper-mcp` routing support for `A_ENGINE_ENDPOINT="/v3/jobs"` with v2 rollback preserved.
- Status projection now exposes project-page fields: `research_plan`, `b_gap`, `a_gap`, `tier`, `summary`, and PDF artifact URL.

Latest local verification:

```bash
cd papers/_experiments/repro-bench-2026-06
/Users/user/projects/ai-paper-workshop/.venv/bin/python3.9 -m pytest \
  newarch/tests/test_engine_v3_core.py \
  newarch/tests/test_engine_v3_paper_pack.py \
  newarch/tests/test_engine_v3_codex_runtime.py \
  newarch/tests/test_engine_v3_hermes_runtime.py \
  newarch/tests/test_engine_v3_runtime_config.py \
  newarch/tests/test_engine_v3_paper_pipeline.py \
  newarch/tests/test_engine_v3_http.py -q
# 48 passed

cd /Users/user/projects/ai-paper-workshop/paper-mcp
node --test test/engine-routes.test.mjs
# 4 passed
node node_modules/typescript/bin/tsc --noEmit
# pass
```

Isolated ac-2012 smoke, not production-mounted:

```text
Remote copy: ac-2012:~/engine-v3-smoke-ec8058b0
Command shape: PAPER_ENGINE_V3=1 PAPER_ENGINE_V3_TOKEN=smoke-token PAPER_ENGINE_V3_RUNTIME=mock
               PAPER_JOBS_DIR=$PWD/jobs-v3-smoke uvicorn http_app:app --host 127.0.0.1 --port 8897

GET  /v3/health                 -> HTTP 200
GET  /v3/capabilities           -> HTTP 200
POST /v3/jobs without token     -> HTTP 401
POST /v3/jobs/viability-probe   -> HTTP 200 with Bearer smoke-token
```

Not yet claimed complete:

- Production a-side deployment completed on ac-2012 for `/v3` routes; `paper-mcp` Worker deploy has not been performed.
- Production `paper-a.cooperation.tw` now returns HTTP 200 for `/v3/health` and `/v3/capabilities`.
- No live v3 golden A/B score has replaced the v2 live golden proof below.

Production deployment smoke (2026-06-24):

```text
Backup timestamp: 20260624-155353
Code deployed to production newarch from local HEAD ca0cfd0a; latest code change in that deploy was ec8058b0.
Env enabled: PAPER_ENGINE_V3=1, PAPER_ENGINE_V3_TOKEN generated on host, PAPER_ENGINE_V3_MAX_LIVE_JOBS=1.
Service: systemctl --user restart paper-job-service -> active.

Localhost checks on ac-2012:
GET  /health                    -> HTTP 200
GET  /v3/health                 -> HTTP 200
GET  /v3/capabilities           -> HTTP 200
POST /v3/jobs missing token     -> HTTP 401
POST /v3/jobs invalid token     -> HTTP 403
POST /v3/jobs/viability-probe   -> HTTP 200 with host-side bearer token
POST /jobs/dry-run              -> HTTP 200

Public tunnel checks:
GET /v3/health                  -> HTTP 200
GET /v3/capabilities            -> HTTP 200
```

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

## 6c. Golden A/B re-run (2026-06-16, codex quota restored) — content beats golden, fig-crossref defect found+fixed, STILL not flipped

- The fail-loud fix VERIFIED in prod: the prior codex-exhausted run shows
  `status=failed`, blocker "brain unavailable at phase3_gap: codex unavailable: …usage
  limit", floor=null, no PDF — clean block, zero garbage (archived
  `jobs/v2_2948a09a83a9.failed-codexquota-20260616`).
- **Re-run end-to-end (all 7 phases)** through prod `/v2/jobs`: `golden_proof` →
  **floor 68.3 > golden 62.2 (+6.1), review 78.0 > golden 57.1 (+20.9), content p0=0**
  (`blocked_review.json`: p0_count=0, floor_failed=False). The new engine genuinely
  produces a better paper than the golden baseline.
- **BUT delivery correctly BLOCKED** — `delivery_audit.json` verdict=blocked,
  **p0_count=1**: `RQ_CROSSREF` "10 broken table/figure cross-references in the PDF".
  Confirmed in the rendered PDF text: `?@fig-forest` ×6 + `?@fig-prisma` ×4 (a reader
  sees "?@fig-forest", not "Figure 1"). The strict gate did its job — refused to ship.
- **Root cause** (`tables.py inject_figures`): it placed each figure float "right after
  its first @ref". forest/prisma are first referenced in the `## Abstract` (before the
  first level-1 `# ` heading) → the `{#fig-}` float landed in front matter, where Quarto
  does NOT register crossref floats → every ref renders `?@fig-`. fig-method (first ref
  in the body) was fine.
- **FIXED via the architecture** (codex prescribed → big-pickle executed → I verified):
  inject_figures now places the float after the first @ref AT/AFTER the first body
  heading (abstract-only refs fall back to right after the first `# ` heading).
  Deterministically verified WITHOUT a full rerun: fixed injector on the buggy QMD →
  floats move to the body → real Quarto render → **broken `?@` markers 10 → 0**, figures
  resolve as Figure 1/2/3. Mirrored to source + regression test
  (`test_inject_figures_places_float_in_body_not_abstract`), 23 gate tests pass.
- **NOT flipped** (user: only-fix-no-rerun, save codex quota): the fix is committed but
  prod `tables.py` is unchanged. Flip still waits on a CLEAN prod /v2 rerun (redeploy the
  fixed pack → rerun → expect delivery=pass, floor>62.2 → flip `A_ENGINE_ENDPOINT`).

## 6d. FLIPPED — production cutover (2026-06-16) — `/v2/jobs` is now the live engine

- **a-side**: the fixed pack (`tables.py` body-placement, `format_repair.py`, `pipeline.py`
  Phase 9b, `engine_routes.py` `/v2/jobs/{id}/paper` download) deployed to prod
  `~/paper-job-service/newarch` (backups `*.pre-figfix-*` / `*.pre-fmtrepair-*` /
  `*.pre-paper-*`), service restarted (no in-flight job). Public tunnel verified:
  `/v2/jobs/{id}/status` 200, `/v2/jobs/{id}/paper` 200 application/pdf 303 KB.
- **CLEAN prod /v2 A/B (the gate)**: end-to-end (8 phases incl. format_repair) →
  **floor 70.8 > 62.2, review 82 > 57.1, delivery=`pass`, delivery_audit p0=0/p1=0,
  0 broken `?@` in the PDF** (`format_repair.json`: crossref_ok, repaired=false — the
  by-construction fix means the first render is already clean). The crossref defect that
  blocked the previous A/B is gone.
- **b-side FLIP**: `A_ENGINE_ENDPOINT` `/jobs` → `/v2/jobs` (wrangler.jsonc) + `wrangler
  deploy` (paper-mcp.alan-chen75.workers.dev, version 4c39708e). Production submit now
  routes to the new engine. `submit_to_pipeline` hardened: if no explicit viability-lock,
  it AUTO-PROBES inline (a flip must not refuse a viable contract just because the grill
  didn't pre-probe; non-viable is still refused).
- **web**: live progress page `/project/?status=<url>` (Hugo, polls the public a-side
  projection every 5s; research plan / gap / tier / phase timeline / floor+delivery+PDF
  download); `/projects/` "查即時進度" links to it. Deploys from `main` (GitHub Pages).
- **Old `/jobs` pipeline stays available** (instant rollback: set `A_ENGINE_ENDPOINT`
  back to `/jobs` + redeploy).

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
- **Self-heal loop was blind to RENDER quality** (why the fig-crossref defect surfaced only at the terminal
  gate, 2026-06-16) — NOW ADDRESSED. The 3-round self-heal review scores the QMD **source**
  (prose/claims/numbers); a broken crossref is invisible there (both the `@fig-forest` ref AND the
  `{#fig-forest}` label are present), it only appears when Quarto COMPILES the PDF. Previously the ONLY step
  that compiled + inspected the PDF was the terminal `delivery_audit`. **Fix shipped (commit, engine-build):**
  (1) the root cause is fixed BY-CONSTRUCTION — `tables.inject_figures` now places floats in the body, so the
  defect does not occur; (2) a minimal **format-repair verify stage** (`format_repair.py`, Phase 9b
  `format_repair` after review_heal) renders the PDF, verifies the figure cross-references resolve, and
  re-renders AT MOST ONCE; (3) the review judgment now also reads the compiled-PDF crossref signal
  (`broken_crossrefs`) so it checks the deliverable, not just the source. **Deliberately minimal — NOT a
  stack of mechanical auto-repairs** (per the 2026-06-16 steer "不可以用太多機械式審查的腳本，會修改不完":
  a pile of auto-repair scripts never converges). It owns exactly one render fact (do the figure crossrefs
  resolve) and reports honestly if a regression survives the single re-render. E2E-verified on ac-2012
  (buggy run copy → 9 broken `?@` → 0; repaired=false because by-construction already clears it). Full live
  convergence in the running pipeline is confirmed at the next prod /v2 rerun.
