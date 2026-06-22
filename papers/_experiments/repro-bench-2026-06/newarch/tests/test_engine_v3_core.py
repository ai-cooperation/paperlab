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
