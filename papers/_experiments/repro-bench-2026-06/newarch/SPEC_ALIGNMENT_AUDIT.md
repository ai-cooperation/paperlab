# Spec Alignment Audit — paper-draft skill (12 phases) vs Hermes+skill engine

Purpose: confirm whether the general Hermes+skill engine (`packs/paper/pipeline.py`,
`build_paper_phases()`) TRULY implements the paper-draft skill's documented methodology,
or has diverged. Two independent reviewers (codex + a Claude Code agent) should verify
this mapping, find additional gaps, and recommend the minimal changes to re-align.

Scope: the DATASET lane (`_is_dataset_lane`, an arbitrary public dataset → real regression
analysis). The b-side (chat.ai grill / paperlab MCP) produces the `research_contract`; the
a-side (this engine) runs the pipeline on it.

---

## A. The skill's phases (paper-draft SKILL.md) and their HARD requirements

| # | Skill phase | Hard requirement (skill) |
|---|---|---|
| 1 | 概念確認 Concept | research question + contribution validated |
| 2 | 文獻搜集 Literature | **≥35 refs (HARD, Phase-2 阻斷檢查)**; DOI 三重驗證 (CrossRef+S2+OpenAlex, ≥2 pass); every bib entry has abstract; doi_verification_report.md |
| 3 | 定位 Positioning | literature landscape; Gap Matrix (≥3 gaps); differentiation; 3 contributions tied to gaps |
| 4 | 結構 Structure | section outline + per-section key claim + figures/tables to ref |
| 5 | 實驗設計 Experiment design | [MVP skip] |
| 6 | 實驗執行 Experiment exec | [MVP skip] |
| 7 | 結果分析 Results analysis | real analysis → real_results |
| 8 | 撰寫 Writing | ≥35 @cite in body; every fig @-referenced; every bib entry cited (no dead refs) |
| 9 | 品質審查 Quality review | 7-dim review + self-heal loop; **Phase-9 文獻複驗 (re-run DOI verify, no newly-added unverified citation)**; 退稿風險 ≤30% |
| 10 | 投稿準備 Submission prep | journal-format package |
| 11 | 審稿回覆 Rebuttal | on-demand |

---

## B. The engine's phases (`build_paper_phases()`) — what each consumes / produces

| Engine phase | Consumes | Produces | Notes |
|---|---|---|---|
| `data` | contract, (dataset lane) fetched data + `contract.literature.verified_refs` | `real_results.json`, `references.bib`, figures | runs the real analysis; **references built as a SUB-STEP here** |
| `gap` | `references.bib`, `real_results.json` | `phase3_positioning.md` | **does NOT read `contract.framing`** |
| `structure` | `phase3_positioning.md`, refs, real_results | `phase4_structure.md` | does NOT read framing; figure labels hardcoded `@fig-forest/prisma/method` (meta) |
| `claim_evidence` | real_results, positioning, structure | `claim_evidence_map.md` | Gate B (claim≤evidence); engine-added, no skill phase |
| `write` | sections + metrics_block + skills | `paper_draft_v0.qmd` | lane-aware (fixed); does NOT read framing |
| `render_gates` | qmd | PDF + gates C/D/F + number_trace | |
| `review_heal` | qmd, real_results, claim_evidence | reviewed qmd | 7-dim review + free-worker fix loop (= skill Phase 9) |
| `format_repair` | qmd | PDF | figure crossref verify, ≤1 re-render |

---

## C. Mapping & alignment verdict

| Skill phase | Engine | Verdict |
|---|---|---|
| 1 概念 | b-side grill (contract.framing/topic/contribution) | ✅ aligned (by design, on b-side) |
| 2 文獻 ≥35 + 三重驗證 | demoted to a `data` sub-step | ⚠️ **PARTIAL**: was OpenAlex-only, no ≥35 gate, delivery-exempt. NOW (this session) added: multi-source (codex discovery + OpenAlex + CrossRef verify), ≥35 fail-closed, lane-aware delivery gate, Layer-2 citation-integrity. But still NOT a first-class phase, and 三重驗證 is CrossRef-only (S2 skipped: rate limits) |
| 3 定位 | `gap` | ❌ **BROKEN**: regenerates positioning from references.bib, **IGNORES contract.framing (gap/positioning/claims that the human shaped on the b-side)** — grep `framing` in pipeline.py = 0 |
| 4 結構 | `structure` | ⚠️ partial: doesn't read framing; meta figure labels hardcoded |
| 5-6 實驗 | `data` (dataset lane real analysis) | ✅ aligned |
| 7 分析 | `data` | ✅ aligned |
| 8 撰寫 | `write` | ⚠️ partial: ≥35-cite requirement not enforced as a gate; lane-aware framing fixed; doesn't read contract.framing |
| 9 審查+自修復 | `render_gates`+`review_heal`+`format_repair` | ✅ mostly; Phase-9 文獻複驗 added this session (citation-integrity D6) |
| 10 投稿準備 | — | ❌ not implemented |
| 11 回覆審稿 | — | ❌ not implemented (on-demand) |
| (none) | `claim_evidence` (Gate B) | engine-added rigor (good) |

