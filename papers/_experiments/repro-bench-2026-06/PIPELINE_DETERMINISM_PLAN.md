# Pipeline Determinism & b↔a Alignment — Implementation Plan

Status: DRAFT for codex review (2026-06-10)
Author: Claude (orchestrator)
Scope: paperlab a-side (`~/paper-job-service/newarch/`, dev copy `papers/_experiments/repro-bench-2026-06/newarch/`)
       + b-side (`~/projects/paperlab-kb/workers/`, Cloudflare Worker, `mcp.paperlab.cooperation.tw`)

## 0. Problem statement & guiding principle

This session's failures all share one root cause: anything "that must be correct" was left to a
weak/external model to generate, then either caught by a gate (detect-and-repair) or missed.
Concrete instances: Copilot quota → job stalled; `&amp;` in bib broke xelatex; 7-col table overflowed;
`[@Nigam2000]` cited for a scikit-learn version; frontmatter drift; ∈ broke pdflatex.

**Guiding principle:** move the *verifiable* parts of a paper from "model generates → gate repairs"
to "deterministic generates → model only does the irreducibly subjective parts (novelty, prose,
interpretation)". Every field made correct-by-construction removes a gate, a revision loop, and a
failure point.

Infra reality (verified 2026-06-10): on ac-2012 the only reachable reviewer backends are Copilot
(premium_interactions exhausted until 2026-07-01), big-pickle/zen-shim (free but hallucinates — cannot
score honestly), and a possibly-placeholder Gemini key. tencent/ac-mac are unreachable from ac-2012.
=> "swap to another model" is NOT a reliable fallback. The reliable fallback must be deterministic.

## Three workstreams (ordered by leverage / urgency)

- WS1 Deterministic floor scoring (fallback) — urgent, small. Stops jobs stalling when the model
  reviewer is down; also reduces model-dependence of the score generally.
- WS2 Contract v2 + deterministic table/figure generation (a-side) — highest leverage. Numbers/tables
  correct-by-construction; kills number-transcription, overflow, fabrication classes.
- WS3 b-side grill/MCP produces Contract v2 (+ verified refs) — closes the loop: b's output format = a's
  execution spec.

---

## WS1 — Deterministic floor scoring (fallback)

### Goal
When the model reviewer (Copilot) is unavailable or returns no 7-dim scores, the job must still
complete `done` with a conservative, defensible, deterministically-computed score — never `failed`,
never stalled at `review_pending`, never a fabricated constant.

### New module: `newarch/floor_score.py`
Pure function `floor_scores(run_dir) -> {scores_7dim, evidence, notes}` computing 6 of 7 dims from
artifacts a already produces. No model calls. Each dim in [1.0, 10.0]:

| dim | deterministic signal (source) | mapping (draft — tune in review) |
|---|---|---|
| evidence_validity | claim-evidence coverage % (claim_evidence_map.md / consistency_gate) | 100%→7.5, linear to 0%→3.0 |
| literature_grounding | #verified DOIs (metadata.json status ok/verified) + in-text cite density + year spread | ≥35 verified & dense→7.5; scale down |
| methodological_rigor | structural checklist over qmd: CV present, CI/bootstrap, significance test, ablation section, sample-size reported | 5/5→7.5, each missing −0.7 |
| limitation_honesty | Limitations section exists + N distinct enumerated limitations | section + ≥4 items→7.5 |
| writing_coherence | gate_d_readability.md grade in range + all expected sections present + prose ≥ floor | in-range & complete→7.0 |
| result_interpretation | detect honest non-significant reporting (p>0.05 mentioned w/o overclaim) + results-section length | heuristic→6.5 baseline |
| novelty | NOT deterministically measurable | conservative fixed 5.0, flagged `floor_estimate` |

`mean_7dim = round(mean, 2)`. Returns `evidence` (the raw signals) so the score is auditable, and
`notes` listing which dims were estimated.

### Integration: `compile_review.compile_reviews`
Replace the current binary (model scores present → score / absent → P0|review_pending) with a layered
policy:
1. If the model reviewer emitted all 7 dims → use them (current behaviour), AND attach floor scores as
   `floor_7dim` for cross-check (log if model and floor diverge > 2.0 on a measurable dim — a signal the
   model hallucinated).
2. If model reviewer unavailable/incomplete → use `floor_scores`. Set
   `score_source: "deterministic_floor"`, keep `reviewer_unavailable: true` (so it's visible the model
   review is pending), but compute `meets_threshold` from the floor mean. Job → `done` (WS1 changes
   job_runner: reviewer_unavailable + a real floor score ⇒ `done`, not `review_pending`).
