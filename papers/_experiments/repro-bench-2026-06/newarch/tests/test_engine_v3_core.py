from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.core import (
    ArtifactRef,
    BrainTask,
    DossierStore,
    GateResult,
    GateSeverity,
    PhaseSpec,
    RuntimeContext,
    TaskResult,
    WorkerTask,
    run_gates,
    PackRegistry,
)
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.runtimes.mock import MockRuntime

pytestmark = pytest.mark.unit


def test_mock_runtime_writes_declared_worker_outputs(tmp_path: Path):
    runtime = MockRuntime()
    task = WorkerTask(
        phase="phase-1",
        prompt="write the file",
        expected_outputs=["sections/method.md"],
    )

    result = runtime.run_worker(task, RuntimeContext(job_id="job-1", run_dir=tmp_path))

    assert result.status == "ok"
    assert result.outputs == {"sections/method.md": tmp_path / "sections/method.md"}
    assert (tmp_path / "sections/method.md").read_text(encoding="utf-8")


def test_pack_registry_preserves_skill_and_tool_provider_seam():
    class DemoToolProvider:
        name = "demo-tools"

        def capabilities(self):
            return {"tools": ["probe"]}

        def run(self, tool_name, args):
            return {"tool_name": tool_name, "args": dict(args)}

    class DemoPack:
        name = "demo"

        def skill_bundle(self):
            return ["domain-review", "domain-writing"]

        def tool_provider(self):
            return DemoToolProvider()

        def gate_registry(self):
            return []

    registry = PackRegistry()
    registry.register("demo", DemoPack)

    pack = registry.create("demo")

    assert registry.names() == ["demo"]
    assert pack.skill_bundle() == ["domain-review", "domain-writing"]
    assert pack.tool_provider().capabilities() == {"tools": ["probe"]}


def test_gate_runner_filters_by_phase_and_fails_closed():
    class DemoPack:
        name = "demo"

        def gate_registry(self):
            return [
                {
                    "id": "contract",
                    "phase": "phase-0",
                    "severity": GateSeverity.BLOCK,
                    "check": lambda _dossier: GateResult.pass_("contract"),
                },
                {
                    "id": "draft",
                    "phase": "phase-1",
                    "severity": GateSeverity.BLOCK,
                    "check": lambda _dossier: (_ for _ in ()).throw(ValueError("boom")),
                },
            ]

    report = run_gates(DemoPack(), {}, phase="phase-1")

    assert report.blocked is True
    assert report.failed_blocks == ["draft"]
    assert len(report.results) == 1
    assert report.results[0].gate_id == "draft"
    assert report.results[0].passed is False
    assert "fail-closed" in report.results[0].details


def test_dossier_store_persists_artifact_hashes_and_checkpoints(tmp_path: Path):
    run_dir = tmp_path / "run"
    artifact = run_dir / "sections" / "intro.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("hello", encoding="utf-8")

    store = DossierStore(run_dir)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.add_artifact("intro", artifact)
    dossier.mark_phase("phase-0", "done")
    store.save(dossier)

    loaded = store.load()

    assert loaded.job_id == "job-1"
    assert loaded.phases["phase-0"] == "done"
    assert loaded.artifacts["intro"].path == "sections/intro.md"
    assert len(loaded.artifacts["intro"].sha256) == 64
    assert (run_dir / "dossier.v3.json").exists()
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "paperlab.artifact_manifest.v3.2"
    assert manifest["artifacts"]["intro"]["path"] == "sections/intro.md"


def test_dossier_store_normalizes_cwd_relative_run_artifact_paths(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    run_dir = workspace / "jobs" / "job-1" / "run"
    artifact = run_dir / "paper_draft_v0.qmd"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("draft", encoding="utf-8")
    monkeypatch.chdir(workspace)

    store = DossierStore(run_dir)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.artifacts["paper_draft_v0.qmd"] = ArtifactRef(
        path="jobs/job-1/run/paper_draft_v0.qmd",
        sha256="",
    )

    store.save(dossier)
    loaded = store.load()

    assert loaded.artifacts["paper_draft_v0.qmd"].path == "paper_draft_v0.qmd"
    assert len(loaded.artifacts["paper_draft_v0.qmd"].sha256) == 64


def test_dossier_store_normalizes_run_prefixed_artifact_paths_from_other_cwd(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    run_dir = workspace / "jobs" / "job-1" / "run"
    artifact = run_dir / "quality_review_round1.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"delivery":"pass"}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    store = DossierStore(run_dir)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.artifacts["quality_review_round1.json"] = ArtifactRef(
        path="jobs/job-1/run/quality_review_round1.json",
        sha256="",
    )

    store.save(dossier)
    loaded = store.load()

    assert loaded.artifacts["quality_review_round1.json"].path == "quality_review_round1.json"
    assert len(loaded.artifacts["quality_review_round1.json"].sha256) == 64


def test_dossier_store_drops_missing_stale_artifacts_on_save(tmp_path: Path):
    run_dir = tmp_path / "run"
    artifact = run_dir / "quality_review_round1.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"delivery":"revise"}\n', encoding="utf-8")

    store = DossierStore(run_dir)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.add_artifact("quality_review_round1.json", artifact)
    store.save(dossier)
    artifact.unlink()

    loaded = store.load()
    store.save(loaded)
    reloaded = store.load()

    assert "quality_review_round1.json" not in reloaded.artifacts


def test_orchestrator_skips_completed_phases_on_resume(tmp_path: Path):
    calls: list[str] = []

    def handler(task: BrainTask, context: RuntimeContext):
        calls.append(task.phase)
        return {"phase": task.phase, "run_dir": str(context.run_dir)}

    phases = [
        PhaseSpec(id="phase-0", handler=handler),
        PhaseSpec(id="phase-1", handler=handler),
    ]
    store = DossierStore(tmp_path)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.mark_phase("phase-0", "done")
    store.save(dossier)

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=phases,
        dossier_store=store,
    )

    final = orchestrator.run(job_id="job-1", resume=True)

    assert calls == ["phase-1"]
    assert final.phases == {"phase-0": "done", "phase-1": "done"}


