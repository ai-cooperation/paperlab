"""General public-dataset analysis lane (domain-agnostic).

The engine must be able to complete ANY public-dataset study (an agent fetches the data,
writes the analysis, runs it) WITHOUT per-dataset code in the engine. The ONLY thing the
engine source knows is the GENERAL machinery: download files, run a script, capture
provenance, and verify (data really fetched, code really ran, every manuscript number
traces to that run). ALL dataset-specific knowledge — variable names, survey design,
model formulas — lives in agent-generated run-dir ARTIFACTS (`analysis_spec.json`,
`analysis.py`), never here.

Litmus test for "general, not a fixed script": a brand-new dataset must run end-to-end
with ZERO change to this package — only different agent artifacts.

Nothing in this package names a dataset, a column, or a study.
"""
from . import fetch, gates, lane, runner, schema, skill_upgrade  # noqa: F401