---

## D. The two ROOT findings (why "just adding references is useless")

1. **a-side ignores the b-side's intellectual framing.** `contract.framing` = {gap, positioning,
   claims} is produced by the human in the grill, but NO a-side phase reads it. `_phase_gap`
   regenerates positioning blind from references.bib. So the discourse is not built on the
   human's positioning — adding references to a blindly-regenerated argument does not make the
   research valuable. **This is the discourse gap, and it matters more than the reference count.**

2. **Phase 2 (literature) was demoted from a gated first-class phase to a side-effect.** The
   b-side brought only 6 DOI candidates; the a-side built refs OpenAlex-only with no ≥35 gate →
   14 refs shipped. The skill makes 文獻 a Phase-2 阻斷檢查 (≥35 or stop).

---

## E. Proposed direction (for the reviewers to critique / improve)

- **b-side**: grill produces ~50 candidate **{title, doi}** + rich framing into the contract
  (currently 6 DOIs). DOIs let the a-side CrossRef-verify exactly; wrong ones are topped up.
- **a-side discourse**: inject `contract.framing` into `_hdr` and have `gap`/`structure`/`write`
  BUILD ON the human's gap/positioning/claims (refine + ground in real refs), not regenerate.
- **a-side references**: verify b's DOIs first (build_refs CrossRef); top-up with codex
  discovery (refs_llm, live-proven 48 verified) only if < 35.
- **gates**: ≥35 fail-closed (done), citation-integrity / Phase-9 re-verify (done).

## F. Questions for reviewers

1. Should Phase 2 (literature) be a first-class engine phase (own checkpoint + gate), or is
   keeping it inside `data` acceptable as long as the ≥35 gate + multi-source hold?
2. Is the "b generates {title,doi}, a verifies + tops up" split correct, or should discovery
   stay entirely a-side? Trade-off: human-in-loop relevance vs grill token cost.
3. How exactly should the a-side consume `contract.framing` without letting it override the
   real_results (claim ≤ evidence must still win)? Where's the line between "honor the human's
   positioning" and "don't claim beyond the data"?
4. Phase 10-11 (submission/rebuttal) — in scope for the engine, or stay manual?
5. Any phase-ordering or missing-gate issue not listed above?

---

## G. Fixes applied (this session — verified by 3 reviewers then implemented)

Reviewers (codex + Claude agent + agy) converged on: framing ignored, Phase 2 demoted, and
the BIGGER defect the original audit missed — **the gates were registered but DEAD** (no
`Phase` set `gates=`; render_gates/review_heal recorded blocks without raising; orchestrator
wiped `blocked=False` at the finish). agy also found a real hole in the new `refs_llm`
(no author validation → a real DOI on a coincidentally title-matching WRONG paper could enter).

| Item | Fix | Status |
|---|---|---|
| **Gate A dead (refs≥35)** | wired `Phase("data", gates={"A"})` → orchestrator runs gate_refs + raises; covers BOTH lanes | DONE, verified (14→block, 35→pass) |
| **claim≤evidence not enforced (dataset lane)** | `number_trace` made parsing-precise (codex: frontmatter/sci-notation/ranges; + Quarto attribute blocks/tbl-colwidths strip) → hard-block on ≥3 untraced (a real fabrication bunch; 1–2 may be methods-rule constants) | DONE, verified (11 false-pos → 1 rule constant, no false-block) |
| **orchestrator masks blockers** | `run()` no longer clears `blocked=True` at the finish line | DONE |
| **refs_llm anti-hallucination hole (agy)** | author-surname validation + title threshold 0.6→0.8 + expanded academic-jargon stopwords | DONE, 7/7 unit (incl. "real DOI wrong author → reject") |
| **a-side ignores framing (discourse root)** | `_framing_block(c)` injects gap/positioning/candidate-claims into `_hdr` (all phases); `_phase_gap` now ANCHORS on the framing, does not regenerate blind. Claims still routed through claim≤evidence (framing = hypothesis, real_results = referee) | DONE |
| **Phase 2 floor only dataset / meta has none** | Gate A (35) now covers both lanes; meta `REF_BACKFILL_TARGET` 26→40 so meta can reach the floor | DONE |
| **b-side search returns OECD figures (real-MCP finding)** | `literature.ts` CrossRef query + `filter=type:journal-article` (no more 10.1787 chart DOIs) | DONE (worker, pending deploy) |