def test_orchestrator_passes_pack_skill_bundle_to_runtime_context(tmp_path: Path):
    seen = {}

    class DemoPack:
        name = "demo"

        def skill_bundle(self):
            return ["domain-skill"]

        def gate_registry(self):
            return []

    def handler(_task: BrainTask, context: RuntimeContext):
        seen["metadata"] = dict(context.metadata)
        return {}

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=DemoPack(),
        phases=[PhaseSpec(id="phase-0", handler=handler)],
        dossier_store=DossierStore(tmp_path),
    )

    orchestrator.run(job_id="job-1", resume=False)

    assert seen["metadata"]["skill_bundle"] == ["domain-skill"]
    assert seen["metadata"]["engine_revision"] == "3.2"


def test_orchestrator_records_engine_revision_in_dossier(tmp_path: Path):
    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="phase-0", handler=lambda _task, _context: {})],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.evidence["engine_revision"] == "3.2"


def test_orchestrator_records_phase_substeps(tmp_path: Path):
    def handler(_task: BrainTask, _context: RuntimeContext):
        return {
            "substeps": [
                {
                    "id": "verify_doi_two_sources",
                    "owner": "deterministic",
                    "status": "done",
                    "outputs": ["artifacts/data/doi_verification.v3_2.json"],
                }
            ]
        }

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="data", handler=handler)],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.evidence["substeps"]["data"] == [
        {
            "id": "verify_doi_two_sources",
            "owner": "deterministic",
            "status": "done",
            "outputs": ["artifacts/data/doi_verification.v3_2.json"],
        }
    ]


def test_orchestrator_updates_gate_substep_after_gate_report(tmp_path: Path):
    class DemoPack:
        name = "demo"

        def gate_registry(self):
            return [
                {
                    "id": "A",
                    "phase": "data",
                    "severity": GateSeverity.BLOCK,
                    "check": lambda _dossier: GateResult.pass_("A"),
                }
            ]

    def handler(_task: BrainTask, _context: RuntimeContext):
        return {
            "substeps": [
                {
                    "id": "gate_A_E",
                    "owner": "validator",
                    "status": "pending",
                    "outputs": [],
                }
            ]
        }

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=DemoPack(),
        phases=[PhaseSpec(id="data", handler=handler, gate_ids=["A"])],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.evidence["substeps"]["data"] == [
        {
            "id": "gate_A_E",
            "owner": "validator",
            "status": "done",
            "outputs": [],
            "failed_blocks": [],
        }
    ]


def test_orchestrator_records_human_checkpoint_for_data_gate_exhaustion(tmp_path: Path):
    class DemoPack:
        name = "demo"

        def gate_registry(self):
            return [
                {
                    "id": "A",
                    "phase": "data",
                    "severity": GateSeverity.BLOCK,
                    "check": lambda _dossier: GateResult.fail(
                        "A",
                        details="bib_count=12, doi_real_rate=None",
                        evidence={"bib_count": 12, "doi_real_rate": None},
                    ),
                }
            ]

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=DemoPack(),
        phases=[PhaseSpec(id="data", handler=lambda _task, _context: {}, gate_ids=["A"])],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.phases["data"] == "blocked"
    assert dossier.evidence["human_checkpoint"] == {
        "status": "human_decision_required",
        "phase": "data",
        "failed_blocks": ["A"],
        "reason": "data evidence could not satisfy hard gates within the configured repair budget",
        "options": [
            "revise_or_narrow_topic",
            "provide_more_seed_references",
            "downgrade_synthesis_type",
            "stop_job",
        ],
    }


