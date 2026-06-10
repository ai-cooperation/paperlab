# Paperlab — Next-Session Handoff (end of 2026-06-10)

Read first: `memory/project_pipeline_determinism.md` + `memory/project_paperlab_pipeline_status.md`,
then `PIPELINE_DETERMINISM_PLAN.md` (the plan, with codex review folded in), then this file.

## 1. System state — b→a is LIVE end-to-end (verified)

- **a-side**: ac-2012 FastAPI `paper-job-service` (user systemd, :8765) + cloudflared user systemd
  `cloudflared-paper-a` (Linger=yes) → `paper-a.cooperation.tw`. Reachable, serving.
- **b-side**: Cloudflare Worker `mcp.paperlab.cooperation.tw` (14 MCP tools), `PIPELINE_API_URL=
  https://paper-a.cooperation.tw`.
- **Verified live this session**: through the real b MCP endpoint, `get_job_status` / `get_paper_result`
  proxy a and return real data (job `proj_2026-06-09_b2a_e2e`: status=done, content_score 7.33,
  simulated=false, real PDF). a's POST /jobs runs the NEW pipeline (paper_driver) end-to-end.
- **Real Springer/elsarticle PDF render** is live on a (Quarto 1.5.57 + elsevier extension + xelatex +
  texlive). `render_springer.py` = deterministic frontmatter normalizer (writes a COPY, canonical qmd
  untouched) + bib sanitize + wide-table tbl-colwidths + double-spaced body / single-spaced refs.
  Served PDF = the real journal layout.

## 2. Determinism upgrade — WS0/WS1/WS2 DONE (a-side), WS3 + WS2-phase2 REMAIN

Goal (user's ask): move "must-be-correct" parts from "weak model generates → gate repairs" to
"deterministic generates → model only does the irreducibly subjective parts". Reduce model dependence.

### DONE (deployed to ac-2012 + tested + committed; commits 34b4d81 → 311cc8f → 8a57c13)
- **WS1 floor scoring** (`floor_score.py`): model-free 6-dim conservative score from existing artifacts
  (novelty excluded). When the model reviewer (Copilot) is down, the job completes `done` WITH a score
  but `meets_threshold=False` + `review_status=floor_only` (floor delivers, does NOT certify — codex's
  key correction). When the model scores, floor is attached as a cross-check (>2.5 divergence → P1
  hallucination flag). job_runner: public status enum unchanged; nuance in new `review_status` +
  `score_source`. `review_pending` retired.
- **WS2 core** (`tables.py`): results/ablation tables generated deterministically from
  `real_experiments/real_results.json`, wrapped in machine-owned `<!-- GENERATED:tbl-* sha256 -->`
  blocks. `inject()` replaces `<!-- TABLE:tbl-* -->` placeholders (phase8 prompt now emits these);
  `verify()` post-render tamper guard (→ P0 TBL_TAMPERED), wired into compile_review. Numbers
  correct-by-construction; column count/width controlled (no overflow).
- **WS0** (`capabilities.py`, `assets/contract_v2.schema.json`, `recipes/hupd_classical_ml_v1.json`):
  `GET /capabilities` (advertises contract_versions [1,2], schema_hash, recipe_ids, reviewer_chain),
  `GET /schema/contract_v2.schema.json`, and a `POST /jobs` v2 executability gate (a v2 contract whose
  experiment doesn't resolve against the recipe → 422 "experiment not executable" + field errors).

### REMAINING — do in this order next session
1. **WS2 phase2 consumption (a-side, small)**: in paper_driver phase2, if the contract carries
   `literature.verified_refs`, write references.bib + metadata.json from them and SKIP the ~23-min
   CrossRef re-verify (doi_gate still spot-checks a sample). This is what makes b's verified refs pay off.
2. **WS0 leftovers (a-side, small)**: provenance record per run (git commit of experiment code, deps,
   data snapshot hash, seed, schema_hash, real_results hash); wire `capabilities.validate_real_results`
   into the post-experiment flow.
3. **WS3 (b-side, TypeScript + Cloudflare deploy — the big one)**: `~/projects/paperlab-kb/workers/`.
   - grill tools (start_brainstorm/confirm_direction/propose_proposal) collect STRUCTURED v2 fields
     (framing.gap/claims, experiment design) instead of only free-text proposal_markdown.
   - search_literature/verify_doi populate `literature.verified_refs[]` server-side.
   - `submit_to_pipeline` (src/pipeline.ts postJob ~L200; contract build ~L140-175; src/mcp.ts L224+,
     L373): first `GET /capabilities`; submit a v2 contract ONLY when a advertises matching
     contract_version + schema_hash AND the experiment validates; else send v1. Pin `schema_hash`.
   - **Injection sanitize** all b-provided free text (titles/authors/abstracts/captions/claims) for
     Markdown/LaTeX before it can reach a's render.
   - macbook pushes ai-cooperation/* over HTTPS; deploy with `npx wrangler deploy`.
4. **Coordinated e2e**: b sends a v2 contract → a accepts (executability gate) → phase2 uses
   verified_refs → generated tables → render → review. If before 2026-07-01, Copilot quota is
   exhausted so it ends `done`/`review_status=floor_only` (real Springer PDF, floor score); after 7/1
   Copilot scores. Verify the whole chain.

## 3. Gotchas / lessons (do not relearn)
- **Two python envs on ac-2012**: service runs `~/paper-job-service/newarch/.venv` (has reportlab now).
  Always `scp` changed modules there + restart `systemctl --user restart paper-job-service` for
  http_app/capabilities changes; phase/render/score modules are picked up per job (no restart needed).
- **Copilot CLI quota**: only models auto/gpt-5-mini/claude-haiku-4.5 exist there and ALL bill to the
  exhausted `premium_interactions` pool (resets 2026-07-01). chat/completions are unlimited but the CLI
  can't reach them. Model pinned to claude-haiku-4.5. Until 7/1, reviewer = floor.
- **xelatex, not pdflatex** (unicode ∈); **bib must be sanitized** (`&amp;`/bare `&` abort xelatex);
  **wide tables need tbl-colwidths** (pandoc overflows unwidthed pipe tables — footnotesize alone fails).
- **Don't re-run a phase on a completed run_dir** (corrupts qmd); run phases in order on a fresh run_dir.
- **Verify the artifact, not the claim** (pdftotext / image-count / vision before reporting done).
- **pre-commit hook** is now the perl version (repo `.git/hooks/pre-commit` re-synced from the fixed
  template; the old grep -P version silently no-scanned). Commit messages with parens: use `-F msgfile`
  (zsh chokes on inline `$(...)` + parens).

## 4. Asset map
- a-side dev: `papers/_experiments/repro-bench-2026-06/newarch/` → ac-2012 `~/paper-job-service/newarch/`.
  New this session: `floor_score.py`, `tables.py`, `capabilities.py`, `render_springer.py`,
  `assets/` (elsevier extension, scientometrics.csl, contract_v2.schema.json), `recipes/`.
- b-side: `~/projects/paperlab-kb/workers/` (src/mcp.ts, src/pipeline.ts) → `npx wrangler deploy`.
- demo token: `mcp_c1a3a599c63d4dff92fd491cc7aece96`. Example clean job: `proj_2026-06-09_b2a_e2e`
  (status=done, real Springer PDF at /jobs/{id}/paper, repo ai-cooperation/paperlab-proj_2026-06-09_b2a_e2e).
- Plan: `PIPELINE_DETERMINISM_PLAN.md`. Commits: 34b4d81 (WS1) / 311cc8f (WS2) / 8a57c13 (WS0).
