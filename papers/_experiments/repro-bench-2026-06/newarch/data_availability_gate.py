#!/usr/bin/env python3
"""Deterministic fail-closed data-source feasibility gate for patent runs."""
from __future__ import annotations

import argparse
import io
import json
import tarfile
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


HUPD_SAMPLE_TAR_URL = "https://huggingface.co/datasets/HUPD/hupd/resolve/main/data/sample-jan-2016.tar.gz"
HUPD_SAMPLE_METADATA_URL = "https://huggingface.co/datasets/HUPD/hupd/resolve/main/hupd_metadata_jan16_2022-02-22.feather"
HUPD_LICENSE = "cc-by-sa-4.0"
HUPD_ACCESS = "public HuggingFace dataset files over HTTPS"
REQUIRED_PATENT_FIELDS = ("decision", "title", "abstract", "main_cpc_label", "filing_date")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _request(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "paperbench-data-availability-gate/1.0"},
    )


def head_status(url: str, timeout: int = 25) -> dict[str, Any]:
    with urllib.request.urlopen(_request(url, "HEAD"), timeout=timeout) as resp:
        return {
            "http_status": int(resp.status),
            "content_length": int(resp.headers.get("content-length") or 0),
            "content_type": resp.headers.get("content-type"),
        }


def load_hupd_metadata_evidence(metadata_url: str = HUPD_SAMPLE_METADATA_URL, timeout: int = 40) -> dict[str, Any]:
    import pandas as pd

    with urllib.request.urlopen(_request(metadata_url), timeout=timeout) as resp:
        raw = resp.read()
    df = pd.read_feather(io.BytesIO(raw))
    required = {"application_number", "decision", "filing_date", "main_cpc_label"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"HUPD metadata missing required columns: {missing}")
    return {
        "metadata_rows": int(len(df)),
        "metadata_columns": sorted(str(c) for c in df.columns),
        "metadata_required_columns_present": True,
    }


def normalize_hupd_record(payload: dict[str, Any]) -> dict[str, str] | None:
    missing = [field for field in REQUIRED_PATENT_FIELDS if not str(payload.get(field) or "").strip()]
    if missing:
        return None
    cpc = str(payload.get("main_cpc_label") or "").strip()
    decision = str(payload.get("decision") or "").strip().upper()
    return {
        "patent_number": str(payload.get("application_number") or payload.get("patent_number") or "").strip(),
        "decision": decision,
        "title": str(payload["title"]).strip(),
        "abstract": str(payload["abstract"]).strip(),
        "claims": str(payload.get("claims") or "").strip(),
        "cpc_label": cpc,
        "cpc_section": cpc[:1],
        "filing_date": str(payload["filing_date"]).strip(),
    }


def collect_hupd_sample_rows(
    limit: int,
    tar_url: str = HUPD_SAMPLE_TAR_URL,
    timeout: int = 60,
    max_members: int = 10000,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_members = 0
    with urllib.request.urlopen(_request(tar_url), timeout=timeout) as resp:
        status = getattr(resp, "status", None)
        if status is not None and int(status) != 200:
            raise RuntimeError(f"HUPD sample tar HTTP status was {resp.status}, expected 200")
        with tarfile.open(fileobj=resp, mode="r|gz") as tar:
            for member in tar:
                if seen_members >= max_members or len(rows) >= limit:
                    break
                if not member.isfile() or not member.name.endswith(".json"):
                    continue
                seen_members += 1
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                try:
                    payload = json.loads(handle.read().decode("utf-8", errors="ignore"))
                except json.JSONDecodeError:
                    continue
                row = normalize_hupd_record(payload)
                if row is not None:
                    rows.append(row)
    return rows


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    decisions = Counter(row["decision"] for row in rows)
    cpc_sections = Counter(row["cpc_section"] for row in rows)
    return {
        "sample_rows": len(rows),
        "decision_counts": dict(sorted(decisions.items())),
        "cpc_section_counts": dict(sorted(cpc_sections.items())),
        "sample_patent_numbers": [row["patent_number"] for row in rows[:5] if row["patent_number"]],
        "required_fields": list(REQUIRED_PATENT_FIELDS),
    }


def lock_payload(
    status: str,
    sample_evidence: dict[str, Any],
    reason: str = "",
    seconds: float = 0.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": "HUPD/hupd sample-jan-2016",
        "type": "dataset",
        "status": status,
        "sample_evidence": sample_evidence,
        "license": HUPD_LICENSE,
        "access": HUPD_ACCESS,
        "generated_at_unix": round(time.time(), 3),
        "probe_seconds": round(seconds, 3),
    }
    if reason:
        payload["reason"] = reason
    return payload


def probe_hupd(
    out_dir: Path,
    sample_rows: int = 120,
    min_rows: int = 40,
    min_cpc_classes: int = 2,
    min_decision_classes: int = 2,
    tar_url: str = HUPD_SAMPLE_TAR_URL,
    metadata_url: str = HUPD_SAMPLE_METADATA_URL,
) -> dict[str, Any]:
    started = time.time()
    out_dir = out_dir.expanduser().resolve()
    try:
        tar_head = head_status(tar_url)
        metadata_head = head_status(metadata_url)
        metadata = load_hupd_metadata_evidence(metadata_url)
        rows = collect_hupd_sample_rows(sample_rows, tar_url=tar_url)
        row_summary = summarize_rows(rows)
        evidence = {
            "dataset_id": "HUPD/hupd",
            "config": "sample",
            "tar_head": tar_head,
            "metadata_head": metadata_head,
            **metadata,
            **row_summary,
        }
        cpc_classes = len([k for k, v in row_summary["cpc_section_counts"].items() if v > 0])
        decision_classes = len([k for k, v in row_summary["decision_counts"].items() if v > 0])
        if len(rows) < min_rows:
            raise RuntimeError(f"HUPD sample returned only {len(rows)} valid rows, need {min_rows}")
        if cpc_classes < min_cpc_classes:
            raise RuntimeError(f"HUPD sample returned only {cpc_classes} CPC classes, need {min_cpc_classes}")
        if decision_classes < min_decision_classes:
            raise RuntimeError(f"HUPD sample returned only {decision_classes} decision classes, need {min_decision_classes}")
        payload = lock_payload("available", evidence, seconds=time.time() - started)
    except Exception as exc:
        evidence = {
            "dataset_id": "HUPD/hupd",
            "config": "sample",
            "required_fields": list(REQUIRED_PATENT_FIELDS),
            "error_type": type(exc).__name__,
        }
        payload = lock_payload("unavailable", evidence, reason=str(exc), seconds=time.time() - started)
    write(out_dir / "data_source_lock.json", json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def require_available(lock: dict[str, Any]) -> None:
    if lock.get("status") != "available":
        raise RuntimeError(f"DATA-AVAILABILITY gate failed: {lock.get('reason', 'source unavailable')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-rows", type=int, default=120)
    args = ap.parse_args()
    lock = probe_hupd(Path(args.out), sample_rows=args.sample_rows)
    print(json.dumps(lock, indent=2, ensure_ascii=False))
    return 0 if lock.get("status") == "available" else 2


if __name__ == "__main__":
    raise SystemExit(main())
