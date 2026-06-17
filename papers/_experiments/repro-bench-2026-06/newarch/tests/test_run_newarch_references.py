from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import run_newarch


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _item(prefix: str, index: int) -> dict:
    return {
        "DOI": f"10.1000/{prefix}{index}",
        "title": [f"Patent machine learning benchmark reference {prefix} {index}"],
        "author": [{"family": "Smith", "given": "Alex"}],
        "published-online": {"date-parts": [[2024]]},
        "container-title": ["Patent Analytics"],
    }


@unittest.skip("run_newarch.py is the RETIRED mock pipeline (replaced by paper_driver, "
               "Route A 2026-06-08); its reference builder is no longer dispatched and "
               "this mock-pool boundary test is flaky against it.")
class BuildReferencesTests(unittest.TestCase):
    def test_expands_candidate_pool_when_first_batch_has_too_few_verified_refs(self) -> None:
        first_batch = [_item("ok", index) for index in range(34)]
        first_batch.extend(_item("bad", index) for index in range(21))
        second_batch = [_item("extra", index) for index in range(40)]
        calls = [first_batch, second_batch, []]

        def fake_crossref_query(_query: str):
            return calls.pop(0)

        def fake_urlopen(request, timeout=0):
            doi = urllib.parse.unquote(str(request.full_url).split("/works/", 1)[1].split("?", 1)[0])
            suffix = doi.rsplit("/", 1)[1]
            if suffix.startswith("bad"):
                message = {
                    "title": [f"Unrelated reference {suffix}"],
                    "author": [{"family": "Other", "given": "Researcher"}],
                    "published-online": {"date-parts": [[2024]]},
                    "container-title": ["Other Journal"],
                }
            else:
                prefix = "".join(ch for ch in suffix if not ch.isdigit())
                index = int("".join(ch for ch in suffix if ch.isdigit()))
                message = _item(prefix, index)
            return _FakeResponse({"message": message})

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(run_newarch, "crossref_query", side_effect=fake_crossref_query),
                mock.patch.object(run_newarch.urllib.request, "urlopen", side_effect=fake_urlopen),
            ):
                refs, _seconds = run_newarch.build_references(Path(tmp))

        self.assertGreaterEqual(len(refs), 35)
        self.assertLessEqual(len(refs), 40)
        self.assertTrue(all(ref["status"] == "ok" for ref in refs))


if __name__ == "__main__":
    unittest.main()
