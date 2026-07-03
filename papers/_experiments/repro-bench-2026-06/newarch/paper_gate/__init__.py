from __future__ import annotations

from pathlib import Path
from typing import Any


# V2 runs produced standalone audit artifacts; V3.2 replaced them with the
# dossier + deterministic gates (V3_2_SPEC.md: legacy audit artifacts "must not
# fail delivery solely because they are absent"). Round 10 (2026-07-03): this
# plugin blocked the reviewer's own render attempt on a V3.2 run by demanding
# v2 artifacts, which the reviewer then reported as an unresolvable P0.
REQUIRED_V2 = (
    "doi_verification_report.md",
    "gate_report.json",
    "claim_evidence_map.md",
    "figure_audit.md",
    "coherence_audit.md",
    "gate_d_readability.md",
    "quality_review_log.md",
)

REQUIRED_V3 = (
    "claim_evidence_map.md",
    "references.bib",
    "quality_review_log.md",
)


def _required_for(root: Path) -> tuple[str, ...]:
    if (root / "dossier.v3.json").is_file():
        return REQUIRED_V3
    return REQUIRED_V2


def _extract_command(args: Any) -> tuple[str, Path]:
    if not isinstance(args, dict):
        return "", Path(".").resolve()
    cmd = str(args.get("command") or args.get("cmd") or "")
    workdir = Path(args.get("workdir") or args.get("cwd") or ".").expanduser()
    return cmd, workdir.resolve()


def _pre_tool_call(tool_name: str = "", args: Any = None, **_: Any) -> dict[str, str] | None:
    cmd, root = _extract_command(args)
    lowered = f"{tool_name} {cmd}".lower()
    gated = ("render" in lowered) or ("submit" in lowered) or ("paper_draft_v0.pdf" in lowered)
    if not gated:
        return None
    missing = [name for name in _required_for(root) if not (root / name).is_file()]
    if missing:
        return {
            "action": "block",
            "message": "paper_gate blocked render/submit; missing artifacts: "
            + ", ".join(missing),
        }
    return None


def _post_tool_call(tool_name: str = "", args: Any = None, result: Any = None, **_: Any) -> None:
    cmd, root = _extract_command(args)
    if "render" not in cmd.lower() and "submit" not in cmd.lower():
        return None
    try:
        with (root / "paper_gate_post_tool.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{tool_name}\t{cmd}\t{type(result).__name__}\n")
    except Exception:
        return None
    return None


def register(ctx: Any) -> None:
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_hook("post_tool_call", _post_tool_call)
