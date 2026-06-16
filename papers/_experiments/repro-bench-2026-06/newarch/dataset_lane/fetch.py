"""Deterministic dataset fetch. The AGENT resolves which files to download (it writes
`data/download_plan.json` = [{url, filename}], e.g. by reading a landing page); but
PYTHON does the actual HTTP GET and records provenance. The agent therefore cannot
fabricate data — a listed URL either returns real bytes (recorded by sha256) or fails.

No dataset, column, or study is named here. Format detection is by extension + a content
sniff only; full parsing is the analysis script's job (it has pandas).
"""
from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path
from typing import Any

from . import schema

MAX_BYTES = 512 * 1024 * 1024          # 512 MB per file ceiling
PROBE_BYTES = 1 << 16                   # sniff window for format/readability
_TABULAR = {"csv", "tsv", "xpt", "sas7bdat", "feather", "parquet", "dta", "sav", "xlsx", "xls", "json"}
_ARCHIVE = {"zip", "gz", "tar", "tgz", "bz2", "xz", "7z"}


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _detect_format(filename: str, head: bytes, content_type: str) -> str:
    ext = _ext(filename)
    if ext in _TABULAR or ext in _ARCHIVE:
        return ext
    sniff = head[:512].lstrip().lower()
    if sniff.startswith(b"<!doctype html") or sniff.startswith(b"<html") or b"text/html" in content_type.encode():
        return "html"
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:2] == b"\x1f\x8b":
        return "gz"
    return ext or "unknown"


def _probe_csv(raw: bytes) -> dict[str, Any]:
    try:
        text = raw[:PROBE_BYTES].decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        cols = rows[0] if rows else []
        return {"readable": len(cols) > 0, "sampled_rows": max(0, len(rows) - 1),
                "columns": cols[:64], "nonempty_columns": sum(1 for c in cols if c.strip())}
    except Exception:  # noqa: BLE001
        return {"readable": False}


def _download_one(url: str, dest: Path, timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "paperlab-dataset-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:   # noqa: S310 - public dataset URL
        status = getattr(resp, "status", 200)
        content_type = resp.headers.get("Content-Type", "")
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise RuntimeError(f"file exceeds {MAX_BYTES} bytes: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    fmt = _detect_format(dest.name, data[:PROBE_BYTES], content_type)
    art: dict[str, Any] = {
        "source_url": url, "filename": dest.name, "http_status": status,
        "content_type": content_type, "bytes": len(data),
        "sha256": schema.sha256_bytes(data), "detected_format": fmt,
        "is_archive": fmt in _ARCHIVE, "is_html": fmt == "html",
    }
    if fmt in ("csv", "tsv"):
        art["probe_sample"] = _probe_csv(data)
    elif fmt in _TABULAR or fmt in _ARCHIVE:
        art["probe_sample"] = {"readable": True, "note": f"{fmt} read by the analysis step (pandas)"}
    else:
        art["probe_sample"] = {"readable": False, "note": fmt}
    return art


def fetch(run_dir: Path, contract: dict[str, Any], *, timeout: int = 120,
          downloader: Any = None) -> dict[str, Any]:
    """Execute the agent's `data/download_plan.json`, write `data/manifest.json` +
    `data_source_lock.json`. `downloader(url, dest, timeout)->artifact` is injectable for
    offline tests. Returns the manifest dict. Never invents data: only what a real GET
    returned (or, in tests, what the injected downloader returned) is recorded."""
    run_dir = Path(run_dir)
    plan = schema.read_json(run_dir, schema.DOWNLOAD_PLAN) or []
    if isinstance(plan, dict):
        plan = plan.get("files") or plan.get("downloads") or []
    dl = downloader or _download_one
    artifacts: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in plan:
        url = (item or {}).get("url")
        if not url:
            continue
        fname = (item or {}).get("filename") or url.rsplit("/", 1)[-1].split("?")[0] or f"file_{len(artifacts)}"
        dest = run_dir / schema.RAW_DIR / fname
        try:
            artifacts.append(dl(url, dest, timeout))
        except Exception as exc:  # noqa: BLE001 - a failed download is recorded, not fatal here; the gate decides
            errors.append(f"{url}: {type(exc).__name__}: {str(exc)[:160]}")
    manifest = {
        "data_source": contract.get("data_source"),
        "artifacts": artifacts,
        "errors": errors,
        "n_files": len(artifacts),
    }
    # hash the manifest body (excluding the hash field itself) so it can be re-verified
    manifest["manifest_sha256"] = schema.sha256_bytes(_canon(manifest))
    schema.write_json(run_dir, schema.MANIFEST, manifest)
    has_real = any(a.get("bytes", 0) > 0 and not a.get("is_html") for a in artifacts)
    schema.write_json(run_dir, schema.SOURCE_LOCK, {
        "source": (contract.get("data_source") or {}).get("name"),
        "kind": "dataset",
        "status": "available" if has_real else "unavailable",
        "manifest_sha256": manifest["manifest_sha256"],
        "n_files": len(artifacts),
    })
    return manifest


def _canon(obj: Any) -> bytes:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
