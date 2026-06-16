# B-side + Web Integration Plan — connect the proven a-engine (codex-reviewed)

> The a-side general engine is proven ([ENGINE_STATUS.md](ENGINE_STATUS.md): beats golden).
> This plan wires it to the EXISTING b-side (chat.ai grill + paper-mcp Worker, [SYSTEM_SPEC_v2.md](SYSTEM_SPEC_v2.md),
> [PAPER_MCP_GRILL_DESIGN.md](PAPER_MCP_GRILL_DESIGN.md)) and the live web progress page (DESIGN §5.3).
> Principle (unchanged): subjective → chat; deterministic → a. Numbers never traverse chat.ai (thin handoff).
> **Codex-reviewed 2026-06-16** — corrections folded in (marked ⟵codex).

## 1. Target end-to-end flow

```
chat.ai grill (thin scope, no numbers)
  → paper-mcp Worker (b): deriveResearchContractFromSession (structured answers, NOT prose)
      → a POST /jobs/viability-probe  ── verdict + contract_hash (a-side RETURNS the hash ⟵codex)
      → store viability_lock {approved, contract_hash, schema_hash, engine_base_url} ⟵codex
      → submit_gate: refuse unless approved + hash-matched + viable + same schema/env ⟵codex
      → a POST /v2/jobs (Idempotency-Key) ── job_id + status_url returned <1s
  → a-side: detached subprocess runs pipeline.run_paper (full 11-phase) → R2 artifacts
      → writes dossier at every checkpoint; on crash marks dossier failed+traceback ⟵codex
  → web /projects/{id} polls a GET /v2/jobs/{id}/status (enriched projection) every 5s
      → research plan · b-gap · a-gap · tier · phase progress · STATUS · final PDF link → email on done
```

## 2. Contract: who calls what

| step | caller | endpoint / function | status |
|---|---|---|---|
| derive contract from grill answers | b Worker | mirror `framework.submission.derive_contract` (structured, not prose) | a-side DONE; TS TODO |
| viability probe (returns hash) | b → a | **`POST /jobs/viability-probe`** → `handle_viability` | **a TODO** (logic done) |
| viability-lock + submit gate | b Worker | `submit_gate`; lock = a-returned hash + schema_hash + base_url ⟵codex | a DONE; TS TODO |
| submit job (idempotent) | b → a | **`POST /v2/jobs` + Idempotency-Key** ⟵codex | endpoint exists; **must run run_paper + idempotency TODO** |
| live status | web → a | `GET /v2/jobs/{id}/status` → `project_status` (enrich ⟵codex) | DONE; **enrich TODO** |
| live page | web | `engine_project_page.html` → Hugo `/projects/{id}` | reference DONE; Hugo TODO |

## 3. a-side tasks (ac-2012 — the first work)

### 3a. `/v2/jobs` → real pipeline as a detached subprocess (THE first step)
- `create_v2_job`: normalize contract → init `dossier.json` immediately → spawn a **`v2-worker` subprocess**
  via `Popen(start_new_session=True)` (survives `KillMode=process`; mirror `job_runner.submit`) running
  `pipeline.run_paper(run_dir, contract, LiveDispatcher(run_dir=run_dir))` → return `{job_id, status_url}` **<1s**.
- The worker wrapper **MUST `try/except` the whole run and on failure write dossier `status=failed` + traceback
  tail** ⟵codex — else `/status` is stuck on the last phase forever.
- **Idempotency** ⟵codex: `_job_id` is deterministic → add an `Idempotency-Key` path (like old `/jobs`) +
  a run-dir lock file so a duplicate submit replays the job_id instead of clobbering the dir.
- **Concurrency = 1** on ac-2012 ⟵codex (`max_live_v2_jobs=1`): concurrent codex/hermes runs fight auth/
  quota/OpenAlex/CPU/the local gateway. Queue or 429 beyond that.

### 3b. `POST /jobs/viability-probe` + corpus cache by contract_hash ⟵codex
- Wrap `handle_viability`. It needs a CORPUS (poolable-k over real works) — `source_probe` only checks
  availability, it does NOT collect. So: collect once, cache at `jobs/_viability_cache/{contract_hash}/_corpus_cache.json`
  + `viability.json`. Submit re-uses the cached corpus if the hash matches (copy/hardlink into run_dir
  before `run_paper`; `meta_analysis.run` already reuses a corpus cache) — else re-collect.
- a-side **RETURNS the contract_hash** in the verdict; the b-side stores it, never recomputes it ⟵codex.
- **FIX the auto-pivot** ⟵codex: `handle_viability` currently LOGS a master auto-pivot but does NOT mutate
  the contract (PICOS/query unchanged). Implement the actual pivot (apply the candidate to the contract +
  re-derive hash) before submit, or downgrade it to "logged suggestion" honestly.

