#!/usr/bin/env python3
"""Independent DOI verification gate (anti-fabrication).

Does NOT trust any producer's doi_verification_report.md. Re-checks every DOI
in references.bib by calling CrossRef directly, then compares the ground truth
against what the producer CLAIMED. Surfaces fabrication.

Distinguishes:
- crossref_ok     : CrossRef 200 -> DOI really exists (real)
- arxiv_404       : 10.48550 prefix + CrossRef 404 -> normal (arXiv lives on DataCite, not fabrication)
- suspicious_404  : non-arXiv DOI + CrossRef 404 -> likely fake / wrong
- undetermined    : network/timeout -> cannot judge

Usage: python3 doi_audit.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAILTO = "aicooperation.tw@gmail.com"  # CrossRef polite pool
CROSSREF = "https://api.crossref.org/works/"


def parse_dois(bib_text: str) -> list[str]:
    return re.findall(r'doi\s*=\s*[{"]\s*([^}"\s]+)\s*[}"]', bib_text, re.IGNORECASE)


def check_crossref(doi: str, timeout: int = 8) -> bool | None:
    """True=200 exists, False=404 absent, None=undetermined (network)."""
    url = CROSSREF + urllib.parse.quote(doi, safe="") + f"?mailto={MAILTO}"
    req = urllib.request.Request(
        url, headers={"User-Agent": f"paperbench/1.0 (mailto:{MAILTO})"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return None


def fetch_crossref_meta(doi: str, timeout: int = 8) -> tuple[str, dict | None]:
    """Single-source verify + COMPLETE. Returns (status, meta):
    ("ok", {title, authors:[str], year, journal}) | ("404", None) | ("undet", None).
    a-side uses this to verify a chat-provided DOI AND fill canonical metadata in
    one CrossRef call — no triple-source verification, no producer trust."""
    url = CROSSREF + urllib.parse.quote(doi, safe="") + f"?mailto={MAILTO}"
    req = urllib.request.Request(url, headers={"User-Agent": f"paperbench/1.0 (mailto:{MAILTO})"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return ("undet", None)
            msg = (json.loads(r.read().decode("utf-8", "ignore")) or {}).get("message") or {}
    except urllib.error.HTTPError:
        return ("404", None)
    except Exception:
        return ("undet", None)
    titles = msg.get("title") or []
    authors = []
    for a in msg.get("author") or []:
        if not isinstance(a, dict):
            continue
        if a.get("family"):
            authors.append(", ".join(p for p in (a.get("family"), a.get("given")) if p))
        elif a.get("name"):
            authors.append(str(a["name"]))
    year = ""
    for k in ("issued", "published-print", "published-online", "published"):
        parts = ((msg.get(k) or {}).get("date-parts") or [[]])
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    containers = msg.get("container-title") or []
    return ("ok", {
        "title": titles[0] if titles else "",
        "authors": authors,
        "year": year,
        "journal": containers[0] if containers else "",
    })


def audit_run(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    bib = run_dir / "references.bib"
    out: dict = {"run": run_dir.name}
    if not bib.is_file():
        out["error"] = "no references.bib"
        return out

    dois = parse_dois(bib.read_text(encoding="utf-8", errors="ignore"))
    out["total_dois_in_bib"] = len(dois)

    real = arxiv404 = suspicious = undet = 0
    suspicious_list = []
    for d in dois:
        is_arxiv = d.lower().startswith("10.48550")
        ok = check_crossref(d)
        time.sleep(0.12)  # polite
        if ok is True:
            real += 1
        elif ok is False:
            if is_arxiv:
                arxiv404 += 1
            else:
                suspicious += 1
                suspicious_list.append(d)
        else:
            undet += 1

    out.update(
        crossref_real=real,
        arxiv_on_datacite=arxiv404,
        suspicious_404=suspicious,
        undetermined=undet,
        suspicious_dois=suspicious_list,
    )

    # What did the producer CLAIM?
    report = run_dir / "doi_verification_report.md"
    if report.is_file():
        rt = report.read_text(encoding="utf-8", errors="ignore")
        out["producer_claimed_verified"] = len(re.findall(r"verified", rt, re.IGNORECASE))
        out["producer_claimed_pending"] = len(re.findall(r"pending", rt, re.IGNORECASE))
    else:
        out["producer_claimed_verified"] = 0
        out["producer_claimed_pending"] = 0

    # Honesty signal: real-existence rate among non-arxiv, determinable DOIs
    determinable = real + suspicious
    out["real_existence_rate"] = round(real / determinable, 3) if determinable else None
    return out


def main(argv: list[str]) -> int:
    base = Path(__file__).resolve().parent
    dirs = [Path(a) for a in argv] if argv else sorted(
        p for p in (base / "runs").iterdir() if p.is_dir()
    )
    results = [audit_run(d) for d in dirs]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    out = base / "scores" / "doi_audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
