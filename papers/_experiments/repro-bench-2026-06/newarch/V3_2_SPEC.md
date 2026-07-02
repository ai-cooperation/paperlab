# Paper Engine V3.2 Spec

## Goal

V3.2 turns the V3.1 engine from a Hermes-driven pipeline with stronger
harnessing into a deterministic control plane with bounded Hermes workers.

The primary correction is architectural, not cosmetic:

- Do not use harness repairs to compensate for an underspecified loop.
- Do not let Hermes self-certify facts that gates must verify.
- Split high-homogeneity tasks into deterministic steps.
- Keep Hermes for semantic work where judgment, synthesis, or writing is needed.
- Add human checkpoints only where the decision cost is high and automation would
  hide uncertainty.

External requests remain `contract_version: 3`. The internal engine revision is
`3.2` and is represented by new artifact schemas, phase routing, and dossier
trace metadata.

## Design Thesis

V3.1 proved that stronger harnessing is necessary but not sufficient. It made
job state, runtime attempts, canonical artifacts, and PDF delivery more
observable. The revalidation jobs then exposed the real defect: the data phase
was still a large Hermes task. Hermes was asked to produce references, DOI
audits, extracted effects, results, and figures in one semantic pass; gates then
tried to normalize whatever shape Hermes produced.

That pattern is not loop engineering. It is:

```text
Hermes free-form generation
-> harness/gate catches drift
-> repair prompt
-> repeat
```

V3.2 replaces it with:

```text
deterministic control plane
-> bounded Hermes worker where useful
-> canonical state
-> deterministic validator
-> explicit repair route or human checkpoint
```

## Harness vs Loop Engineering Case Study

Paper Lab is now the concrete case for separating harness and loop design.

| Layer | General definition | Paper Lab V3.2 meaning |
|---|---|---|
| State layer | External memory, plan files, artifact records | Contract, dossier, candidate manifests, canonical artifacts, gate reports, repair log |
| Validation layer | Tests and validators that decide truth | DOI two-source verification, citation integrity, figure existence, PDF render, section numbering, table width checks |
| Harness layer | Boundaries around a worker | Runtime supervision, sandbox, expected outputs, candidate freezing, permissions, timeouts, skill bundle metadata |
| Orchestration layer | Multi-step task routing | Phase graph, deterministic substeps, retry routes, human checkpoints |
| Loop layer | Self-propelled execution until pass/block | Bounded phase loops with stop conditions and validator-owned truth |

The V3.2 rule is:

```text
Harness owns boundaries.
Loop owns progress.
Validators own truth.
State owns continuity.
Humans own high-decision-cost judgment.
```

## Task Homogeneity Routing

The engine must route work by homogeneity, verifiability, and decision cost.

| Task class | Examples | Owner | Why |
|---|---|---|---|
| High homogeneity, objectively verifiable | DOI verification, reference count, citation syntax, raw citation token detection, table width, section numbering, PDF render | Deterministic script/validator | Repetition is high; facts are checkable; model self-report is unsafe |
| Medium homogeneity, partially verifiable | Abstract-level effect extraction, claim-evidence mapping, figure narrative alignment | Tool-assisted bounded Hermes worker plus validator | Semantics matter, but outputs must still fit schemas |
| Low homogeneity, judgment-heavy | Research gap framing, contribution positioning, discussion, limitations, final acceptability | Hermes semantic worker plus optional human checkpoint | Quality depends on reasoning and taste; false certainty is worse than blocking |
| High decision cost | Topic viability, non-poolable evidence, weak literature base, final delivery quality | Human checkpoint or explicit blocked state | Automation should surface uncertainty, not bury it in repair loops |

## Version Evolution

### V1: Deterministic Control, Limited Agentic Behavior

V1 was more controllable because the flow was mostly deterministic:

- phases were explicit;
- artifacts were expected in known places;
- gates were closer to the core flow;
- failures were easier to localize.

The weakness was limited agentic recovery and weak contract handoff. It was
controllable, but not a mature loop.

### V2: Contract and B-side Handoff

V2 improved the front/back split:

- b-side produced a research contract;
- a-side consumed that contract;
- job records and URLs existed as a service boundary.

