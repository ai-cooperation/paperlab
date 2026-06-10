"""Deterministic real-Springer (elsarticle) render via Quarto + xelatex.

Produces a journal-formatted paper_draft_v0.pdf from paper_draft_v0.qmd using the
quarto-journals/elsevier extension (elsarticle.cls) + scientometrics.csl — the same
stack the Paper Lab Scientometrics papers use.

Core philosophy (matches the rest of the pipeline): the weak generation model cannot
be trusted to emit perfect journal frontmatter, so we NORMALISE it deterministically
(Paper-1 / Scientometrics standard) before handing off to Quarto. Bib HTML-entity
corruption (`&amp;`) is likewise sanitised deterministically — xelatex treats a bare
`&` as an alignment tab and aborts otherwise.

Falls back to the reportlab renderer at the call site if Quarto is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS = SCRIPT_DIR / "assets"
QUARTO_BIN = os.environ.get("PAPER_QUARTO_BIN", str(Path.home() / "opt" / "quarto" / "bin" / "quarto"))

DEFAULT_KEYWORDS = ["reproducible benchmark", "text classification", "machine learning"]


def quarto_available() -> bool:
    return Path(QUARTO_BIN).is_file() or shutil.which("quarto") is not None


def _quarto() -> str:
    return QUARTO_BIN if Path(QUARTO_BIN).is_file() else "quarto"


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text_without_fences, body)."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _old_title(fm: str, contract: dict[str, Any]) -> str:
    m = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', fm)
    if m and m.group(1).strip():
        return m.group(1).strip().strip('"')
    return str(contract.get("topic") or "Research Manuscript").strip()


def _extract_abstract(fm: str, body: str) -> tuple[str, str]:
    """Pull the abstract out of a leading `# Abstract` section (preferred) or the old
    frontmatter; return (abstract_text, body_without_abstract_section)."""
    am = re.search(r"(?ms)^#\s*Abstract\s*\n+(.*?)(?=\n#\s)", body)
    if am:
        abstract = " ".join(am.group(1).split())
        body = body[: am.start()] + body[am.end():]
        return abstract, body
    fm_abs = re.search(r"(?ms)^abstract:\s*\|?\s*\n((?:[ \t]+.*\n?)+)", fm)
    if fm_abs:
        return " ".join(fm_abs.group(1).split()), body
    fm_abs1 = re.search(r'(?m)^abstract:\s*"?(.+?)"?\s*$', fm)
    if fm_abs1:
        return fm_abs1.group(1).strip(), body
    return "", body


def _extract_keywords(fm: str, contract: dict[str, Any]) -> list[str]:
    block = re.search(r"(?ms)^keywords:\s*\n((?:\s*-\s*.+\n?)+)", fm)
    if block:
        kws = [re.sub(r"^\s*-\s*", "", ln).strip() for ln in block.group(1).splitlines() if ln.strip()]
        kws = [k for k in kws if k]
        if kws:
            return kws[:6]
    seed = " ".join(str(contract.get(k) or "") for k in ("topic", "method", "contribution"))
    toks = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", seed)
    stop = {"with", "from", "this", "that", "their", "using", "based", "analysis", "extension"}
    picked: list[str] = []
    for t in toks:
        tl = t.lower()
        if tl not in stop and tl not in picked:
            picked.append(tl)
        if len(picked) >= 5:
            break
    return picked or DEFAULT_KEYWORDS


def _strip_trailing_references(body: str) -> str:
    # Quarto regenerates the bibliography; a hand-written `# References` heading at the
    # very end would otherwise double up.
    return re.sub(r"(?ms)\n#\s*References\s*\n*\Z", "\n", body)


def normalize_frontmatter(run_dir: Path, contract: dict[str, Any], src_name: str = "paper_draft_v0.qmd",
                          out_name: str = "paper_springer.qmd") -> Path:
    """Write a journal-normalised COPY (out_name) of the canonical qmd. The canonical
    paper_draft_v0.qmd is left untouched so the consistency / claim-evidence / prose
    gates keep operating on the model's original output."""
    qmd = run_dir / src_name
    text = qmd.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    title = _old_title(fm, contract)
    abstract, body = _extract_abstract(fm, body)
    keywords = _extract_keywords(fm, contract)
    body = _strip_trailing_references(body).lstrip("\n")

    abstract = abstract or "Abstract pending."
    abs_yaml = "\n".join("  " + line for line in re.findall(r".{1,110}(?:\s|$)", abstract))
    kw_yaml = "\n".join(f"  - {k}" for k in keywords)
    journal = str(contract.get("target_journal") or "Scientometrics").strip() or "Scientometrics"

    title_esc = title.replace('"', r"\"")
    new_fm = (
        "---\n"
        f'title: "{title_esc}"\n'
        "author:\n"
        "  - name: Cooperation.TW\n"
        "    email: paperlab@cooperation.tw\n"
        "    affiliations:\n"
        "      - id: pl\n"
        "        name: Paper Lab\n"
        "        city: Taipei\n"
        "        country: Taiwan\n"
        "    attributes:\n"
        "      corresponding: true\n"
        "date: last-modified\n"
        "abstract: |\n"
        f"{abs_yaml}\n"
        "keywords:\n"
        f"{kw_yaml}\n"
        "format:\n"
        "  elsevier-pdf:\n"
        "    keep-tex: true\n"
        "    pdf-engine: xelatex\n"
        "    journal:\n"
        f"      name: {journal}\n"
        "      formatting: review\n"
        "      model: 3p\n"
        "      cite-style: authoryear\n"
        "csl: scientometrics.csl\n"
        "bibliography: references.bib\n"
        "number-sections: true\n"
        "link-citations: true\n"
        "---\n\n"
    )
    out = run_dir / out_name
    out.write_text(new_fm + body, encoding="utf-8")
    return out


