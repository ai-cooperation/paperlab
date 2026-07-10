# ADR-001: Deterministic assembly boundary (stop the format-variance patch treadmill)

Status: ACCEPTED — three-way consensus (this engineer + codex/gpt-5 + agy). Second
round resolved all 5 open questions; codex and agy converged fully.
Date: 2026-07-07
Supersedes backlog #16 ("review schema class fix via prompt + normalizer tolerance")

---

## RESOLUTION (second review, codex + agy converged)

- **Q1 (abstract location)**: abstract prose lives in `sections/00_abstract.md`,
  NOT in `metadata.json` — long LaTeX-heavy prose in JSON is an escaping trap
  (`\alpha`, quotes, newlines break validation). `metadata.json` stays strictly
  structural (title, authors, layout, bibliography keys, section order, review
  record). Both reviewers agreed.
- **Q2 (source map)**: essential for v1 but low-overhead. Assembler emits HTML
  comment markers around each block in the generated qmd —
  `<!-- SOURCE: sections/01_introduction.md -->` … `<!-- END SOURCE: ... -->` —
  so a xelatex crash is grep-traceable back to the source file. (agy's form;
  codex's sidecar JSON manifest is an equivalent alternative — pick the comment
  markers for v1 simplicity.)
- **Q3 (stale-render)**: do NOT fix stale-render as a separate pre-rebuild patch.
  Build the freshness invariant INTO the assembler: hash `metadata.json` + all
  ordered `sections/*`, write a render manifest beside the generated qmd/pdf, the
  render step always updates it, the delivery gate compares current source hash to
  the manifest, mismatch = BLOCKED (not warning). The stale-render bug disappears
  structurally. Both agreed.
- **Q4 (smallest slice)**: abstract + frontmatter + freshness TOGETHER (not
  abstract alone). metadata.json (title/authors/layout/bib/section-order) →
  read sections/00_abstract.md → assembler emits frontmatter + exactly one
  Abstract + abstract body + remaining legacy sections concatenated as-is →
  generated qmd marked generated, never edited by repair/heal → source-hash
  manifest + freshness gate → run a KNOWN double-Abstract case as the proof. This
  kills the highest-value defect class first and validates the boundary before
  touching review-record/citations/all gates. Both agreed.
- **Q5 (gate migration + CRITICAL healer rule)**:
  - MOVE to read `sections/` + `metadata.json`: abstract/duplicate-abstract,
    consistency (title/abstract/claims/section presence), claim-evidence, citation
    presence, prose length/section completeness, review-heal EDIT TARGETS, any
    gate that writes repairs.
  - KEEP on generated qmd/pdf: render success, PDF-surface checks, references
    rendered/non-empty, template/layout, delivery freshness, source-map diagnostics.
  - **CRITICAL (agy)**: the healing loop MUST edit source files
    (`sections/*.md` / `metadata.json`) and trigger re-assembly — NEVER edit the
    generated qmd (it is overwritten). A surface gate failing on content (e.g.
    page-10 text overflow) makes the healer modify the SOURCE section, not the qmd.

Backlog: replaces #16. Sequencing becomes: build the Q4 vertical slice (which
subsumes the stale-render fix via the freshness invariant), prove it on the
double-Abstract case, then expand to review-record and the remaining gates. The
current 4 jobs are the validation suite for the new architecture, NOT landed on the
old one.

---

## Context: the patch treadmill is a structural symptom

Over a multi-day V3.2 campaign we landed ~45 fixes. A large fraction are ONE
meta-class: **the LLM emitted a reasonable-but-non-canonical format/field
variant; the mechanical layer didn't cover it; we added one more rule after the
fact.** Recent evidence (real commits, last 2 days):

- `_extract_abstract` matched only `# Abstract` → missed `# Abstract {.unnumbered}`
  (fix) → then missed bold `**Abstract**` (fix). Two commits, one bug, and it
  produced a DOUBLE ABSTRACT in the delivered PDF that mechanical gates (floor
  84–86) passed — caught only by a human eyeballing page 1 at the VIP checkpoint.
- review-record: agent wrote `capability_decision_trace` list instead of flat
  fields (relocate fix) → then `score_0_10` instead of `score` (relocate fix).
- citation `[@key]` markers dropped in rewrites → empty References (prompt-pin +
  rendered-PDF gate).

The gates are being outrun by format variance. This is patch-not-loop, which our
own rule `feedback_build_the_loop_not_the_patch` warns against.

## The root cause is architectural, and it is SHARED by V2 and V3.2

Both architectures let **the model decide the final artifact format**:

- **V2** (`packs/paper/pipeline.py:_phase_write`): 7 workers write
  `sections/*.md` prose, then a `phase8_compose` BRAIN assembles them into
  `paper_draft_v0.qmd`. The compose prompt (line 451) literally says *"Assemble
  these section drafts ... Plus an Abstract you write. Frontmatter: title,
  author..."* — the model writes the Abstract AND the frontmatter AND decides
  layout. That is exactly where format variance (e.g. the double Abstract) enters.
- **V3.2** (current): same open loop, plus a growing pile of post-hoc normalizers
  and gates that try to catch each new model format variant after the fact.

So V2 and V3.2 are the SAME architecture on "who owns format": the model. V3.2
just added more after-the-fact catching. This is the open loop.

## Decision (proposed): move ASSEMBLY from the model to deterministic code

Three independent reviews (this engineer, codex/gpt-5, agy/Antigravity) converged
on: **take format out of the model's hands.** The model produces content values;
deterministic code produces artifact shape.

