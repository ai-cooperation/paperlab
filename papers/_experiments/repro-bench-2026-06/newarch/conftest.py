"""Pytest harness bootstrap for the engine a-side (newarch).

The deterministic core + gates live in this directory as bare modules
(``import paper_driver``), so the engine root must be importable no matter
where pytest is launched from. Pytest already adds the dir holding the
rootdir conftest to ``sys.path``, but we make it explicit so ``make test``
and ad-hoc ``pytest path/to/test`` both resolve imports identically.

Also publishes the frozen fixtures (ENGINE_BUILD_PLAN.md "Fixtures" table):
big corpora are stored gzipped and decompressed to a tmp path on demand so
the git tree stays slim while the loaded object is the real frozen corpus.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ENGINE_ROOT = Path(__file__).resolve().parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

FIXTURES_DIR = ENGINE_ROOT / "tests" / "fixtures"


def _load_json_maybe_gz(path: Path) -> Any:
    """Load a fixture that may be stored as ``name.json`` or ``name.json.gz``."""
    if path.suffix == ".gz" or not path.exists():
        gz = path if path.suffix == ".gz" else path.with_suffix(path.suffix + ".gz")
        if gz.exists():
            with gzip.open(gz, "rt", encoding="utf-8") as fh:
                return json.load(fh)
    with path.open("rt", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return FIXTURES_DIR / "golden_paper"


@pytest.fixture(scope="session")
def load_fixture_json() -> Callable[[str], Any]:
    """Return a loader for any json fixture by name (transparently un-gzips)."""

    def _load(name: str) -> Any:
        return _load_json_maybe_gz(FIXTURES_DIR / name)

    return _load


@pytest.fixture
def corpus_path(tmp_path: Path) -> Callable[[str], Path]:
    """Materialise a (possibly gzipped) corpus fixture to a real ``.json`` path.

    The deterministic lanes (``meta_analysis.run``, ``phase0`` probe) read a
    corpus cache *path*; this hands them the real frozen corpus on disk without
    committing a 5 MB uncompressed blob.
    """

    def _materialise(name: str) -> Path:
        src = FIXTURES_DIR / name
        out = tmp_path / name
        data = _load_json_maybe_gz(src)
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return out

    return _materialise
