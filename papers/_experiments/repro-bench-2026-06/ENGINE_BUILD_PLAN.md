# Engine Build Plan — TDD-driven task list

> Status: planning, 2026-06-15. Companion to [ENGINE_GENERAL_SPEC.md](ENGINE_GENERAL_SPEC.md) +
> [HERMES_NATIVE_ORCHESTRATOR_DESIGN.md](HERMES_NATIVE_ORCHESTRATOR_DESIGN.md).
> **TDD is the process** (owner): every task names its **test FIRST** (the RED test that defines
> "done"), then the minimal implementation to GREEN, then refactor. No task is "done" without its test.

## Principles + coverage
- **Test-first, always.** RED (failing test encoding the spec) → GREEN (minimal impl) → refactor.
- **Coverage target ≥ 80 %** on the framework + the gates (the deterministic core *is* the value, so it
  is the most-tested). Reasoning quality is checked by e2e + golden review-score, not unit coverage.
- **Stacks:** a-side Python → `pytest`; b-side Worker (TS) → `vitest` + Miniflare; e2e → a harness
  driving the FastAPI job service against frozen fixtures.
- **No network in unit/integration tests** — all external data is fixtured (frozen corpus, recorded
  MCP/HTTP responses). Network only in a gated nightly e2e.
- **Reasoning quality = golden-score + rubric-assertions** (codex fix — golden-score alone is a cop-out):
  e2e golden review-score AND structured-artifact assertions: gap-matrix completeness, claim-evidence /
  findings coverage, contradiction detection, source-anchoring (every quantitative claim cited).
- **Thin-handoff is a tested invariant** (GENERAL_SPEC §2.3): no fixture/contract passes dense numbers
  through a chat.ai tool call; tests assert the handoff contract is number-free and the a-side owns the
  numbers.

## Fixtures (build in Phase 0, reused everywhere)
| Fixture | What | Used by |
|---|---|---|
| `corpus_exercise.json` | frozen exercise-depression `_corpus_cache.json` (2400 works) | extraction, meta-pool, viability |
| `corpus_mindfulness_thin.json` | frozen thin corpus (6 poolable) | viability non-viable + tier |
| `contract_paper.json` / `_insurance` / `_ifrs` | sample contracts per domain | schema, contract-derivation |
| `golden_paper/` | the exercise-depression run (qmd + real_results + figures + score 56/75) | regression baseline, render, gates |
| `overclaim_samples.md` | known overclaims (ICS "1200 configs", "≥90% when 100%") | Gate B |
| `dup_figure.qmd` | a qmd with each figure embedded twice | figure dedup |
| `insurance_kb_small/` | small insurance KB: stale + conflicting docs, known findings | insurance pack viability, evidence, gates |
| `insurance_gatefail/` | a thin-body / orphan-footnote / uncited-number report | insurance `gate_registry` |
| `contract_thin_handoff.json` | a grill→contract with NO dense numbers | thin-handoff invariant |

---

> **RE-SEQUENCED per codex review (2026-06-15):** the **DomainPack interface (was Phase 11) moves to
> Phase 1** — design the pack contract FIRST from the two real domains (paper + insurance,
> ENGINE_GENERAL_SPEC §2.2), then build the paper pack THROUGH the interface. Otherwise the framework
> crystallises around paperlab. And the **b-side + frontend production work (Phases 8–9) moves to AFTER
> the engine golden-proof (Phase 10)**, or behind a feature flag + shadow mode — never churn production
> around an unproven orchestrator. Phase numbers below keep their labels; the **dependency order at the
> bottom is authoritative**.

## Phase 0 — Test harness + fixtures  *(foundation; nothing else starts without it)*
- **RED:** a trivial `pytest`/`vitest` run is wired in CI and a coverage report prints. Fixtures above
  exist and load.
- **GREEN:** harness + fixtures committed; `make test` runs Python + TS + reports coverage.

## Phase 1 — Root-cause the extraction inconsistency  *(BLOCKING — it is the real score suppressor)*
Symptom: same corpus + PICOS, three code paths report different poolable-k — phase0 **probe = 8**,
meta lane **= 3** (pooled log-ratio), my direct `synthesis.extract` test **= 23**.
- **RED:** `test_extraction_consistency` — runs `meta_analysis.run`, `phase0` probe, and a direct
  `screen_picos+extract` over `corpus_exercise.json` with the SAME picos; asserts they agree on
  poolable-k per scale. (Fails today.)