### 3c. Enrich the status projection ⟵codex
`project_status` must add: `status` (running|done|blocked|failed), `artifacts.pdf` (R2/path), `summary.floor_100`,
`summary.delivery`, `updated_at`/history tail. The web page needs the final PDF link + a terminal state.

### 3d. Operational hardening of LiveDispatcher under the FastAPI service ⟵codex
- `codex_bin` / `hermes_bin` = ABSOLUTE paths (systemd PATH won't have them); service runs as the user with
  a valid `~/.codex/auth.json` and correct `HOME`.
- **Big-pickle gateway health check**: if `127.0.0.1:8898` is down, drafts silently block — fail loud.
- Render deps in PATH: Quarto / xelatex / pdftotext / pdftocairo.
- **Process groups**: launch codex/hermes in their own group; on timeout kill the GROUP (else grandchildren leak).
- **Reaper**: uvicorn won't reap completed detached children — add a small reaper/supervisor.
- **Watchdog**: `max_steps` is not a time limit — add a wall-clock heartbeat + stale-job marker.
- Email-notify on completion (`notify_email` already flows through submit, §5.3).

## 4. b-side tasks (paper-mcp Cloudflare Worker, TS — after 3)
- Thin client; do NOT reimplement a-side logic. `deriveResearchContractFromSession`; submit refuses without an
  approved lock; PICOS/title change → hash (from a-side) mismatch → re-probe.
- **Lock = a-returned contract_hash + schema_hash + engine_base_url** ⟵codex — a staging lock must not
  authorize a production submit.
- **Thin handoff enforced MECHANICALLY** ⟵codex: the a-side REJECTS any contract carrying dense numbers /
  extracted findings / chat-supplied `level|tier|source|target_journal` (don't trust the convention).
- A/B config-routed: b has `A_ENGINE_ENDPOINT = /jobs | /v2/jobs`; old `/jobs` stays default until a golden A/B passes.

## 5. web tasks (paperlab Hugo — read-only, safe, can go early)
- `/projects/{id}` adopts `engine_project_page.html`: poll `GET /v2/jobs/{id}/status` every 5s; render the 4
  blocks (research plan / b-gap / a-gap / tier) + phase timeline + `status` + final PDF link. No Hugo rebuild.
- submit returns the page URL immediately (resolves before content fills).

## 6. Invariants (don't regress)
- Thin handoff, mechanically enforced (a-side rejects dense numbers / chat-set level·tier·source).
- Deterministic gates re-run on the a-side independently.
- level/tier/source/target_journal server-decided.
- Non-destructive deploy: `KillMode=process`, in-flight worker survives; absolute paths + md5-verify after scp.
- Production `paper-a.cooperation.tw` stays on the old pipeline until a golden A/B greenlights `/v2/jobs`.

## 7. Sequencing (smallest safe first — codex-endorsed) — STATUS 2026-06-16

1. ✅ **DONE + live-validated** — a: `/v2/jobs` → run_paper detached subprocess (3a) + exception→failed
   wrapper + idempotency + concurrency + enriched projection. Validated on the `engine-live-newarch` copy
   (port 8899, separate `PAPER_JOBS_DIR`): POST 0.02s, dossier immediate, worker survives uvicorn restart,
   a fresh-corpus run finished end-to-end (floor 70.8 > golden 62.2, delivery=pass, PDF 320KB).
2. ✅ **DONE** — a: `/jobs/viability-probe` + corpus cache by contract_hash (3b) + projection enrichment
   (3c) + op-hardening (3d: gateway health check, process-group kill, wall-clock watchdog) + auto-pivot fix.
   Live-validated: a direct probe on 2012 collected 2400 works → viable, max_k=8, cached.
3. ✅ **DONE** — web: `engine_project_page.html` renders the enriched projection (status/PDF/floor). Hugo
   `/projects/{id}` adopts it (read-only) — remaining = drop the template into the paperlab site repo.
4. ✅ **DONE (code)** — b: paper-mcp `probe_viability` tool + viability-lock (D1) + submit gate over the
   /v2 path + A/B routing. `tsc` clean. Remaining = `wrangler d1 migrations apply` + deploy (gated).
5. ◑ **config ready** — `A_ENGINE_ENDPOINT` (default `/jobs`). Flip to `/v2/jobs` ONLY after a golden A/B.

### Remaining to go live (deployment, gated — not code)
- a-side: deploy the v2 routes + viability_service to the PROD `paper-job-service` (or front `engine-live`
  behind the tunnel) with `PAPER_ENGINE_V2=1`; keep the old `/jobs` pipeline as the A/B oracle.
- b-side: `wrangler d1 migrations apply paper-mcp-db` (0002) + `wrangler deploy`; leave `A_ENGINE_ENDPOINT=/jobs`.
- Run a golden A/B (same contract through `/jobs` and `/v2/jobs`); when v2 ≥ old on the floor + gates, flip
  `A_ENGINE_ENDPOINT=/v2/jobs`. Production stays on the old loop until then.
