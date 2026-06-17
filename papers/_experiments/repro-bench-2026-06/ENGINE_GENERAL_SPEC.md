# General Research/Report Generation Engine — Spec (PRD + Architecture)

> Status: **owner-decided 2026-06-15 — substrate = Hermes + Skill, brain = codex.**
> Planning package: this doc (PRD/architecture) · [HERMES_NATIVE_ORCHESTRATOR_DESIGN.md](HERMES_NATIVE_ORCHESTRATOR_DESIGN.md)
> (framework + paper-pack system/tech detail) · [ENGINE_BUILD_PLAN.md](ENGINE_BUILD_PLAN.md) (TDD task list).

## 1. Purpose + the decision

Build ONE general, domain-agnostic, MCP-pluggable agent that produces **high-quality research / report
artifacts across domains and levels**, reused by multiple front-ends:
- **paperlab** — academic papers (master / phd / journal), via the paperlab grill MCP.
- **insurance** — VIP research reports, via the insurance MCP agent side.
- **IFRS** — regulatory-comparison reports, via the IFRS MCP.

**Decision (owner): substrate = Hermes + Skill; brain = codex** (`openai-codex` provider) + big-pickle
workers. **Why Hermes over the codex-brain MVP** — the deciding axis is *generality / reuse across
domains, MCP-pluggable, build-once*:
- Hermes is a **domain-agnostic agent platform**: native **skills** mechanism (swap domain = swap skill
  bundle), native **MCP tools** (connect insurance MCP / IFRS MCP by config), `delegate_task`
  sub-agents, memory, compaction. "Load a domain skill + connect a domain MCP" is its design point.
- The codex-brain MVP is a **paper-specific Python script**; generalizing it = re-inventing what Hermes
  already provides (skills loading, MCP, delegate, memory) per domain. Not worth it for 3+ domains.
- We **do not lose the MVP's proven quality**: Hermes runs **codex as the parent model** (verified:
  `openai-codex` provider on ac-2012) + big-pickle workers. So Hermes+Skill = **codex brain (quality) +
  general platform (reuse)**.
- The MVP was not wasted: it **proved the recipe** (codex brain + full skill + deterministic gates +
  self-heal → 80-pt-level reasoning; exercise-depression case floor 56 / review 75, capped by evidence
  not orchestration). That recipe now runs ON Hermes, generalized.

**Build once, swap packs.**

## 2. Two layers: framework (write once) + domain pack (one per domain)

### 2.1 Domain-agnostic orchestration framework — the reusable core
Detailed in [HERMES_NATIVE_ORCHESTRATOR_DESIGN.md](HERMES_NATIVE_ORCHESTRATOR_DESIGN.md); all of it is
domain-independent and written once:
- **Hermes parent (codex brain)** + `delegate_task` **big-pickle workers** (parent-level fan-out only;
  depth-2 constraint).
- **Python control-plane wrapper** owns the state machine (checkpoints, gates, work-queue, fan-out);
  the agent owns reasoning inside each dispatched unit.
- **Dossier** — the reasoning-continuity checkpoint (decisions, gaps, claim-evidence, gate results,
  obligations); not just artifacts.
- **Gates A–F** — deterministic, wrapper-enforced (contract/refs, claim≤evidence, figures, readability,
  experiment-value, logic-audit). Thresholds are pack-supplied.
- **Three-stage review + self-heal** — strong-brain reviewers + deterministic floor + 3 rounds.
- **Viability probe + tier interaction** — master = auto-pivot + `research_steering_log`; phd/journal =
  pause + confirm.
- **Live status publishing** — dossier projection → project page (dynamic, no rebuild).
- **Hang strategy** — lean orchestrator + checkpoint + fresh-resume; watchdog at 60–65 %.

### 2.2 Pluggable domain pack — grounded in TWO real domains (paper + insurance)
The seam below is **not speculative** — it is the common structure extracted from the proven paper
pack and the mapped insurance KB report system (insurance-kb-v2). Both run the same lifecycle:
**grill → typed evidence (with sources) → outline → body → BLOCK/WARN gates → deliverable.** codex's
review is honoured: the framework owns the gate *lifecycle*; concrete gates/evidence/viability are
**pack-registered**, not framework-constant.

```
DomainPack = {
  grill_schema:     structured scope questions the front-end asks (THIN — no dense numbers; §2.3)
  contract_schema:  the canonical contract derived from grill answers + canonicalize()/hash()
  skill_bundle:     the domain's SKILL.md set (hermes skills)
  data_sources:     domain MCP/tools the AGENT pulls facts+numbers from (server-side; §2.3)
  evidence_model:   typed findings/claims with mandatory sources + how they're cited
  viability_probe:  pack.viability.probe(contract, sources) -> ViabilityVerdict (+ candidate pivots)
  section_template: the deliverable's section outline
  gate_registry:    the BLOCK/WARN checks this pack registers (run by the framework's gate lifecycle)
  deliverable:      render(dossier) -> the final artifact
  review_rubric:    the structured-artifact assertions reviewers/tests check (gap matrix, findings…)
}
```

