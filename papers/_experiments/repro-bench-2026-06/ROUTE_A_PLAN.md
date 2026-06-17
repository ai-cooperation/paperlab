# Route A Implementation Plan v2 — Real paper-draft via Hermes phasefix driver

> Supersedes the agy v1 draft (which misread the mechanism as `claude -p`). Verified 2026-06-08
> against ac-2012 + run dirs + behavior_notes.md. Decision locked: **dual-lane + hard DOI anti-cheat gate**.

## 0. What is actually true (verified, corrects v1)

- The execution harness is **Hermes** (Nous Research agentic CLI), installed in a venv on ac-2012 at
  `~/.hermes/hermes-agent/venv/bin/hermes`. NOT `claude -p`. No Agent SDK credits involved.
- The phase-by-phase driver **already exists and works**: ac-2012 `~/paperbench/run_hermes_phasefix.py`.
  It runs `hermes -m <model> --provider <provider> -z <prompt>` once per phase, `cwd=run_dir`, using
  files-on-disk as checkpoints. This is the fix for the context-compression hang (Hermes rotates session
  ids near the compression threshold and loses cwd/messages, so a single mega-session hangs).
- Models reach Hermes via providers. Free = `big-pickle` over `--provider custom` at local
  `http://127.0.0.1:8898/v1` (config: `~/.hermes/config.yaml`). Paid honest = `--provider gemini`
  (needs `GOOGLE_API_KEY`/`GEMINI_API_KEY`).
- **Benchmark verdict (behavior_notes.md): the free big-pickle-class model FABRICATES DOI verification**
  (marked 45 verified with 2 real HTTP calls; a 404 labeled VERIFIED). Honest performers (gemini, codex)
  are paid. => the free lane is only acceptable with a hard, independent CrossRef re-verify gate.
- Real HUPD experiment engine already exists and is genuinely real: `newarch/real_patent_experiment.py`
  (no simulated fallback) -> `real_experiments/real_results.json`. job_runner already probes the data gate.
- ac-2012 lacks claude CLI / `~/.claude/skills` / quarto+LaTeX, but **reportlab 3.6.8** is present
  (PDF via ReportLab fallback). Skills are copied as `~/paperbench/hermes-input/*.SKILL.md`.

## 1. Defect map (where the fakeness lives — confirmed)

`newarch/run_newarch.py` is a self-contained mock; the rot is entirely inside it (job_runner.py is sound):
- **Hardcoded 7-dim scoring**: lines 949-955 (novelty 5.8 / methodological_rigor 7.6 / evidence_validity 8.3 /
  literature_grounding 7.6|6.8 / result_interpretation 7.5 / limitation_honesty 8.4 / writing_coherence 7.8),
  `"critical synthesis"` keyword hack at 952, mean computed ~977. Scorer never reads prose.
- **Templated prose**: hardcoded Python string literals from ~line 1145. ~1783-word skeleton, mid-sentence truncation.
- **Keyword-only gates**: ~925-945 (presence of "TF-IDF"/"McNemar"/"not a new model" as proxy for quality).

## 2. The real wiring gap (the one-line root cause)

`job_runner.run_pipeline()` (lines 257-298) **ignores `routing_decision["driver"]`**. router.py already emits
per-level `driver` ("hermes" for master, "agy-codex" for phd/journal-paid) + `model_chain` + `lane` + `hooks`,
but run_pipeline always shells `run_newarch.py --model <m>` regardless, and run_newarch.py ignores the model.
Route A = make run_pipeline dispatch the **real Hermes phasefix driver** by `driver`, and have that driver emit
the artifact contract job_runner already consumes.

## 3. Integration contract (job_runner consumes — do NOT change job_runner)

extract_output() (job_runner.py 301-381) reads, from `run_dir`:
- `final_content_review_deterministic.json` -> `mean_7dim`, `problems[]`(severity P0/P1), `elite.desk_reject_probability`, `p0_count`/`p1_count`
- `gate_report.json` -> `no_p0`, `p1_count`, `no_prose_skeleton`, `prose_completeness_passed`, `prose_total_words`, `real_status`
- `newarch_trace.json`
- `real_experiments/real_results.json` -> `status`, `simulated`(bool), `simulation_markers`
- `metadata.json` -> list of refs each with `status` (DOI real-rate)
- `paper_draft_v0.pdf` (>1000 bytes)
The replacement driver MUST emit exactly these. This is the seam; everything else stays.

## 4. Model strategy (LOCKED: dual-lane + hard DOI anti-cheat)

| lane (router level) | driver | model/provider | review hooks | DOI gate |
|---|---|---|---|---|
| master `mvp/CPU-real` | hermes | `big-pickle` / custom @127.0.0.1:8898 | deterministic_content_review (7dim) | **hard CrossRef re-verify override** |
| phd `real-experiment` | hermes | `gemini` / provider gemini | + elite_review | hard CrossRef re-verify override |
| journal paid | hermes | `gemini` (fallback codex) | full 3-layer | hard CrossRef re-verify override |

Note: unify the paid lane onto **Hermes + `--provider gemini`** (one driver, two providers) instead of router's
current literal `"agy-codex"`. Small router edit: paid `driver` -> `"hermes"`, `model_chain` -> `["gemini"]`
(keep `["codex"]` as fallback). The anti-cheat DOI gate runs on **every** lane — it is what makes the free
big-pickle lane safe despite the model's proven DOI dishonesty.

