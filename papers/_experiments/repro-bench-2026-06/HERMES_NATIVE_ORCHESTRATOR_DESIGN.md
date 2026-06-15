# Hermes-Native Orchestrator — Architecture B Design

> Status: **owner-aligned spec + codex implementation design + codex critical-review applied + all
> owner decisions resolved (2026-06-14)**, pending build go-ahead. Decisions: brain = flat-rate
> subscription codex (cost not a gate); workers = big-pickle; Gate E = check early + adjust-and-log
> (never hard-block); external-reviewer outage = retry (no score → no output).
>
> **▶ 2026-06-15 — substrate decision LOCKED: Hermes + Skill (codex brain), built as a GENERAL engine.**
> This doc is now the **domain-agnostic framework + the paper domain-pack** detail under
> [ENGINE_GENERAL_SPEC.md](ENGINE_GENERAL_SPEC.md) (PRD/architecture for the general engine reused by
> paperlab / insurance / IFRS). The codex-brain MVP proved the recipe; it is rebuilt ON Hermes (codex
> as the `openai-codex` parent model + big-pickle `delegate_task` workers) so the same orchestration
> framework serves every domain by swapping the pack. Build sequence + tests: [ENGINE_BUILD_PLAN.md](ENGINE_BUILD_PLAN.md).
> Supersedes the `newarch/paper_driver.py` assembly-line orchestration. Companion to
> [SYSTEM_SPEC_v2.md](SYSTEM_SPEC_v2.md) (a/b boundaries) and [WS3_BWORKER_DESIGN.md](WS3_BWORKER_DESIGN.md).

> **Feasibility — smoke-verified on ac-2012 (2026-06-14):** hermes v0.15.1 runs; big-pickle worker via
> hermes ✓ (`SMOKE_BIGPICKLE_OK`); **`delegate_task` parent→child fan-out ✓** (`CHILD_OK` — the core
> primitive); all 11 deterministic assets present (→ `paperctl` is a pure refactor). Codex brain
> available two ways: hermes `openai-codex` provider (one-time `hermes auth` needed — currently "No
> Codex credentials stored") OR the already-authed codex CLI (proven all session). Two trivial setup
> items: `hermes auth` (or use the CLI), and scp the full 28-skill bundle (7/28 currently on ac-2012).
> **Executable: confirmed.** "Hits 80" is what the proof slice (§4 steps 5–7) tests — it cannot be
> known from smokes.

## 1. Problem (why this exists)

The 8 published paperlab cases (~80/100) were produced by **Claude Code running the full
`paper-draft` skill holistically** — one strong agent reads the whole skill, carries reasoning
across phases, uses tools + sub-agents, runs real experiments, iterates, and self-heals (3-round
loop to score ≥80).

The automated server pipeline (`newarch/paper_driver.py`, ~60/100) runs the **same skill** but as a
**crippled assembly line**: 7 isolated `hermes -z` one-shot subprocess calls, one per phase, "read
only what you need, stop after phase N", files-on-disk as the *only* handoff, phases 5–6 (real
experiments) deleted, Phase 9 self-healing replaced by regex patching.

**The gap is orchestration, not the model** (codex confirmed twice; big-pickle run as a real agent is
fine, run as a form-filler is not). The checkpoint boundary between phases stores *conclusions*
(files), not *reasoning* — a capable model cannot use reasoning it never receives.

## 2. Architecture B (owner-aligned)

**The Hermes agent becomes the orchestrator and natively runs the FULL skill end-to-end (the 11
numbered phases 1–11; "Phase 0" viability calibration is a deterministic pre-step), exactly like
Claude Code does.** Python flips from orchestrator to (a) deterministic **tool provider**, (b) **outer
gate enforcer**, and (c) — per the codex review — a deterministic **control-plane state machine** that
owns the checkpoint/gate/work-queue loop while the agent owns the reasoning inside each dispatched
unit (so the parent never has to hold the whole run in context; see §3.3).

> Terminology: "12-phase" is used loosely for the workflow; the skill is numbered 1–11 (+ Phase 0
> pre-step). Use the **phase IDs**, never the count, in code/gates/checkpoints to avoid drift.