3. Never invent: novelty stays a flagged conservative constant; floor is documented as a floor.

### job_runner.extract_output
- `score_source` surfaced in output.
- status: `done` whenever `score_float is not None and pdf` (floor provides a score) — so the
  `review_pending` state from the prior hardening is now reserved only for "floor also failed to
  compute" (should be rare). Keep the explicit blocker note when floor was used.

### Reviewer chain (config-driven, future-proof)
`PAPER_REVIEWER_CHAIN = "copilot,gemini,floor"` (env). paper_driver tries each in order; `floor` is the
terminal always-succeeds tier. Gemini tier gated on a *validated* key (probe at startup; skip if
placeholder). This makes adding a backend a config change, not code.

### Tests (pytest, on ac-2012 venv)
- floor_scores on the e2e run_dir → all 7 dims in range, evidence populated.
- compile_reviews with reviewer_status=unavailable → score_source=floor, meets_threshold computed,
  no REVIEW_INCOMPLETE P0.
- Regression: existing model-scored run still 7.33/done, floor attached as cross-check.

---

## WS2 — Contract v2 + deterministic table/figure generation (a-side)

### Contract v2 schema (backward-compatible superset of current research_contract.json)
Add optional structured blocks; a-side reads them when present, else falls back to current model-driven
behaviour (so old contracts still run).

```jsonc
{
  // existing fields kept (job_id, project_id, topic, research_question, contribution, data_source,
  // target_journal, level, tier, method, seed_refs, ...)
  "contract_version": 2,
  "framing":  { "gap": "...", "claims": ["TF-IDF≈BoW not significant", ...], "positioning": "..." },
  "literature": { "verified_refs": [ {"key","doi","title","authors","year","abstract","verified":true} ],
                  "min_count": 35 },
  "experiment": {
    "dataset": {"name","url","probe_required","split_spec"},
    "tasks":   [ {"name","type","n_classes"} ],
    "models":  [...], "baselines": [...],
    "metrics": ["macro_f1","accuracy"],
    "ablations": [ {"factor":"max_features","grid":[1000,5000,10000,25000]} ],
    "eval_protocol": {"cv_folds":5, "bootstrap_iters":300, "sig_test":"mcnemar"}
  },
  "artifacts": {
    "tables":  [ {"id":"tbl-main","caption":"...","columns":[...],"source":"real_results.acceptance"} ],
    "figures": [ {"id":"fig-main","caption":"...","type":"bar_ci","source":"real_results.acceptance"} ]
  }
}
```

### New module: `newarch/tables.py` — deterministic table generation from real_results.json
`render_tables(run_dir, contract) -> {tbl_id: markdown}`. For each `artifacts.tables[*]` spec (or a
default spec derived from `experiment.metrics` when v1), read `real_experiments/real_results.json` and
emit a markdown table:
- controls column COUNT (cap, e.g. ≤6; combine mean±std into one cell) → no overflow by construction;
- controls rounding, CI formatting `[lo, hi]`, abbreviations (model acronyms from `experiment.models`);
- emits the `: caption {#tbl-id tbl-colwidths=[...]}` line with deterministic widths.
The numbers come from results JSON, not the model → claim-evidence for table cells is guaranteed.

### Figure labels from data
Extend figure generation so panel labels / annotations (e.g. "300 bootstrap resamples", n per class)
are templated from `experiment.eval_protocol` + real_results, not authored free-hand. Closes the
"fig1 says 1,000 but actually 300" gap. (If figure code is model-authored, inject a deterministic
caption + a values table the figure must match; verify counts.)

### a-side phase consumption
- phase2 (literature): if `literature.verified_refs` present → write references.bib + metadata.json from
  it, SKIP re-search/re-verify (saves the ~23 min CrossRef pass); doi_gate still spot-re-verifies a
  sample as anti-regression.
- phase7 (results/tables): replace model-written result tables with `tables.render_tables(...)` output
  spliced into the qmd; model writes only surrounding prose. consistency_gate then has near-nothing to
  catch.
- phase8 (claims): map `framing.claims` to results; flag a claim with no supporting result row.
- render: `target_journal` → deterministic template/csl (already done for Scientometrics→elsarticle).

### Migration / safety
- All v2 blocks OPTIONAL. `contract_version` gates new paths. v1 contracts unchanged.
- tables.py output goes through the same render_quality gate.
- Unit tests: tables.render_tables on the e2e real_results → exact expected markdown (numbers, widths,
  ≤6 cols). Idempotent.

---

## WS3 — b-side: grill/MCP produces Contract v2

