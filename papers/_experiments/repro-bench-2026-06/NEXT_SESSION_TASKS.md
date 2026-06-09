# Paperlab Pipeline — Next-Session Handoff (end of 2026-06-09)

Read first: `memory/project_paperlab_pipeline_status.md`, then `SYSTEM_SPEC.md`, then this file.

## 1. What is DONE this session (Route A: real a-side pipeline)

The a-side fake pipeline (`run_newarch.py`: hardcoded 7.57 score, 1783-word stub prose, keyword
gates) is REPLACED by a real one. 11 commits on `main` (2f65a53 → 59b3868):

| commit | what |
|---|---|
| 2f65a53 | Route A real pipeline: `paper_driver.py` (Hermes phasefix driver, big-pickle), router→hermes, job_runner dispatch by driver |
| 88901de | Copilot = Engine B reviewer (big-pickle can't judge — hallucinates) |
| e93e141 | Copilot emits find_replace task list driving the revision loop |
| b8a6a25 | embed figures: .svg ref → .png twin fallback |
| 522f764 | renderer: frontmatter abstract, DejaVu/Liberation fonts (no tofu), blue linked citations |
| f539f60 | render-quality gate (broken PDF → P0 → fails meets_threshold) |
| 1520b1a | inline LaTeX math ($\pm$→±) + phase7 figure-correctness shift-left |
| 370f28d | TikZ architecture figures (journal-quality, not matplotlib boxes) |
| 2364e6e + 3979f6f | TikZ band-label overlap: template + deterministic normalize |
| 59b3868 | harden vs qmd "NN\|" line-prefix corruption + robust figure detection |

**Architecture (validated):** generation/rewrite = big-pickle (free); Engine C `consistency_gate.py`
= deterministic factual-contradiction gate (reliable trigger); Engine B = Copilot review/score +
qualitative tasks (honest, ~2.76 credits/call); `revision_tasks.py` task-driven loop + validation +
rollback; `render_qmd_reportlab.py` Springer render; `compile_tikz_figures` compiles model-authored
TikZ → png/svg; render-quality gate. **Core philosophy: don't trust the weak model's self-judgment —
enforce deterministically** (DOI gate, render gate, math conversion, TikZ label normalize all do this).

**Validated E2E (job routeA-e2e-003, system python `job_runner.py worker`):** status=done,
content_score 8.21, real 4702-word prose, real HUPD data (simulated=False), DOI gate real-rate 1.0,
TikZ architecture fig (correct: 2000 rows/300 resamples/5 classifiers/5-fold), 5 figures embedded,
abstract/citations(97 links)/± symbols correct, render-quality CLEAN.

## 2. The PRIMARY next task: connect b → a (serve the a-side + end-to-end)

The a-side LOGIC is done but was only validated by running `job_runner.py worker` directly with
**system python3**. The serving layer is NOT live and there is an env gap. To make the a-side
reachable from b (mcp.paperlab.cooperation.tw) and the phone/chat.ai:

### 2a. Fix the env mismatch (BLOCKER — verified gap)
- The FastAPI service uses `~/paper-job-service/newarch/.venv`; job_runner spawns the worker via
  `sys.executable`, so under the service the worker runs in `.venv`.
- `.venv` HAS pyarrow/sklearn/pandas/numpy but is **MISSING reportlab** → `render_pdf` would crash.
- Fix: `~/paper-job-service/newarch/.venv/bin/pip install reportlab` (+ verify the venv can import
  everything paper_driver/compile_review/revision_tasks need). System-level deps already present and
  shared: texlive+tikz, graphviz `dot`, pdftoppm/pdftocairo, pdflatex. Copilot token loads from
  `~/.env` inside paper_driver.copilot_env() (python-agnostic) — OK.
- Also confirm the venv python is ≥ the version paper_driver uses (3.10 ok).

### 2b. Start the a-side FastAPI service (persistent)
- App: `~/paper-job-service/newarch/http_app.py` (imports job_runner + router). Endpoints (see
  SYSTEM_SPEC §4 + job_service_schema.md): POST /jobs/dry-run, POST /jobs (idempotency key), GET
  /jobs/{id}/status, GET /jobs/{id}/result, GET /jobs/{id}/paper (PDF).
- Run: `cd ~/paper-job-service/newarch && .venv/bin/uvicorn http_app:app --host 127.0.0.1 --port <P>`.
- Make it a **systemd unit** (currently there is NO systemd unit for paper-job-service — it was run
  manually before). Set `PROJECTS_GITHUB_PAT` (repo creation), jobs dir, COPILOT_GITHUB_TOKEN env.

### 2c. Start cloudflared tunnel (paper-a.cooperation.tw)
- Only `cloudflared/paper-job-service-tunnel.example.yml` exists (a TEMPLATE). cloudflared is INACTIVE.
- Create the real tunnel config + credentials, bind `paper-a.cooperation.tw` → the uvicorn port, run
  as systemd. (See SYSTEM_SPEC §2; the b-side Worker calls a over this tunnel.)

### 2d. End-to-end b→a test with the NEW pipeline
- From the b side (chat.ai connector → mcp.paperlab.cooperation.tw, demo token
  `mcp_c1a3a599c63d4dff92fd491cc7aece96`): grill → confirm_contract → submit_to_pipeline → poll
  get_job_status → get_paper_result. OR hit the a HTTP endpoints directly first.
- ACCEPT: a real job submitted via HTTP runs the NEW pipeline (paper_driver, not run_newarch), in the
  venv, produces status=done + a real PDF (figures, abstract, dynamic score), retrievable via
  /jobs/{id}/paper. Confirm the b-side tools return it.

## 3. Secondary / remaining (lower priority)
- **Content P1s**: Copilot flagged real qualitative issues (feature confound, Bonferroni scope,
  overstated generalizability) — currently noted (P1), not fixed. Could feed P1 copilot tasks into the
  loop, or accept as author-revision items.
- **Journal-format exactness**: Scientometrics specs (84/174mm width, patterns+colour, max 234mm
  height), real co-authors, ethics/data-availability statements, scaled experiments — author-stage.
- **agy as 2nd reviewer**: blocked (AnyDesk passphrase + Antigravity session layer). Copilot suffices.
- **pre-commit hook**: uses `grep -P` (GNU) on macOS BSD grep → noisy errors, doesn't block commits;
  change to `grep -E` (file: `~/.git-templates/hooks/pre-commit`, security-sensitive — show diff first).

## 4. Gotchas / lessons (do not relearn the hard way)
- **Two python envs on ac-2012**: system `/usr/bin/python3` (where this session installed
  pyarrow/sklearn/brotlicffi/copilot + ran direct worker tests) vs service `.venv` (uvicorn/fastapi,
  missing reportlab). Align them or the b→a path breaks where the direct test passed.
- **Do NOT re-run phase7 on a completed run_dir**: phase7 precedes phase8 in the real flow (no qmd
  yet). Re-running it on a finished run made big-pickle rewrite the qmd with "NN\|" line prefixes
  (177 lines corrupted). Hardened now (renderer strips, gate flags RQ_LINEPREFIX, phase7 forbids qmd
  edits), but the lesson stands: run phases in order on a fresh run_dir.
- **Verify the artifact, not the claim**: served broken PDFs twice (missing figures, then corruption)
  before checking the actual PDF. Always pdftotext/image-count/gate-check before reporting "done".
- **Weak model (big-pickle)**: good at following edit instructions, CANNOT be trusted to judge
  (hallucinates) or to copy template fine-details (ignored `above left`). Use deterministic gates +
  post-processing for anything that must be correct.

## 5. Asset locations
- a-side code (dev): `papers/_experiments/repro-bench-2026-06/newarch/` → deployed to ac-2012
  `~/paper-job-service/newarch/`. Key files: paper_driver.py, consistency_gate.py, revision_tasks.py,
  compile_review.py, render_qmd_reportlab.py, job_runner.py, router.py, http_app.py.
- Hermes harness: ac-2012 `~/.hermes/hermes-agent/venv/bin/hermes`; big-pickle via zen-shim
  (systemd `zen-shim.service`, 127.0.0.1:8898). Skills copied to `~/paperbench/hermes-input/*.SKILL.md`
  (incl. figure-design).
- Copilot: `/usr/bin/copilot` (Node 22), token `COPILOT_GITHUB_TOKEN` in ac-2012 `~/.env` (600).
- b-side: `~/projects/paperlab-kb/workers/` → `mcp.paperlab.cooperation.tw` (deployed, working before).
- Example E2E run: ac-2012 `~/paper-job-service/newarch/_e2e/jobs/routeA-e2e-003/run/` (clean PDF).