_HTML_ENTITIES = (("&amp;", r"\&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'))


def sanitize_bib(run_dir: Path) -> None:
    bib = run_dir / "references.bib"
    if not bib.is_file():
        return
    t = bib.read_text(encoding="utf-8")
    for ent, rep in _HTML_ENTITIES:
        t = t.replace(ent, rep)
    # Escape any remaining bare ampersand (xelatex alignment-tab trap) without
    # double-escaping an already-escaped \&.
    t = re.sub(r"(?<!\\)&", r"\\&", t)
    bib.write_text(t, encoding="utf-8")


def ensure_assets(run_dir: Path) -> None:
    ext_src = ASSETS / "_extensions"
    if ext_src.is_dir():
        shutil.copytree(ext_src, run_dir / "_extensions", dirs_exist_ok=True)
    csl_src = ASSETS / "scientometrics.csl"
    if csl_src.is_file():
        shutil.copy2(csl_src, run_dir / "scientometrics.csl")


def render(run_dir: Path, contract: dict[str, Any] | None = None, timeout_s: int = 420) -> bool:
    """Normalise + render paper_draft_v0.qmd to a real elsarticle PDF. Returns True on
    a valid PDF, False otherwise (caller may fall back to reportlab)."""
    run_dir = Path(run_dir)
    qmd = run_dir / "paper_draft_v0.qmd"
    pdf = run_dir / "paper_draft_v0.pdf"
    if not qmd.is_file() or not quarto_available():
        return False
    if contract is None:
        contract = {}
        cpath = run_dir / "research_contract.json"
        if cpath.is_file():
            try:
                contract = json.loads(cpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                contract = {}
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    work_name = "paper_springer.qmd"
    work_pdf = run_dir / "paper_springer.pdf"
    try:
        normalize_frontmatter(run_dir, contract, out_name=work_name)
        sanitize_bib(run_dir)
        ensure_assets(run_dir)
    except Exception as exc:  # normalisation must never hard-crash the pipeline
        (log_dir / "render_springer.stderr.txt").write_text(f"normalize failed: {exc}", encoding="utf-8")
        return False
    env = os.environ.copy()
    env.setdefault("QUARTO_NO_TINYTEX", "1")
    proc = subprocess.run(
        [_quarto(), "render", work_name, "--to", "elsevier-pdf"],
        cwd=run_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout_s, env=env,
    )
    if work_pdf.is_file() and work_pdf.stat().st_size > 1000:
        shutil.move(str(work_pdf), str(pdf))
        return True
    (log_dir / "render_springer.stderr.txt").write_text(
        (proc.stderr or proc.stdout or "")[-3000:], encoding="utf-8")
    return False


if __name__ == "__main__":
    import sys
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps({"ok": render(rd)}, ensure_ascii=False))
