"""Phase 3 (ENGINE_BUILD_PLAN): the Hermes orchestrator CONTROL PLANE — offline.

The live brain (codex `openai-codex`) + big-pickle `delegate_task` run on ac-2012
(CHILD_OK smoke-verified there 2026-06-14); here we prove the deterministic wrapper
that bounds them: delegate -> CHILD_OK, dossier + checkpoint written, and a FRESH
session resumes from the dossier WITHOUT replaying completed phases. A MockDispatcher
stands in for the live worker.
"""
from __future__ import annotations

import json

import pytest

from framework import (
    MockDispatcher,
    Orchestrator,
    OrchestratorBlocked,
    Phase,
    WorkerPacket,
    WorkerResult,
)
from packs.paper import PaperPack

pytestmark = pytest.mark.unit


def _packet(tid="w1"):
    return WorkerPacket(task_id=tid, role="section-writer", worker_class="drafter",
                        task_goal="draft Methods", allowed_files_write=["sections/methods.md"])


# ── smoke: dispatch CHILD_OK + dossier + checkpoint ──────────────────────────
def test_smoke_dispatch_dossier_checkpoint(tmp_path):
    calls: list[str] = []

    def h_setup(o): calls.append("setup")
    def h_work(o):
        calls.append("work")
        res = o.fan_out([_packet()])
        assert res[0].ok and res[0].status == "CHILD_OK"
    def h_finish(o): calls.append("finish")

    phases = [Phase("setup", h_setup),
              Phase("work", h_work, checkpoint_artifacts=["sections/methods.md"]),
              Phase("finish", h_finish)]
    disp = MockDispatcher()
    orch = Orchestrator(tmp_path, PaperPack(), disp, phases,
                        job_id="smoke", contract={"topic": "t", "level": "master"})
    dossier = orch.run()

    assert calls == ["setup", "work", "finish"]
    assert len(disp.calls) == 1                                   # one delegate_task
    assert (tmp_path / "dossier.json").is_file()
    assert (tmp_path / "checkpoint_manifest.json").is_file()
    assert (tmp_path / "orchestrator_checkpoint.md").is_file()
    dels = dossier.data["delegations"]
    assert len(dels) == 1 and dels[0]["status"] == "CHILD_OK"
    assert dossier.data["status"]["phase"] == "done"
    assert dossier.data["run"]["mode"] == "paper"


# ── fresh-resume: completed phases are NOT replayed ──────────────────────────
def test_resume_does_not_replay_completed_phases(tmp_path):
    state = {"fail_B_once": True}
    calls1: list[str] = []

    def make(calls):
        def hA(o): calls.append("A")
        def hB(o):
            calls.append("B")
            if state["fail_B_once"]:
                state["fail_B_once"] = False
                raise OrchestratorBlocked("B", reason="simulated worker crash")
            o.fan_out([_packet("wB")])
        def hC(o): calls.append("C")
        return [Phase("A", hA, checkpoint_artifacts=[]), Phase("B", hB), Phase("C", hC)]

    pack, disp = PaperPack(), MockDispatcher()
    orch1 = Orchestrator(tmp_path, pack, disp, make(calls1),
                         job_id="resume", contract={"topic": "t"})
    with pytest.raises(OrchestratorBlocked):
        orch1.run()
    assert calls1 == ["A", "B"]                                   # A done, B crashed
    assert orch1.completed_phases() == ["A"]

    # FRESH session over the same run dir — A must NOT run again
    calls2: list[str] = []
    orch2 = Orchestrator.resume(tmp_path, pack, MockDispatcher(), make(calls2))
    orch2.run()
    assert "A" not in calls2                                      # completed phase not replayed
    assert calls2 == ["B", "C"]                                  # crashed B resumed, then C
    assert orch2.completed_phases() == ["A", "B", "C"]


# ── watchdog: runaway dispatch is bounded ────────────────────────────────────
def test_watchdog_caps_dispatch(tmp_path):
    def h(o):
        o.fan_out([_packet(f"w{i}") for i in range(10)])

    orch = Orchestrator(tmp_path, PaperPack(), MockDispatcher(), [Phase("flood", h)],
                        job_id="wd", contract={}, max_steps=3)
    with pytest.raises(OrchestratorBlocked) as ei:
        orch.run()
    assert "watchdog" in ei.value.reason


# ── gate block is terminal, never a silent pass ──────────────────────────────
def test_gate_block_raises_not_silent(tmp_path):
    def h(o):
        pass   # leaves evidence.references empty -> paper Gate A fails

    orch = Orchestrator(tmp_path, PaperPack(), MockDispatcher(),
                        [Phase("p2", h, gates=frozenset({"A"}))],
                        job_id="g", contract={})
    with pytest.raises(OrchestratorBlocked):
        orch.run()
    d = json.loads((tmp_path / "dossier.json").read_text(encoding="utf-8"))
    assert d["status"]["blocked"] is True
    assert "A" in d["status"]["blockers"]


# ── checkpoint manifest hashes detect partial/garbled worker writes ──────────
def test_checkpoint_manifest_hashes(tmp_path):
    def h(o):
        (o.run_dir / "sections").mkdir(exist_ok=True)
        (o.run_dir / "sections" / "methods.md").write_text("body", encoding="utf-8")

    orch = Orchestrator(tmp_path, PaperPack(), MockDispatcher(),
                        [Phase("w", h, checkpoint_artifacts=["sections/methods.md"])],
                        job_id="m", contract={})
    orch.run()
    manifest = json.loads((tmp_path / "checkpoint_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["sections/methods.md"]["sha256"]
    assert orch.dossier.verify_artifacts() == {"sections/methods.md": True}
    (tmp_path / "sections" / "methods.md").write_text("tampered", encoding="utf-8")
    assert orch.dossier.verify_artifacts() == {"sections/methods.md": False}


# ── dossier projection feeds the live status page (P7) ───────────────────────
def test_dossier_projection_shape(tmp_path):
    orch = Orchestrator(tmp_path, PaperPack(), MockDispatcher(), [],
                        job_id="proj", contract={"level": "phd"})
    proj = orch.dossier.projection()
    assert proj["job_id"] == "proj" and proj["tier"] == "phd"
    assert set(proj) >= {"phase", "checkpoint", "blocked", "gaps", "refs", "score", "round"}


def test_custom_responder_can_block_a_worker(tmp_path):
    def responder(p: WorkerPacket) -> WorkerResult:
        return WorkerResult(task_id=p.task_id, status="blocked", blockers=["nope"])

    captured: list[WorkerResult] = []

    def h(o):
        captured.extend(o.fan_out([_packet()]))

    Orchestrator(tmp_path, PaperPack(), MockDispatcher(responder), [Phase("x", h)],
                 job_id="b", contract={}).run()
    assert captured[0].status == "blocked" and not captured[0].ok
