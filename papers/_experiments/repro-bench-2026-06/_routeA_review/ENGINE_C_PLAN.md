# Engine C + Task-Driven Revision Loop — Implementation Plan

Converged design (Claude + agy AGY_REVIEW_LOOP_DESIGN.md). Goal: make the review→revision loop
reliably TRIGGER on real contradictions and execute CONCRETE, machine-verifiable edit tasks, on the
free big-pickle stack (ac-2012 is air-gapped: no copilot/gh/agy/codex, only Hermes+big-pickle).

## 0. Principle
- Engine C (deterministic) is the reliable trigger + safety net for factual/structural contradictions.
- Engine B (big-pickle reviewer-agent) only handles qualitative issues, emitting the SAME task schema.
- Edits are TARGETED find_replace (no full-file rewrite) → minimal regression surface.
- Loop exit = Engine C reports 0 P0 tasks (NOT the weak model's p0_count).

## 1. New / changed files
| File | Action | Role |
|---|---|---|
| `newarch/consistency_gate.py` | NEW | Engine C: compare qmd claims vs real_results.json → P0/P1 tasks |
| `newarch/revision_tasks.py` | NEW | task schema, applier (find_replace + guardrails), verify |
| `newarch/mechanical_check.py` | VENDOR (copy from top-level) | post-revision validation (words/cites/cells) |
| `newarch/verify_matrix.py` | VENDOR | post-revision artifact validation |
| `newarch/paper_driver.py` | MODIFY | replace p0-based loop with task-driven loop |
| review prompts in paper_driver | MODIFY | Engine B emits the task schema |

## 2. Task schema (final — Engine C and Engine B both emit this)
```json
{ "id": "DET-YEAR-001",
  "engine": "C" | "B",
  "severity": "P0" | "P1",
  "type": "value_swap" | "block_rewrite",
  "target_section": "3.3 Evaluation Protocol",
  "target_content": "<exact substring expected in the qmd>",
  "replacement_content": "<concrete text>  (C value_swap: gate supplies it; block_rewrite/B: model supplies)",
  "description": "<why>",
  "grounding": "real_results.json: filing_year_distribution={2016:2000}",
  "verification": { "absent": "<regex must NOT match after edit>",
                    "present": "<regex must match after edit>",
                    "min_words": 3800, "preserve_cites": true } }
```
- `value_swap`: exact substring → exact replacement (Python does it deterministically, no model).
- `block_rewrite`: locate the block by `target_content`/section; the model generates `replacement_content`
  for THAT block only (used by Engine C's prose contradictions + all Engine B tasks).

## 3. Engine C checks (consistency_gate.py) — vs real_results.json ground truth
| Check | Ground truth | Flag when qmd claims | Task |
|---|---|---|---|
| Temporal split | `scientometrics.filing_year_distribution` = {2016:2000} (single year) | any train/test YEAR-range split (regex `20\d2\s*[–-]\s*20\d2`, "training on 20.., testing on 20..") with years not all in the real set | P0 block_rewrite → nested 5-fold CV on the real cohort |
| CPC class count | `n_classes[cpc_section]` = 7 | "9-class"/"9 CPC"/"A-H, Y"/class count ≠ 7 | P0 value_swap → "7" |
| Classifier count | len(`models`) = 5 | "six classifiers"/"6 models"/N≠5 | P0 value_swap → "five/5" |
| Feature count | len(`features`) = 2 | N≠2 | P1 value_swap |
| Bootstrap N | `bootstrap_samples` = 300 | "2,000 bootstrap"/"1000 replicates"/N≠300 | P1 value_swap → "300" |
| CV folds | `cv_requested` = 5 | folds ≠ 5 | P1 value_swap |
| Headline F1 | real holdout f1_macro set (e.g. 0.6143, 0.5392) | a quoted "best F1" not present in real set | P0 block_rewrite |
- Output: `consistency_tasks.json` (list of tasks) + a `real_existence`-style summary. Pure regex/number
  compare; zero model, milliseconds, 100% reproducible. Encoded checks are HUPD-classical-ML specific;
  documented as such (generalization = future work; do not silently claim universal coverage).

## 4. Task applier (revision_tasks.py)
- `apply_value_swap(qmd, task)`: assert `target_content` present (else record unresolved); sanitize
  replacement (strip HTML/reportlab tags except `<i>/<b>`); replace; return new qmd.
- `apply_block_rewrite(run_dir, task, model, provider)`: locate block (by target_content, else section
  heading); build a TIGHT prompt (only that block + grounding + verification) → big-pickle returns the
  replacement block only; sanitize; verify cite-keys in old block ⊆ new block (preserve_cites); swap.
- `verify_task(qmd, task)`: `absent` regex must not match, `present` regex must match → task done.
- Guardrails (agy failure modes): target-exists precheck + section fallback; replacement sanitize;
  citation-key preservation; min_words floor on the whole doc.

## 5. Validation gate + rollback (per round)
After applying a round's tasks: re-render (render_qmd_reportlab), then require ALL of:
- every P0 task `verify_task` passes,
- `mechanical_check.score_run`: words ≥ 3000, citations ≥ 35, empty_cells == 0,
- `verify_matrix`: required gate artifacts still present,
- PDF renders > 1000 bytes, real headline numbers still present (no data regression).
If any fails → restore qmd + artifacts from `history_round_{n}/` (rollback) and STOP the loop, keeping the
last good version. (Never ship a regressed round.)

## 6. Loop integration in paper_driver.main()
Replace the current `while p0_count>0` loop with:
```
tasks = consistency_gate.run(run_dir) + engine_b_tasks(run_dir)   # B optional this phase
round = 0
while any(t.severity=="P0" for t in tasks) and round < max_rounds:
    round += 1; archive_round(run_dir, round)
    apply_tasks(run_dir, tasks)                 # value_swap deterministic; block_rewrite via big-pickle
    render_pdf(run_dir)
    if not validation_gate(run_dir): rollback(run_dir, round); break
    tasks = consistency_gate.run(run_dir) + engine_b_tasks(run_dir)   # re-detect
# final score via compile_review (now p0 should be 0 because Engine C is satisfied)
```
- compile_review still produces the score artifact; Engine C tasks feed `problems[]` so p0_count and the
  task set agree. meets_threshold (already requires no_p0) now reflects the deterministic truth.

## 7. Engine B reviewer-agent (same schema) — phase 2 of build
Reframe the review Hermes call: prompt big-pickle to output ONLY a `{"tasks":[...]}` list (qualitative:
flow, missing subsection, formatting), each a `block_rewrite` with target_content + verification. No
scoring prose. compile_review parses the json block (already does) into the unified task list.

## 8. Build order + acceptance
1. `consistency_gate.py` + unit test on the e2e-002 qmd (the false-pass case): MUST emit the temporal-split
   P0 + (9-class? / 6-classifier? / bootstrap?) tasks it actually contains. Accept: ≥1 P0 emitted, all
   grounded in real_results.json.
2. `revision_tasks.py` + unit test: a value_swap and a block_rewrite apply + verify; guardrails reject a
   citation-dropping / truncating replacement.
3. Wire task-driven loop into paper_driver; run on e2e-002 copy → Engine C flags temporal split → loop
   fixes → Engine C re-run reports 0 P0, contradiction gone, words ≥ 3800, cites preserved, PDF renders.
4. Engine B reviewer-agent prompt; full fresh E2E.
5. git commit a stable point.

## 9. Open questions for review
- value_swap replacement for the temporal split is really a prose rewrite (block_rewrite) — confirm we
  route prose contradictions to block_rewrite (model) and only number/word mismatches to value_swap
  (deterministic). [proposed: yes]
- Rollback policy: on validation fail, STOP keeping last-good (proposed) vs retry once. [proposed: stop]
- Engine B in the first cut, or land Engine C + loop first and add B after? [proposed: C + loop first]
