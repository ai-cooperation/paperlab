# ADR-001 Slice 1 Implementation Plan: Deterministic Assembly (abstract + frontmatter + freshness)

Status: PLANNED — code-grounded, cross-reviewed (Plan agent design + codex review;
codex's 4 corrections folded in, all verified against the real code).
Date: 2026-07-07
Implements: ADR_001_deterministic_assembly.md RESOLUTION Q1-Q5.
Baseline: engine test suite 538 passed / 2 skipped (the 1 failing
test_real_patent_experiment is a pre-existing anaconda NumPy-2.x/scipy ABI break,
NOT engine code — env picks up /opt/anaconda3 not .venv).

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
