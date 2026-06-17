# Paper Job Service Schema

This directory exposes the validated new-architecture paper pipeline as a
callable core. Policy routing lives in `router.py`; execution and persisted job
state live in `job_runner.py`.

## Input: `research_contract.json`

Required object:

```json
{
  "job_id": "hupd-cpu-job-001",
  "source": "paper-mcp",
  "level": "master",
  "tier": "free",
  "topic": "CPU-only HUPD classical ML benchmark",
  "research_question": "Can a complete real-data CPU benchmark lift the patent paper above the reject ceiling?",
  "contribution": "A fail-closed, reproducible HUPD patent benchmark using classical sklearn models.",
  "data_source": {
    "name": "HUPD/hupd",
    "type": "dataset",
    "probe_required": true
  },
  "target_journal": "Scientometrics"
}
```

Fields:

| Field | Type | Rule |
|---|---|---|
| `job_id` | string | Stable ID used under `jobs/<job_id>/`; no path separators. |
| `source` | string | Currently `paper-mcp`. |
| `level` | string | `master`, `phd`, or `journal`. This is the academic bar and auto-derives `content_threshold`, `review_depth`, `model_policy`, and `needs_real_experiment_lane`. |
| `tier` | string | `free` or `vip`. |
| `topic` | string | User-facing topic summary. |
| `research_question` | string | Main question to write/evaluate against. |
| `contribution` | string | Intended contribution boundary. |
| `data_source.name` | string | Currently probe-supported: `HUPD/hupd` / Harvard USPTO Patent Dataset. |
| `data_source.type` | string | Currently `dataset`. |
| `data_source.probe_required` | boolean | Must be `true`; runner is fail-closed. |
| `target_journal` | string | Venue target used for contract/provenance. |
| `target_journal_q` | string | Optional for `journal` level: `q1`, `q2`, `q3`, or `q4`. If omitted, the router defaults journal threshold to `7.0`. |
| `model_policy` | string | Optional legacy field. Routing is derived from `level`; do not use this as the source of truth. |

`tier` and `level` are separate dimensions:

- `tier` means who pays / priority (`free` or `vip`).
- `level` means academic bar (`master`, `phd`, or `journal`).

Level-derived policy:

| Level | `content_threshold` | `review_depth` | `model_policy` | `needs_real_experiment_lane` |
|---|---:|---|---|---|
| `master` | `6.0` | `7dim` (Elite optional) | `free` / `big-pickle` | `false` |
| `phd` | `7.0` | `7dim+elite` | `paid` / `agy -> codex` | `true` |
| `journal` | By target Q (`q1=8.0`, `q2=7.5`, `q3=7.0`, `q4=6.5`; default `7.0`) | `full-3-layer` | By tier | By topic |

## Router Output

`python3 job_runner.py route samples/research_contract_hupd_cpu.json`

```json
{
  "source": "paper-mcp",
  "tier": "free",
  "level": "master",
  "content_threshold": 6.0,
  "review_depth": "7dim",
  "model_policy": "free",
  "needs_real_experiment_lane": false,
  "elite_required": false,
  "elite_optional": true,
  "lane": "mvp/CPU-real",
  "model_chain": ["big-pickle"],
  "driver": "hermes",
  "hooks": ["data_availability_gate", "paper_gate", "deterministic_content_review"],
  "timeout_seconds": 21600,
  "fallback_policy": {
    "paid_fallback": false,
    "max_attempts_per_model": 2,
    "fallback_on": ["retryable_runtime_error"]
  }
}
```

Policy:

| Source | Tier | Level | Route |
|---|---|---|---|
| `paper-mcp` | Any | `master` | `big-pickle`, threshold `6.0`, `7dim`, Elite optional, no real-experiment lane. |
| `paper-mcp` | Any | `phd` | `agy -> codex`, threshold `7.0`, `7dim+elite`, paid fallback, real-experiment lane required. |
| `paper-mcp` | `free` | `journal` | `big-pickle`, target-Q threshold, full 3-layer review, real lane by topic. |
| `paper-mcp` | `vip` | `journal` | `agy -> codex`, target-Q threshold, full 3-layer review, real lane by topic. |

## Output: `output.json`

The runner writes `jobs/<job_id>/output.json`:

```json
{
  "job_id": "hupd-cpu-job-001",
  "status": "done",
  "run_dir": "jobs/hupd-cpu-job-001/run",
  "level": "master",
  "content_score": 6.58,
  "content_threshold": 6.0,
  "meets_threshold": true,
  "desk_reject": 0.389,
  "above_5_5": true,
  "gates": {
    "data_availability": "available",
    "paper_gate_blocked": false,
    "no_p0": true,
    "p1_count": 0,
    "real_status": "completed"
  },
  "doi_real_rate": 1.0,
  "pdf_path": "jobs/hupd-cpu-job-001/run/paper_draft_v0.pdf",
  "real_vs_simulated": {
    "real_status": "completed",
    "simulated_markers_final": 0,
    "simulation_markers": 0,
    "simulated": false
  },
  "blockers": []
}
```

Possible `status` values: `submitted`, `running`, `done`, `blocked`, `failed`.

## CLI

```bash
python3 job_runner.py submit samples/research_contract_hupd_cpu.json
python3 job_runner.py status hupd-cpu-job-001
python3 job_runner.py result hupd-cpu-job-001
```

For deterministic foreground validation:

```bash
python3 job_runner.py submit samples/research_contract_hupd_cpu.json --no-start
python3 job_runner.py worker --job-id hupd-cpu-job-001
```