- Investigate the hypotheses: (a) probe re-collects fresh vs lane uses seeded cache → different corpus;
  (b) `meta_analysis.run` de-dups to one-effect-per-study while the direct test counts all; (c)
  `require_any` applied in one path not another; (d) by-scale split (SMD k=8 vs log-ratio k=3 are
  different strata, not a bug — confirm).
- **GREEN:** one authoritative poolable-k per (corpus, picos); the three paths agree (or the
  difference is documented + intended). Re-score `golden_paper` — expect evidence_validity to rise if
  the lane was under-extracting.

## Phase 2 — `paperctl` (paper-pack deterministic tools as CLI) + golden tests
- **RED:** `test_paperctl_golden` — each command (`refs`, `data meta-analysis`, `figures`, `tables`,
  `render`, `gate phase2|b|c|d|e|f`, `review compile`, `provenance`) reproduces the `golden_paper`
  outputs byte-for-byte (or within a declared tolerance for floats).
- **GREEN:** extract the deterministic functions from `paper_driver.py`/modules into a `paperctl` CLI;
  pin with the golden tests. (Pure refactor; zero behavior change.)

## Phase 3 — Framework: Hermes orchestrator (codex brain + delegate big-pickle)  *(補完整 hermes-delegate 版)*
Prereq: one-time `hermes auth` to store codex creds (the `openai-codex` provider).
- **RED:** `test_hermes_smoke` — load the skill bundle; `delegate_task` one worker → returns `CHILD_OK`;
  orchestrator writes `dossier.json` + a checkpoint; **fresh-resume from dossier** continues from the
  checkpoint without replaying history.
- **GREEN:** build the Hermes-native orchestrator: parent = codex (`openai-codex`), workers = big-pickle
  via `delegate_task` (parent-level fan-out), skill bundle loaded, Python control-plane wrapper owns
  the state machine + checkpoints, fresh-session resume. Replaces the MVP's monolithic codex calls with
  the delegate fan-out (7 section writers, fix-agents) per §3.1/§3.6 of the design doc.

## Phase 4 — Gates A–F + matrix checks (deterministic core)
- **RED, per gate:** known-pass + known-fail fixtures →
  - Gate A: refs < 35 / DOI real-rate < floor → block.
  - **Gate B:** `overclaim_samples.md` → each overclaim is a P0; independent claim extraction catches an
    *unlisted* claim.
  - Gate C: `dup_figure.qmd` → dedup to exactly one embed (2→1, idempotent); figure number ≠ real_results
    → P0.
  - Gate D: placeholder / under-length / render-fail → block.
  - Gate E: `corpus_mindfulness_thin.json` → value verdict triggers adjust-or-pause (per tier).
  - Gate F: a planted contradiction / cherry-pick → `audit.py` P0.
- **GREEN:** port/keep each gate behind `paperctl gate *`; the wrapper re-runs them independently (a weak
  worker cannot skip a gate). Most exist — this phase *pins them with tests* so they cannot regress.

## Phase 5 — Three-stage review + self-heal
- **RED:** `test_selfheal` — a sub-threshold draft triggers fix-agents-by-failure-type; loop stops at
  no-P0 ∧ floor-not-failed ∧ score ≥ 80, OR 3 rounds then **block + report (no silent pass)**; using the
  exercise fixture, the floor stays flat across rounds (evidence-bound) while the review score rises.
- **GREEN:** implement the staged review + self-heal on the framework (strong-brain reviewers ≠ writer;
  external = codex CLI / copilot; deterministic floor is the hard cross-check, not certification).

## Phase 6 — Viability probe + tier interaction
- **RED:** `test_viability` — `corpus_mindfulness_thin` → `non_viable` verdict + ≥1 `candidate_pivot` +
  `contract_hash`; `level=master` → auto-pivot + a `research_steering_log` written; `level=phd` →
  `paused_for_user` (no auto-run).
- **GREEN:** add a-side `/jobs/viability-probe` wrapping `phase0_calibration.run_phase0` (returns the
  lockable verdict); add the `level` branch + `paused_for_user` state + the steering log (§5.1/§5.2).

## Phase 7 — HTTP job-service integration (orchestrator replaces the old pipeline)  *(integration spec — was missing)*
- **RED:** `test_http_orchestrator` — `POST /jobs` (paper contract) routes to the **new** orchestrator
  (not `paper_driver.py`'s old loop); `GET /jobs/{id}/status` returns the **dossier projection** (phase,
  b-gap, a-gap, tier, progress), not just coarse status.
