# ADR-001 Slice 1 Implementation Plan: Deterministic Assembly (abstract + frontmatter + freshness)

Status: PLANNED v3 — v1 (Plan agent + codex) → 5-adversary stress test (3 gaps) → v2
→ codex + agy dual adversarial review of v2 (2 more blockers + agy found the deepest
one v2 under-weighted). v3 (§V3 below) closes all three-way-agreed gaps. §V3 supersedes
§V2 supersedes v1 where they conflict. NOT yet implemented; this is the plan of record.
Date: 2026-07-07 (v1) / 2026-07-08 (v2, v3)
Implements: ADR_001_deterministic_assembly.md RESOLUTION Q1-Q5.
Baseline: engine test suite 538 passed / 2 skipped (the 1 failing
test_real_patent_experiment is a pre-existing anaconda NumPy-2.x/scipy ABI break,
NOT engine code — env picks up /opt/anaconda3 not .venv).

---

## §V4. Final corrections from the v3 confirmation review (codex + agy converged; supersedes §V3 where they conflict) — IMPLEMENTATION BASELINE

v3 confirmation verdicts: V3-A CLOSED by both. V3-B STILL-OPEN (same missing input
found by both). V3-C NEW-HOLE (same root found by both + this engineer independently).
Both reviewers unprompted: step 1 (IR+schema) safe to start immediately.

### V4-A (= V3-A, closed) — no change. Batch reset = existing failure trigger OR staleness.

### V4-B — render source set, final enumeration
- ADD `research_contract.json` to RENDER_SOURCE_FILES: it drives table-template
  selection (tables.py:259 contribution_type, tables.py:373 figspec_for data_source)
  and title/journal/keywords fallback (render_springer.py:278/290/384-391).