## 5. Staged implementation (each step independently verifiable)

### Stage 0 — prereq verification (no code)
- Confirm Hermes venv runs: `~/.hermes/hermes-agent/venv/bin/hermes --version`.
- Confirm big-pickle endpoint live: `curl -s http://127.0.0.1:8898/v1/models`.
- Confirm gemini creds present for paid lane (`GOOGLE_API_KEY`/`GEMINI_API_KEY` in Hermes `.env`).
- Sync latest skill files into `~/paperbench/hermes-input/` (paper-draft, doi-verifier, simulated-data,
  mvp-gatekeeper, paper-review-skill, elite-reviewer-audit).
- **Accept**: all three checks return OK; hermes-input has the 6 skill .md files.

### Stage 1 — parameterize the phasefix driver
- Fork `run_hermes_phasefix.py` -> `paper_driver.py` (live at ac-2012 `~/paper-job-service/newarch/`).
- Remove hardcoded topic + MVP-only BASE_REQUIREMENTS; inject from `contract.json` (topic, research_question,
  contribution, target_journal). Add a `--lane` switch: `cpu-real` (real data, no `^S^`) vs `mvp` (simulated).
- Keep per-phase fresh-process + file-checkpoint + verify + `--resume-from` (the hang fix — do not regress it).
- **Accept**: dry-run on a fixture contract produces `phase1_concept.md`, `references.bib` (>=35 entries),
  `phase4_structure.md`; topic in outputs matches the contract, not the old hardcoded patent topic.

### Stage 2 — job_runner dispatch by driver
- In `run_pipeline()`: branch on `routing_decision["driver"]`. For `"hermes"`, invoke `paper_driver.py
  --run-dir <run_dir> --model <model_chain[0]> --provider <derived> --lane <derived>`. Preserve attempts/log/
  timeout/fallback semantics already there.
- **Accept**: a master-tier job runs paper_driver (not run_newarch.py); `worker.log` shows hermes phase calls;
  job reaches a real `run_dir` with phase artifacts. job_runner.py diff is confined to run_pipeline.

### Stage 3 — real HUPD data into Phase 7 (CPU-real lane)
- Before Phase 7, driver runs `real_patent_experiment.py` -> `real_experiments/real_results.json` (real, CPU).
- Phase 7 prompt for `cpu-real` lane: read `real_results.json`, populate tables/figures with **real** values,
  drop `^S^`. Inject the CPU-only/BERT-excluded limitation directive into Phase 8.
- **Accept**: `real_results.json` has `simulated=false`, real f1_macro; tables/figures show those exact values;
  no `^S^` markers in the master-lane QMD.

### Stage 4 — hard DOI anti-cheat gate (makes free lane safe)
- After Phase 2, driver runs `doi_audit.py` / `verify_matrix.py` to independently re-check each DOI against
  CrossRef. **Override** model-claimed `status` in `metadata.json` with the independent result; compute
  `doi_real_rate`. Fail-closed if real-rate < threshold (e.g. 0.80) -> job `blocked` with reason.
- **Accept**: feed a known-fabricated metadata.json; gate flips the bogus `verified` to real status and the
  job blocks when real-rate is below threshold. (Directly neutralizes the proven big-pickle DOI lie.)

### Stage 5 — real 3-layer review -> scoring artifact (kills the 7.57 constant)
- After Phase 8/9, driver runs the review skills via Hermes phases: mvp-gatekeeper -> `mvp_check_report.md`,
  paper-review-skill -> `paper_review_report.md`, (elite tiers) elite-reviewer-audit -> `elite_audit_report.md`.
  Each review prompt MUST emit a trailing fenced ```json block with structured scores (robust parsing).
- A deterministic `compile_review.py` parses those JSON blocks -> writes `final_content_review_deterministic.json`
  (real `mean_7dim`, `problems[]`, `p0/p1_count`, `elite.desk_reject_probability`) + `gate_report.json` +
  `newarch_trace.json`. No hardcoded constants anywhere.
- **Accept**: two different papers produce two different `mean_7dim` (NOT 7.57); scores demonstrably track
  prose quality (e.g. a deliberately gutted draft scores lower).

### Stage 6 — end-to-end acceptance
- Rerun a real master-tier job through job_runner worker.
- **Accept (Route A done)**: QMD >3000 words, no mid-sentence truncation; `mean_7dim` dynamic & prose-derived;
  DOI real-rate gate enforced; `paper_draft_v0.pdf` >1000 bytes; job status `done`; job_runner.py contract intact.

## 6. Risks & open questions

1. **Gemini creds for paid lane** — needs `GOOGLE_API_KEY` in Hermes env on ac-2012; verify before phd/journal runs.
2. **big-pickle endpoint uptime** — `127.0.0.1:8898` must be running; add a Stage-0-style health check the driver
   asserts before starting (fail fast, not mid-run).
3. **Phase 9 hang recurrence** — the one prior hang was phase9 (`partial_hung_after_qmd`). Mitigate with the
   existing per-phase timeout + `--resume-from`; consider splitting Phase 9 (gates) from render into two bounded phases.
4. **Review-skill JSON discipline** — parsing depends on the review phases emitting the trailing fenced JSON;
   enforce it hard in the prompt and fail the gate if the block is absent (don't silently default scores).
5. **Wall-clock** — free big-pickle was 2h08m; gemini ~7m. master lane timeout already 21600s; fine. Surface
   per-phase timing in newarch_trace.json so slow phases are visible.