The main defect was a lane mismatch: some paths still behaved like v2 jobs even
when the product expectation had moved toward v3. V2 also still allowed a-side
phases to ignore important b-side framing.

### V3: Hermes-driven Pipeline

V3 introduced the Hermes+skill engine direction:

- a-side phases delegated to Hermes/Codex-like workers;
- expected outputs and gates existed;
- the engine aimed for automatic repair and delivery.

The defect was that Hermes was treated as the owner of whole phases. The data
phase in particular mixed high-homogeneity verification with semantic synthesis.
That made skill usage hard to observe and gate facts unstable.

### V3.1: Stronger Harness and Canonical Artifacts

V3.1 tightened the harness:

- runtime process supervision;
- candidate snapshots for every runtime attempt;
- canonical data artifact;
- canonical-first gate reads;
- same-phase repair for missing declared outputs;
- stricter PDF delivery validation.

The revalidation result was useful: jobs no longer disappeared silently, repair
attempts were visible, and canonical artifacts existed. But all three
revalidation jobs blocked in the data phase. This showed that V3.1 improved
observability without fixing the loop boundary.

### V3.2: Deterministic Control Plane plus Bounded Hermes Workers

V3.2 keeps the V3/V3.1 infrastructure but changes ownership:

- the orchestrator owns phase graph and retry routes;
- deterministic steps own verifiable facts;
- Hermes owns bounded semantic tasks;
- gates read canonical artifacts only;
- repair routes target failed substeps, not vague whole-phase prompts;
- high-decision-cost failures block with a human-readable decision report.

This is not a rollback to V1. It borrows V1's control-plane clarity while keeping
V3's runtime, candidate, and canonical artifact infrastructure.

## V3.2 Architecture

### Contract Layer

No public API break:

- external `contract_version` remains `3`;
- internal revision is recorded as `engine_revision: "3.2"`;
- b-side contracts may keep the current schema;
- a-side must preserve and consume `contract.framing` as hypothesis context, not
  as validated evidence.

### Control Plane Layer

The phase graph becomes the source of truth. A phase may contain substeps, each
with an owner:

```json
{
  "id": "verify_doi_two_sources",
  "owner": "deterministic",
  "inputs": ["references.candidates.json"],
  "outputs": ["artifacts/data/doi_verification.v3_2.json"],
  "validator": "doi_two_source",
  "repair_route": "top_up_references"
}
```

Allowed owners:

- `deterministic`
- `hermes_bounded`
- `validator`
- `human_checkpoint`

### Data Loop

The current monolithic `data` phase is split into a bounded data loop:

```text
1. normalize_contract
2. collect_reference_candidates
3. verify_doi_two_sources
4. top_up_references_if_needed
5. extract_abstract_level_effects
6. write_canonical_data
7. generate_figures
8. gate_A_E
```

Ownership:

| Step | Owner | Notes |
|---|---|---|
| normalize_contract | deterministic | Preserve b-side framing and topic constraints |
| collect_reference_candidates | Hermes bounded or search tool | Produces candidates, not truth |
| verify_doi_two_sources | deterministic | Produces verification fact used by Gate A |
| top_up_references_if_needed | bounded loop | Stops when floor passes or source exhaustion is reached |
| extract_abstract_level_effects | Hermes bounded plus schema validator | Produces structured effect candidates |
| write_canonical_data | deterministic | Converts validated facts into canonical artifact |
| generate_figures | deterministic script | Reads canonical data, not free-form Hermes text |
| gate_A_E | validator | Blocks or warns from canonical inputs only |

### Semantic Writing Loop

Hermes remains valuable for:

- gap and positioning;
- structure planning;
- section drafting;
- discussion and limitations;
- review/heal suggestions.

V3.2 makes those tasks bounded:

- each task receives the exact canonical inputs it may use;
- each task writes candidate outputs;
- validators decide whether candidates can be promoted;
- repairs target the failed validator evidence.

### Human Checkpoint Layer

Human checkpoints are not interactive prompts inside every run. They are terminal
states with decision reports. A job may block as:

```text
blocked:human_decision_required
```

Examples:

