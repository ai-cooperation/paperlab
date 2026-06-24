from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.core import (
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
        }
    ]
    assert dossier.artifacts["paper_draft_v0.qmd"].path == "paper_draft_v0.qmd"
    assert len(dossier.artifacts["paper_draft_v0.qmd"].sha256) == 64


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


def test_orchestrator_repair_attempt_numbers_continue_on_resume(tmp_path: Path):
    class ResumeRepairRuntime(MockRuntime):
        name = "resume-repair"

        def __init__(self):
            self.calls = []

        def run_brain(self, task: BrainTask, context: RuntimeContext):
            self.calls.append(task.task_id)
            refs = context.run_dir / "references.bib"
            refs.write_text(
                "@article{one}\n@article{two}\n"
                if task.task_id == "data:repair:2" else
                "@article{one}\n",
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

    assert runtime.calls == ["data:brain", "data:repair:2"]
    assert final.phases["data"] == "done"
    assert final.delegations[-1]["task_id"] == "data:repair:2"
