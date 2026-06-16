# B-side + Web Integration Plan — connect the proven a-engine

> The a-side general engine is proven ([ENGINE_STATUS.md](ENGINE_STATUS.md): beats golden).
> This plan wires it to the EXISTING b-side (chat.ai grill + paper-mcp Worker, [SYSTEM_SPEC_v2.md](SYSTEM_SPEC_v2.md),
> [PAPER_MCP_GRILL_DESIGN.md](PAPER_MCP_GRILL_DESIGN.md)) and the live web progress page (DESIGN §5.3).
> Principle (unchanged): subjective → chat; deterministic → a. Numbers never traverse chat.ai (thin handoff).

## 1. Target end-to-end flow

```
chat.ai grill (thin scope, no numbers)
  → paper-mcp Worker (b): derive_contract (structured answers, NOT prose)
      → a `/jobs/viability-probe`  ── viability verdict + contract_hash
      → store viability_lock (approved + hash)        [framework.submission rules]
      → submit_gate: refuse unless approved + hash-matched + viable
      → POST a `/v2/jobs` (the contract)  ── job_id + status_url returned immediately
  → a-side: pipeline.run_paper (full 11-phase, codex brain + free big-pickle) → R2 artifacts
      → writes dossier at every checkpoint
  → web `/projects/{id}` page polls a `/v2/jobs/{id}/status` (dossier projection) every 5s
      → research plan · b-gap · a-gap · tier decision · phase progress → final PDF + email on done
```

## 2. Contract: who calls what (the seam is already built on the a-side)

| step | caller | endpoint / function | status |
|---|---|---|---|
| derive contract from grill answers | b Worker | `framework.submission.derive_contract` (canonical rules; TS mirrors) | a-side DONE; TS thin client TODO |
| viability probe | b Worker → a | `POST /jobs/viability-probe` → `framework.viability.handle_viability` | **a endpoint TODO** (logic done) |
| viability-lock + submit gate | b Worker | `framework.submission.lock_for` / `submit_gate` | a-side DONE; TS mirror TODO |
| submit job | b Worker → a | `POST /v2/jobs` | endpoint DONE; **must call `pipeline.run_paper` TODO** |
| live status | web → a | `GET /v2/jobs/{id}/status` → `engine_routes.project_status` | DONE (projection shape pinned by test) |
| live page | web | `engine_project_page.html` (reference) → Hugo `/projects/{id}` | reference DONE; **Hugo adopt TODO** |

## 3. Concrete tasks

### a-side (ac-2012 — small, the hard part is done)
1. **Wire `/v2/jobs` to the real pipeline.** Today it runs only the bounded intake phase. Change
   `engine_routes.create_v2_job` to start `pipeline.run_paper(run_dir, contract, LiveDispatcher(run_dir=...))`
   in a worker subprocess (mirror `job_runner.submit`'s `start_new_session` so a redeploy can't kill an
   in-flight run — SYSTEM_SPEC_v2 §7), and return job_id immediately.
2. **Expose `POST /jobs/viability-probe`** wrapping `handle_viability` (collect/seed corpus → verdict +
   contract_hash). Returns the lockable ViabilityVerdict. (Grill calls it early; submit re-runs it.)
3. **Status projection already lives in the dossier** — `pipeline.run_paper` already checkpoints every
   phase, so `/v2/jobs/{id}/status` returns live progress with no extra work.
4. **Email-notify on completion** (`notify_email` already flows through submit per design §5.3).
5. **Decide /jobs routing**: keep the old `paper_driver` pipeline behind the flag for A/B, OR point the
   b-side at `/v2/jobs` directly. Recommend: b-side → `/v2/jobs` once a golden A/B passes.

### b-side (paper-mcp Cloudflare Worker)
6. **Thin client over the a-side rules** (do NOT reimplement logic): `deriveResearchContractFromSession`
   mirrors `derive_contract`; submit refuses without an approved hash-matched `viability_lock`
   (`submit_gate`); a PICOS/title change after approval → hash mismatch → re-probe. (framework.submission
   is the source of truth; the TS just calls the a-side or mirrors the hash.)
7. **Thin handoff (HARD)**: the grill passes ONLY structured scope choices (PICOS / scope enums), never
   dense numbers/findings — the a-side owns all numbers (ENGINE_GENERAL_SPEC §2.3; OpenAI Lockdown forces this).
8. **level/tier server-decided** — strip chat overrides (SYSTEM_SPEC_v2 §5).

### web (paperlab Hugo site)
9. **`/projects/{id}` dynamic page** = adopt `engine_project_page.html`: poll `GET /v2/jobs/{id}/status`
   every 5s, render the 4 blocks (research plan / b-gap / a-gap / tier) + phase timeline + final PDF link.
   No Hugo rebuild per update — it reads the live projection (design §5.3).
10. **submit returns the page URL immediately** (link resolves before content fills in).

## 4. Invariants to preserve (don't regress)

- Thin handoff: numbers never cross chat.ai.
- Deterministic gates re-run on the a-side independently (a weak grill/worker can't skip a gate).
- level/tier/source/target_journal are server-decided, stripped from chat overrides.
- Non-destructive deploy: `KillMode=process`, in-flight worker survives redeploy; md5-verify after scp.
- Production `paper-a.cooperation.tw` stays on the old pipeline until a golden A/B greenlights `/v2/jobs`.

## 5. Sequencing (smallest safe first)

1. a: `/v2/jobs` → run_paper (subprocess) + `/jobs/viability-probe` + email. Validate with a real submit.
2. web: `/projects/{id}` page over the projection (read-only; safe).
3. b: viability-lock + submit gate + derive-contract (thin client). A/B vs old `/jobs`.
4. Flip the b-side default to `/v2/jobs` once the A/B golden passes; retire the old loop behind a flag.