**This is NOT a rollback to V2.** V2's `sections/` split is kept (prose by LLM is
good). What changes is the ASSEMBLER: V2/V3.2 = LLM composes; this ADR = program
composes. One word — the assembler's identity — is the difference between an open
loop and a deterministic one, and it is the difference between a patch treadmill
existing or not.

```
V2:        LLM writes sections → LLM composes qmd (writes its own Abstract) → gates
V3.2:      LLM writes → LLM composes → post-hoc normalize variants → more gates   ← the treadmill
This ADR:  LLM writes sections + metadata VALUES → PROGRAM composes qmd → gates    ← variance source gone
```

### Chosen form: "Directory-as-Schema" (agy's refinement of codex's schema-first)

codex proposed a schema-first JSON boundary. agy pressure-tested it and found a
real trap: a single large JSON payload holding academic prose causes JSON-escaping
hell (LaTeX `$a^b$`, backslashes, newlines break the parser → infinite agent
self-correction) and degrades prose quality (LLMs write worse inside JSON string
tokens). Adopted refinement — put the schema boundary at the DIRECTORY level:

1. **Strict metadata** — `metadata.json`: title, authors, `abstract` TEXT,
   bibliography keys, review record. Validated against a JSON Schema at the
   tool-call boundary; retry on mismatch; NO post-hoc normalization on the happy
   path (normalizers demoted to legacy/migration only).
2. **Raw prose sections** — `sections/NN_*.md`: body prose only, NO Abstract
   marker, NO frontmatter. LLM writes these freely (judgment + prose stay with
   the model).
3. **Deterministic assembler** — reads `metadata.json`, emits the frontmatter and
   the abstract, appends sections in order, produces `paper_draft_v0.qmd` /
   `paper_springer.qmd` as GENERATED artifacts (no longer model-authored source of
   truth). The assembler NEVER injects a placeholder stub ("Abstract pending.");
   missing required structured content → `blocked+report`, not a placeholder PDF.

### Boundary rule (what stays vs moves)

- **Model keeps** (judgment + prose): abstract text, section prose, findings +
  severity rationale, review judgments, evidence/source intent, dimension score
  VALUES.
- **Code owns** (structure + delivery): YAML/frontmatter, heading levels + journal
  template, review-record field names/schema, citation-marker rendering from
  structured cite keys, References generation, pass/fail thresholds, hash binding,
  freshness, stale-render detection, PDF-surface gates.

### Domain-generality guard (D4: this engine must stay domain-general)

`metadata.json` carries `layout: paper|slides|report|...`; the assembler loads a
layout-specific template. Small VERSIONED IRs (`PaperDraftIR v1`,
`ReviewRecordIR v1`) with per-domain adapters — NOT one giant universal assembler,
NOT one free-form markdown contract. Domain-general = each domain has explicit
typed contracts + a deterministic renderer.

### Anti-treadmill guard (so the rebuild doesn't become its own treadmill)

**Decouple prose validation from structural validation** (agy). Gates validate
only STRUCTURE ("does `sections/01_introduction.md` exist and contain ≥ N words?
does `metadata.json` conform to schema?"), NEVER regex the prose body's format
style. The assembler owns layout/headings/fonts deterministically. This kills the
exact class of check (regex a heading marker variant) that produced this treadmill.

## Sequencing (proposed)

1. **Fix the one remaining stale-render bug first** (mechanical plumbing:
   format_repair=done → revalidate skips re-render → delivered PDF lags source).
   Small, all three reviews agree.
2. **Do NOT land the current 4 jobs on the old architecture.** codex + agy agree:
   relying on a human to catch double-Abstracts is an unsafe state; pushing jobs
   through creates sunk cost/rework. Instead —
3. **Build Directory-as-Schema**, then run the 4 jobs through it as the VALIDATION
   SUITE. If they pass the new system, the architecture is proven.

## Known costs / risks (stated honestly)

- Sizable rebuild: `paper_draft_v0.qmd` / `paper_springer.qmd` become generated,
  not authoritative; write/format_repair/review phases change shape.
- Debuggability: a xelatex error on generated-qmd line 452 won't map to a source
  file unless the assembler emits source maps / line→file mapping. (Mitigation
  required.)
- Round-trip edits: a fix in review_heal must edit `sections/*.md` /
  `metadata.json`, never the generated qmd (which is overwritten).
- Migration: in-flight jobs authored under the old model-owns-format contract need
  a migration path (the demoted normalizers serve here).

## Open questions for the second review (codex + agy)

Q1. Is "Directory-as-Schema" the right final form, or does putting the abstract
    TEXT in `metadata.json` reintroduce a smaller escaping problem (long prose in
    JSON)? Should the abstract also be a `sections/00_abstract.md` file that
    metadata only REFERENCES, so no long prose ever lives in JSON?
Q2. The assembler needs a source-map / line→file mapping for debuggability. Is
    that essential for v1, or acceptable to defer? What's the minimum viable form?
Q3. Sequencing: is "fix stale-render, then rebuild, 4 jobs as validation suite"
    correct — or should stale-render be folded INTO the rebuild (since the new
    assembler always re-renders, the stale-render bug may disappear for free)?
Q4. What is the smallest first vertical slice that proves the architecture without
    a multi-week rebuild? (Candidate: metadata.json + assembler for the ABSTRACT
    path only, leaving everything else as-is, to kill the double-Abstract class
    first and validate the boundary before expanding.)
Q5. Does making qmd a generated artifact break any existing gate that currently
    reads the model-authored qmd as source of truth (consistency gate, claim-
    evidence gate, prose gates)? Which gates must move to read sections/metadata
    instead?
```
