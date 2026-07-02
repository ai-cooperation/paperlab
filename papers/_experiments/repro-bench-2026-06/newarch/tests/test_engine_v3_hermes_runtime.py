from __future__ import annotations

import signal
import stat
import time
from pathlib import Path

import pytest

from engine_v3.core import BrainTask, RuntimeContext, WorkerTask
from engine_v3.runtimes.hermes import HermesCodexRuntime, HermesRunResult, _terminate_run_dir_processes

pytestmark = pytest.mark.unit


def test_hermes_runtime_brain_writes_declared_file(tmp_path: Path):
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["command"] = command
        (cwd / "gap.md").write_text("gap", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_brain(
        BrainTask(phase="gap", prompt="write gap", expected_outputs=["gap.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["gap.md"]
    assert "openai-codex" in seen["command"]


def test_hermes_runtime_worker_uses_big_pickle_and_writes_declared_file(tmp_path: Path):
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["command"] = command
        (cwd / "sections" / "intro.md").parent.mkdir(parents=True)
        (cwd / "sections" / "intro.md").write_text("intro", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_worker(
        WorkerTask(phase="write", prompt="write intro", expected_outputs=["sections/intro.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["sections/intro.md"]
    assert "big-pickle" in seen["command"]
    assert "--toolsets" in seen["command"]


def test_review_heal_requires_fresh_review_json_and_log(tmp_path: Path):
    (tmp_path / "quality_review_round1.json").write_text('{"old": true}\n', encoding="utf-8")
    (tmp_path / "quality_review_log.md").write_text("old log\n", encoding="utf-8")

    def stale_runner(_command: list[str], cwd: Path, _timeout_s: int):
        assert (cwd / "quality_review_round1.json").read_text(encoding="utf-8") == '{"old": true}\n'
        assert (cwd / "quality_review_log.md").read_text(encoding="utf-8") == "old log\n"
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    stale = HermesCodexRuntime(runner=stale_runner).run_brain(
        BrainTask(
            phase="review_heal",
            prompt="review",
            expected_outputs=["quality_review_round1.json", "quality_review_log.md"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert stale.status == "blocked"
    assert stale.changed_files == []
    assert stale.blockers == [
        "stale declared output: quality_review_log.md",
        "stale declared output: quality_review_round1.json",
    ]
    assert (tmp_path / "quality_review_round1.json").read_text(encoding="utf-8") == '{"old": true}\n'
    assert (tmp_path / "quality_review_log.md").read_text(encoding="utf-8") == "old log\n"
    backups = list((tmp_path / "artifacts" / "stale_outputs").glob("**/quality_review_round1.json"))
    assert backups

    def fresh_runner(_command: list[str], cwd: Path, _timeout_s: int):
        time.sleep(0.001)
        (cwd / "quality_review_round1.json").write_text('{"new": true}\n', encoding="utf-8")
        (cwd / "quality_review_log.md").write_text("new log\n", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    fresh = HermesCodexRuntime(runner=fresh_runner).run_brain(
        BrainTask(
            phase="review_heal",
            prompt="review",
            expected_outputs=["quality_review_round1.json", "quality_review_log.md"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert fresh.status == "ok"
    assert fresh.changed_files == ["quality_review_log.md", "quality_review_round1.json"]


def test_review_heal_snapshots_old_review_files_before_runner(tmp_path: Path):
    (tmp_path / "quality_review_round1.json").write_text('{"old": true}\n', encoding="utf-8")
    (tmp_path / "quality_review_log.md").write_text("old log\n", encoding="utf-8")

    def runner(_command: list[str], cwd: Path, _timeout_s: int):
        assert (cwd / "quality_review_round1.json").read_text(encoding="utf-8") == '{"old": true}\n'
        assert (cwd / "quality_review_log.md").read_text(encoding="utf-8") == "old log\n"
        (cwd / "quality_review_round1.json").write_text('{"new": true}\n', encoding="utf-8")
        (cwd / "quality_review_log.md").write_text("new log\n", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    result = HermesCodexRuntime(runner=runner).run_brain(
        BrainTask(
            phase="review_heal",
            prompt="review",
            expected_outputs=["quality_review_round1.json", "quality_review_log.md"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert (tmp_path / "quality_review_round1.json").read_text(encoding="utf-8") == '{"new": true}\n'
    assert (tmp_path / "quality_review_log.md").read_text(encoding="utf-8") == "new log\n"
    assert any(
        path.read_text(encoding="utf-8") == '{"old": true}\n'
        for path in (tmp_path / "artifacts" / "stale_outputs").glob("**/quality_review_round1.json")
    )


def test_hermes_runtime_loads_pack_skill_bundle(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "paper-draft"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("paper rules", encoding="utf-8")
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["prompt"] = command[command.index("-z") + 1]
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner, skill_root=skill_root)
    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["paper-draft"]},
        ),
    )

    assert result.status == "ok"
    assert "engine_v3_skill_context.md" in seen["prompt"]
    assert "paper rules" not in seen["prompt"]
    assert (tmp_path / "engine_v3_skill_context.md").read_text(encoding="utf-8").count("paper rules") == 1


def test_hermes_runtime_keeps_large_skill_bundle_out_of_argv(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "qmd-writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("table rule\n" * 10000, encoding="utf-8")
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["prompt"] = command[command.index("-z") + 1]
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner, skill_root=skill_root)
    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["qmd-writer"]},
        ),
    )

    assert result.status == "ok"
    assert len(seen["prompt"]) < 1000
    assert "table rule" not in seen["prompt"]
    assert (tmp_path / "engine_v3_skill_context.md").stat().st_size > 100_000


def test_hermes_runtime_errors_when_declared_skill_is_missing(tmp_path: Path):
    called = False

    def runner(_command: list[str], _cwd: Path, _timeout_s: int):
        nonlocal called
        called = True
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_brain(
        BrainTask(phase="write", prompt="write"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["qmd-writer"]},
        ),
    )

    assert result.status == "error"
    assert result.blockers == ["missing skill: qmd-writer"]
    assert called is False


@pytest.mark.parametrize(
    "message",
    [
        "usage limit reached",
        "authentication failed",
        "rate limit exceeded",
        "provider unavailable",
    ],
)
def test_hermes_runtime_classifies_provider_failures_as_error(tmp_path: Path, message: str):
    runtime = HermesCodexRuntime(
        runner=lambda _command, _cwd, _timeout_s: HermesRunResult(
            exit_code=0,
            stdout=message,
            stderr="",
        )
    )

    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "error"
    assert result.blockers == [message]


def test_hermes_runtime_blocks_when_declared_output_missing(tmp_path: Path):
    runtime = HermesCodexRuntime(
        runner=lambda _command, _cwd, _timeout_s: HermesRunResult(
            exit_code=0,
            stdout="CHILD_OK",
            stderr="",
        )
    )

    result = runtime.run_worker(
        WorkerTask(phase="write", prompt="write", expected_outputs=["missing.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.blockers == ["missing declared output: missing.md"]


def test_hermes_runtime_finishes_when_outputs_exist_but_process_hangs(tmp_path: Path):
    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("done.md").write_text("done", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_complete_grace_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(phase="data", prompt="write", expected_outputs=["done.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["done.md"]
    assert time.monotonic() - started < 5
    assert "terminated after all declared outputs were stable" in result.stdout_tail


def test_hermes_runtime_unblocks_when_partial_outputs_stop_changing(tmp_path: Path):
    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("references.bib").write_text("@article{x, title={x}}", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_complete_grace_s=0.1,
        output_partial_idle_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(
            phase="data",
            prompt="write",
            expected_outputs=["references.bib", "figures/fig_forest_plot.svg"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.changed_files == ["references.bib"]
    assert result.blockers == ["missing declared output: figures/fig_forest_plot.svg"]
    assert time.monotonic() - started < 5
    assert "terminated after partial declared outputs stopped changing" in result.stdout_tail


def test_hermes_runtime_unblocks_when_no_declared_outputs_appear(tmp_path: Path):
    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("paper_gate_post_tool.log").write_text("working but no declared outputs", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_startup_idle_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(
            phase="data",
            prompt="write",
            expected_outputs=["references.bib", "doi_audit.json"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.changed_files == []
    assert result.blockers == [
        "missing declared output: references.bib",
        "missing declared output: doi_audit.json",
    ]
    assert time.monotonic() - started < 5
    assert "terminated after no declared outputs appeared" in result.stdout_tail


def test_review_heal_watches_review_artifacts_not_manuscript_edits(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text("old draft\n", encoding="utf-8")
    (tmp_path / "paper_springer.qmd").write_text("old springer\n", encoding="utf-8")

    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("paper_springer.qmd").write_text("edited but no review\\n", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_startup_idle_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(
            phase="review_heal",
            prompt="repair review",
            expected_outputs=[
                "quality_review_round1.json",
                "quality_review_log.md",
                "paper_draft_v0.qmd",
                "paper_springer.qmd",
            ],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.blockers == [
        "missing declared output: quality_review_round1.json",
        "missing declared output: quality_review_log.md",
    ]
    assert result.changed_files == ["paper_springer.qmd"]
    assert time.monotonic() - started < 5
    assert "terminated after no declared outputs appeared" in result.stdout_tail


def test_review_heal_finishes_when_fresh_review_artifacts_exist(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text("draft\n", encoding="utf-8")
    (tmp_path / "paper_springer.qmd").write_text("springer\n", encoding="utf-8")

    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("quality_review_round1.json").write_text('{"p0_count": 0}\\n', encoding="utf-8")
Path("quality_review_log.md").write_text("reviewed\\n", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_complete_grace_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(
            phase="review_heal",
            prompt="repair review",
            expected_outputs=[
                "quality_review_round1.json",
                "quality_review_log.md",
                "paper_draft_v0.qmd",
                "paper_springer.qmd",
            ],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["quality_review_log.md", "quality_review_round1.json"]
    assert time.monotonic() - started < 5
    assert "terminated after all declared outputs were stable" in result.stdout_tail


def test_hermes_runtime_terminates_orphan_process_groups_in_run_dir(tmp_path: Path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    nested_dir = run_dir / "real_experiments"
    nested_dir.mkdir()
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "123").mkdir()
    (proc_root / "124").mkdir()
    (proc_root / "999").mkdir()
    (proc_root / "123" / "cwd").symlink_to(run_dir)
    (proc_root / "124" / "cwd").symlink_to(nested_dir)
    (proc_root / "999" / "cwd").symlink_to(tmp_path)

    def fake_getpgid(pid: int) -> int:
        return {123: 9001, 124: 9002, 999: 9999}[pid]

    killed = []
    monkeypatch.setattr("engine_v3.runtimes.hermes.os.getpgid", fake_getpgid)
    monkeypatch.setattr("engine_v3.runtimes.hermes.os.getpid", lambda: 111)
    monkeypatch.setattr("engine_v3.runtimes.hermes.os.killpg", lambda pgid, sig: killed.append((pgid, sig)))
    monkeypatch.setattr("engine_v3.runtimes.hermes.time.sleep", lambda _seconds: None)

    _terminate_run_dir_processes(run_dir, proc_root=proc_root, grace_s=0)

    assert killed == [
        (9001, signal.SIGTERM),
        (9002, signal.SIGTERM),
        (9001, signal.SIGKILL),
        (9002, signal.SIGKILL),
    ]


def test_outputs_complete_requires_change_against_baseline(tmp_path: Path):
    """Repair tasks edit declared outputs IN PLACE. Pre-existing unchanged files
    must NOT count as completion — the 2026-07-02 rerun showed the watcher
    killing Hermes after 60s grace because the repair targets already existed,
    reporting exit 0 with zero changed files."""
    from engine_v3.runtimes.hermes import (
        _existing_outputs,
        _output_signature_map,
        _outputs_complete,
    )

    (tmp_path / "paper_draft_v0.qmd").write_text("old body", encoding="utf-8")
    (tmp_path / "paper_springer.qmd").write_text("old body", encoding="utf-8")
    expected = ["paper_draft_v0.qmd", "paper_springer.qmd"]
    baseline = _output_signature_map(_existing_outputs(tmp_path, expected))

    # unchanged pre-existing outputs: not complete (Hermes still working)
    existing = _existing_outputs(tmp_path, expected)
    assert _outputs_complete(existing, expected, baseline, set()) is False

    # one file rewritten, the other untouched: still not complete
    (tmp_path / "paper_draft_v0.qmd").write_text("expanded body " * 50, encoding="utf-8")
    existing = _existing_outputs(tmp_path, expected)
    assert _outputs_complete(existing, expected, baseline, set()) is False

    # both rewritten: complete
    (tmp_path / "paper_springer.qmd").write_text("expanded body " * 50, encoding="utf-8")
    existing = _existing_outputs(tmp_path, expected)
    assert _outputs_complete(existing, expected, baseline, set()) is True


def test_outputs_complete_for_fresh_files_created_from_empty_baseline(tmp_path: Path):
    from engine_v3.runtimes.hermes import _existing_outputs, _outputs_complete

    expected = ["phase3_positioning.md"]
    # baseline empty: file did not exist before the task
    assert _outputs_complete(_existing_outputs(tmp_path, expected), expected, {}, set()) is False
    (tmp_path / "phase3_positioning.md").write_text("new artifact", encoding="utf-8")
    assert _outputs_complete(_existing_outputs(tmp_path, expected), expected, {}, set()) is True


def test_complete_grace_resets_while_hermes_keeps_editing(tmp_path: Path):
    """The completion grace is a STABILITY window: as long as declared outputs
    keep changing, Hermes is still working and must not be killed (run3 killed
    the expansion mid-edit at 1468/3000 words because grace started at the
    first save and never reset)."""
    from engine_v3.runtimes.hermes import _output_signature_map, _existing_outputs, _subprocess_runner

    expected = ["out_a.txt", "out_b.txt"]
    for rel in expected:
        (tmp_path / rel).write_text("baseline", encoding="utf-8")
    baseline = _output_signature_map(_existing_outputs(tmp_path, expected))
    # writes immediately, keeps editing for ~6s, then marks done and idles
    script = (
        "for i in 1 2 3 4 5 6; do "
        "echo edit-$i >> out_a.txt; echo edit-$i >> out_b.txt; sleep 1; "
        "done; echo FINISHED; sleep 30"
    )
    result = _subprocess_runner(
        ["bash", "-c", script],
        tmp_path,
        timeout_s=60,
        expected_outputs=expected,
        baseline_signature=baseline,
        output_complete_grace_s=3.0,
        output_startup_idle_s=60.0,
        output_partial_idle_s=60.0,
    )

    # all six edits must have landed: the kill may only happen after the
    # outputs went stable for the grace window
    assert "edit-6" in (tmp_path / "out_a.txt").read_text(encoding="utf-8")
    assert "edit-6" in (tmp_path / "out_b.txt").read_text(encoding="utf-8")
    assert "FINISHED" in result.stdout
    assert result.terminated_reason == "outputs_complete"


def test_idle_kill_without_output_change_is_reported_not_faked_ok(tmp_path: Path):
    """A watcher kill before any output changed must not masquerade as a
    successful run (run3 repair:4 was killed thinking at 180s idle and came
    back status ok / changed=[] -> repair_noop burned the budget)."""
    from engine_v3.runtimes.hermes import _output_signature_map, _existing_outputs, _subprocess_runner

    expected = ["out_a.txt"]
    (tmp_path / "out_a.txt").write_text("baseline", encoding="utf-8")
    baseline = _output_signature_map(_existing_outputs(tmp_path, expected))
    result = _subprocess_runner(
        ["bash", "-c", "sleep 30"],
        tmp_path,
        timeout_s=60,
        expected_outputs=expected,
        baseline_signature=baseline,
        output_complete_grace_s=2.0,
        output_startup_idle_s=60.0,
        output_partial_idle_s=2.0,
    )

    assert result.terminated_reason == "partial_idle"


def test_runtime_reports_blocked_when_watcher_killed_hermes_without_changes(tmp_path: Path):
    from engine_v3.runtimes.hermes import HermesCodexRuntime, HermesRunResult
    from engine_v3.core import BrainTask, RuntimeContext

    (tmp_path / "paper_draft_v0.qmd").write_text("unchanged", encoding="utf-8")

    def fake_runner(command, cwd, timeout_s):
        return HermesRunResult(
            exit_code=0,
            stdout="",
            stderr="Hermes process terminated after partial declared outputs stopped changing for 180.0 seconds.",
            terminated_reason="partial_idle",
        )

    rt = HermesCodexRuntime(runner=fake_runner, require_skill_bundle=False)
    task = BrainTask(
        task_id="render_gates:repair:1",
        phase="render_gates",
        prompt="repair",
        expected_outputs=["paper_draft_v0.qmd"],
    )
    result = rt.run_brain(task, RuntimeContext(job_id="j", run_dir=tmp_path, metadata={}))

    assert result.status == "blocked"
    assert any("watcher terminated" in b for b in result.blockers)
