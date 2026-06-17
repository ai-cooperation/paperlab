# Engine test fixtures (ENGINE_BUILD_PLAN.md Phase 0)

Frozen inputs reused across phases. Big corpora are gzipped; `conftest.py`
(`load_fixture_json`, `corpus_path`) decompresses them transparently so the git
tree stays slim while tests see the real frozen object.

| fixture | source | what | consumed by |
|---|---|---|---|
| `corpus_exercise.json.gz` | ac-2012 `proj_2026-06-13_epmc/run/_corpus_cache.json` | real exercise-depression corpus, 2400 works | extraction-consistency (P1), meta-pool, viability |
| `corpus_mindfulness_thin.json.gz` | ac-2012 `proj_2026-06-15_mindfulness/run/_corpus_cache.json` | real corpus, 2400 works but thin poolable-k | viability non-viable + tier (P6) |
| `golden_paper/` | ac-2012 `proj_2026-06-13_epmc/run` (curated subset) | the exercise-depression deterministic run: contract, refs, metadata, gate_report, real_results, figures (svg+png), qmd, review | regression baseline, paperctl golden (P2), gates (P4), render |
| `contract_paper.json` | copy of `golden_paper/research_contract.json` | real paper contract (PICOS) | DomainPack interface (P1*), schema |
| `contract_insurance.json` | authored, spec §2.2 | insurance VIP contract (scope/region/timeframe/audience/depth) | DomainPack interface (P1*) |
| `contract_ifrs.json` | authored, spec §2.2 | IFRS clause-diff contract (speculative pack #3) | DomainPack interface (P1*) |
| `contract_thin_handoff.json` | authored, spec §2.3 | number-free grill→contract | thin-handoff invariant test |
| `overclaim_samples.md` | authored from ICS/SMC review failures | labeled overclaims + 1 planted unlisted | Gate B (P4) |
| `dup_figure.qmd` | authored on the real embed pattern | each figure embedded twice | Gate C / inject_figures dedup (P4) |
| `insurance_kb_small/` | authored | 5 docs (1 stale, 1 conflicting pair) + `known_findings.json` oracle | insurance pack viability/evidence/gates (P1*) |
| `insurance_gatefail/` | authored | `report.md` tripping 4 gates + `expected_gate_report.json` oracle | insurance gate_registry (P4) |

`test_fixtures_load.py` asserts every row above exists and loads (the Phase 0 GREEN bar).