- **GREEN:** wire the orchestrator into the FastAPI service (`http_app.py`); the status endpoint reads
  the dossier; old pipeline retired or behind a flag for A/B.

## Phase 8 — b-side viability-lock + deterministic contract derivation (Worker)
- **RED (vitest):** `submit_to_pipeline` without an approved viability-lock → refused; a contract is
  derived deterministically from structured `meta_plan` grill answers (not chat prose); changing
  title/PICOS after approval → `contract_hash` changes → re-probe required.
- **GREEN:** add `probe_research_viability` (calls a-side `/jobs/viability-probe`), store
  `viability_lock`, `deriveResearchContractFromSession()`, the project state machine, and the submit
  gate; demote the giant `submit_to_pipeline` instruction blob (§3.1 grill-controllability).

## Phase 9 — Live project page (detail page + poll + dossier projection)
- **RED:** `test_project_detail` — `/projects/{id}` renders and polls `/api/projects/:id`, which returns
  live a-side status; the page shows the 4 blocks (research plan, b-gap, a-gap, tier decision) +
  timeline; dynamic, **no Hugo rebuild**.
- **GREEN:** create the `/projects/{id}` detail template (poll every 5 s); `GET /api/projects/:id`
  fetches fresh a-side status; dossier projection feeds the 4 blocks; email-notify on completion (§5.3).

## Phase 10 — Run the full skill on Hermes + fine-tune skills
- **RED:** `test_golden_paper_on_hermes` — running the full `paper-draft` bundle via Hermes on the
  frozen corpus reproduces ≥ the golden review score (75) and PASSES all gates. (Skills were written for
  Claude Code; expect drift.)
- **GREEN:** run, observe where skills under-perform on Hermes, **fine-tune the skill bundle**, iterate
  until the golden bar is met. (Owner: "跑完整 skill 再微調 skill".)

## Phase 1\* — DomainPack interface (FIRST, per codex; was Phase 11)  *(design the seam before paper hardens)*
- **RED:** `test_pack_interface` — the `DomainPack` contract (ENGINE_GENERAL_SPEC §2.2) is satisfied by
  BOTH the paper pack AND a **real-ish insurance pack** loaded from `insurance_kb_small/` (NOT a stub),
  proving the seam holds across the two real domains, with zero `import paper_*` / `import insurance_*`
  in the framework.
- **GREEN:** define the `DomainPack` interface from paper + insurance; the framework calls packs
  generically; build the paper pack THROUGH it from Phase 2 on. IFRS is a later pack, not a framework
  change.

---

## Dependency order (authoritative — codex-corrected 2026-06-15)
`harness+fixtures (P0)` → **`DomainPack interface from paper+insurance (P1*, was P11)`** →
`extraction-bug root-cause (P1)` → `paperctl THROUGH the interface (P2)` → `hermes orchestrator (P3)` →
(`gates (P4)`, `review+self-heal (P5)`) → `viability+tier (P6)` → `HTTP integration (P7)` →
`skill fine-tune + golden Hermes proof (P10)` → **then, behind a feature-flag + shadow mode:**
`b-side viability-lock (P8)` + `frontend live page (P9)`.
Two rules: (1) design the seam from two real domains BEFORE the deterministic core hardens around paper;
(2) prove the engine on golden runs BEFORE touching the live paperlab worker/site.

## Planning artifacts to author with the build (codex — currently missing)
OpenAPI contract (a-side `/jobs/*` + `/jobs/viability-probe`); state-machine table (project + viability
+ tier states); JSON schemas (dossier core, worker packet, gate report, checkpoint manifest, ViabilityVerdict);
error taxonomy; observability/runbook; rollout/rollback plan (incl. the old-pipeline feature flag);
security/privacy model (insurance client data, confidentiality); **DomainPack authoring guide**;
evaluator/rubric spec (the reasoning rubric-assertions). Author each alongside the phase that needs it.

## Open questions — ANSWERED by codex review 2026-06-15 (kept for the record)
1. Is the framework/pack split (§2.2 interface) the right seam, or will insurance/IFRS need framework
   changes we haven't anticipated?
2. Phase 3: is `hermes delegate_task` (depth-2, no-child-delegate) sufficient for 7 section writers +
   fix-agents at parent level, or does the wrapper need its own fan-out for some roles?
3. Phase 7: retire the old pipeline outright, or keep it behind a flag as an A/B oracle for regression?
4. TDD for the *reasoning* layer (gap/writing quality) is golden-score-based, not unit — is that the
   right line, or should we add rubric-assertion tests on the gap matrix / claim-evidence map?