| field | **paper pack (#1, proven)** | **insurance pack (#2, mapped)** |
|---|---|---|
| grill_schema | PICOS (intervention / outcome / population) | scope / region / timeframe / audience / depth |
| evidence_model | claim-evidence map + DOI-verified refs | findings `{type, content, source_url(required), date}` + `[^N]` |
| data_sources | OpenAlex / EuropePMC / CrossRef | crawled news (36k index) / monthly wiki / past reports / web(Exa+DDG) |
| viability_probe | poolable-k (compatible effects) | target_findings yield from sources (5/10/15) |
| gate_registry | DOI-rate, refs≥35, claim≤evidence, figures, logic-audit | body_too_thin **BLOCK**, footnote_orphan **BLOCK**, uncited_quantitative, single_source_overreliance |
| deliverable | QMD → PDF | markdown → DOCX (no PDF) |
| section_template | Abstract/Intro/Related/Methods/Results/Discussion/Limitations/Conclusion | 市場概況/競品/觀察洞察/歷史對照/策略建議/風險限制/參考資料 |

- **IFRS pack (#3)** — clause-level cross-standard diff; gates = clause-authority / version / effective-
  date / missing-clause. **Still speculative** (no real build yet) → it CONFIRMS/REFINES the seam when
  built, it does not design it. Two real domains define the contract; the third validates it.

**The framework never imports a domain; it calls the pack through this interface.** Adding a domain =
write a pack, not touch the framework.

**The framework never imports a domain; it calls the pack through the interface.** Adding a domain =
write a pack, not touch the framework.

### 2.3 The THIN-HANDOFF invariant (forced by the OpenAI safety filter, validated 2026-06-14)
A hard platform fact, not a preference: **OpenAI Lockdown Mode (2026-06-04) intercepts MCP tool calls
that carry dense numbers / currency symbols / special chars** at the ChatGPT platform layer — before
they reach any server (four-way verified: server-side calls 100 % succeed; the same finding blocked on
ChatGPT but written losslessly on Claude). So:
- **The chat.ai front-end (grill) passes only THIN, number-free scope** (the `grill_schema` choices).
  It NEVER passes dense numbers, findings, or report bodies through tool calls.
- **The a-side engine owns ALL numbers + facts + prose** — it pulls them server-side from the pack's
  `data_sources` and writes the deliverable on the server, where no such filter applies.
This is why the engine is not "nice to have" for insurance — it is the **fix** for the block that
currently degrades the insurance VIP product (findings with `€170.00` / `1,645 億步` get dropped on
ChatGPT). The same thin handoff is required for paperlab. Architecture invariant: **numbers never
traverse chat.ai; the grill is thin; the a-side is where the detail lives.**

## 3. Brain / worker / MCP / determinism model
| Concern | Owner |
|---|---|
| Orchestration loop, gate enforcement, state machine | Python wrapper (deterministic) |
| Reasoning: gap, structure, writing, **review judgment**, fixes | **codex** (hermes parent, `openai-codex`) |
| Bounded drafting / fixing (section writers, fix-agents) | **big-pickle** (hermes `delegate_task`) |
| Domain data + tools | **domain MCP** (hermes mcp) + the pack's `*ctl` |
| Facts, figures, render, "refuse bad artifacts" | the pack's deterministic tools + framework gates |
Governing rule (unchanged): *the model owns reasoning + delegation; Python owns facts, gates, render,
and refusal to pass bad artifacts.*

## 4. Multi-domain reuse — what stays constant vs varies
| | Framework (constant) | Domain pack (varies) |
|---|---|---|
| orchestration / dossier / gates A–F / review+self-heal / viability+tier / live-status / hang | ✅ one impl | — |
| skill bundle | — | paper-draft+27 / insurance / ifrs |
| deterministic tools (`*ctl`) | — | meta-analysis / KB-report / clause-diff |
| MCP connections | — | OpenAlex+PMC / insurance-KB / IFRS |
| contract schema + gate thresholds + deliverable render | — | per domain |
The engine's durable value is the **constant column**; each new product is a **pack** in the varying
column. This is why "一次做到" pays off across paperlab + insurance + IFRS.

## 5. Non-goals / explicit boundaries
- Not a chat UI — front-ends (paperlab grill / insurance / IFRS MCPs) own the conversation; the engine
  is the a-side executor.
- Not domain-coupled — zero `import paper_*` in the framework; the paper specifics live only in the
  paper pack.
- Not "trust the model" — every must-be-correct fact passes a deterministic gate (the architecture's
  whole thesis).