def test_orchestrator_routes_gate_a_repair_to_reference_top_up(tmp_path: Path):
    class DemoPack:
        name = "demo"

        def gate_registry(self):
            return [
                {
                    "id": "A",
                    "phase": "data",
                    "severity": GateSeverity.BLOCK,
                    "check": lambda _dossier: GateResult.fail("A", details="not enough references"),
                }
            ]

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=DemoPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=lambda _task, _context: {},
                gate_ids=["A"],
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)
    repair_events = [
        event for event in dossier.evidence["trace"] if event.get("event") == "repair_decision"
    ]

    assert repair_events[0]["route"] == "repair:data.verify_doi_two_sources:top_up_references"


def test_orchestrator_records_runtime_delegation_and_artifacts(tmp_path: Path):
    class WritingRuntime(MockRuntime):
        name = "writer"

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            path = context.run_dir / task.expected_outputs[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("draft", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={task.expected_outputs[0]: path},
                changed_files=[task.expected_outputs[0]],
            )

    orchestrator = EngineV3Orchestrator(
        runtime=WritingRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="write",
                handler=lambda _task, _context: {"ok": True},
                prompt="write draft",
                expected_outputs=["paper_draft_v0.qmd"],
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.phases["write"] == "done"
    assert dossier.delegations == [
        {
            "task_id": "write:brain",
            "phase": "write",
            "runtime": "writer",
            "class": "brain",
            "status": "ok",
            "declared_outputs": ["paper_draft_v0.qmd"],
            "changed_files": ["paper_draft_v0.qmd"],
            "blockers": [],
            "candidate_manifest": "artifacts/candidates/write/write_brain/manifest.v3_1.json",
            "candidate_outputs": [
                "artifacts/candidates/write/write_brain/paper_draft_v0.qmd",
            ],
        }
    ]
    assert dossier.artifacts["paper_draft_v0.qmd"].path == "paper_draft_v0.qmd"
    assert len(dossier.artifacts["paper_draft_v0.qmd"].sha256) == 64

    manifest_path = tmp_path / "artifacts" / "candidates" / "write" / "write_brain" / "manifest.v3_1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "paperlab.candidate.v3.1"
    assert manifest["phase"] == "write"
    assert manifest["task_id"] == "write:brain"
    assert manifest["declared_outputs"] == ["paper_draft_v0.qmd"]
    assert manifest["outputs"][0]["declared_path"] == "paper_draft_v0.qmd"
    assert manifest["outputs"][0]["candidate_path"] == (
        "artifacts/candidates/write/write_brain/paper_draft_v0.qmd"
    )
    assert len(manifest["outputs"][0]["sha256"]) == 64
    assert (tmp_path / manifest["outputs"][0]["candidate_path"]).read_text(encoding="utf-8") == "draft"


def test_orchestrator_indexes_handler_artifacts_without_runtime_task(tmp_path: Path):
    class NoCallRuntime(MockRuntime):
        def run_brain(self, task: BrainTask, context: RuntimeContext):
            raise AssertionError("deterministic handler phase should not call runtime")

    def handler(_task: BrainTask, context: RuntimeContext):
        pdf = context.run_dir / "paper_draft_v0.pdf"
        pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
        return {"artifacts": {"paper_draft_v0.pdf": pdf}}

    dossier = EngineV3Orchestrator(
        runtime=NoCallRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="format_repair", handler=handler)],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert dossier.phases["format_repair"] == "done"
    assert dossier.artifacts["paper_draft_v0.pdf"].path == "paper_draft_v0.pdf"
    assert len(dossier.artifacts["paper_draft_v0.pdf"].sha256) == 64
    assert dossier.delegations == []


def test_orchestrator_blocks_phase_when_runtime_output_missing(tmp_path: Path):
    class BlockingRuntime(MockRuntime):
        name = "blocked-runtime"

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=["missing declared output: draft.md"],
            )

    called = []
    orchestrator = EngineV3Orchestrator(
        runtime=BlockingRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="write",
                handler=lambda _task, _context: called.append("handler") or {},
                prompt="write draft",
                expected_outputs=["draft.md"],
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert called == []
    assert dossier.phases["write"] == "blocked"
    assert dossier.delegations[0]["status"] == "blocked"


def test_orchestrator_allows_planning_handler_backfill_after_missing_output(tmp_path: Path):
    class BlockingRuntime(MockRuntime):
        name = "blocked-runtime"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=["missing declared output: phase4_structure.md"],
            )

    def handler(_task: BrainTask, context: RuntimeContext):
        structure = context.run_dir / "phase4_structure.md"
        structure.write_text("# Phase 4 Structure\n", encoding="utf-8")
        return {"artifacts": {"phase4_structure.md": structure}}

    dossier = EngineV3Orchestrator(
        runtime=BlockingRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="structure",
                handler=handler,
                prompt="write structure",
                expected_outputs=["phase4_structure.md"],
                max_repair_attempts=0,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert dossier.phases["structure"] == "done"
    assert dossier.artifacts["phase4_structure.md"].path == "phase4_structure.md"
    assert [delegation["status"] for delegation in dossier.delegations] == ["blocked"]
    assert any(event.get("event") == "runtime_non_ok_handler_recheck_attempt" for event in dossier.evidence["trace"])


def test_orchestrator_allows_write_handler_backfill_when_phase_has_repair_budget(tmp_path: Path):
    class BlockingRuntime(MockRuntime):
        name = "blocked-runtime"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=["missing declared output: paper_draft_v0.qmd"],
            )

    def handler(_task: BrainTask, context: RuntimeContext):
        draft = context.run_dir / "paper_draft_v0.qmd"
        draft.write_text("# Draft\n", encoding="utf-8")
        return {"artifacts": {"paper_draft_v0.qmd": draft}}

    dossier = EngineV3Orchestrator(
        runtime=BlockingRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="write",
                handler=handler,
                prompt="write paper",
                expected_outputs=["paper_draft_v0.qmd"],
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert dossier.phases["write"] == "done"
    assert dossier.artifacts["paper_draft_v0.qmd"].path == "paper_draft_v0.qmd"


def test_orchestrator_repairs_missing_declared_outputs_before_runtime_block(tmp_path: Path):
    class MissingThenRepairRuntime(MockRuntime):
        name = "missing-then-repair"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append((task.task_id, task.prompt))
            if task.task_id == "data:brain":
                return TaskResult(
                    task_id=task.task_id,
                    status="blocked",
                    blockers=["missing declared output: references.bib"],
                )
            refs = context.run_dir / "references.bib"
            refs.write_text("@article{one,title={One}}\n", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 1:
                    return GateResult.pass_("A", "bib_count=%s" % count)
                return GateResult.fail("A", details="bib_count=%s (floor 1)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    runtime = MissingThenRepairRuntime()
    dossier = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair missing data outputs",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert [call[0] for call in runtime.calls] == ["data:brain", "data:repair:1"]
    assert "required declared outputs" in runtime.calls[1][1]
    assert dossier.phases["data"] == "done"
    assert dossier.gate_reports[-1]["blocked"] is False
    assert [delegation["status"] for delegation in dossier.delegations] == ["blocked", "ok"]


def test_orchestrator_allows_handler_to_backfill_after_missing_output_repairs_exhausted(tmp_path: Path):
    class MissingRuntime(MockRuntime):
        name = "missing-runtime"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=["missing declared output: real_experiments/real_results.json"],
            )

    class DataPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                return (
                    GateResult.pass_("G")
                    if dossier.evidence.get("data_ready")
                    else GateResult.fail("G", details="data not ready")
                )

            return [{"id": "G", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        out = context.run_dir / "real_experiments" / "real_results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('{"status":"completed","simulated":false}', encoding="utf-8")
        return {
            "gate_inputs": {"data_ready": True},
            "artifacts": {"real_experiments/real_results.json": out},
        }

    dossier = EngineV3Orchestrator(
        runtime=MissingRuntime(),
        domain_pack=DataPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect data",
                expected_outputs=["real_experiments/real_results.json"],
                gate_ids=["G"],
                repair_prompt="repair data",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert dossier.phases["data"] == "done"
    assert [delegation["status"] for delegation in dossier.delegations] == ["blocked", "blocked"]
    assert [report["blocked"] for report in dossier.gate_reports] == [False]
    assert any(event.get("event") == "runtime_non_ok_handler_recheck_attempt" for event in dossier.evidence["trace"])


def test_orchestrator_allows_gate_handler_recheck_after_runtime_error_for_heal_phases(tmp_path: Path):
    class ErrorRuntime(MockRuntime):
        name = "error-runtime"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="error",
                blockers=["provider unavailable after existing artifacts were present"],
            )

    class ClaimPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                return (
                    GateResult.pass_("B")
                    if dossier.evidence.get("claim_healed")
                    else GateResult.fail("B", details="claim still blocked")
                )

            return [{"id": "B", "phase": "claim_evidence", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, _context: RuntimeContext):
        return {"gate_inputs": {"claim_healed": True}}

    dossier = EngineV3Orchestrator(
        runtime=ErrorRuntime(),
        domain_pack=ClaimPack(),
        phases=[
            PhaseSpec(
                id="claim_evidence",
                handler=handler,
                prompt="repair claims",
                expected_outputs=["claim_evidence_map.md"],
                gate_ids=["B"],
                max_repair_attempts=0,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert dossier.phases["claim_evidence"] == "done"
    assert [report["blocked"] for report in dossier.gate_reports] == [False]
    assert any(event.get("event") == "runtime_non_ok_handler_recheck_attempt" for event in dossier.evidence["trace"])


def test_orchestrator_rechecks_blocked_gate_phase_before_runtime_on_resume(tmp_path: Path):
    class NoCallRuntime(MockRuntime):
        name = "no-call"

        def run_brain(self, _task: BrainTask, _context: RuntimeContext):
            raise AssertionError("preflight gate recheck should skip runtime")

    class ReviewPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                return (
                    GateResult.pass_("R")
                    if dossier.evidence.get("review_ready")
                    else GateResult.fail("R", details="review not ready")
                )

            return [{"id": "R", "phase": "review_heal", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, _context: RuntimeContext):
        return {"gate_inputs": {"review_ready": True}}

    store = DossierStore(tmp_path)
    review = tmp_path / "quality_review_round1.json"
    review.write_text('{"delivery":"pass"}\n', encoding="utf-8")
    existing = store.create(job_id="job-1", domain="demo")
    existing.mark_phase("review_heal", "blocked")
    existing.add_artifact("quality_review_round1.json", review)
    store.save(existing)

    dossier = EngineV3Orchestrator(
        runtime=NoCallRuntime(),
        domain_pack=ReviewPack(),
        phases=[
            PhaseSpec(
                id="review_heal",
                handler=handler,
                prompt="review",
                expected_outputs=["quality_review_round1.json"],
                gate_ids=["R"],
            )
        ],
        dossier_store=store,
    ).run(job_id="job-1", resume=True)

    assert dossier.phases["review_heal"] == "done"
    assert dossier.delegations == []
    assert any(event.get("event") == "resume_preflight_gate_passed" for event in dossier.evidence["trace"])


def test_orchestrator_can_fallback_to_source_data_artifacts_for_revalidation(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    source_run = jobs_dir / "v3_source123" / "run"
    run_dir = jobs_dir / "v3_target456" / "run"
    source_run.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (run_dir / "research_contract.input.json").write_text(
        json.dumps({"metadata": {"source_job_id": "v3_source123"}}),
        encoding="utf-8",
    )
    for rel in ["references.bib", "doi_audit.json"]:
        (source_run / rel).write_text("source %s\n" % rel, encoding="utf-8")

    class MissingRuntime(MockRuntime):
        name = "missing-runtime"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=[
                    "missing declared output: references.bib",
                    "missing declared output: doi_audit.json",
                ],
            )

    dossier = EngineV3Orchestrator(
        runtime=MissingRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="data",
                handler=lambda _task, _context: {},
                prompt="collect data",
                expected_outputs=["references.bib", "doi_audit.json"],
            )
        ],
        dossier_store=DossierStore(run_dir),
    ).run(job_id="v3_target456", resume=False)

    assert dossier.phases["data"] == "done"
    assert (run_dir / "references.bib").read_text(encoding="utf-8") == "source references.bib\n"
    assert (run_dir / "doi_audit.json").read_text(encoding="utf-8") == "source doi_audit.json\n"
    assert [delegation["status"] for delegation in dossier.delegations] == ["blocked", "ok"]
    assert dossier.delegations[-1]["runtime"] == "missing-runtime+source-fallback"
    assert dossier.delegations[-1]["task_id"] == "data:source_fallback"
    assert dossier.artifacts["references.bib"].path == "references.bib"
    assert any(
        event.get("event") == "runtime_missing_outputs_fallback_applied"
        for event in dossier.evidence["trace"]
    )


def test_orchestrator_bootstraps_revalidation_data_from_source_before_runtime(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    source_run = jobs_dir / "v3_source123" / "run"
    run_dir = jobs_dir / "v3_target456" / "run"
    source_run.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (run_dir / "research_contract.input.json").write_text(
        json.dumps({"metadata": {"revalidation": "v3.2-test", "source_job_id": "v3_source123"}}),
        encoding="utf-8",
    )
    for rel in ["references.bib", "doi_audit.json"]:
        (source_run / rel).write_text("source %s\n" % rel, encoding="utf-8")

    class NoCallRuntime(MockRuntime):
        name = "no-call"

        def run_brain(self, _task: BrainTask, _context: RuntimeContext):
            raise AssertionError("revalidation source bootstrap should avoid data runtime")

    dossier = EngineV3Orchestrator(
        runtime=NoCallRuntime(),
        domain_pack=object(),
        phases=[
            PhaseSpec(
                id="data",
                handler=lambda _task, _context: {},
                prompt="collect data",
                expected_outputs=["references.bib", "doi_audit.json"],
            )
        ],
        dossier_store=DossierStore(run_dir),
    ).run(job_id="v3_target456", resume=False)

    assert dossier.phases["data"] == "done"
    assert [delegation["status"] for delegation in dossier.delegations] == ["ok"]
    assert dossier.delegations[0]["runtime"] == "no-call+revalidation-bootstrap+source-fallback"
    assert any(
        event.get("event") == "revalidation_source_bootstrap_applied"
        for event in dossier.evidence["trace"]
    )


def test_orchestrator_blocks_review_heal_when_hermes_missing_review_outputs(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for rel in [
        "paper_draft_v0.qmd",
        "paper_springer.qmd",
        "claim_evidence_map.md",
        "references.bib",
        "doi_audit.json",
        "real_experiments/real_results.json",
        "sections/introduction.md",
        "sections/related_work.md",
        "sections/methods.md",
        "sections/results.md",
        "sections/discussion.md",
        "sections/limitations.md",
        "sections/conclusion.md",
    ]:
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")

    store = DossierStore(run_dir)
    existing = store.create(job_id="job-1", domain="paper")
    existing.gate_reports.extend(
        [
            {"phase": "claim_evidence", "blocked": False, "failed_blocks": [], "results": []},
            {"phase": "render_gates", "blocked": False, "failed_blocks": [], "results": []},
        ]
    )
    store.save(existing)

    class MissingReviewRuntime(MockRuntime):
        name = "missing-review"

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            return TaskResult(
                task_id=task.task_id,
                status="blocked",
                blockers=[
                    "missing declared output: quality_review_round1.json",
                    "missing declared output: quality_review_log.md",
                ],
            )

    expected_outputs = [
        "quality_review_round1.json",
        "quality_review_log.md",
        "sections/introduction.md",
        "sections/related_work.md",
        "sections/methods.md",
        "sections/results.md",
        "sections/discussion.md",
        "sections/limitations.md",
        "sections/conclusion.md",
        "paper_draft_v0.qmd",
        "paper_springer.qmd",
    ]
    dossier = EngineV3Orchestrator(
        runtime=MissingReviewRuntime(),
        domain_pack=object(),
        phases=[
                PhaseSpec(
                    id="review_heal",
                    handler=lambda _task, _context: {},
                    prompt="review",
                    expected_outputs=expected_outputs,
                    repair_prompt="repair review",
                    repair_expected_outputs=expected_outputs,
                    max_repair_attempts=3,
                )
        ],
        dossier_store=store,
    ).run(job_id="job-1", resume=True)

    assert dossier.phases["review_heal"] == "blocked"
    assert not (run_dir / "quality_review_round1.json").exists()
    assert not (run_dir / "quality_review_log.md").exists()
    assert "quality_review_round1.json" not in dossier.artifacts
    assert dossier.delegations[-1]["runtime"] == "missing-review"
    assert dossier.delegations[-1]["task_id"] == "review_heal:repair:3"
    assert dossier.delegations[-1]["status"] == "blocked"
    assert dossier.evidence["trace"][-1]["event"] == "phase_runtime_block"


def test_orchestrator_repairs_blocked_gate_before_terminal_block(tmp_path: Path):
    class RepairingRuntime(MockRuntime):
        name = "repairing-runtime"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append(task.task_id)
            refs = context.run_dir / "references.bib"
            refs.write_text(
                "@article{one,title={One}}\n"
                if ":repair:" not in task.task_id else
                "@article{one,title={One}}\n@article{two,title={Two}}\n",
                encoding="utf-8",
            )
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 2:
                    return GateResult.pass_("A", "bib_count=%s" % count)
                return GateResult.fail("A", details="bib_count=%s (floor 2)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    runtime = RepairingRuntime()
    orchestrator = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair refs",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert runtime.calls == ["data:brain", "data:repair:1"]
    assert dossier.phases["data"] == "done"
    assert [report["blocked"] for report in dossier.gate_reports] == [True, False]
    assert dossier.delegations[-1]["task_id"] == "data:repair:1"


def test_orchestrator_traces_noop_gate_repair_and_stops_budget(tmp_path: Path):
    class NoopRepairRuntime(MockRuntime):
        name = "noop-repair-runtime"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append(task.task_id)
            refs = context.run_dir / "references.bib"
            if not refs.exists():
                refs.write_text("@article{one,title={One}}\n", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=[] if ":repair:" in task.task_id else ["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 2:
                    return GateResult.pass_("A", "bib_count=%s" % count)
                return GateResult.fail("A", details="bib_count=%s (floor 2)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    runtime = NoopRepairRuntime()
    dossier = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair refs",
                max_repair_attempts=3,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert runtime.calls == ["data:brain", "data:repair:1"]
    assert dossier.phases["data"] == "blocked"
    assert any(event.get("event") == "repair_noop" for event in dossier.evidence["trace"])


def test_review_heal_fresh_review_resets_stale_repair_budget_without_reusing_task_ids(tmp_path: Path):
    store = DossierStore(tmp_path)
    existing = store.create(job_id="job-1", domain="demo")
    existing.phases.update(
        {
            "data": "done",
            "gap": "done",
            "structure": "done",
            "write": "done",
            "claim_evidence": "done",
            "render_gates": "done",
            "review_heal": "blocked",
        }
    )
    existing.delegations.extend(
        {
            "task_id": "review_heal:repair:%s" % attempt,
            "phase": "review_heal",
            "runtime": "hermes-codex",
            "class": "brain",
            "status": "blocked",
            "declared_outputs": ["quality_review_round1.json", "quality_review_log.md"],
            "changed_files": [],
            "blockers": ["stale declared output: quality_review_round1.json"],
        }
        for attempt in (1, 2, 3)
    )
    store.save(existing)

    class ReviewRuntime(MockRuntime):
        name = "review-runtime"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append(task.task_id)
            review = context.run_dir / "quality_review_round1.json"
            log = context.run_dir / "quality_review_log.md"
            if task.task_id == "review_heal:brain":
                review.write_text('{"delivery":"revise"}\n', encoding="utf-8")
                log.write_text("real review\n", encoding="utf-8")
                return TaskResult(
                    task_id=task.task_id,
                    status="ok",
                    outputs={"quality_review_round1.json": review, "quality_review_log.md": log},
                    changed_files=["quality_review_round1.json", "quality_review_log.md"],
                )
            if task.task_id == "review_heal:repair:4":
                review.write_text('{"delivery":"pass"}\n', encoding="utf-8")
                log.write_text("real review after repair\n", encoding="utf-8")
                return TaskResult(
                    task_id=task.task_id,
                    status="ok",
                    outputs={"quality_review_round1.json": review, "quality_review_log.md": log},
                    changed_files=["quality_review_round1.json", "quality_review_log.md"],
                )
            return TaskResult(task_id=task.task_id, status="blocked", blockers=["unexpected repair"])

    class ReviewPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                delivery = dossier.evidence.get("review", {}).get("delivery")
                if delivery == "pass":
                    return GateResult.pass_("R", "review passed")
                return GateResult.fail("R", details="review failed: delivery=revise")

            return [{"id": "R", "phase": "review_heal", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        review = json.loads((context.run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
        return {"gate_inputs": {"review": review, "review_log_present": True}}

    runtime = ReviewRuntime()
    dossier = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=ReviewPack(),
        phases=[
            PhaseSpec(
                id="review_heal",
                handler=handler,
                prompt="review",
                expected_outputs=["quality_review_round1.json", "quality_review_log.md"],
                gate_ids=["R"],
                repair_prompt="repair review",
                repair_expected_outputs=["quality_review_round1.json", "quality_review_log.md"],
                max_repair_attempts=3,
            )
        ],
        dossier_store=store,
    ).run(job_id="job-1", resume=True)

    assert runtime.calls == ["review_heal:brain", "review_heal:repair:4"]
    assert dossier.phases["review_heal"] == "done"
    assert [report["blocked"] for report in dossier.gate_reports[-2:]] == [True, False]


def test_orchestrator_repair_prompt_includes_gate_evidence(tmp_path: Path):
    class CapturingRuntime(MockRuntime):
        name = "capturing-runtime"

        def __init__(self):
            self.prompts = []

        def run_brain(self, task: BrainTask, _context: RuntimeContext):
            self.prompts.append(task.prompt)
            return TaskResult(task_id=task.task_id, status="ok")

    class EvidencePack:
        name = "demo"

        def gate_registry(self):
            def check(_dossier):
                return GateResult.fail(
                    "B",
                    details="1 P0 overclaim",
                    evidence={
                        "flagged": [
                            {
                                "claim": "unsupported causal claim",
                                "reasons": ["causal language exceeds evidence"],
                            }
                        ]
                    },
                )

            return [
                {
                    "id": "B",
                    "phase": "claim_evidence",
                    "severity": GateSeverity.BLOCK,
                    "check": check,
                }
            ]

    runtime = CapturingRuntime()
    dossier = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=EvidencePack(),
        phases=[
            PhaseSpec(
                id="claim_evidence",
                handler=lambda _task, _context: {},
                prompt="write claim evidence",
                expected_outputs=["claim_evidence_map.md"],
                gate_ids=["B"],
                repair_prompt="repair claims",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert "unsupported causal claim" in runtime.prompts[-1]
    assert dossier.gate_reports[0]["results"][0]["evidence"]["flagged"][0]["claim"] == (
        "unsupported causal claim"
    )


def test_orchestrator_uses_repair_expected_outputs(tmp_path: Path):
    class CapturingRuntime(MockRuntime):
        name = "capturing"

        def __init__(self):
            self.repair_outputs = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            if ":repair:" in task.task_id:
                self.repair_outputs = list(task.expected_outputs)
            for rel in task.expected_outputs:
                path = context.run_dir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok", encoding="utf-8")
            return TaskResult(task_id=task.task_id, status="ok")

    class RepairPack:
        name = "repair-pack"

        def gate_registry(self):
            calls = {"n": 0}

            def check(_dossier):
                calls["n"] += 1
                return GateResult(
                    gate_id="B",
                    passed=calls["n"] > 1,
                    severity=GateSeverity.BLOCK,
                )

            return [{"id": "B", "phase": "claim_evidence", "severity": GateSeverity.BLOCK, "check": check}]

    runtime = CapturingRuntime()
    EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=RepairPack(),
        phases=[
            PhaseSpec(
                id="claim_evidence",
                handler=lambda _task, _context: {},
                prompt="write claims",
                expected_outputs=["claim_evidence_map.md"],
                repair_expected_outputs=["claim_evidence_map.md", "paper_draft_v0.qmd"],
                gate_ids=["B"],
                repair_prompt="repair",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    ).run(job_id="job-1", resume=False)

    assert runtime.repair_outputs == ["claim_evidence_map.md", "paper_draft_v0.qmd"]


def test_orchestrator_blocks_after_repair_budget_exhausted(tmp_path: Path):
    class StillInsufficientRuntime(MockRuntime):
        name = "still-insufficient"

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            refs = context.run_dir / "references.bib"
            refs.write_text("@article{one,title={One}}\n", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 2:
                    return GateResult.pass_("A")
                return GateResult.fail("A", details="bib_count=%s (floor 2)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    orchestrator = EngineV3Orchestrator(
        runtime=StillInsufficientRuntime(),
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair refs",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.phases["data"] == "blocked"
    assert [report["blocked"] for report in dossier.gate_reports] == [True, True]


def test_orchestrator_accepts_repair_outputs_when_gate_passes_despite_runtime_error(tmp_path: Path):
    class NoisyRepairRuntime(MockRuntime):
        name = "noisy-repair"

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            refs = context.run_dir / "references.bib"
            if ":repair:" in task.task_id:
                refs.write_text("@article{one}\n@article{two}\n", encoding="utf-8")
                return TaskResult(
                    task_id=task.task_id,
                    status="error",
                    blockers=["nonzero exit after writing repaired artifacts"],
                )
            refs.write_text("@article{one}\n", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 2:
                    return GateResult.pass_("A", "bib_count=%s" % count)
                return GateResult.fail("A", details="bib_count=%s (floor 2)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    orchestrator = EngineV3Orchestrator(
        runtime=NoisyRepairRuntime(),
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair refs",
                max_repair_attempts=1,
            )
        ],
        dossier_store=DossierStore(tmp_path),
    )

    dossier = orchestrator.run(job_id="job-1", resume=False)

    assert dossier.phases["data"] == "done"
    assert [report["blocked"] for report in dossier.gate_reports] == [True, False]
    assert dossier.delegations[-1]["status"] == "error"


def test_orchestrator_does_not_exceed_total_repair_budget_on_resume(tmp_path: Path):
    class ResumeRepairRuntime(MockRuntime):
        name = "resume-repair"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append(task.task_id)
            refs = context.run_dir / "references.bib"
            refs.write_text("@article{one}\n", encoding="utf-8")
            return TaskResult(
                task_id=task.task_id,
                status="ok",
                outputs={"references.bib": refs},
                changed_files=["references.bib"],
            )

    class RefFloorPack:
        name = "demo"

        def gate_registry(self):
            def check(dossier):
                count = int(dossier.evidence.get("ref_count") or 0)
                if count >= 2:
                    return GateResult.pass_("A", "bib_count=%s" % count)
                return GateResult.fail("A", details="bib_count=%s (floor 2)" % count)

            return [{"id": "A", "phase": "data", "severity": GateSeverity.BLOCK, "check": check}]

    def handler(_task: BrainTask, context: RuntimeContext):
        refs = context.run_dir / "references.bib"
        return {"gate_inputs": {"ref_count": refs.read_text(encoding="utf-8").count("@article")}}

    store = DossierStore(tmp_path)
    dossier = store.create(job_id="job-1", domain="demo")
    dossier.mark_phase("data", "blocked")
    dossier.delegations.append(
        {
            "task_id": "data:repair:1",
            "phase": "data",
            "runtime": "resume-repair",
            "class": "brain",
            "status": "error",
            "declared_outputs": ["references.bib"],
            "changed_files": [],
            "blockers": ["prior failed repair"],
        }
    )
    store.save(dossier)

    runtime = ResumeRepairRuntime()
    final = EngineV3Orchestrator(
        runtime=runtime,
        domain_pack=RefFloorPack(),
        phases=[
            PhaseSpec(
                id="data",
                handler=handler,
                prompt="collect refs",
                expected_outputs=["references.bib"],
                gate_ids=["A"],
                repair_prompt="repair refs",
                max_repair_attempts=1,
            )
        ],
        dossier_store=store,
    ).run(job_id="job-1", resume=True)

    assert runtime.calls == ["data:brain"]
    assert final.phases["data"] == "blocked"
    assert final.delegations[-1]["task_id"] == "data:brain"
