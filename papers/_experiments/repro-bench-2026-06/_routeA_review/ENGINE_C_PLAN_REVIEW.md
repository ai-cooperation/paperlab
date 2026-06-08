# Engine C + Task-Driven Revision Loop — Implementation Plan Review

**Author:** Antigravity
**Date:** 2026-06-08
**Target Plan:** `_routeA_review/ENGINE_C_PLAN.md`

---

## 1. Correctness: Regex and Claim Scanning Analysis

We analyzed the raw markdown text in [`_routeA_review/produced/paper_draft_v0.qmd`](file:///Users/user/projects/ai-paper-workshop/papers/_experiments/repro-bench-2026-06/_routeA_review/produced/paper_draft_v0.qmd) against the proposed regexes in Section 3 of the plan. We identified several critical mismatches and bugs:

*   **Temporal Split Regex Bug (Critical Miss):**
    *   *Plan Regex:* `20\d2\s*[–-]\s*20\d2`
    *   *Actual Prose (Line 80):* `temporal holdout (training on 2014--2018 applications, evaluating on 2020 applications)`
    *   *Why it will MISS:* 
        1. The term `\d2` in the regex matches a single digit followed by the literal character `2` (e.g. `2012`, `2092`). It does not match a 2-digit range like `\d{2}`.
        2. The dash character class `[–-]` matches a single hyphen or en-dash. However, raw QMD files use double hyphens `--` (e.g., `2014--2018`).
        3. The plan expects to match `"training on 20.., testing on 20.."`. The actual prose uses the phrase `"evaluating on 2020 applications"`, not `"testing on"`.
    *   *Fix:* Update the regex to `20\d{2}\s*(?:--|[-–])\s*20\d{2}` and ensure the phrasing search covers both `"testing on"` and `"evaluating on"`.

*   **CV Folds Check (High False-Positive Risk):**
    *   *Actual Prose (Lines 78, 92):* The document correctly contains both `3-fold inner cross-validation` and `5-fold nested cross-validation` (or `outer 5-fold`).
    *   *Why it will FALSE-POSITIVE:* If the regex naively checks for any occurrences of `\d+-fold` and flags when the number is not `5`, it will capture the legitimate `3-fold` inner CV mention and flag a P1 violation.
    *   *Fix:* Restrict the check to the outer cross-validation description or ignore "inner" when validating the main CV fold count.

*   **Headline F1 Phrasing (Miss Risk):**
    *   *Actual Prose:* The F1 scores are mentioned in three different styles:
        1. `"highest holdout macro F1 (0.6143)"` (Abstract, line 22)
        2. `"highest holdout macro F1 of 0.6143"` (Results, line 101)
        3. `"best holdout macro F1 of 0.5392"` (Results, line 135)
    *   *Fix:* The regex must be flexible enough to handle parentheses and variable prepositions: `(?:highest|best) holdout macro F1 (?:of )?\(?(\d\.\d+)\)?`.

---

## 2. Reuse Fit: Validation Script Integration

We verified the interfaces of [`mechanical_check.py`](file:///Users/user/projects/ai-paper-workshop/papers/_experiments/repro-bench-2026-06/mechanical_check.py) and [`verify_matrix.py`](file:///Users/user/projects/ai-paper-workshop/papers/_experiments/repro-bench-2026-06/verify_matrix.py) to confirm integration compatibility:

*   **Word Count Assumption (Mismatched Interface):**
    *   *Plan Assumption:* Section 5 assumes `mechanical_check.score_run` verifies `words >= 3000`.
    *   *Reality:* `mechanical_check.score_run()` does NOT calculate word counts. It only counts `qmd_bytes` (character length). Prose word count is implemented in [`newarch/compile_review.py`](file:///Users/user/projects/ai-paper-workshop/papers/_experiments/repro-bench-2026-06/newarch/compile_review.py) as `_qmd_prose_words()`.
    *   *Fix:* The validation gate must explicitly check `compile_review._qmd_prose_words()` or update `mechanical_check.py` to support word count.
*   **Verify Matrix `doi_map` Requirement (High Integration Risk):**
    *   *Plan Assumption:* Section 5 calls `verify_matrix` to ensure artifacts are present.
    *   *Reality:* The primary function `verify_matrix.audit_run(run_dir, doi_map)` requires a `doi_map` argument. If called with an empty dictionary `{}` or omitted, the P9 DOI gate will fail (returning `FABRICATED` due to no evidence), causing the validation gate to fail and trigger rollback.
    *   *Fix:* The driver must load `run_dir / "doi_audit.json"` (produced by `doi_gate`) to populate the `doi_map` before calling `verify_matrix.audit_run()`.

---

## 3. Applier Risk: Find-and-Replace Robustness

The split between `value_swap` (deterministic replacement) and `block_rewrite` (model-guided replacement) is conceptually correct, but has execution risks:

*   **Fuzzy and Formatting Mismatches:** Verbatim searches (`qmd.find(target_content)`) will fail on minor white-space variations, such as newlines (`\n`) introduced by formatting.
    *   *Fix:* The matching logic must normalize whitespace before comparison or use whitespace-insensitive regexes.
*   **Collateral Replacements:** Short `target_content` strings (e.g., swapping a bare `"9"` to `"7"` for class count) will cause disastrous collateral edits elsewhere in the paper (e.g., editing `0.95` or `Section 9`).
    *   *Fix:* Ensure `target_content` includes surrounding context (e.g. `"9-class"` or `"9 CPC sections"`), and enforce that replacements only happen when a unique match is found within the specified `target_section`.

---

## 4. Loop & Convergence: Exit Conditions and Rollback Policy

*   **Loop Soundness:** The loop bounds iterations with `max_rounds` (default 2), preventing infinite runs. Exiting on Engine C's `p0_count == 0` is correct and aligns with the safety-net design.
*   **Crash Recovery Risk:** If `apply_tasks` or `render_pdf` throws an exception (e.g. PDF generation crash due to bad LaTeX), the process will terminate before hitting the validation gate check, leaving the repository in a corrupted/unrenderable state.
    *   *Fix:* Wrap the loop body in a `try...except` block, ensuring that any crash triggers `rollback(run_dir, round)` before exiting or re-raising the error.

---

## 5. Answers to Open Questions (Section 9)

1.  **Temporal Split Routing:** **Confirm routing to `block_rewrite`.** Re-writing a temporal split claim requires adjusting surrounding grammar and context. A deterministic `value_swap` is too brittle.
2.  **Rollback Policy:** **Confirm STOP on validation failure.** Retrying with a weak model (`big-pickle` / Hermes) under tight resources will likely repeat failures or waste execution budget. Stopping preserves the best valid draft.
3.  **Engine B Timing:** **Confirm Engine C + Loop first.** Landing the deterministic gate first validates the loop orchestration and editor engine without prompt-engineering noise.

---

## 6. Verdict: GO-WITH-CHANGES

### Must-Fix Punch List:
1.  **Correct Regexes in `consistency_gate.py`:** Update the temporal split regex to `20\d{2}\s*(?:--|[-–])\s*20\d{2}` and handle the `"evaluating on"` phrasing.
2.  **Distinguish CV Folds:** Guard the fold count regex so it does not trigger a false-positive on `"3-fold"` inner cross-validation.
3.  **Use Prose Word Count:** Do not rely on `mechanical_check.py` for word counts; use `compile_review._qmd_prose_words()` in the validation gate.
4.  **Supply `doi_map` to `verify_matrix.audit_run`:** Read `run_dir / "doi_audit.json"` to build the audit map before validation.
5.  **Robust Exception Handling:** Wrap the loop's task execution and rendering in `try...except` to guarantee rollback on a process or compile crash.
