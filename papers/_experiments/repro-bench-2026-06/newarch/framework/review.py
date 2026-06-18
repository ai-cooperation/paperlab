"""Three-stage review + self-heal loop (DESIGN §3.6) — where 60->80 lives.

The strong-brain reviewer (codex-class, NEVER the writer, NEVER the parent) produces
findings + a 7-dim score; the deterministic FLOOR (floor_score.py) is a conservative
hard cross-check, NOT certification. PASS is decided by the floor + the wrapper, not
by a model saying "looks good":

    PASS  ==  p0 == 0  AND  floor NOT failed  AND  strong-review score >= target

On any fail the wrapper delegates fix-agents BY FAILURE TYPE (big-pickle, parent-
level), updates the dossier, and re-reviews. Stop at PASS, OR after `max_rounds`
rounds -> terminal block + report (NEVER a silent pass). The floor is evidence-bound:
fixing prose cannot raise it, so across rounds the floor stays flat while the review
score rises — exactly the signature of real improvement vs gaming.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .dispatch import Dispatcher, WorkerPacket
from .dossier import Dossier

TARGET_SCORE = 80.0
MAX_ROUNDS = 3


@dataclass
class ReviewOutcome:
    round: int
    score: float                                   # strong-brain 7-dim, /100
    p0_count: int
    floor: float                                   # deterministic floor, /100
    floor_failed: bool
    findings_by_type: dict[str, list[str]] = field(default_factory=dict)
    p1_count: int = 0                              # minor findings (cleared only for VIP tier)
    p2_count: int = 0

    def passed(self, target: float, clear_minor: bool = False) -> bool:
        base = self.p0_count == 0 and not self.floor_failed and self.score >= target
        # VIP tier (clear_minor) also requires P1/P2 to be cleared; the standard tier
        # stops at "no P0 + floor ok + score >= target" and leaves minor findings recorded.
        return base and (not clear_minor or (self.p1_count == 0 and self.p2_count == 0))


@dataclass
class SelfHealResult:
    status: str                                    # "passed" | "blocked"
    rounds: int
    history: list[ReviewOutcome]

    @property
    def passed(self) -> bool:
        return self.status == "passed"


# review_fn(dossier, round) -> ReviewOutcome  (strong brain + deterministic floor).
# Injected so the loop is testable; the production wiring is build_review_fn() below.
ReviewFn = Callable[[dict[str, Any], int], ReviewOutcome]


class SelfHealLoop:
    def __init__(self, dossier: Dossier, dispatcher: Dispatcher, review_fn: ReviewFn, *,
                 target_score: float = TARGET_SCORE, max_rounds: int = MAX_ROUNDS,
                 clear_minor: bool = False):
        self.dossier = dossier
        self.dispatcher = dispatcher
        self.review_fn = review_fn
        self.target = target_score
        self.max_rounds = max_rounds
        self.clear_minor = clear_minor          # VIP tier: also heal P1/P2, not just P0+score

    # ── self-heal: one fix-agent per failure type (parent-level fan-out) ─────
    def _dispatch_fixers(self, outcome: ReviewOutcome) -> list[str]:
        dispatched: list[str] = []
        for ftype, findings in outcome.findings_by_type.items():
            packet = WorkerPacket(
                task_id=f"fix-{ftype}-r{outcome.round}",
                role=f"fix:{ftype}", worker_class="fixer",
                task_goal=f"repair {ftype} findings (round {outcome.round})",
                relevant_excerpts="\n".join(findings),
                acceptance_criteria=[f"all {ftype} findings resolved"],
                allowed_files_write=["paper_draft_v0.qmd"])
            res = self.dispatcher.delegate(packet)
            self.dossier.record_delegation(
                {"id": packet.task_id, "task": packet.task_goal,
                 "worker_class": "fixer", "model": packet.resolved_model(),
                 "status": res.status, "failure_type": ftype})
            dispatched.append(ftype)
        return dispatched

    def _record_round(self, outcome: ReviewOutcome, fixers: list[str]) -> None:
        self.dossier.data["revision_loop"] = {
            "round": outcome.round, "score": outcome.score,
            "floor": outcome.floor, "floor_failed": outcome.floor_failed,
            "p0_count": outcome.p0_count, "p1_count": outcome.p1_count,
            "p2_count": outcome.p2_count, "clear_minor": self.clear_minor,
            "target_score": self.target, "remaining_tasks": fixers}
        log = self.dossier.run_dir / "quality_review_log.md"
        line = (f"- round {outcome.round}: score={outcome.score} floor={outcome.floor} "
                f"p0={outcome.p0_count} floor_failed={outcome.floor_failed} "
                f"fixers={fixers}\n")
        with log.open("a", encoding="utf-8") as fh:
            if outcome.round == 1:
                fh.write("# Quality review log (self-heal)\n\n")
            fh.write(line)
        self.dossier.save()

    def _block_and_report(self, history: list[ReviewOutcome]) -> None:
        last = history[-1]
        self.dossier.update_status(
            blocked=True,
            blockers=[f"review: {self.max_rounds} rounds, score {last.score} < {self.target} "
                      f"or p0={last.p0_count} or floor_failed={last.floor_failed}"])
        (self.dossier.run_dir / "blocked_review.json").write_text(
            __import__("json").dumps(
                {"status": "blocked_review", "rounds": len(history),
                 "final_score": last.score, "floor_failed": last.floor_failed,
                 "p0_count": last.p0_count}, indent=2), encoding="utf-8")

    def run(self) -> SelfHealResult:
        history: list[ReviewOutcome] = []
        for rnd in range(1, self.max_rounds + 1):
            outcome = self.review_fn(self.dossier.data, rnd)
            history.append(outcome)
            if outcome.passed(self.target, self.clear_minor):
                self._record_round(outcome, [])
                self.dossier.update_status(blocked=False)
                return SelfHealResult("passed", rnd, history)
            fixers = self._dispatch_fixers(outcome)        # self-heal by failure type
            self._record_round(outcome, fixers)
        self._block_and_report(history)                    # terminal: no silent pass
        return SelfHealResult("blocked", self.max_rounds, history)


# ── production wiring (live): strong-brain reviewer (dispatch) + deterministic floor
def build_review_fn(dispatcher: Dispatcher, floor_fn: Callable[[dict[str, Any]], dict[str, Any]],
                    parse_review: Callable[[Any], tuple[float, int, dict[str, list[str]]]]) -> ReviewFn:
    """Compose a ReviewFn from a strong-brain reviewer dispatch + the deterministic
    floor. The reviewer is a child != writer != parent (anti-self-grading, §3.6); the
    floor is the un-gameable cross-check. Used by the orchestrator's Phase 9."""

    def _review(dossier_data: dict[str, Any], rnd: int) -> ReviewOutcome:
        packet = WorkerPacket(
            task_id=f"review-r{rnd}", role="reviewer", worker_class="reviewer",
            task_goal="7-dim strong-brain review (findings only; never edit the paper)",
            allowed_files_write=[f"review_round_{rnd}.json"])
        result = dispatcher.delegate(packet)
        score, p0, findings = parse_review(result)
        floor = floor_fn(dossier_data)
        return ReviewOutcome(round=rnd, score=score, p0_count=p0,
                             floor=float(floor.get("overall", 0.0)),
                             floor_failed=bool(floor.get("failed", False)),
                             findings_by_type=findings)

    return _review
