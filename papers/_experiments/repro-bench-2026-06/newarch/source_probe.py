#!/usr/bin/env python3
"""Generalised data-source availability probe (grill Step-4 — confirm, don't collect).

PAPER_MCP_GRILL_DESIGN.md Step 4: during grill, b calls a to test whether the
chosen data source is actually OBTAINABLE, and greys out unavailable options on
the spot. This confirms reachability only — it does NOT download/collect the data.

Supported source kinds (by data_source.type + fields):
- HUPD dataset (name contains "hupd") -> full schema probe (data_availability_gate).
- dataset / api with a `url`         -> HTTP reachability (HEAD, GET-range fallback).
- literature                          -> OpenAlex corpus size for the topic/query.

Returns a lock payload: {source, type, status: available|unavailable, sample_evidence,
reason?, probe_seconds, generated_at_unix}. Never raises on a probe failure — an
unreachable source is reported as status=unavailable, not an exception.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import data_availability_gate

MAILTO = "aicooperation.tw@gmail.com"
OPENALEX_WORKS = "https://api.openalex.org/works"
DEFAULT_MIN_RECORDS = 50  # literature lane needs a non-trivial corpus to analyse
UA = f"paperbench/1.0 (mailto:{MAILTO})"


def _lock(source: str, type_: str, status: str, evidence: dict[str, Any],
          reason: str = "", seconds: float = 0.0) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "type": type_,
        "status": status,
        "sample_evidence": evidence,
        "generated_at_unix": round(time.time(), 3),
        "probe_seconds": round(seconds, 3),
    }
    if reason:
        payload["reason"] = reason
    return payload


def probe_url(url: str, timeout: int = 15) -> dict[str, Any]:
    """Reachability only. HEAD first; some hosts reject HEAD, so fall back to a
    1-byte ranged GET. status=available iff a 200/206/2xx/3xx is returned."""
    started = time.time()
    for method, headers in (("HEAD", {}), ("GET", {"Range": "bytes=0-0"})):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code = r.status
                ctype = r.headers.get("Content-Type", "")
                clen = r.headers.get("Content-Length")
                ev = {"http_status": code, "content_type": ctype, "content_length": clen, "method": method}
                ok = 200 <= code < 400
                return _lock(url, "url", "available" if ok else "unavailable", ev,
                             "" if ok else f"HTTP {code}", time.time() - started)
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue  # host dislikes HEAD; retry with GET-range
            return _lock(url, "url", "unavailable", {"http_status": e.code, "method": method},
                         f"HTTP {e.code}", time.time() - started)
        except Exception as e:  # noqa: BLE001 - any network failure = unavailable, not a crash
            if method == "HEAD":
                continue
            return _lock(url, "url", "unavailable", {"error": str(e)[:200], "method": method},
                         "unreachable", time.time() - started)
    return _lock(url, "url", "unavailable", {"error": "no method succeeded"},
                 "unreachable", time.time() - started)


def probe_openalex(query: str, min_records: int = DEFAULT_MIN_RECORDS, timeout: int = 20) -> dict[str, Any]:
    """Confirm a literature/meta-analysis corpus exists: OpenAlex must return at
    least `min_records` works for the topic. Counts only — nothing is downloaded."""
    started = time.time()
    url = f"{OPENALEX_WORKS}?search={urllib.parse.quote(query)}&per_page=1&mailto={MAILTO}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", "ignore"))
        count = int((body.get("meta") or {}).get("count") or 0)
    except Exception as e:  # noqa: BLE001
        return _lock("OpenAlex", "literature", "unavailable", {"error": str(e)[:200]},
                     "OpenAlex query failed", time.time() - started)
    ok = count >= min_records
    return _lock("OpenAlex", "literature", "available" if ok else "unavailable",
                 {"records": count, "min_records": min_records, "query": query},
                 "" if ok else f"only {count} works (< {min_records})", time.time() - started)


def probe(contract: dict[str, Any], run_dir: Path | None = None) -> dict[str, Any]:
    """Dispatch a generalised availability probe by data_source type. Confirmation
    only (grill Step-4). Writes data_source_lock.json when run_dir is given."""
    ds = contract.get("data_source")
    if not isinstance(ds, dict):
        lock = _lock("unknown", "unknown", "unavailable", {"error": "no data_source"},
                     "data_source must be an object")
    else:
        type_ = str(ds.get("type") or "").lower()
        name = str(ds.get("name") or "")
        url = str(ds.get("url") or "").strip()
        if "hupd" in name.lower() or "harvard uspto" in name.lower():
            lock = data_availability_gate.probe_hupd(run_dir or Path("."), sample_rows=160) \
                if run_dir else _lock("HUPD/hupd", "dataset", "available", {"note": "HUPD registered"})
        elif type_ in ("literature", "meta-analysis", "meta_analysis"):
            lock = probe_openalex(name or str(contract.get("topic") or ""),
                                  int(ds.get("min_records") or DEFAULT_MIN_RECORDS))
            lock["type"] = type_
        elif url:
            lock = probe_url(url)
            lock["source"] = name or url
            lock["type"] = type_ or "url"
        else:
            lock = _lock(name or "unknown", type_ or "unknown", "unavailable",
                         {"error": "no url and not a known registered source"},
                         "a literature source needs a topic/query; a dataset/api source needs a `url` to probe")
    if run_dir is not None:
        try:
            (run_dir / "data_source_lock.json").write_text(
                json.dumps(lock, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return lock


if __name__ == "__main__":  # quick manual probe: python source_probe.py '<json contract>'
    import sys
    c = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(probe(c), indent=2, ensure_ascii=False))