- fewer than 35 verifiable references after bounded top-up;
- no poolable or abstract-level extractable effects;
- evidence supports only a descriptive review, not the requested meta-analysis;
- final PDF passes mechanical gates but remains below VIP quality expectations.

The status page should expose the checkpoint reason, evidence summary, and
recommended options.

## Canonical Artifacts

V3.2 adds schema versioned artifacts while keeping V3.1 paths readable during
migration.

### Reference Candidates

`artifacts/data/reference_candidates.v3_2.json`

```json
{
  "schema_version": "paperlab.reference_candidates.v3.2",
  "topic": "...",
  "items": [
    {
      "title": "...",
      "doi": "...",
      "source": "b_contract|search|hermes",
      "reason": "topic match",
      "candidate_status": "unverified"
    }
  ]
}
```

### DOI Verification

`artifacts/data/doi_verification.v3_2.json`

```json
{
  "schema_version": "paperlab.doi_verification.v3.2",
  "total_candidates": 50,
  "retained_references": 38,
  "two_source_verified": 38,
  "two_source_rate": 1.0,
  "sources": ["crossref", "openalex"],
  "unverified": []
}
```

Gate A must read this artifact through canonical data, not Hermes-written
`doi_audit.json` directly.

### Effects

`artifacts/data/effects.v3_2.json`

```json
{
  "schema_version": "paperlab.effects.v3.2",
  "poolable_k": 8,
  "abstract_level_count": 8,
  "effect_rows": [],
  "non_poolable_reason": null
}
```

### Canonical Data

`artifacts/data/canonical.v3_2.json`

```json
{
  "schema_version": "paperlab.data.v3.2",
  "references": {
    "count": 38,
    "two_source_verified": 38
  },
  "verification": {
    "two_source_rate": 1.0,
    "source_artifact": "artifacts/data/doi_verification.v3_2.json"
  },
  "effects": {
    "poolable_k": 8,
    "abstract_level_count": 8,
    "source_artifact": "artifacts/data/effects.v3_2.json"
  },
  "figures": [],
  "human_checkpoint": null
}
```

## State Machine

V3.1 used a phase-level state machine:

```text
pending -> running -> normalized -> gated -> repair_needed -> done | blocked
```

V3.2 adds substep states:

```text
pending
-> running
-> produced_candidate
-> validated
-> promoted
-> repair_needed
-> done | blocked | human_decision_required
```

Repair must name the failed substep:

```text
repair:data.verify_doi_two_sources:top_up_references
repair:data.extract_abstract_level_effects:schema_fix
repair:write.claim_evidence:downgrade_claims
```

Generic whole-phase repair prompts are allowed only as a compatibility fallback.

## Gate Ownership

| Gate | V3.2 owner | Inputs |
|---|---|---|
| A references/DOI | deterministic validator | `canonical.v3_2.json`, `doi_verification.v3_2.json` |
| B claim-evidence | validator plus review brain for semantic claims | canonical data, claim map, manuscript |
| C figures | deterministic validator | figure registry and files |
| D readability | deterministic validator | manuscript |
| E research value | warning validator plus human checkpoint when evidence is structurally insufficient | canonical effects |
| F logic | deterministic checks plus review brain | manuscript, canonical data |
| R review/heal | bounded semantic loop | review artifacts |
| Z delivery | deterministic validator | PDF/render artifacts |

## Skill Engine Semantics

Skills are capabilities, not proof that a task was done correctly.

V3.2 records skill usage in candidate manifests:

```json
{
  "skill_invocations": [
    {
      "name": "doi-verifier",
      "declared_by": "orchestrator",
      "outputs": ["artifacts/data/doi_verification.v3_2.json"]
    }
  ]
}
```

For hard gates, skill usage alone is never sufficient. The artifact must validate.

## Implementation Slices

1. Add V3.2 artifact schemas and loaders.
2. Add a substep model to `PhaseSpec` or a new `PhasePlan` type.
3. Split the `data` phase into deterministic substeps while keeping the public
   phase id `data` for status compatibility.
4. Implement deterministic DOI verification artifact generation.
5. Make Gate A consume `canonical.v3_2.json` and fail closed when
   `two_source_rate` is missing.
