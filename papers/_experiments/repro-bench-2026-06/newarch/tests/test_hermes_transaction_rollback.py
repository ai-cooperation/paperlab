from __future__ import annotations

"""Transaction rollback for non-ok Hermes attempts.

Root cause (job v3_4dc73d199e17, review_heal infinite stale loop): a
review_heal:repair attempt edited manuscript files (sections/limitations.md,
claim_evidence_map.md, references.bib) successfully but did NOT rewrite the
review artifacts in the same attempt. The runtime judged 'stale declared
output' (blocked) and only restored the QUARANTINED files -- and quarantine
only covered the two review artifacts (_fresh_required_outputs). The manuscript
edits stayed on disk (partial write), producing a "new manuscript + old review"
dirty state that the mtime guard + Gate R correctly refused to re-stamp/pass
forever -> infinite loop.

Fix (three-way audit, agy priority 1): TaskResult non-ok (blocked/error) must
roll back ALL file changes the attempt made (transaction semantics), not only
the review artifacts. Pre-existing files are restored to their pre-attempt
bytes; files created during the attempt are unlinked. ok results keep every
change (unchanged behavior). The mtime guard and Gate R are NOT touched -- they
are correct; widening the stamp would let un-reviewed edits earn a pass verdict.
"""

from pathlib import Path

import pytest

from engine_v3.core import BrainTask, RuntimeContext, WorkerTask
from engine_v3.runtimes.hermes import HermesCodexRuntime, HermesRunResult