### Deliberately NOT hard-blocked yet (would false-positive)
- **Gate C (figures)** / **Gate F (logic)**: on the existing run C fails on stale evidence (a
  fresh run's data phase registers figures) and F reports 14 logic items of unknown precision
  (possibly meta-tuned). Left RECORDED, not raising, until their precision is verified on a
  fresh dataset run. Enforce-then-false-block is worse than record.
- **Gate B mechanical matrix** (meta lane): needs the claim_evidence_map parsed into rows; the
  dataset lane's claim≤evidence is covered by the now-precise number_trace. Follow-up.

### Still open (out of this session's scope)
- b-side grill should accumulate ~50 candidates via `search_literature` (currently ~6).
- Phases 10–11 (submission/rebuttal) — intentionally manual.
- 三重驗證 is single-source CrossRef verify + multi-source discovery — relabel honestly, do not
  claim CrossRef+S2+OpenAlex ≥2-pass.

---

## H. Second pass — all 12 missed/partial items done + e2e validated

The reviewer-flagged items I had skipped (section G under-counted them) were ALL completed,
then codex did an acceptance review (found 2 fail-OPEN holes), then a fresh e2e run caught 4
more bugs that no parse/import/unit check could. Final state: **all 6 gates LIVE + an honest
paper delivers with 0 false-blocks** (job v2_f432cfbd275b: delivery=pass, 0 P0, PDF, 50/50
in-body cites, floor 58.3).

| Gate | Severity | Status (e2e-verified) |
|---|---|---|
| A refs>=35 + doi_real_rate>=0.80 | BLOCK | LIVE, fail-CLOSED (rate=None blocks) |
| B claim<=evidence | numbers=BLOCK(number_trace) / qualitative=WARN | qualitative is the review BRAIN's call (semantic), NOT a keyword hard-gate |
| C figures paired | BLOCK | LIVE (figures registered {name,svg,png}) |
| D readability | BLOCK | LIVE |
| E research value | WARN | LIVE — well-powered null = valuable (a-side confirms VALUE) |
| F logic | BLOCK | LIVE — dataset drops quantifier scan (number_trace owns numbers) |
| number_trace | BLOCK (>=2) | robust: full real_results walk + comma-strip + rounding tolerance |

### The principle this pass nailed down (the core correction)
- **Deterministic gate** ⟺ deterministic AND general facts: refs count, integrity hard-gates,
  figures-exist, and number traceability (a number must trace to a computed result — true for
  ANY dataset; thousands-commas + rounding are universal number formatting, so handling them is
  principled, NOT a fixed script).
- **Review brain** ⟺ semantic judgment: qualitative overclaim (causal language, universals).
  A keyword regex enumerating noun contexts for "causes" (of/across/leading/major…) is linguistic
  whack-a-mole — a fixed script wearing a general coat. Gate B's qualitative half is now advisory
  (records candidates) and the brain judges in context.

### e2e-only bugs (parse/import/unit all passed; only a live run surfaced them)
1. Gate B flagged "causes" the NOUN ("causes of death") → fixed-script regex was the wrong tool → advisory.
2. number_trace: "1,071" split into "071" (comma) + rounded CI/spline values → 25 false untraced → 0.
3. `re` never imported in pipeline.py (used inside `_phase_render_gates`) → NameError only on a live run.
4. D7: writer cited 29/50 refs (21 dead) → D7 correctly BLOCKED → compose prompt fixed to cite >=35 + every entry.

### codex acceptance fixes (fail-OPEN integrity)
- gate_refs PASSED on doi_real_rate=None → now fail-CLOSED.
- number_trace blocked only at >=3 → tightened to >=2.

Commits: 6e3ef83 e03df99 3b8ff76 4896f1e 37ae62d 2cc3d74 414980e 04dde29 ea37b8d.

---

## Class A fixed-script residue cleanup (2026-06-18)

Standing directive: the general dataset lane must hold ZERO dataset-specific knowledge in
SOURCE — all case knowledge lives in agent-produced run artifacts. codex flagged 6 Class A
residues; all fixed (codex wrote A–C; D+E applied inline after codex flaked narrate-no-apply
twice). Reviewer (Claude) bounded scope + ran per-batch acceptance against real run dirs.

| # | Residue | Fix | Commit |
|---|---------|-----|--------|
| 1+2 | `schema.dataset_research_value` + `figures.sample_flow` string-matched country/year keys (`analytic_countries`, `analytic_year_*`) — and the agent emits DIFFERENT keys each run (one run `analytic_countries`, another `merged_country_year_rows`), so the match was fragile AND unreliable | agent DECLARES generic `sample_flow.analytic_units` / `unit_label` / `time_min` / `time_max` (lane.py prompts emit them, like `primary_model_id`); consumers read the declaration first, legacy keys only as backward-compat fallback | ea2f63f |
| 3 | `_limitations_caveats` hardcoded "country-year data / unweighted panel / aggregate indicators" — false for survey-weighted microdata or cross-sectional studies | `_limitations_caveats(c, rr)`: unit phrasing from `unit_label`, ` panel` only when longitudinal, `"unweighted"` only when `survey_design.weighted is False`, generic "observed indicators". floor_score-scored tokens (subset/generalize/external validity/associational/not causal) all preserved | aa335d6 |
| 4 | `"hupd" not in name` substring duplicated in `_is_dataset_lane` (pipeline) + `figspec_for` (tables) | `capabilities.REGISTERED_FAST_LANE_TOKENS` + `is_registered_fast_lane(ds)` — the literal lives once in the registry; both consumers ask it. HUPD stays a legitimate registered fast-lane (intentional, not residue) | 1d75af5 |
| 5 | `_template_for` DEFAULTED the general dataset lane to the HUPD-specific `classical_ml_benchmark` template | explicit empty `TEMPLATES["dataset_agent_analysis"]=[]` (writer owns dataset tables via metrics_block) + route the lane there + neutral default for unknown lanes; HUPD still routes via the benchmark rule | d417fed |
| 6 | figure-inject fallback sentence hardcoded meta language ("analysis pipeline and pooled results") | neutral "The corresponding result is shown in {ref}." | d417fed |

### Litmus re-audit (post-fix, read-only scan of general-lane source)
- No case-specific dataset literal (nhanes/owid/gdp/country-code/CPC) in general-lane source.
- Remaining `analytic_year_*` / `"countries" in k` occurrences are the DECLARED-FIRST,
  legacy-fallback paths only (a new dataset declares the generic fields and never hits them) —
  intentional backward-compat, not residue. `tables.py:132 year_range` is scientometric-lane-internal.
- Registered HUPD lane (`real_patent_experiment.py`, `data_availability_gate.py`, capabilities
  registry) is INTENTIONAL architecture — pre-verified golden lane, not general-lane residue.

### Regression (changed-module unit suite on ac-2012)
56 passed. 5 pre-existing failures (PROVEN not from this work: `primary_model_id` required field +
`format_repair` phase, both prior-session changes; my 4 commits' combined diff greps EMPTY on those
symbols). 17 errors = `golden_dir` fixture missing in temp-dir copy (conftest not copied) = harness
artifact, not code.

Commits: ea2f63f aa335d6 1d75af5 d417fed.

---

## Delivered-paper quality fixes (2026-06-18, user audit of the live re-run)

User audited the delivered dataset paper (job v2_adebc36b20ea) and caught three real gaps
that `delivery=pass` masked (delivery=pass means 0 P0 + score>=target + renders — NOT
"clean tables / all issues fixed"):

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| 1 | Tables AND prose dumped raw 16-decimal floats (`3.6285577215297318`, `p = 1.149e-83`) — the dataset lane's tables are writer-authored (tables.generate -> [] for it), so the deterministic `_f(n=3)` rounding was never applied | `number_format.format_numbers`: column-aware table rounding (p-value cols -> p</=, others 3 sig figs) + prose rounding (>=5-decimal artifacts + p-values; DOIs/years/counts untouched). Wired into `format_repair.verify_and_repair` AFTER number_trace so `<0.001` can't trip traceability. Verified: 171 artifacts + 2 sci-notation -> 0; crossrefs/cites/years intact | 3684c0b |
| 2 | Review loop stopped at "no P0 + score>=target", leaving the final round's P1/P2 recorded-but-UNFIXED (verified: round-2 edits' replacement absent from the delivered qmd) | VIP tier now also clears P1/P2: `ReviewOutcome.p1_count/p2_count` + `passed(target, clear_minor)` requires p1==p2==0 when clear_minor; `_phase_review_heal` sets clear_minor=(tier=='vip') + 5 rounds (vs 3). Standard tier unchanged | 70ebb74 |
| 3 | "12 phase" claim: pipeline is 8 orchestrator phases covering paper-draft Phase 1-9. Phase 10-11 (submission + reviewer-response/rebuttal) are a VIP HUMAN service, deliberately out of the automated pipeline | Documented at `build_paper_phases` | 70ebb74 |

Honest note: the earlier "完整確認" confirmed delivery MECHANICS (0 P0, floor passes, renders),
not deeper quality (table precision, residual P1). The user's three observations were all correct.
