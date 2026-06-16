"""Self-upgrading SKILL loop — the "Skill" half of Hermes+Skill. After a run that hit
(and fixed) failures, the BRAIN distils a GENERAL lesson from what went wrong and appends
it to the relevant skill's failure-case library, so the NEXT run does not repeat the
mistake. The system writes its own skills from its own errors.

Domain-agnostic: the lesson is distilled from whatever gate failed; this module names no
dataset. It only ever appends to a SMALL allow-list of dataset-lane skills (never creates
arbitrary files), and de-dupes by title so the library does not grow unbounded.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import schema

Dispatch = Callable[[str, list[str]], bool]

# the only skills the self-upgrade loop may touch (its own lane's skills)
_ALLOWED_SKILLS = {"dataset-fetch", "survey-weighted-analysis", "number-trace-writing"}
_FAILCASE_HEADING = "## 累積失敗案例（self-upgrade，勿手改格式）"


def _distill_prompt(failed_ids: list[str], contract: dict[str, Any]) -> str:
    ds = (contract.get("data_source") or {})
    return (
        "You are the SKILL-UPGRADE brain. A dataset-analysis run hit these deterministic gate "
        f"failures (then they were fixed): {failed_ids}. Context: data_source type="
        f"{ds.get('type')}, a public dataset analysed by an agent.\n"
        "Distil ONE short, GENERAL lesson that would have prevented the FIRST failure — general "
        "to ANY dataset, NOT specific to this one (no specific dataset/column names). Pick the "
        "single most relevant skill to file it under.\n"
        "Write `skill_lesson.json` = {\"skill\": one of "
        f"{sorted(_ALLOWED_SKILLS)}, \"title\": \"<=8-word handle\", "
        "\"lesson\": \"2-4 sentence general rule, imperative voice\"}. "
        "If nothing generalisable, write {\"skill\": null}. End with CHILD_OK.")


def distill_and_persist(run_dir: Path, history: list[dict[str, Any]], contract: dict[str, Any],
                        *, brain: Dispatch, bundle_dir: Path) -> dict[str, Any] | None:
    """If the run fixed real failures, distil + persist a general lesson. Returns the
    persisted {skill, title} or None. Never raises into the caller."""
    failed = sorted({pid for h in (history or []) for pid in (h.get("problem_ids") or []) if pid})
    if not failed:
        return None                                       # clean run — nothing to learn
    try:
        brain(_distill_prompt(failed, contract), [schema.SKILL_LESSON])
        lesson = schema.read_json(run_dir, schema.SKILL_LESSON) or {}
    except Exception:  # noqa: BLE001 - learning is best-effort, never break the run
        return None
    skill = lesson.get("skill")
    title = (lesson.get("title") or "").strip()
    body = (lesson.get("lesson") or "").strip()
    if skill not in _ALLOWED_SKILLS or not title or not body:
        return None
    if _append_failcase(Path(bundle_dir), skill, title, body):
        return {"skill": skill, "title": title}
    return None


def _append_failcase(bundle_dir: Path, skill: str, title: str, body: str) -> bool:
    """Append a de-duped failure-case entry to the skill's SKILL.md. Returns True if added."""
    md = bundle_dir / skill / "SKILL.md"
    if not md.is_file():
        return False
    text = md.read_text(encoding="utf-8")
    if title in text:                                     # already learned this — de-dupe
        return False
    entry = f"\n### {title}\n{body}\n"
    if _FAILCASE_HEADING not in text:
        text = text.rstrip() + f"\n\n{_FAILCASE_HEADING}\n> 由 self-upgrade 迴路從真實失敗自動累積。\n" + entry
    else:
        text = text.rstrip() + "\n" + entry
    md.write_text(text, encoding="utf-8")
    return True