pytestmark = pytest.mark.unit


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_stale_block_rolls_back_manuscript_and_new_files(tmp_path: Path):
    """The exact shape of the v3_4dc73d199e17 loop: repair edits an existing
    manuscript file + creates a new file but leaves the review artifacts
    untouched -> stale blocked. All manuscript changes must be rolled back so
    the next attempt starts from a clean 'old manuscript + old review' state."""
    _write(tmp_path / "quality_review_round1.json", '{"delivery": "revise"}\n')
    _write(tmp_path / "quality_review_log.md", "old log\n")
    _write(tmp_path / "sections" / "limitations.md", "old limitations\n")

    def repair_runner(_command, cwd: Path, _timeout_s):
        # edits an existing manuscript file (in place)
        (cwd / "sections" / "limitations.md").write_text(
            "REPAIRED limitations\n", encoding="utf-8"
        )
        # creates a brand new manuscript file
        (cwd / "claim_evidence_map.md").write_text("new map\n", encoding="utf-8")
        # but does NOT rewrite the review artifacts -> stale
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    result = HermesCodexRuntime(runner=repair_runner).run_brain(
        BrainTask(
            task_id="review_heal:repair:3",
            phase="review_heal",
            prompt="repair",
            expected_outputs=[
                "quality_review_round1.json",
                "quality_review_log.md",
                "sections/limitations.md",
                "claim_evidence_map.md",
            ],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert "stale declared output" in result.blockers[0]
    # existing manuscript file restored to pre-attempt bytes
    assert (tmp_path / "sections" / "limitations.md").read_text(
        encoding="utf-8"
    ) == "old limitations\n"
    # file created during the attempt is unlinked (did not exist before)
    assert not (tmp_path / "claim_evidence_map.md").exists()
    # review artifacts unchanged (they were never rewritten)
    assert (tmp_path / "quality_review_round1.json").read_text(
        encoding="utf-8"
    ) == '{"delivery": "revise"}\n'
    assert (tmp_path / "quality_review_log.md").read_text(encoding="utf-8") == "old log\n"
    # after rollback nothing changed vs baseline
    assert result.changed_files == []


def test_missing_block_rolls_back_all_changes(tmp_path: Path):
    """missing declared outputs branch: any partial writes must be rolled
    back too, not left as orphan half-work."""
    _write(tmp_path / "references.bib", "@article{old, title={old}}\n")

    def runner(_command, cwd: Path, _timeout_s):
        (cwd / "references.bib").write_text(
            "@article{new, title={new}}\n", encoding="utf-8"
        )
        (cwd / "sections").mkdir(parents=True, exist_ok=True)
        (cwd / "sections" / "intro.md").write_text("partial intro\n", encoding="utf-8")
        # never writes the declared figure -> missing
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    result = HermesCodexRuntime(runner=runner).run_brain(
        BrainTask(
            task_id="write:1",
            phase="write",
            prompt="write",
            expected_outputs=["references.bib", "sections/intro.md", "figures/fig.svg"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert any("missing declared output: figures/fig.svg" in b for b in result.blockers)
    assert (tmp_path / "references.bib").read_text(encoding="utf-8") == (
        "@article{old, title={old}}\n"
    )
    assert not (tmp_path / "sections" / "intro.md").exists()
    assert result.changed_files == []


def test_provider_failure_rolls_back_all_changes(tmp_path: Path):
    """provider failure branch: even though the model errored, whatever it
    wrote before failing must be reverted."""
    _write(tmp_path / "sections" / "methods.md", "old methods\n")

    def runner(_command, cwd: Path, _timeout_s):
        (cwd / "sections" / "methods.md").write_text("dirty methods\n", encoding="utf-8")
        (cwd / "new_artifact.md").write_text("dirty new\n", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="HTTP 429: usage limit reached", stderr="")

    result = HermesCodexRuntime(
        runner=runner, brain_fallback_model=None
    ).run_brain(
        BrainTask(
            task_id="write:1",
            phase="write",
            prompt="write",
            expected_outputs=["sections/methods.md", "new_artifact.md"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "error"
    assert (tmp_path / "sections" / "methods.md").read_text(encoding="utf-8") == (
        "old methods\n"
    )
    assert not (tmp_path / "new_artifact.md").exists()


def test_exit_nonzero_rolls_back_all_changes(tmp_path: Path):
    """hermes exit != 0 branch also rolls back partial writes."""
    _write(tmp_path / "sections" / "results.md", "old results\n")

    def runner(_command, cwd: Path, _timeout_s):
        (cwd / "sections" / "results.md").write_text("half-written\n", encoding="utf-8")
        return HermesRunResult(exit_code=1, stdout="boom", stderr="traceback")

    result = HermesCodexRuntime(
        runner=runner, brain_fallback_model=None
    ).run_brain(
        BrainTask(
            task_id="write:1",
            phase="write",
            prompt="write",
            expected_outputs=["sections/results.md"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "error"
    assert "hermes exited with 1" in result.details
    assert (tmp_path / "sections" / "results.md").read_text(encoding="utf-8") == (
        "old results\n"
    )


def test_ok_keeps_all_changes(tmp_path: Path):
    """ok results must preserve every change: edited files stay edited, new
    files stay created. This is the non-regression guard for the fix."""
    _write(tmp_path / "sections" / "limitations.md", "old limitations\n")

    def runner(_command, cwd: Path, _timeout_s):
        (cwd / "sections" / "limitations.md").write_text(
            "REPAIRED limitations\n", encoding="utf-8"
        )
        (cwd / "claim_evidence_map.md").write_text("new map\n", encoding="utf-8")
        (cwd / "quality_review_round1.json").write_text('{"delivery":"pass"}\n', encoding="utf-8")
        (cwd / "quality_review_log.md").write_text("fresh log\n", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    result = HermesCodexRuntime(runner=runner).run_brain(
        BrainTask(
            task_id="review_heal:repair:1",
            phase="review_heal",
            prompt="repair then review",
            expected_outputs=[
                "quality_review_round1.json",
                "quality_review_log.md",
                "sections/limitations.md",
                "claim_evidence_map.md",
            ],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert (tmp_path / "sections" / "limitations.md").read_text(
        encoding="utf-8"
    ) == "REPAIRED limitations\n"
    assert (tmp_path / "claim_evidence_map.md").read_text(encoding="utf-8") == "new map\n"
    assert set(result.changed_files) == {
        "quality_review_round1.json",
        "quality_review_log.md",
        "sections/limitations.md",
        "claim_evidence_map.md",
    }


def test_operator_owned_file_still_restored_on_ok(tmp_path: Path):
    """operator_owned_files stay on their independent human-QA channel: a
    worker edit is reverted even when the attempt is ok. The transaction
    rollback must not disturb this pre-existing protection."""
    _write(tmp_path / "operator_findings.md", "- P0: References empty\n")

    def runner(_command, cwd: Path, _timeout_s):
        (cwd / "operator_findings.md").write_text("# cleared by worker\n", encoding="utf-8")
        (cwd / "out.md").write_text("done\n", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    result = HermesCodexRuntime(runner=runner).run_brain(
        BrainTask(
            task_id="review_heal:repair:1",
            phase="review_heal",
            prompt="repair",
            expected_outputs=["out.md"],
        ),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"operator_owned_files": ["operator_findings.md"]},
        ),
    )

    assert result.status == "ok"
    assert (tmp_path / "operator_findings.md").read_text(encoding="utf-8") == (
        "- P0: References empty\n"
    )
    assert (tmp_path / "out.md").read_text(encoding="utf-8") == "done\n"


def test_watcher_termination_rolls_back_partial_writes(tmp_path: Path):
    """The watcher-terminated (partial_idle) path is also non-ok: a repair
    that edited a manuscript file but never reached the review write is
    idle-killed, blocked, and its manuscript edit must be rolled back."""
    import stat as _stat

    _write(tmp_path / "paper_draft_v0.qmd", "old draft\n")

    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("paper_draft_v0.qmd").write_text("edited but no review\\n", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | _stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_startup_idle_s=0.1,
        output_partial_idle_s=0.1,
    )

    result = runtime.run_brain(
        BrainTask(
            task_id="review_heal:repair:1",
            phase="review_heal",
            prompt="repair review",
            expected_outputs=[
                "quality_review_round1.json",
                "quality_review_log.md",
                "paper_draft_v0.qmd",
            ],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    # manuscript edit rolled back to pre-attempt bytes
    assert (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8") == "old draft\n"
    assert result.changed_files == []
