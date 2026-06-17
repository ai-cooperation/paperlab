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
