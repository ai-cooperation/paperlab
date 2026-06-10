# WS3 — b worker capability-negotiated v2 contract (design for review)

## 🔒 LOCKED ARCHITECTURE (user decision 2026-06-10 — SUPERSEDES §2 A/B and §RESOLUTION below)

Three layers, each does ONLY its job. NEVER push deterministic work onto b/Worker.

| Layer | Does (only this) | Never |
|---|---|---|
| **chat.ai** (phone grill, user's own quota incl. deep-research) | the subjective/creative work: research direction + a **DOI list** + framing/experiment design. **Grill must push HARD to make this deep** — this is b's value. | does NOT verify DOIs |
| **b / Worker** | thin MCP handoff + task record. **Zero compute, no verify, no model calls.** "b only does what MUST be on b." | compute / verify / store-verified-metadata |
| **a (ac-2012 agent)** | takes the DOI list → **single-source CrossRef verify + complete canonical metadata** → real experiment / render / review. | triple-source verify (that's the ~23-min cost) |

- **The ~23-min cost was TRIPLE verification (CrossRef + S2 + OpenAlex)**, not "a re-doing b's work". Simplify to a **single CrossRef** call per DOI (~40 → ~20s). No layer pays the batch cost on a hot path; chat verifies nothing, b computes nothing, a does one cheap CrossRef per ref.
- **WS3 (b-side) real deliverable**: DEEPEN the grill so chat.ai emits a thorough structured research package (direction + DOI list + framing + experiment). The Worker just packages + hands off (one `/capabilities` fetch → build v2/v1 → pin schema_hash → sanitize free text). Grill does NOT verify DOIs.
- **WS2 reframe (a-side, corrects this session's commit bf76949)**: the "trust b's verified_refs + spot-check" path is WRONG. a's phase2 must instead: receive the DOI list → single-CrossRef verify ALL → complete metadata → build bib. Do NOT trust b; do NOT only spot-check. (The bib builder + LaTeX-escape from bf76949 are reusable; the trust/spot-check logic is removed.)
- Essence (the reflection): subjective deep-prep → the model (chat); deterministic verification → a, mechanically; b is a thin pipe.

Everything below (§0–§4) is the pre-decision exploration, kept for rationale only.

---

## 0. Philosophy (must hold)
The whole determinism program: move "must-be-correct" work from
weak-model-generates→gate-repairs to deterministic/by-construction, so each
gate and revision loop disappears. WS3 is the b↔a interface layer. Same rules:
- **capability negotiation, NOT deploy-by-convention** (codex's correction to the plan).
- **never trust the producer's claim**: b's verified_refs are re-verified server-side.
- **never let b's free text reach a's render unsanitized** (injection defense at the source).
- **honest verification**: a full authenticated b→a v2 e2e needs a logged-in claude.ai
  session (chat-side) — cannot be driven headless. We verify negotiation logic +
  /capabilities + typecheck + sanitize, deploy, and report the chat-side remainder.

## 1. Current state

### a-side (DONE, deployed ac-2012)
- `GET /capabilities` → `{contract_versions:[1,2], schema_hash:"966d06dbad9fab9e",
  schema_url, experiment_recipe_ids:["hupd_classical_ml_v1"], max_payload_bytes:1_000_000,
  renderer, reviewer_chain}` (verified live).
- `POST /jobs` v2 executability gate → 422 if an experiment block doesn't resolve
  against the recipe registry.
- phase2 consumes `literature.verified_refs`: builds references.bib/metadata.json
  by construction, **spot-checks** a deterministic sample vs CrossRef (skips the
  ~23-min full re-verify); failing sample escalates to the full doi_gate.
- post-run `validate_real_results` (v2 experiment must satisfy resolved plan) +
  per-run `provenance.json`.
- v2 contract_v2.schema.json: required `[job_id, topic]`; optional blocks
  `framing{gap,claims[],positioning}`, `literature{min_count, verified_refs[]}`,
  `experiment{recipe_id,dataset,tasks,models,baselines,metrics,ablations,eval_protocol}`,
  `artifacts{tables,figures}`. `verified_refs[]` item: `{key, doi?, title?, authors[]?,
  year?, abstract_ref?, verified(bool, required)}`.

### b-side (current, ~/projects/paperlab-kb/workers/, TS Cloudflare Worker)
14 MCP tools. Flow:
`start_brainstorm`→`confirm_direction(decisions A/B/C ×5)`→`add_seed_ref`(KV session)
→`propose_proposal`(markdown skeleton)→`save_project`(D1 row + R2 markdown)
→`submit_to_pipeline`(reads project, builds **v1** contract, POST /jobs).

Key constraint: structured data (seeds[] with source_url DOIs, decisions) lives
ONLY in the KV brainstorm session (24h TTL). The **project** (D1+R2) persists only
proposal markdown + scalar decision fields (field, innovation_strategy,
data_source, journal_tier, output_scope, seed_ref_count). `submit_to_pipeline`
operates on `project_id` and may run after the session expired.
`submit_to_pipeline` already accepts an optional `research_contract` override arg
that is merged over the built contract (`{...base, ...overrides}`).

## 2. The fork: how does structured v2 data reach submit_to_pipeline?

### Option A — override channel (proposed)
Chat passes structured fields through the EXISTING `research_contract` override:
`submit_to_pipeline(project_id, research_contract:{framing, experiment,
literature:{verified_refs}})`. Server then:
1. sanitizes every b-provided free-text field,
2. `GET /capabilities`,
3. **server-side re-verifies** each verified_ref DOI via CrossRef (sets `verified`
   honestly; chat's say-so is not trusted),
4. builds a v2 contract iff a advertises v2 AND (no experiment block OR
   experiment.recipe_id ∈ advertised recipe_ids), pinning `schema_hash`,
5. else builds v1 (current behavior).
- Pros: no schema migration; smallest unverifiable surface; fully typecheckable;
  forward-compatible (can persist later). Tool description guides chat to fill
  framing.gap/claims + experiment from the grill it already ran.
- Cons: depends on chat passing the structured override; if chat omits it, the
  job is v1 (graceful degrade, not failure). Structured data not persisted.

### Option B — persist intake sidecar
`save_project` also writes `projects/{id}.intake.json` (decisions + seeds +
optional framing/experiment). `submit_to_pipeline` reads it, server-verifies DOIs,
builds v2.
- Pros: survives session TTL; structured intake is durable + auditable.
- Cons: larger change (project-session, projects-store, mcp, pipeline); more code
  that can't be fully e2e-verified headless; needs save_project to accept the new
  structured args anyway (same chat dependency as A for framing/experiment).

## 3. Proposed implementation (Option A)

### pipeline.ts
- `fetchCapabilities(base): Promise<Caps|null>` — `GET /capabilities`, 8s timeout,
  null on any error (→ fall back to v1, never block submit on a capabilities miss).
- `sanitizeFreeText(s)` — strip control chars; neutralize LaTeX specials
  (`\ & % # _ $ ~ ^ { }`) and Markdown/HTML risk (leading `|`, backtick fences);
  cap length. Applied to topic/research_question/contribution + framing.gap,
  each claim, every verified_ref title/authors, table/figure captions.
- `verifyRefs(refs): Promise<VerifiedRef[]>` — for each ref with a DOI, CrossRef
  `works/{doi}` (reuse literature.ts verifyDoi); set `verified` from the 200/404;
  fill title/authors/year from CrossRef truth (overrides b-claimed); drop or keep
  with verified:false? → keep with honest flag (a filters verified===true).
  Bounded concurrency, total cap (e.g. ≤40), per-call 8s.
- `decideContractVersion(caps, contract)` → `{version:1|2, schema_hash?, reason}`:
  v2 iff caps?.contract_versions includes 2 AND (no experiment OR
  experiment.recipe_id ∈ caps.experiment_recipe_ids). Pin caps.schema_hash.
- `buildResearchContract` extended: when v2, add `contract_version:2`,
  `schema_hash`, sanitized `framing`, validated/sanitized `experiment`,
  `literature:{min_count, verified_refs}` (server-verified). v1 path unchanged.
- Payload size guard vs caps.max_payload_bytes (abstracts are abstract_ref, not inline).

### mcp.ts
- Extend `submit_to_pipeline` tool description: chat MAY pass research_contract
  with framing{gap,claims} + experiment{recipe_id,...} + literature{verified_refs}
  collected during grill; server verifies + negotiates. No new required args.
- (Optional, deferred) extend grill tool descriptions to emit structured
  framing/experiment alongside markdown — description-level, no server change.

### Verification I can do headless
- `npm run typecheck` (tsc --noEmit).
- Pure-function checks for sanitizeFreeText / decideContractVersion (node harness).
- Live `GET /capabilities` already confirmed.
- `wrangler deploy` (HTTPS push to ai-cooperation/*).
- CANNOT: authenticated b→a v2 e2e (needs chat.ai login + a saved project) — report as chat-side TODO.

## RESOLUTION (codex rate-limited; reviewed by agy 2026-06-10, converged with own crux analysis)
- **Decision: Option B**, but the carrier is *verified canonical metadata*, not raw seeds.
- **DOI cost split (the crux)**: NEVER re-verify at submit (Worker subrequest cap ~50 +
  wall-clock budget; 40 CrossRef calls would blow it). verify_doi runs at GRILL time →
  store CrossRef canonical metadata in the session seed → save_project persists it to an
  R2 sidecar `projects/{id}.intake.json` → submit READS the sidecar (no CrossRef) → a-side
  spot-checks as the safety net. b verifies once, honestly; a samples. Symmetric to a's doi_gate.
- Q2 verified:false → drop CrossRef-404 (fake) refs, block if below min_count; KEEP non-DOI
  (arXiv) refs with verified:false (renderer still needs them).
- Q3 unsupported recipe_id → do NOT silently downgrade AND do NOT hard-fail the whole job;
  drop the experiment block + return an explicit warning (job still runs v2-literature / v1).
- Q4 /capabilities unreachable → v1 fallback but NOT silent (return pipeline_warning).
- Q5 schema_hash mismatch → downgrade to v1.
- Q6 sanitize: bibtex key strict regex ^[A-Za-z0-9_:.-]+$, DOI regex + urlencode, LaTeX ESCAPE
  (not strip) of \ { } % & $ # _ ^ ~.
- MUST-FIX ranked: (1) DOI split — submit never hits CrossRef; (2) Option B persistence;
  (3) bibtex key sanitize; (4) cache /capabilities ~15min; (5) LaTeX escape not strip.

## 4. Questions for the reviewer
1. A vs B given the determinism philosophy + verification constraints. Is the
   override channel an acceptable carrier, or does "structured grill fields" in
   the plan mandate persistence (B)?
2. verified_refs with verified:false — keep (honest, a filters) or drop before send?
3. Should b BLOCK submit when chat passes an experiment block whose recipe_id is
   NOT advertised (hard fail), or silently downgrade to v1 (graceful)? Plan says
   "submit v2 ONLY when experiment validates" — downgrade seems right, but does
   silent downgrade hide a chat mistake?
4. Negotiation failure modes: /capabilities unreachable → v1 fallback. Acceptable,
   or should it surface a warning to chat so the user knows they didn't get v2?
5. schema_hash mismatch (b built against an older schema than a advertises): pin
   a's advertised hash and send v2 anyway, or downgrade to v1? (a re-validates, so
   sending v2 is safe; but the contract may carry fields a's schema dropped.)
6. Anything in the injection-sanitize surface we're missing (BibTeX key injection,
   DOI field, author names with `\`)?