6. Implement effect extraction schema validation and `effects.v3_2.json`.
7. Generate figures from canonical/effects artifacts.
8. Add human checkpoint state and status serialization.
9. Add regression tests for all new canonical artifact adapters.
10. Re-run three V3.1 blocked topics as V3.2 revalidation jobs.

## Acceptance Criteria

V3.2 is acceptable only when all of the following are true:

- A topic that lacks enough verifiable references blocks with
  `human_decision_required` or a precise data blocker, not a generic Hermes
  failure.
- Gate A never reads raw Hermes-authored DOI audit fields as the source of truth.
- Every V3.2 data job writes `canonical.v3_2.json`.
- Candidate manifests identify whether outputs came from deterministic code,
  bounded Hermes, validator, or human checkpoint.
- A failed DOI floor triggers reference top-up before consuming repair budget on
  a generic data prompt.
- A non-poolable topic produces an honest checkpoint or Gate E warning instead
  of fabricated effect rows.
- At least one revalidation job reaches manuscript/PDF stages, or the blocker is
  demonstrably a topic/evidence limitation rather than pipeline drift.

## Non-goals

- Do not change the public b-side contract version.
- Do not remove V3.1 readers until migration jobs prove V3.2 artifacts.
- Do not turn every semantic quality issue into a deterministic regex gate.
- Do not make Hermes responsible for declaring gate truth.
- Do not add hooks as a substitute for missing substep design.

## Open Questions

1. Which two DOI/metadata sources are required for the initial deterministic
   verifier: CrossRef plus OpenAlex, or CrossRef plus Semantic Scholar?
2. Should b-side collect more reference candidates, or should a-side own top-up
   entirely?
3. What exact UI should `human_decision_required` expose on paperlab.cooperation.tw?

## Decisions (2026-07-02, product owner)

The following were open questions 4 and 5; they are now decided and binding.

### D1. Low-poolability topics: explicit downgrade, not block

When the contract requests a meta-analysis but the evidence yields
`poolable_k = 0` (or below floor), the engine downgrades the deliverable to a
narrative/systematic review WITHOUT meta-analysis and continues to delivery.

Constraints that make the downgrade honest rather than a new bypass:

- The downgrade is an explicit recorded event: dossier entry, status page
  surface, and a `lane_downgrade` record in canonical data.
- The manuscript must state the downgrade and its evidence reason.
- No pooled-effect artifacts may exist in a downgraded run: no forest plot,
  no pooled-effect tables, no moderator claims.
- Rationale: b-side grill already gates topic-lane fit; blocking again on
  a-side would strand paid VIP jobs. Silent rewriting is still forbidden.

### D2. VIP delivery requires a human checkpoint for now

Even when all mechanical gates pass, a VIP job stops at
`human_review_required` before final delivery. Mechanical gates cannot verify
grounding/judgment-level quality (proven by the a64ad5b gate-widening
incident). The checkpoint is removed only after the Hermes domain-expert
review provenance mechanism has a sampled human-audit pass rate high enough
to justify spot-checking instead.

### D3. V3.2 (newarch engine_v3) is the production line

The B coherent-agent engine (`paper_agent/`) is paused. V3.2 fixes are
product fixes at P0 priority. The review-integrity work (no deterministic
pass-like review, provenance-verified Gate R, verdict freshness, content
honesty gates) is the launch blocker set.

### D4. The general-engine intent is binding (2026-07-02, product owner)

This engine is the general Hermes+Skill research/report engine; paper is
only the FIRST domain proof. Insurance and IFRS packs share the same
framework. Every mechanism added for the paper product (review provenance,
freshness, downgrade routing, human checkpoints) must be designed
domain-neutral in the general layer, with domain artifact names declared by
the domain pack (see `engine_v3/packs/paper_artifacts.py`).

Enforcement is mechanical, not aspirational:
`tests/test_engine_layer_domain_neutrality.py` scans the general layer
(engine_v3 root + core/) for domain tokens and fails on any new leak. Its
KNOWN_DEBT allowlist records pre-existing violations and may only shrink.
Litmus: adding a new domain pack must require zero changes in general-layer
source.