Repo: `~/projects/paperlab-kb/workers/` (TypeScript, Hono, D1). Tools in `src/mcp.ts`, pipeline calls in
`src/pipeline.ts` (posts to `https://paper-a.cooperation.tw/jobs`).

### Changes
1. **Structured grill state** (D1 project row gains a `contract_v2` JSON column): grill tools write
   structured fields instead of only free-text:
   - `start_brainstorm` → framing.gap, research_question
   - `confirm_direction` → framing.contribution_type, framing.claims, positioning
   - `search_literature` / `add_seed_ref` → run CrossRef + verify_doi **server-side**, store
     `literature.verified_refs[]` (DOI+title+authors+year+abstract+verified), not just titles
   - new `define_experiment` (or extend `propose_proposal`) → experiment{dataset,tasks,models,baselines,
     metrics,ablations,eval_protocol} + artifacts{tables,figures} specs (b's LLM scaffolds structure;
     data-bound cells left for a)
2. **`submit_to_pipeline`** posts Contract v2 (validated against a JSON schema shared with a) instead of
   `proposal_markdown` free text. Keep `proposal_markdown` as a rendered human view derived from v2.
3. **Schema sharing**: one `contract_v2.schema.json` checked into both repos (or fetched), so b validates
   before submit and a validates on receive (fail fast with field-level errors).

### MCP tool description updates
Reframe tool descriptions so the model driving the connector *elicits* the structured fields (the grill
becomes a spec-filling interview, not open chat). Align with the existing grill-mode skill.

### Backward-compat
- a accepts both v1 and v2 (WS2 migration). b can ship v2 incrementally; until then a runs v1 path.

---

## Cross-cutting

- **Shared schema** `contract_v2.schema.json` is the alignment artifact (single source of truth for the
  a↔b interface). Both sides validate against it.
- **render_doctor() preflight** (small, from reflection): verify quarto/xelatex/elsarticle/extension +
  compile a 5-line smoke doc before the real render; fail fast with a clear message.
- **Unified render_prep sanitizer**: consolidate scattered fixes (bib &amp;, line-prefix, math, frontmatter,
  table colwidths) into one auditable pass + a regression corpus of known-bad inputs.

## Sequencing & rollout
1. WS1 (floor_score + compile_review + job_runner) — independent, deployable now, fixes the urgent
   "copilot down" stall. ~1 module + 2 edits + tests.
2. WS2 (Contract v2 schema + tables.py + phase7 consumption) — a-side only, backward-compatible. Biggest
   accuracy win.
3. WS3 (b worker) — depends on the v2 schema from WS2; deploy b after a accepts v2.
4. Cross-cutting (render_doctor, render_prep) — fold in alongside.

Each WS: dev copy → py_compile → deploy ac-2012 → pytest on venv → e2e spot-check → git commit.

---

## REVISION (post-codex review, 2026-06-10) — adopted changes

Codex review (59.8k tok) accepted the direction but flagged that WS1 as drafted risks becoming a
"reviewer-down auto-approve" bypass, WS2 needs an *executability* contract (not just richer JSON), and
WS3 must not deploy v2 by convention. All accepted. Key changes:

### WS1 corrections (CRITICAL — floor must not bypass the threshold)
- **Floor makes the job a `done` DELIVERABLE, but does NOT satisfy `meets_threshold` for journal/phd
  lanes.** Output carries `score_source: deterministic_floor` and `review_status: model_review_pending`;
  `meets_threshold` is `false` (or a separate `provisional: true`) until a real model reviewer scores it.
  Floor unblocks delivery + retrieval, it does NOT certify the paper passed. (mvp/low lanes may treat
  floor as provisional-pass — decide per lane, default conservative.)
- **novelty: excluded from the mean.** Emit `novelty: null`, report `mean_6_floor`. If a 7-key consumer
  needs it, add `novelty_display` but never use it in a threshold decision. No fixed 5.0 in pass/fail.
- **Hard pre-gates before any floor number** (else floor = 0/blocked, not a soft score):
  `real_results.status == completed`, zero simulation markers, no open consistency-gate P0, every
  table cell traces to real_results (hash), every *major* conclusion mapped to a result row / stat test.