- `renderer_fingerprint` must be CONTENT-DERIVED (hash of render_springer.py +
  tables.py + number_format.py + format_repair.py + assets/scientometrics.csl +
  assets/_extensions/**), not a manually bumped stamp (codex: manual stamps rot).
  Same for `assembler_fingerprint` (hash of engine_v3/assembly/*.py).
- figures: hash ALL files under figures/ (over-inclusive is safe for staleness —
  worst case an unused-figure change forces one extra re-render; never a missed stale).
- Quarto/xelatex binary drift: explicitly OUT of source-hash scope (documented
  reproducibility limit).

### V4-C — review-freshness stamp binds to SOURCES; two hash sets; explicit handler wiring
- **Root fix (agy's, better than skip-on-pass):** the review-freshness stamp
  (`reviewed_manuscript_sha256`) binds to what the reviewer/healer actually edits —
  `paper_meta.json` + abstract + ordered sections — NOT the derived qmd. New
  `paper_artifacts.review_manuscript_files(run_dir)`: returns the source set when
  `paper_meta.json` exists, else legacy `MANUSCRIPT_FILES` (qmd) for in-flight jobs.
  All 5 stamp call sites (paper.py:557, 1633, 1646, 2092, 2100) switch to it. Then
  `ensure_assembled` rewriting the derived qmd can NEVER invalidate a verdict — the
  qmd is out of the stamp set. Dissolves the mtime trap at paper.py:1651 structurally.
- **Two hash sets:** `ASSEMBLY_SOURCE_FILES` (paper_meta.json + abstract + section_order;
  triggers re-assemble) ⊂ `RENDER_SOURCE_FILES` (adds references.bib +
  research_contract.json + real_results.json + figures/* + fingerprints; feeds
  is_delivery_stale + the Z freshness conjunct). A figure-only change re-renders but
  does not re-assemble.
- **ensure_assembled is write-if-changed:** assemble in memory, compare bytes, write
  only on difference → idempotent, mtime-stable, needs no extra trigger manifest.
  No-op on legacy runs (no paper_meta.json) — old path stays live through validation
  (C4 preserved).
- **Explicit wiring (codex):** format_repair uses `_format_repair_handler`
  (paper.py:466/2075), NOT `_collect_gate_inputs` — ensure_assembled must be wired
  into BOTH handlers explicitly.
- **Orchestrator stays domain-neutral:** instead of a `manifest_source` string,
  PhaseSpec gains `staleness_probe: Callable[[Path], bool] | None = None`; the paper
  pipeline sets it to `manifest.is_delivery_stale` on format_repair. Zero paper
  strings in engine core (litmus preserved).

### V4 transition rules (keep prod safe)
- New-architecture behavior activates ONLY when `paper_meta.json` exists in the run.
  Legacy runs keep the existing composer/resync path untouched until 8a/8b (which land
  only after live validation).
- Z-gate freshness conjunct returns no findings for legacy runs (not applicable) —
  it must never block an in-flight legacy job.
- Section filenames stay FLAT (sections/introduction.md …) — `section_order` in
  paper_meta.json is the ordering source of truth; renaming to NN_ prefixes is
  cosmetic churn, skipped.

---

## §V3. Dual-review corrections (codex + agy on v2; 3 more gaps closed; supersede §V2)

codex + agy independently reviewed v2. Both: NOT ready. They converged on the SAME
structural truth from different angles. Root cause under all three: **v2's "check /
hash / re-run" sets were still drawn too narrow, and the re-assembly step had no
mechanical home.** All fixes below are three-way agreed and re-verified against the code.

### V3-A. Batch re-render trigger is ADD-staleness, not SUBSTITUTE (fixes V2-A)
v2 made the batch `format_repair done->blocked` reset conditional on
`is_delivery_stale`. WRONG: batch revalidate's legitimate job includes "a gate/threshold
changed, sources did NOT move, force a re-render + re-validate" — the exact case
`tests/test_revalidate_v3_batch.py:63-88` exercises ("PDF content-quality validation
missing"). Conditional-on-stale skips that forever → infinite failed revalidation.
- **Fix:** the batch reset fires on `(existing delivery-gate/acceptance failure trigger)
  OR is_delivery_stale`. Staleness is ADDED as a reason to re-render, never SUBSTITUTED
  for the existing failure-driven trigger. `is_delivery_stale` is still the shared
  predicate the orchestrator line-62 skip consults; the batch keeps its own
  failure-driven trigger AND gains the staleness one.
- Tests: `test_batch_reset_on_gate_logic_change_unchanged_sources` (re-render still
  happens), `test_batch_reset_also_on_stale_sources`, `test_orchestrator_skip_uses_shared_is_delivery_stale`.

### V3-B. Render manifest hashes EVERY deterministic render input (fixes V2-B)
v2 expanded to meta+refs+sections but still MISSED the non-prose render inputs. Verified:
`tables.generate()` reads `real_experiments/real_results.json` (tables.py:265-273) and
`format_repair.render()` injects tables (format_repair.py:31-42); `inject_figures()`
reads `figures/*` and rewrites the qmd (tables.py:400-408, 457-458). A real_results or
figure change with unchanged prose → stale tables/figures in the delivered PDF while the
hash says fresh.
- **Fix — `RENDER_SOURCE_FILES` = meta + all sections + references.bib +
  `real_experiments/real_results.json` + the `figures/*` files inject_figures consumes,
  PLUS a version stamp** (`assembler_version` + `renderer_version`) in the manifest so
  an assembler/renderer logic change (sources untouched) is also caught. Enumerate the
  render-input set FROM the code (grep every read in render_springer.render +
  format_repair + tables), not from memory — this is the discipline the 3 rounds taught.
- **sanitize_bib idempotency:** assert `sanitize(sanitize(x))==sanitize(x)`. agy flagged
  a real pre-existing bug: `re.sub(r"(?<!\\)&", r"\\&", t)` leaves a bare `&` on input
  containing `\\&` or `\&amp;` → xelatex crash. If the idempotency test reproduces it,
  fix the regex as a SEPARATE small commit (log it; not caused by the manifest, but the
  manifest's idempotency requirement surfaces it).
- Tests: `test_render_source_files_covers_all_render_reads` (grep-derived list),
  `test_manifest_flips_on_real_results_change`, `test_manifest_flips_on_figure_change`,
  `test_manifest_flips_on_version_bump`, `test_sanitize_bib_idempotent`.

### V3-C. Re-assembly is a first-class idempotent step wired into every qmd-reading phase (fixes V2-C — the deepest gap)
agy's blocker, verified in code: `_ensure_write_outputs_v3_2` early-returns if the qmd
exists (paper.py:731), and `_collect_gate_inputs` calls it ONLY when `phase=="write"`
(paper.py:494 region) — NOT in render_gates/review_heal/claim_evidence. So after the
healer edits `sections/*.md`, the qmd is NEVER re-assembled; the read-only gates re-read
the STALE qmd, see the same defect, fail forever → infinite heal loop, budget exhausted.
The ADR Q5 "re-assemble after heal" contract was stated as INTENT in v1/v2 but had NO
mechanical home. This is the crux that makes a read-only gate on a derived artifact
safe-or-not.
- **Fix — new `ensure_assembled(run_dir)`**: idempotent, re-assembles from current
  sources WHEN the source hash moved since the last assemble (uses the same
  `RENDER_SOURCE_FILES` hash; no-op when unchanged, so no wasted work). DROP the
  "early-return if qmd exists" — replace with "re-assemble iff sources changed."
- **Wire it at the START of `_collect_gate_inputs` for EVERY phase that reads the
  generated qmd**: write, claim_evidence, render_gates, review_heal, format_repair.
- **Also wire it into `revalidate_v3_batch` preflight** BEFORE the content validators
  run (revalidate_v3_batch.py:109-116 / 212-218) — codex's surface: batch preflight
  reads the generated qmd before any orchestrator re-assemble.
- THEN a read-only gate on the generated qmd is provably safe: the qmd is guaranteed
  freshly re-derived from current sources before any gate reads it. This is what makes
  V2-C's MOVE-vs-KEEP-READONLY split correct.
- Title-fallback fix CONFIRMED correct by both (assert rendered title == meta.title
  catches render_springer._old_title fallback at render_springer.py:48-52). Unchanged.
- Tests: `test_ensure_assembled_reassembles_after_source_edit`,
  `test_ensure_assembled_noop_when_unchanged`,
  `test_heal_edit_propagates_to_gates_no_infinite_loop` (THE regression for this gap),
  `test_batch_preflight_reassembles_before_validators`.

### V3-D. Unchanged (V2-D held under both reviews)
PhaseSpec trailing default field safe; migration nested-heading-as-body consistent;
fail-closed on stub abstract. No change.

### §V3 sequencing delta
`ensure_assembled` + `RENDER_SOURCE_FILES` + `is_delivery_stale` (shared predicate) are
built in steps 2-3 (manifest/assembler) and are the PREREQUISITES the wiring steps
consume. Wiring (steps 6-7) now MUST call `ensure_assembled` at the head of every
qmd-reading phase handler and in the batch preflight. The batch reset keeps its existing
failure trigger + gains staleness (V3-A). Everything else per §V2/v1.

### Meta-lesson (folded into memory)
Three rounds, one root cause each: I substituted "the set I imagined" for "the set the
code touches." Discipline now explicit in the plan: for any hash/check/re-run set,
ENUMERATE from the code; and a derived-artifact gate is only safe if the artifact is
provably re-derived before the gate — that re-derivation needs a wired home, not stated
intent.

---

## §V2. Stress-test corrections (3 real gaps closed; supersede v1 §4a/§4c/§6/§8)

Stress test verdict (all evidence re-verified against the real code before folding):
- **HELD (1):** write-phase/assembler integration — `max_repair_attempts=2` bounds the
  loop, fail-closed routes back to the model correctly (paper.py:427-434,
  orchestrator.py:136-141). No change.
- **HALF-FALSE-ALARM (1):** migration — the adversary shouted "migrate_legacy_run
  doesn't exist!" which is trivially true (it is what the plan WRITES). But it found a
  REAL sub-fact: only **1** real run dir has a qmd (`hupd-cpu-job-001-vip/run/`),
  **0** have a `sections/` dir, and `split_sections` (run_newarch.py) only matches
  level-1 `#` headings → nested `## Statistical Analysis` collapses into prose. See V2-C.

### V2-A. Freshness must be one shared predicate called by BOTH resume paths (was §4c)

Root cause the adversary confirmed: there are **two** resume paths, not one.
1. `orchestrator.py:62` — `if resume and phases.get(id)=="done": continue` (bare skip).
2. `revalidate_v3_batch.py:148-151` — batch reset: when `format_repair=="done"` it
   **unconditionally** rewrites it to `"blocked"` on disk to force a re-run.

v1 §4c only addressed path 1, AND path 2 has the opposite defect (it always re-runs,
never checks staleness). Fix — a **single shared predicate**, two callers:

- New `engine_v3/assembly/manifest.py::is_delivery_stale(run_dir) -> bool` — true iff
  the render manifest is missing, or the current source hash ≠ manifest hash, or the
  delivered PDF is older than any hashed source. (Wraps `freshness_findings`; the two
  share one implementation.)
- **Path 1 (orchestrator):** before the bare `continue` on a `done` phase, if the
  phase declares a freshness manifest (see V2-D `PhaseSpec.manifest_source`), call
  `is_delivery_stale`; if stale, DON'T skip — fall through to re-run. Non-stale → skip
  as today (no false re-render — closes the "every resume re-renders" risk).
- **Path 2 (batch revalidate):** change the unconditional `format_repair -> blocked`
  reset (line 148-151) to reset **only when `is_delivery_stale(run_dir)`**. So batch
  stops always-re-rendering and instead re-renders exactly when sources moved.
- Both paths now share ONE staleness definition — no drift between them. This is the
  "fix the class across ALL user-facing surfaces" rule applied: the stress test caught
  that I'd fixed one surface and left the second.

Tests: `test_orchestrator_resume_rerenders_on_stale_manifest`,
`test_orchestrator_resume_skips_when_fresh` (no false re-render),
`test_batch_revalidate_reset_only_when_stale`.

### V2-B. Freshness manifest has its OWN source set, taken AFTER render-time mutation (was §4a)

Two real facts the adversary confirmed:
1. `MANUSCRIPT_FILES = ("paper_draft_v0.qmd",)` (paper_artifacts.py:16) deliberately
   EXCLUDES `references.bib` — it is the *review-freshness* stamp set and must stay
   minimal (used by review_provenance at paper.py:557/1633/2092/2100). **Do NOT
   overload it** for the render manifest.
2. `sanitize_bib` (render_springer.py:354-364) **mutates `references.bib` in place** at
   render time (`&amp;`→`\&`, bare `&`→`\&`), AND `number_format.format_qmd`
   (format_repair.py:61) + `_repair_generated_content_quality_v3_2` (paper.py:1099)
   both mutate `paper_draft_v0.qmd` in place before `post_format_sha`. So "one
   pre-manifest normalization step" was false — there are ≥3 render-time source writes.

Fix — decouple the render manifest's hash set from `MANUSCRIPT_FILES`, and hash the
POST-normalization bytes:

- New constant in paper_artifacts.py: `RENDER_SOURCE_FILES: tuple[str,...] =
  ("paper_meta.json", "references.bib") + tuple(sections in section_order)`. The
  manifest hashes THIS set, not `MANUSCRIPT_FILES`. (Generated qmd is NOT hashed as a
  source — it is a derived artifact; hashing it would couple the hash to the two
  in-place qmd mutators.)
- **Ordering contract (deterministic, single point):** the render step runs, in fixed
  order: (1) assemble from sources → generated qmd; (2) ALL render-time source
  normalizers ONCE (`sanitize_bib` on references.bib; nothing mutates paper_meta.json
  or sections — those are model/healer-owned and frozen at render); (3) compute source
  hash over `RENDER_SOURCE_FILES` (now stable); (4) xelatex render → PDF; (5) write
  manifest. The generated-qmd mutators (`format_qmd`, `_repair_generated_content_quality`)
  run on the DERIVED qmd only and never touch a hashed source, so they cannot flip the
  hash. Idempotency of `sanitize_bib` is still asserted (`sanitize(sanitize(x))==sanitize(x)`)
  as a belt.
- Because `references.bib` IS now in the hashed set, a healer/model bib edit is
  detected (v1 missed this — the adversary's "MISSING FILE FROM MANIFEST" point).

Tests: `test_render_source_files_excludes_generated_qmd`,
`test_manifest_hash_stable_across_double_render` (assemble+render twice → identical
hash, proving sanitize_bib doesn't flip it), `test_bib_edit_flips_manifest`,
`test_sanitize_bib_idempotent`.

### V2-C. Gate migration — split MOVE into MOVE-vs-KEEP-READONLY (was §6)

The adversary confirmed a real class error in v1: some "MOVE to sources" gates guard
defects that **only exist after assembly** (cross-boundary), so reading per-section
sources loses them. Corrected disposition:

- `_validate_citation_distribution` (paper.py:2480): **KEEP reading generated qmd,
  READ-ONLY** (not MOVE). It detects a 30+30-citation dump spanning a section boundary
  — a *post-join* property invisible in any single `sections/*.md`. The healer edits
  sources; this gate validates the assembled artifact; that is correct as long as the
  gate never WRITES (it doesn't). Same for any distribution/cross-boundary gate.
- `_validate_title_language` (paper.py:2515): **read `paper_meta.json.title` (source of
  truth) AND assert the rendered title matches** — because `render_springer._old_title`
  (render_springer.py:48-52) silently falls back to `contract.get("topic")` if its
  regex misses, so validating only the source lets a fallback title reach the PDF. Gate
  reads meta title + asserts the generated springer frontmatter title equals it.
- `_validate_text_encoding` (paper.py:1537): **scan sources AND generated qmd**
  (superset, not a move). Mojibake can enter both at authoring (sources) and at
  assembly/normalization (generated). Scanning only sources loses assembly-introduced
  corruption. Cheap to scan both.
- `_validate_inline_heading_leakage` (paper.py:2631): **scan `sections/*.md` AND the
  generated qmd** (superset). Glued headings enter from prose (source) but the assembler
  source-map comments / joins could also introduce a glued line; scan both.
- `_validate_citations_rendered` (paper.py:2654): safe to MOVE to sections (it checks
  presence of `[@key]` markers, a per-section-visible property). Unchanged from v1.

Net rule (new, written into the plan): a gate MOVES to sources **only if the defect it
guards is visible in a single source file**. If the defect is a post-assembly / cross-
boundary / render-fallback property, the gate **STAYS on the generated/rendered artifact
but READ-ONLY** (never writes; the healer's write target is always a source). This is
the precise boundary v1 blurred.

### V2-D. Small contract + migration-scope corrections

- `PhaseSpec` (contracts.py:138) gains an optional `manifest_source: str | None = None`
  field (frozen dataclass, default None) so the orchestrator can ask "does this phase
  carry a freshness manifest?" at the line-62 skip. Only `format_repair` sets it.
  Domain-neutral (a path string), no paper strings in engine core.
- Migration scope is **1 real legacy job**, not "4". The "4 jobs" (DTP3/ESG/Transfer/
  e9e1) are the ac-2012 VALIDATION suite (step 10), not local migration inputs. Local
  migration is proven on `hupd-cpu-job-001-vip/run/` + the `golden_paper` fixture only.
- Migration heading split must handle nested `##`/`###` (not just level-1 `#` like
  `split_sections`): the migrator keeps a section's full subtree as that section's body
  (split on level-1 `#` boundaries, preserve inner `##` as body text — which is correct,
  since inner headings belong INSIDE the section file). Add
  `test_migration_preserves_nested_subheadings`.
- Migration fail-closed on unrecoverable abstract (stub/`Pending.`/missing) — reuse the
  quarantined `_ABSTRACT_STUB_RE` in migration.py; never write a stub section. Add
  `test_migration_fail_closed_on_stub_abstract`.

### §V2 sequencing delta
Insert before v1 step 6 (wiring): implement `is_delivery_stale` +
`RENDER_SOURCE_FILES` + `PhaseSpec.manifest_source` as part of steps 2-3 (manifest +
assembler), so the wiring steps 6-7 consume them. Steps 8a/8b (gate deletes/moves)
adopt the V2-C MOVE-vs-KEEP-READONLY split. Everything else unchanged.

---

---

## 0. Two hard constraints verified in the code (they shape everything)

1. **`metadata.json` is TAKEN.** In every run dir it is a list of ~47 bibliography
   records (`key/doi/title/authors/year/journal/status`), written by
   `run_newarch.py:296`, read as a list by `floor_score.py:88`, `job_runner.py:371`,
   `delivery_audit.py:98`. The ADR's structural metadata MUST be a new name:
   **`paper_meta.json`**. Verified: `golden_paper/metadata.json` is `list, len 47`.
2. **A domain-neutral hash primitive already exists.** `review_provenance.manuscript_sha256(run_dir, files)`
   (review_provenance.py:67) hashes an ordered file list. The freshness manifest
   reuses it — no new hashing code, stays engine-layer domain-neutral.

## 0b. codex review corrections (folded in, each verified)

- **C1 — KEEP the delivered-PDF gate.** Do NOT delete `_validate_pdf_rendered_no_stub`
  (paper.py:2266). The assembler proves the *generated qmd* is single-Abstract;
  only a gate on the *rendered PDF* proves the *user's actual artifact* is. It stops
  being the PRIMARY defense (structure now guarantees it) but stays as the
  delivered-artifact assertion — its failure now signals an assembler/render bug, not
  model variance. (Our own `feedback_gate_must_judge_rendered_artifact` law.)
- **C2 — `_validate_inline_heading_leakage` MOVES, not DELETE.** Verified paper.py:2638
  scans for headings glued to paragraph tails (`...conclusion. ## Related Work`).
  This enters from PROSE; a healer editing `sections/*.md` can still write it. The
  assembler placing SECTION headings on their own lines does not prevent a glued
  heading INSIDE a section body. So it MOVES to scan `sections/*.md`.
- **C3 — the manifest alone does NOT beat `phase_skip_done`.** Verified orchestrator.py:62:
  `if resume and dossier.phases.get(phase.id) == "done": continue` fires BEFORE
  `_can_resume_preflight_recheck`. A `format_repair=done` phase is skipped entirely on
  resume — adding `expected_outputs` does nothing. The freshness gate must run on the
  delivery path INDEPENDENT of phase status (see §4c). This is a real orchestrator
  change, not just a manifest write.
- **C4 — step 8 is too big for one commit; no feature flag needed.** Split the
  treadmill deletion. Keep the OLD blocking delivery gate live THROUGH the 4-job
  validation (step 10); delete obsolete source gates only AFTER validation passes.

---

## 1. New files (module `engine_v3/assembly/`, small files 200-400 lines)

| Path | Purpose |
|---|---|
| `engine_v3/assembly/__init__.py` | Exports: `assemble_paper`, `AssemblyResult`, `read_manifest`, `write_manifest`, `freshness_findings`. |
| `engine_v3/assembly/ir.py` | Frozen `PaperDraftIR` v1 + `SectionRef` + `Author`. `SCHEMA_VERSION="paperdraft.v1"`. Domain-general IR. |
| `engine_v3/assembly/metadata_schema.py` | `PAPER_META_SCHEMA_V1` dict + `load_paper_meta(run_dir) -> PaperMeta | list[str]` (validate; findings on mismatch). NO prose. |
| `engine_v3/assembly/assembler.py` | `assemble_paper(run_dir, *, layout="paper") -> AssemblyResult`. Reads paper_meta.json + sections/00_abstract.md + ordered sections -> generated qmd, one Abstract, source maps; fail-closed, never stub. |
| `engine_v3/assembly/layout_springer.py` | Paper/Springer (elsarticle) adapter. THE ONE place abstract placement per surface is decided. |
| `engine_v3/assembly/manifest.py` | `source_hash`, `write_manifest`, `read_manifest`, `freshness_findings`. Reuses manuscript_sha256. |
| `engine_v3/assembly/migration.py` | `migrate_legacy_run(run_dir) -> bool`. Legacy qmd -> paper_meta.json + sections. THE DEMOTED old regexes live here ONLY. |

Tests: `test_assembly_{assembler,manifest,metadata_schema,migration}.py` + the PROOF
`test_assembly_double_abstract_proof.py`.

## 2. `paper_meta.json` v1 (structural only — NO prose)

Required: `schema_version`(const "paper_meta.v1"), `layout`(enum paper|slides|report),
`title`(str), `authors`(>=1, each `name` req + `email?`/`affiliation?`),
`abstract_ref`(PATH `sections/00_abstract.md` — a REFERENCE, never prose),
`bibliography`(str), `section_order`(>=1 `sections/NN_*.md` paths).
Optional: `csl`, `keywords[]`, `journal`, `review_record_ref`.
`additionalProperties:false` so prose-in-JSON is REJECTED (guards Q1).
NOT in it: abstract/section prose, review record contents, YAML format block,
heading levels, thresholds.

## 3. Assembler (assemble_paper)

Frozen IR: `PaperDraftIR(schema_version, layout, title, authors, keywords,
bibliography, csl, journal, abstract, sections)` — `abstract` loaded FROM
sections/00_abstract.md, never from JSON. `AssemblyResult(ok, written,
blocked_findings, source_sha256)`.

Order (single Abstract by construction):
1. load_paper_meta -> validate -> findings => `ok=False`, write NO qmd.
2. load sections/00_abstract.md; missing/`<40` words => FAIL-CLOSED (no stub —
   kills render_springer.py:287 at source).
3. load each section_order path; missing/thin => fail-closed w/ exact path.
4. build PaperDraftIR.
5. `layout_springer.render_ir(ir)`: GENERATED_BANNER -> YAML frontmatter
   (title/authors/keywords/bib/csl/journal/format; **abstract NOT in draft
   frontmatter**) -> ONE `## Abstract`+body wrapped in source-map comments -> each
   section wrapped in source maps. For SPRINGER: `abstract: |` frontmatter block from
   ir.abstract (single source) + NO body Abstract heading. Abstract exists in exactly
   ONE place per surface, chosen deterministically by the adapter.
6. write paper_draft_v0.qmd + paper_springer.qmd (both start GENERATED_BANNER,
   overwrite-only).
7. write manifest (§4). return ok=True.

Source maps (Q2): `<!-- SOURCE: sections/NN.md -->` … `<!-- END SOURCE: ... -->`
around every block => xelatex crash grep-traceable to source file.
Fail-closed writes `assembly_block_report.json` (machine-readable), NEVER a
placeholder PDF.
Domain boundary: assembler.py + ir.py + manifest.py are domain-general; ALL
elsarticle/journal knowledge in layout_springer.py, selected by `meta.layout`.
Adding `slides` = new adapter, no assembler change (D4).

## 4. Freshness manifest

- File `render_manifest.json` beside generated qmd.
- Hashes ordered sources: paper_meta.json, sections/00_abstract.md, each
  section_order path, references.bib (via manuscript_sha256).
- Format: `{schema_version:"render_manifest.v1", source_sha256, source_files[],
  generated[], rendered:"paper_draft_v0.pdf", rendered_at, assembler_version}`.

### 4a. When it is written (C5 anti-treadmill — SINGLE pre-manifest normalization)
The render step writes the manifest AFTER all render-time source transforms
(including `sanitize_bib`). To avoid an infinite hash-flip loop: make source
normalization a SINGLE pre-manifest step — `sanitize_bib` runs ONCE before
assemble+manifest, and after that render is READ-ONLY except generated artifacts.
Normalize source bytes (strip trailing whitespace) before hashing so idempotent
re-runs are stable. `test_idempotent` + `test_render_twice_hash_stable` guard this.

### 4b. How the delivery gate reads it
`_format_repair_handler` adds `delivery_freshness = manifest.freshness_findings(run_dir)`
to gate_inputs. `freshness_findings` recomputes current source hash, compares to
manifest.source_sha256; mismatch OR missing manifest OR PDF older-than-any-source =>
findings. Z gate `_gate_delivery` gains `freshness_manifest_ok = not
delivery_freshness_findings` conjunct. Mismatch => `passed=False`,
detail "delivery is stale: sources changed after last render; re-assemble+re-render".

### 4c. C3 fix — freshness must run despite phase_skip_done
Because orchestrator.py:62 skips a `done` phase entirely on resume, the freshness
check cannot live ONLY inside the format_repair handler. Chosen fix (minimal,
verified-safe): make the resume skip freshness-aware — before `continue` on a `done`
`format_repair`, run `manifest.freshness_findings`; if non-empty, DON'T skip (re-run
the phase). Concretely: in `run()`, replace the bare `phase_skip_done continue` with
a guard that, for phases carrying a freshness manifest, re-runs when the manifest is
stale. Alternative considered (a dedicated always-run delivery-freshness gate phase
after format_repair) is heavier; deferred. Unit test: a `done` format_repair with an
edited source resumes into a re-render, not a skip.

## 5. Phase-table changes
- write: `_ensure_write_outputs_v3_2` rewritten to call `assemble_paper` (DELETE
  `_compose_qmd_v3_2` + hardcoded Abstract 906-908). WRITE_OUTPUTS gains
  paper_meta.json + numbered sections; keeps paper_draft_v0.qmd as a GENERATED output
  (so the missing-output loop still routes back to the model on fail-closed).
- format_repair: re-invoke assemble_paper + write_manifest at top (replaces the
  resync pile at 2097). Re-assembly idempotent.
- render_springer: DELETE _extract_abstract (55) / _sanitize_abstract (90) / the
  line-287 stub; becomes a thin xelatex driver on the already-correct springer qmd.
- DELETE: _compose_qmd_v3_2 (880), _ensure_paper_springer_source_v3_2 (916),
  _resync_springer_abstract_from_draft (938), _remove_frontmatter_abstract (975),
  _replace_frontmatter_abstract (992), _insert_qmd_yaml_flag (1015),
  _frontmatter_abstract (2549), _ABSTRACT_STUB_RE (2544).

## 6. Gate migration (codex-corrected)

| Gate | Line | Disposition | Note |
|---|---|---|---|
| `_validate_frontmatter_stub` | 2572 | DELETE (after step 7) | stub structurally impossible |
| `_validate_pdf_rendered_no_stub` | 2266 | **KEEP (C1)** | delivered-PDF single-Abstract assertion; NOT deleted |
| `_validate_inline_heading_leakage` | 2631 | **MOVE to sections/* (C2)** | glued heading enters from prose; healer can still write it |
| `_validate_citations_rendered` | 2654 | MOVE to sections/meta | qmd now generated |
| `_validate_citation_distribution` | 2480 | MOVE to sections | " |
| `_validate_title_language` | 2515 | MOVE to paper_meta.json.title | title now structural |
| `_validate_text_encoding` | 1537 | MOVE target set to sections/* + refs | " |
| `_validate_caption_claims` | 2448 | STAY (already source-aware; drop generated-qmd from its `sources`) | |
| `_validate_table_widths` | 2683 | STAY on paper_springer.qmd | render-surface |
| `_validate_render_log_overflow` | 2397 | STAY on .log | render diag |
| `_validate_pdf_references_rendered` | 2292 | STAY on rendered PDF | |
| `_validate_pdf_content_quality` | 2346 | STAY on rendered PDF | |
| `_validate_bib_author_integrity` | 2600 | STAY on references.bib | code-owned source |
| Z gate `_gate_delivery` | packs | EXTEND w/ delivery_freshness | §4b |

Net: 1 DELETE (deferred to step 8 after validation), 5 MOVE, 7+ STAY (incl. the
KEPT PDF gate), 1 EXTEND.

## 7. What the healer edits
REVIEW_HEAL_OUTPUTS drops paper_draft_v0.qmd/paper_springer.qmd; adds paper_meta.json
+ sections/*. Healer edits SOURCES only; re-assemble after heal/repair. Generated qmd
is overwrite-only, GENERATED_BANNER-marked, never an editable output (Q5 CRITICAL).
REVIEW_HEAL_PROMPT gains: "Fix content by editing sections/*.md and paper_meta.json
only; the qmd files are generated and will be overwritten — do not edit them."

## 8. Migration / back-compat
`assemble_paper` calls `migration.migrate_legacy_run(run_dir)` once when
paper_meta.json absent but a legacy qmd exists: parse frontmatter -> synthesize
paper_meta.json; extract body Abstract -> sections/00_abstract.md; split by headings
-> sections/NN_*.md (map legacy introduction.md -> 01_introduction.md); delete legacy
qmd; re-assemble. THE DEMOTED regexes (_frontmatter_abstract, old _extract_abstract)
live here ONLY. Best-effort + idempotent; unrecoverable => fail-closed (no stub),
route back to model. Migration mapper accepts both flat + numbered section names.

## 9. Test plan (TDD, tests first) — see agent design; key adds from codex:
- `test_render_twice_hash_stable` (C5): render twice, assert references.bib +
  generated qmd + manifest hash stable (no sanitize_bib flip loop).
- `test_done_format_repair_rerenders_on_stale_source` (C3): a `done` format_repair
  with an edited source resumes into a re-render, not phase_skip_done.
- KEEP `_validate_pdf_rendered_no_stub`'s tests (C1) — do not delete.
- PROOF: `test_assembly_double_abstract_proof.py` on golden_paper (verified it has
  the exact shape: draft `# Abstract` heading L17 + springer `abstract: |` L14).

## 10. Sequencing (codex-corrected — step 8 split, PDF gate kept through validation)
1. ir + metadata_schema + schema tests.
2. manifest + tests (hash stable, freshness pass/block, render-twice-stable).
3. assembler + layout_springer + tests (single-Abstract BOTH surfaces, source maps,
   fail-closed, never-stub, idempotent).
4. migration + tests.
5. PROOF test on golden_paper.
6. wire write phase (assemble_paper); update WRITE_OUTPUTS + 2 write-handler tests.
7. wire format_repair + Z freshness + **C3 resume-skip freshness guard**; strip
   render_springer stub. **Keep all OLD delivery gates live.**
8a. (after step 10 validates) delete _validate_frontmatter_stub + the dead
   render_springer/compose/resync functions.
8b. (after step 10 validates) MOVE the 4 source gates + inline-heading-leakage to
   sources.
9. healer round-trip (edit sources only; re-assemble after heal).
10. run the 4 real jobs (DTP3/ESG/Transfer/e9e1) as the validation suite on ac-2012
   through the new path, OLD gates still live. Only after single-Abstract fresh PDFs
   confirmed do 8a/8b land.

## 11. Slice-specific risks + mitigations
- paper_meta.json vs metadata.json collision -> use paper_meta.json everywhere;
  schema test asserts distinctness; migration reads qmd never metadata.json.
- section renumbering breaks flat WRITE_OUTPUTS names -> migration accepts both;
  section_order is source of truth; keep `sections/*.md` globs.
- window where a gate validates a derived artifact vs source-editing healer ->
  MOVE gates (8b) only AFTER validation, and never leave a resume path where the
  qmd is validated while the healer edits sources (C1 PDF gate covers the gap).
- springer/draft abstract divergence -> single abstract_placement decision per
  surface, unit-tested on BOTH surfaces.
- freshness false-positive from post-manifest source churn -> C5: single
  pre-manifest normalization, render read-only after.
- phase_skip_done bypasses freshness -> C3 resume-skip freshness guard.
