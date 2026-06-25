# Paper Engine V3.1 Spec

## Goal

V3.1 keeps the external v3 API and contract lane, but tightens the internal
engine boundary so Hermes output cannot drift into untyped artifacts that gates
must guess.

The primary success criteria are:

- Terminal job status matches the run directory.
- Terminal jobs have no run-dir orphan processes.
- Gates read canonical artifacts before legacy/Hermes artifacts.
- Missing runtime outputs route to same-phase repair while repair budget remains.
- PDF completion is declared only after final delivery gates pass.

## Architecture

### Contract Layer

External requests remain `contract_version: 3`. The internal engine revision is
`3.1` and is represented by canonical artifact schema versions rather than a new
public contract version.

### Runtime Supervisor Layer

The Hermes runtime owns process lifecycle:

- process group termination
- no-output idle timeout
- partial-output idle timeout
- all-output completion grace
- run-dir orphan process cleanup
- stdout/stderr tail capture

Runtime `blocked` results caused only by missing declared outputs are repairable
while the phase has repair budget.

### Candidate Artifact Layer

Hermes may write current v3 artifacts for compatibility. V3.1 introduces a
canonicalization layer that converts those outputs into typed engine artifacts.
Future work should move Hermes to writing `candidate/*` files only.

### Canonical Artifact Layer

The data phase canonical artifact is:

`artifacts/data/canonical.v3_1.json`

Shape:

```json
{
  "schema_version": "paperlab.data.v3.1",
  "references": {
    "count": 35
  },
  "verification": {
    "two_source_rate": 1.0
  },
  "effects": {
    "poolable_k": 8,
    "abstract_level_count": 8,
    "interpretation": "abstract_level"
  },
  "figures": [
    {
      "name": "fig_prisma_flow",
      "png": true,
      "svg": true
    }
  ],
  "source_files": {
    "doi_audit": "doi_audit.json",
    "real_results": "real_experiments/real_results.json"
  }
}
```

### Gate Layer

Gate inputs must prefer canonical artifacts. Legacy schema adapters remain only
as migration fallback. New Hermes schema variants must be normalized into
canonical artifacts, not added directly to gate logic.

Gate A reads:

- `references.count`
- `verification.two_source_rate`

Gate E reads:

- `effects.poolable_k`

### State Machine

Each phase follows:

`pending -> running -> normalized -> gated -> repair_needed -> done | blocked`

Runtime missing-output blocks are repairable:

`runtime_block(missing declared outputs) -> repair_same_phase:missing_declared_outputs`

Other runtime errors remain terminal unless a phase explicitly owns a recovery
route.

## Implementation Slices

1. Add canonical data artifact module.
2. Make `paperctl._build_dossier` canonical-first.
3. Make data phase handler write canonical data when raw artifacts exist.
4. Add regression tests for canonical Gate A/E.
5. Later slices move Hermes to `candidate/*` writes and freeze run-dir attempts.