- Strengthened per-dim signals (replace the gameable v1 mappings):
  - evidence_validity: coverage AND the hard pre-gates above; vague/few-claim padding capped.
  - literature_grounding: verified-DOI *rate* + cited-in-text rate + relevance to claims + recency
    spread; cap if references are unused (anti citation-stuffing). Not raw count.
  - methodological_rigor: + split/leakage validation, seed/provenance present, metric appropriateness,
    baseline coverage, executable-protocol match — not just a 5-item checklist.
  - limitation_honesty: limitations must name *actually-detected* weaknesses (single dataset,
    classical-only, class imbalance, non-significant tests), not just count ≥4.
  - writing_coherence: low weight, capped (presence/length ≠ coherence).
  - result_interpretation: derive from `real_results.statistical_tests`, not prose length.
- Mapping policy: **hard absolute gates first, then numeric mappings calibrated against prior reviewed
  runs** (store a small calibration set); no live-percentile runtime corpus (drifts).

### WS0 (NEW — must land before WS2/WS3)
1. **Shared schema served by a**: `GET /schema/contract_v2.schema.json` + a `GET /capabilities`
   advertising: supported `contract_version`s, `schema_hash`, supported `experiment_recipe_id`s,
   max payload, renderer/result-schema versions. Every submitted job pins the `schema_hash`; both sides
   log it. (Replaces "checked into both repos" which drifts.)
2. **Experiment capability registry** (a-side): `recipes/<id>.json` (e.g. `hupd_classical_ml_v1`) listing
   supported datasets/tasks/models/features/metrics/ablations, allowed param ranges, expected
   `real_results` schema, min rows/classes.
3. **`validate_experiment_contract(contract) -> resolved_experiment_plan.json`** BEFORE running: reject or
   downgrade unsupported fields up front. AFTER running: validate actual `real_results.json` against the
   resolved plan (tasks/metrics present, folds/bootstrap match, models/features match, no sim markers).
4. **Machine-owned generated blocks** in the qmd:
   `<!-- GENERATED:tbl-main source=real_results sha256=... -->` … `<!-- /GENERATED -->`. The model writes
   ONLY prose outside these. A **post-render verifier** re-parses every generated table and confirms each
   numeric cell still equals real_results (catches model tampering inside protected regions).
5. **Provenance record** written every run: git commit of experiment code, dependency versions, dataset
   snapshot id/hash, random seed, schema_hash, real_results hash.

### WS2 corrections
- v2 blocks NOT all optional: for the real-experiment lane, `experiment`, `eval_protocol`,
  `artifacts.tables` are REQUIRED (validated by WS0 #3).
- tables.py = **per-contribution-type templates** over generic rendering primitives (avoid an
  under-specified generic table mini-language). Output goes inside GENERATED blocks (WS0 #4).
- Dataset determinism: cache an immutable data snapshot or record exact sampled IDs (external
  HUPD/PatentsView can change/fail).

### WS3 corrections
- **Capability negotiation**: b calls a's `GET /capabilities` and submits v2 ONLY when a advertises a
  matching `schema_hash` + `contract_version`; otherwise submits v1. No deploy-by-convention.
- `verified_refs`: compact metadata inline; full abstracts stored by reference (D1/R2) with keys/hashes.

### Cross-cutting additions
- **Security**: sanitize ALL b-provided free text (titles, authors, abstracts, captions, claims) for
  Markdown/LaTeX injection before render — folds into the unified render_prep sanitizer.
- **Fuzz tests**: unsupported task/metric, fake DOI, oversized refs, malicious caption, v2→v1 a-side,
  partial v2, mismatched schema_hash.
- **Status decision**: replace the public `review_pending` with `done` + a `review_status`
  (`scored | model_review_pending | floor_only`) field, so the public status enum stays
  `submitted/running/done/blocked/failed` and the review nuance rides in `review_status`.

### Revised ordering
WS0 (schema + capability registry + executability validator + GENERATED-block plumbing + provenance)
→ WS1 (floor scoring, now non-bypassing) → WS2 (tables.py + phase consumption) → WS3 (b worker w/
capability negotiation). WS1 can start in parallel with WS0 since floor scoring only reads existing
artifacts; but the `review_status`/status decision (WS0 cross-cutting) lands with WS1.

## Open questions for codex
- Floor-score dim→number mappings: are the thresholds defensible, or should floor be *relative*
  (percentile vs a reference corpus) rather than absolute?
- Should `novelty` floor be a fixed 5.0, or omitted (mean over 6 dims) with an explicit "novelty:
  unscored" flag?
- Contract v2: put `verified_refs` abstracts inline (big payload) or store by reference (D1/R2) and pass
  keys?
- tables.py: generic spec-driven generator vs per-contribution-type templates — which is more robust?
- Risk of a-side reading b-provided `experiment` spec that doesn't match what the real experiment code
  can actually run (spec/impl drift) — how to validate the experiment spec is executable before running?