Owner decisions (2026-06-14):
1. Hermes + full-skill agent = replicate the 80-pt quality (success criterion).
2. **Model tiering** (refined 2026-06-14): top brain / architect = the owner's **flat-rate
   subscription codex**; delegated workers = free **big-pickle**. **Cost is therefore not a per-paper
   concern — the only acceptance constraint is passing the quality gates.** (This overrides the earlier
   "not the codex CLI" note; reconciled in §3.1 — the Python *wrapper*, not the codex CLI, owns the
   control plane, so codex's brittleness objection no longer applies.)
3. **Scope tiering**: non-GPU topics first (meta-analysis/literature → deterministic meta-pool tool,
   no GPU). GPU real-experiment topics = paid VIP, added later via ac-3090 chaining.

Consistent with the locked a/b architecture: a-side stays "deterministic verification + agentic
generation"; only the *agentic half* changes from "Python calls the model per phase" to "agent runs
the skill". Determinism (DOI, pooling, figures, render, gates) stays in code.

## 3. Implementation design (codex-validated)

### 3.1 Model wiring — brain = subscription codex; workers = big-pickle
**Brain/architect = the owner's flat-rate subscription codex; workers = free big-pickle.** Codex's
original review argued against the codex CLI as orchestrator (it would need a custom scheduler/merge) —
but its OWN later point (§3.3) puts that control plane in the **Python wrapper regardless**. So the
objection dissolves: the wrapper owns the state machine + fan-out + merge + gates; the brain is just
the per-batch reasoner, and that reasoner is the subscription codex. The **dossier** (§3.3/§3.5) is
what gives the per-batch brain its reasoning continuity — so this is NOT the old assembly line (strong
brain + full skill context + dossier handoff + matrix gates, vs the old weak model + bounded prompts +
files-only handoff).

**Wiring — RESOLVED (verified 2026-06-14):** hermes has a first-class **`openai-codex` provider**
("OpenAI Codex — requires hermes auth"), and **ac-2012 already has the codex CLI (`/usr/bin/codex`) +
codex auth + this provider** (currently `provider: custom` → big-pickle). So the clean **hermes-parent
with `provider: openai-codex`** as brain + `delegate_task` big-pickle workers (the original option a) is
available — no codex-CLI-shell fallback needed. The codex auth is ChatGPT **OAuth, not an API key**
(`OPENAI_API_KEY:false`, oauth tokens present); the only micro-detail to confirm when wiring is that
the `openai-codex` provider draws on that **flat OAuth subscription** (not a per-token key), which
preserves the "cost is not a gate" premise. Fallback if ever needed: wrapper invokes the codex CLI
(also subscription-OAuth, proven working). Workers = big-pickle; control plane = the Python wrapper.

Children CANNOT delegate (hermes depth-2, delegate stripped). So **fan-out is owned at the top** (by
the wrapper / parent): phase workers, section writers, reviewers, fix-agents are all top-level
dispatches — never nested.

```
paper_orchestrator.py  (wrapper = control plane: state machine, fan-out, gates, checkpoints)
  brain (reasoning per batch): subscription codex  [hermes-parent model OR wrapper-invoked codex CLI]
  skills: full 28-skill paper-draft bundle (loaded by the brain / workers)
  tools: terminal/files/web + deterministic paperctl tools
  workers: hermes -z -m big-pickle  (fresh task_id, no delegate/memory/execute_code)
```
Every delegation prompt states: you are a bounded worker; you cannot delegate; read only the files in
this slice; write only your declared output files; return a concise completion report (changed files +
unresolved blockers).

**Worker classes (codex review — NOT all big-pickle; reviewers MUST be strong, or they miss
conceptual flaws — and the parent must never judge its own run):**

| Class | Role | Model | Write scope |
|---|---|---|---|
| drafter | phase workers, 7 section writers | big-pickle | `sections/*.md` (own file only) |
| fixer | prose / figure / table / citation fix-agents | big-pickle | the one artifact assigned |
| reviewer | Stage 1–3 review **judgment** | **strong (codex-class), isolated child ≠ writer ≠ parent** | review report only (never edits the paper) |
| external | Stage 4 independent peer review | **codex CLI + copilot** (models ≠ orchestrator) | review report only |

Each delegation prompt names its class + the model override for that class. Reviewer/external classes
are read-only on the manuscript (they emit findings; fixers apply them) — this enforces "never grade
your own homework".

### 3.2 Run the full skill natively — **the COMPLETE 28-skill bundle** (not just paper-draft)
paper-draft is the **orchestrator** skill; it invokes **27 sub-skills** across the 11 phases. The
WHOLE bundle (284 KB, all present at `~/.claude/skills/`, verified 2026-06-14) must be copied into the
hermes skills dir, or the quality cannot be reproduced. Bundle by phase:

| Phase | Skills invoked |
|---|---|
| 1 Concept | innovation-positioning, journal-fit |
| 2 Literature | doi-verifier, bib-manager, literature-synthesis |
| 3 Positioning | literature-synthesis, innovation-positioning |
| 4 Structure | research-contract, figure-design |
| 5 Exp design *(VIP/GPU)* | experiment-validator, baseline-min-set, ablation-min-proof |
| 6 Exp exec *(VIP/GPU)* | experiment-tracker, gpu-monitor |
| 7 Results | qmd-writer, figure-table-checker, statistical-validation, simulated-data *(MVP)*, figure-design |
| 8 Writing | academic-writing, qmd-writer, journal-templates, paper-logic-audit *(Gate F)* |
| 9 Review (St 0–4 + self-heal) | doi-verifier, mvp-gatekeeper, paper-review-skill, elite-reviewer-audit, paper-logic-audit, llm-peer-review, research-verification, academic-writing |
| 10 Submission | submission-bundle, journal-submission, bib-manager |
| 11 Rebuttal | rebuttal-matrix, academic-writing |
| supplementary | research-landscape *(post-Phase 9, knowledge graph)*, paper-delivery-audit, data-preprocessing |

Supporting files to bundle too: **`paper-logic-audit/audit.py`** (7-scan logic audit). Python deps
for `research-landscape`: networkx, plotly, matplotlib, bibtexparser. All other skills are SKILL.md-only.

**Skill vs tool (they coexist, intentionally):** a skill is *judgment/guidance*; a deterministic tool
is *mechanical execution*. Where a skill has a deterministic counterpart, the skill must instruct the
agent to CALL the tool, not hand-roll: doi-verifier→`paperctl refs audit`, figure-design/figure-table-
checker→`paperctl figures`+gate, statistical-validation/simulated-data→meta pooling, paper-logic-audit
→`audit.py`, journal-templates/qmd-writer→`paperctl render`. Pure-guidance skills (academic-writing,
innovation-positioning, literature-synthesis, mvp-gatekeeper, elite-reviewer-audit, …) have no tool —
the agent does the reasoning, guided by them.

**Worker fan-out pattern (drives the delegate_task batches; all parent-level since children can't
delegate):** Phase 2 = up to 5 parallel DOI/literature workers; Phase 7 = 2 (tables / figures);
Phase 8 = **7 parallel section writers** (Methods→Results→Discussion→Related Work→Intro→Conclusion→
Abstract, then a composition pass); Phase 9 = N fix-agents-by-failure-type per self-heal round.

Package the bundle as a hermes skill set under `~/.hermes/skills/` (paper-draft + all 27). Add a
per-run `AGENTS.md` with orchestration invariants only:
run the full skill end-to-end; do not phase-bound; do not skip Phase 3 positioning or Phase 9
Stage 0/1/2; use delegate_task for bounded workers; use deterministic paper tools; maintain
`dossier.json` after every major decision; never claim completion until outer gates pass.

**Guarantee Phase 3 + Phase 9 by making them OUTER-GATED, not agent-discretionary** (the two things
System 2 lost):
- before Phase 4: require `phase3_positioning.md` + `dossier.claims.gaps[≥3]` + differentiation statement.
- before final: require DOI reverify + claim_evidence_map + figure_audit + coherence_audit +
  gate_d_readability + quality_review_log + (score ≥80 OR three logged repair rounds).

### 3.3 Hang strategy (delegation alone is NOT enough — the wrapper owns a control plane)
**The deterministic Python wrapper owns a work-queue / state machine** (checkpoints, gates, which
batch to dispatch next); the hermes parent only *decides the content of the next batch* and reasons
inside it. "Lean context + watchdog" alone is necessary but NOT sufficient (codex review): a parent
managing literature workers + figures + 7 writers + reviewers + fix-agents can blow context through
summaries alone — the state machine *outside* the agent is what bounds it. This is the line that keeps
B from sliding back into the assembly line: Python owns the *loop*, the agent owns the *thinking*.

Keep in **live orchestrator context**: current phase, gate state, latest delegation summaries, open
decisions, next 1–3 actions. Push everything else to **dossier files**: full contract, phase outputs,
refs/metadata, DOI reports, real_results summaries, claim-evidence map, review findings, revision
history, worker records, gate failures.

Checkpoints: after phase2-refs / phase3-positioning / phase4-structure / meta-analysis-real-results /
phase8-qmd / render / each phase9-round. At each: orchestrator writes `dossier.json` +
`orchestrator_checkpoint.md` (exact next action); **wrapper stops the process before compaction
pressure**; wrapper resumes in a **fresh session seeded from `dossier.json` + `orchestrator_checkpoint.md`**
— NOT `hermes --continue` as the primary path (verify its behavior first; if it reloads full history
the watchdog only *delays* the hang; use `--continue` only as a proven-safe optimization). Checkpoints
write an **atomic manifest with artifact hashes**; all gates are **idempotent** and recover from
partial worker writes.

**Hard watchdog: force checkpoint + restart at ~60–65% context — do not wait for hermes
auto-compaction.** Backstop (required before VIP/GPU): fix the hermes compaction bug — on session_id
rotation, migrate/alias file/terminal/tool cache from old→new session_id for the same task_id
(lookup order: current session → active task_id cache → previous-session alias); add SQLite
busy_timeout + a regression test (long session → compaction → file read → terminal call → no deadlock).

### 3.4 Deterministic tools — CLI first (not MCP)
Expose existing deterministic assets as a stable CLI `paperctl` (simpler/auditable than MCP; hermes
already has terminal):
```
paperctl refs build-from-dois|audit --run-dir RUN
paperctl data meta-analysis --run-dir RUN
paperctl figures meta --run-dir RUN
paperctl tables inject --run-dir RUN
paperctl render --run-dir RUN
paperctl gate phase2|phase3|phase8|phase9|final --run-dir RUN
paperctl review compile --run-dir RUN
paperctl provenance --run-dir RUN
```
Mandatory assets behind it: DOI (doi_audit, build_refs_from_doi_list, doi_gate); meta
(phase0_calibration, meta_analysis, synthesis, corpus_sources, meta_figures); figures/tables
(meta_figures.generate, compile_tikz_figures, tables.inject/inject_figures); render (render_springer,
render_qmd_reportlab, render_pdf); gates/review (consistency_gate, revision_tasks, compile_review,
data_availability_gate, paper_gate plugin).

**Outer enforcement**: when the agent exits / a checkpoint completes → wrapper runs `paperctl gate
current` **independently**. If fail: write `dossier/gate_failures.json`, resume orchestrator with the
exact failures, block final status. If pass: advance checkpoint. The agent may call tools, but the
wrapper re-runs the gates — this is what stops a big-pickle worker from skipping checks.

### 3.5 Dossier schema (`dossier.json`)
> **Framework core + pack extension (codex):** the framework dossier CORE is domain-generic — `run`,
> `status`, `gates`, `delegations`, `revision_loop`, `claims` (generic). The paper-specific fields below
> (`references.bib_count`, `doi_real_rate`, `real_results`, `figures`, `claim_evidence` rows) are the
> **paper pack's typed extension**. Insurance extends with `findings`/`sources`; IFRS with
> `clauses`/`diffs`. The framework never reads pack-extension fields directly — only the pack does.
`schema_version, run{job_id,run_dir,mode,lane,target_journal,language}, contract{topic,
research_question,contribution,data_source,synthesis}, status{phase,checkpoint,blocked,blockers},
claims{research_gaps,contributions,core_claims,claim_evidence}, evidence{references{bib_count,
doi_real_rate,abstract_coverage}, real_results{path,summary}, figures, tables}, artifacts{...},
gates{phase2,phase3,phase8,phase9,final}, delegations[{id,task,worker_model,input_slice,outputs,
status}], revision_loop{round,score,target_score,remaining_tasks}`.

**Worker packet** (workers have NO parent history → must be a fully self-contained packet; codex
flagged file-paths + core_claims as too thin → generic prose / starvation): `task_id, role,
worker_class, model, task_goal, relevant_excerpts (verbatim, not just paths), exact_metrics,
citation_mini_bib, claim_evidence_rows (the rows this worker may rely on), no_go_claims (forbidden
overclaims), style_constraints, allowed_files_read[], allowed_files_write[] (isolated output dir),
output_schema, input_artifact_hashes, acceptance_criteria[]`.

### 3.6 Phase 9 — the three-stage review + self-heal (where 60→80 lives)
Two "three-stage" mechanisms must FUSE: the skill's escalating review depth, and the current
pipeline's anti-gaming reviewer cascade + deterministic floor. Every stage is an **outer-enforced
gate**, never agent self-certification.

| Stage | What | Who runs it | Hard gate (wrapper-enforced) |
|---|---|---|---|
| 0 (pre) | DOI reverify + figure check | deterministic `paperctl` | DOI real-rate ≥ floor; figure numbers == real_results |
| 1 MVP | mvp-gatekeeper P0/P1/P2 checklist | deterministic checks + strong-brain triage | **P0 == 0** |
| 2 Review | paper-review-skill 7-dim **+ `floor_score.py`** | strong-brain reviewer (findings) + deterministic floor (cross-check) | floor not-failed **AND** 7-dim ≥ 80/100 |
| 3 Elite | elite-reviewer-audit 12-dim **+ `audit.py`** | strong-brain elite reviewer + deterministic logic-audit | **retirement risk < 30%; audit.py P0 == 0** |
| 4 external | independent peer review | **codex CLI + copilot** (models ≠ orchestrator) | findings feed self-heal (anti self-bias) |

**Anti-gaming principles (why it reaches 80 instead of *claiming* 80) — these are the crux of the
fix:**
1. Review JUDGMENT runs on the **strong brain (codex-class), never big-pickle** — a weak reviewer
   cannot find conceptual flaws (a root cause of the current pipeline's weak review). big-pickle only
   *executes fixes*, it does not *judge*.
2. The system never grades its own homework: reviewer workers are **independent of the section
   writers**, and Stage 4 uses **external models** (codex CLI — exactly the role codex recommended for
   itself — + copilot). `floor_score.py` (1–10, deliberately conservative) + `audit.py` are
   deterministic **blockers / cross-checks, NOT certification** — they can FAIL a paper but do not by
   themselves certify a journal-grade pass (floor_score says exactly this in its own docstring).
   **Normalized score scale:** report everything on **/100** (`floor_score`'s 1–10 maps ×10). PASS at
   Stage 2 = floor not-failed **AND** strong-reviewer 7-dim ≥ 80/100 **AND** Stage-1 P0 = 0.
3. The agent produces rich findings, but PASS is decided by the **deterministic floor + outer
   wrapper**, not by a model saying "looks good".

**Self-heal loop (the thing System 2 deleted):** on any stage fail → orchestrator delegates
fix-agents-**by-failure-type** (big-pickle workers, parent-level batch) with the exact findings as
self-contained dossier task slices → updates dossier → re-runs the FAILED stage. Stop condition:
Stage 1 P0==0 AND Stage 2 floor≥threshold AND Stage 3 risk<30% — OR **3 rounds logged then block +
report** (never a silent pass).

**Existing review assets → tools/workers (preserved, re-orchestrated):** `floor_score.py` →
`paperctl gate phase9` (the hard floor); copilot/codex reviewers → external-reviewer delegations
(Stage 4 independence + codex dual-account rotation already built); `consistency_gate.py` +
`compile_review.py` → `paperctl review compile`; `audit.py` → Stage 3 logic audit; the existing
mechanical "drop hallucinated review tasks" check stays (verify a finding's target text is a real
substring before acting on it).

### 3.7 Matrix-based structured checks (the agent↔determinism interface)
Matrices are how the skill makes checks structured + auditable: every claim / gap / fix / risk is a
ROW that must be FILLED (agent judgment) **and** VERIFIED (deterministically where possible). They are
the clean interface between agent reasoning and the un-gameable gates — and the 60-pt System 2 had
none of them. Each matrix is stored as a **first-class structured table in the dossier**.

| Matrix | Phase/Gate | Columns | How B fills + verifies |
|---|---|---|---|
| **Gap Matrix** | Phase 3 | Gap × Description × Existing Work × Our Approach + Differentiation Statement | agent fills; gate: ≥3 gaps, each Existing-Work cites a real ref (substring vs references.bib), Differentiation present |
| **Claim-Evidence Map (Gate B)** | Phase 7→8 (block before writing) | Claim × Evidence × source-file × valid? × **Exact-Match?** × **N-Support** × **attribution-verb** | **deterministic `paperctl gate claim-evidence`**: numbers exact-match vs real_results JSON; N counted; verb-tier rule; no orphan claim. Any fail = **P0 block** |
| **Gap 4Q** | elite Stage 3 | Q1–Q4 ✅/❌ | strong-brain elite fills; gate: all four pass or logged |
| **Retirement-risk matrix** | elite Stage 3 | risk % + 3 simulated-reviewer objections | strong-brain; gate risk < 30% |
| **Rebuttal Matrix** | Phase 11 | comment × severity × response × section × claim-adjustment | `build_rebuttal_matrix.py` + `verify_rebuttal.py` → tools |
| **Ablation Matrix** | Phase 5 *(VIP/GPU)* | component × removal-effect | experiment lane |

**Central rule:** the agent FILLS rows (judgment: what is the claim, where is the evidence), `paperctl`
VERIFIES rows mechanically where possible, the wrapper ENFORCES. This is the cleanest realization of
"skill guides + tool enforces + can't be gamed".

**Gate B (claim ≤ evidence) is the spine** and is nearly fully mechanical → it MUST be a deterministic
`paperctl gate claim-evidence` that hard-blocks. Its three machine-checkable disciplines:
- **Exact-Match**: every number/range/% in a claim must equal its evidence in real_results JSON
  (claim "≥90%" while actual 100% → fail; fix the claim or the evidence).
- **N-Support**: each inductive claim shows its data-point count; N<3 forces a "sample too small"
  caveat.
- **Attribution-verb tier** (auto-downgrade by N + effect size): N≥10 & p<0.01 → `dominates`/`causes`;
  N∈[3,10] → `correlates with`/`is associated with`; N<3 → `suggests`/`is consistent with` (strong
  causal verbs banned).

**Anti-gaming (codex review): the gate must NOT trust only agent-filled rows.** `paperctl gate
claim-evidence` independently EXTRACTS claims from the actual QMD / section drafts, then checks (a)
every extracted claim has a matrix row — no "unlisted claim" smuggled past the gate — and (b) a
minimum claim coverage per section. A claim the agent forgot to list is itself a P0.

This is the direct antidote to the real overclaim disasters (ICS "1200+ configurations" but most
invalid, "R²=0.94" at n=5; LLM-latency "≥90%" when actually 100%). The dossier's
`claims.claim_evidence` rows therefore carry `exact_match`, `n_support`, and `verb_tier` fields.

### 3.8 Hard-gates table (A–F) — the PAPER PACK's gate set
> **Framework vs pack (ENGINE_GENERAL_SPEC §2.2):** the FRAMEWORK owns the gate *lifecycle* (register →
> run → enforce → block → feed failure back as a dossier task). The concrete gates A–F below are the
> **paper pack's `gate_registry`**, not framework constants. Insurance registers body_too_thin /
> footnote_orphan / uncited_quantitative / single_source; IFRS registers clause-authority / version /
> effective-date / missing-clause. Same lifecycle, different registered gates.

Each gate has a CLI command, inputs, a machine verdict, and a blocking exit code. The agent may
self-check, but the wrapper re-runs these independently and a non-zero exit BLOCKS + feeds the failure
back as a dossier task (codex review: these were implicit / partly missing — Gate C, D, E especially).

| Gate | When | `paperctl` cmd | Checks | Block on |
|---|---|---|---|---|
| **A** contract/refs | after Phase 2 | `gate refs` | contract fields complete; ≥35 bib entries; abstract coverage; DOI real-rate | DOI real-rate < floor, refs < 35 |
| **B** claim ≤ evidence | Phase 7→8 (before writing) | `gate claim-evidence` | independent claim extraction vs matrix rows; exact-match vs real_results; N-support; verb-tier; no orphan/unlisted claim | any P0 row |
| **C** figure quality | before Phase 8 + Stage 0.5 | `gate figures` | SVG+PNG exist; file size sane; renderable; captions; axis labels ≥14pt; no overlapping labels; no empty table cells; in-figure numbers == real_results; PDF-layer visible | any P0 |
| **D** readability/render | Phase 9 | `gate readability` (wraps `compile_review.py`) | prose completeness; section coverage; no placeholders; citation syntax; CJK-aware word count; PDF render quality | placeholder found / render fail / under-length |
| **E** experiment value | **early (Phase 0/1/3 framing)** + re-check after results | `gate value` | is the result worth writing? steer the question/claim to the evidence | does NOT hard-block — **adjust + log** (see below) |
| **F** logic/coherence | Phase 8 after writing | `gate logic` (wraps `audit.py`) | 7-scan: formula extrema, internal contradiction, cherry-pick, concept-inventory diff, narrative↔evidence alignment | any P0 scan hit |

Gate E (owner decision 2026-06-14): the value check happens **early — at framing (Phase 0/1/3), not
the end** — because that is when you can still steer the question (owner: "研究價值在第一個結果出來時就
判斷，不要等寫完才問"). If value-insufficiency only surfaces **late** (after results), the policy is
**ADJUST, never hard-block**: downgrade the claim / reframe as a null-or-limitations result so the
paper is framed to the evidence — and **log the adjustment reason + before/after + process to a
traceable `value_adjustment_log.md`** so the steering is auditable. It still runs before the
Claim-Evidence Map + section writers.

### 3.9 Risks, caps, and policies (codex review)
- **Cost is NOT a gating constraint** (owner decision): architect = flat-rate **subscription codex**,
  workers = free **big-pickle** → no meaningful per-paper marginal cost. The ONLY acceptance constraint
  is **passing the quality gates**. Keep just a runaway-safety wall-clock/iteration cap (abort +
  checkpoint), not a token/cost budget.
- **Non-determinism in A/B:** CrossRef/OpenAlex/Europe-PMC/meta retrieval must be **cached + pinned**
  for the A/B run, or the comparison is noise (reuse the existing collect-once `_corpus_cache.json`).
- **Gate-gaming:** independent claim extraction + minimum per-section claim coverage (Gate B).
- **Worker starvation:** rich self-contained packets (§3.5), not bare file paths.
- **Checkpoint loss:** atomic checkpoint manifest + artifact hashes + idempotent gates + recovery from
  partial worker writes.
- **Parallel write conflicts:** workers write isolated `sections/*.md`; only the composition pass merges
  into `paper_draft_v0.qmd`.
- **External-reviewer outage → BOUNDED retry → blocked/manual** (owner decision + codex fix): the
  review is mandatory (no score → no output). On codex/copilot auth/rate failure, back off + retry up
  to **N times**; if still failing, transition to a terminal **`blocked_review` / manual-review** state
  (surfaced to the user) — never provisional-pass, never emit an uncertified artifact. *Infinite* retry
  is an ops failure mode; bounded retry + a terminal blocked state instead.

## 4. Migration — smallest end-to-end proof
A/B on ONE non-GPU meta-analysis topic, same contract.
- **A (baseline)**: current `paper_driver.py` (~60).
- **B (new)**: `paper_orchestrator.py --brain subscription-codex --worker-model big-pickle --lane
  meta-analysis --skill-bundle paper-draft+27 --max-revision-rounds 3`.

**Keep** (as tools): DOI audit/build-refs, phase0 calibration, meta_analysis lane, meta_figures,
tables injection, TikZ compile, renderers, consistency_gate, revision validation, compile_review,
provenance, blocked-review writer.
**Discard**: PAPER_PHASES list, phase-bounded prompt bodies, the one-shot phase subprocess loop,
"stop after Phase N", the phase5/6-deletion assumption.

Build steps (codex review — cheaper validation FIRST, full A/B last; do not jump straight to a B run):
1. **Extract `paperctl`** from `paper_driver.py` deterministic functions; pin tests against existing
   COMPLETED runs (outputs must match) — zero-risk pure refactor.
2. **Schema-validate** `dossier.json`, worker packets, gate reports, checkpoint manifests (fail fast).
3. **Port the missing gates first** as `paperctl` commands: B claim-evidence, C figures,
   D readability/render, E value, F logic-audit (§3.8) — usable even before the orchestrator exists.
4. **Copy the 28-skill bundle** into the hermes skills dir (unchanged; verify closure) + run-dir
   `AGENTS.md` invariants (§3.2).
5. **Hermes smoke test** (cheap): load the bundle, delegate ONE child, write dossier, checkpoint, and
   **resume fresh from dossier** — proves the continuity primitive before any paper.
6. **Micro proof** (cheap, high-signal): just Phase 3 positioning + Gap Matrix, OR Phase 7→8 claim-map
   + one section writer — proves reasoning continuity / claim-evidence discipline.
7. **Full A/B** only now: `paper_orchestrator.py` meta-analysis lane end-to-end, **cached/pinned
   corpus**, fixed reviewer-availability; compare vs the 60-pt driver on content-review score, gate
   report, DOI rate, render quality, word count, **Phase 3 gap quality**, repair rounds, hang rate.

**Governing rule:** *Python no longer tells the paper how to think. Hermes owns reasoning and
delegation. Python owns facts, gates, rendering, and refusal to pass bad artifacts.*

## 5. Viability interaction + live project status (owner design, 2026-06-15)

### 5.1 One viability probe, two call sites (grill ≡ phase0)
> **Generic API + pack adapter (codex):** the framework exposes `pack.viability.probe(contract, sources)
> -> ViabilityVerdict {viable, reason, metric, candidate_pivots, contract_hash}`. The PAPER pack
> implements it via `phase0_calibration.run_phase0` / poolable-k (below); the INSURANCE pack implements
> it via target_findings yield from its sources. The framework owns the verdict shape + the lock; the
> pack owns "what makes this domain feasible".
The grill's up-front feasibility gate and a-side phase0 are the SAME probe — a new a-side
`/jobs/viability-probe` wrapping `phase0_calibration.run_phase0` (collect + PICOS + count poolable-k +
saturation + codex gap/viability judgment + candidate pivots). The grill calls it **early** (to pass a
real yield gate, not just OpenAlex paper-count — the mindfulness-anxiety failure: thousands of papers
but only 6 poolable); submit re-runs it; a `contract_hash` **viability-lock** keeps both identical.
chat.ai never decides viability and never owns the canonical contract (codex grill-controllability
review: the contract is Worker-derived from structured grill answers; submit refuses without a
hash-matched approved lock).

### 5.2 Non-viable handling branches by `level` (tier) — owner's key addition
- **master**: AUTONOMOUS pivot — apply the best candidate pivot + proceed, and write a complete
  `research_steering_log` (discovery + why-pivoted + analysis) into the project, delivered alongside
  the report. Not silent — autonomous + **fully transparent**; master-level stakes carry the trade-off.
- **phd / journal**: STOP. Write verdict + pivot options to the project as `pending_confirmation` +
  notify the user; resume only on confirmation. Two confirm channels: (a) project-page button,
  (b) chat.ai reads the paused b-side session via MCP → discuss → append → resume → a-side continues.
The `research_steering_log` is the generalized `value_adjustment_log` (§3.8 Gate E): master = delivery
companion, phd = confirmation-request content. Its quality (why this pivot, what was discarded) is
first-class — the ONLY safeguard for the master auto-pivot. State machine adds: a `level` branch after
viability + a `paused_for_user` state (phd/journal) + the steering-log artifact.

### 5.3 Live project status (a-side publishes continuously)
On b→a handoff chat.ai returns a project link to paperlab.cooperation.tw (link is correct). Today the
page is stale during the ~40-min run: `sync_project_repo` (job_runner.py:686) fires only at coarse
transitions (skeleton at start, then terminal). Fix: a-side publishes a **continuously-updated project
status at EVERY checkpoint** — it already maintains the dossier, so the status is a webpage-friendly
projection of it — auto-uploaded to the designated store (extend `sync_project_repo` or add a status
callback to the Worker). The page must reasonably show, live:
1. **Research plan** (from b-side via MCP) — the proposal/contract.
2. **b-side gap** — the gap the grill determined.
3. **a-side gap** — phase0/phase3 gap (may refine/validate/change b-side's; showing BOTH = transparent
   direction evolution).
4. **a-side current decision** — tier (master/phd), viability verdict, pivot/pause state, live phase
   progress.
**Resolved (owner, 2026-06-15): a DYNAMIC project page reading a designated data location — NO Hugo
rebuild per update.** The flow:
1. At **submit (b→a handoff)** the system generates the **data location + the project page URL** and
   returns the link to chat.ai immediately (the link already resolves; only its content fills in).
2. a-side then **only runs the pipeline** and writes status/artifacts to that location at every
   checkpoint (the dossier projection). No rebuild — the page is dynamic over the store.
3. The page (`paperlab.cooperation.tw/projects/{id}`) **fetches + renders live** — progress while
   running, the final report when done. Concretely: a-side POSTs status JSON to a Worker
   `/projects/{id}/status`; the page reads `/api/projects/{id}` client-side.
4. If the user gave an **email** in chat.ai, it is carried into the project info; when the report is
   produced an **auto-notification email** is sent. (notify_email already flows through submit.)
Full loop: grill → submit → link returned → live page tracks (research plan, b-gap, a-gap, tier
decision, phase progress) → report rendered + email on completion.
(Build-time: verify how the existing project page currently fetches — the link already works, content
is just stale, so a fetch path exists; extend that, don't rebuild it.)
