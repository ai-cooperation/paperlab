from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import paper_driver as pd


def _contract(refs: list[dict]) -> dict:
    return {"contract_version": 2, "job_id": "j", "topic": "t",
            "literature": {"verified_refs": refs}}


class VerifiedRefsExtractTest(unittest.TestCase):
    def test_v1_contract_has_no_verified_refs(self) -> None:
        self.assertEqual(pd.contract_verified_refs({"topic": "t"}), [])

    def test_only_verified_with_key_kept(self) -> None:
        refs = [
            {"key": "a", "verified": True},
            {"key": "b", "verified": False},   # not verified
            {"key": "", "verified": True},      # no key
            {"verified": True},                  # no key field
        ]
        out = pd.contract_verified_refs(_contract(refs))
        self.assertEqual([r["key"] for r in out], ["a"])


class BibEscapeTest(unittest.TestCase):
    def test_latex_specials_neutralised(self) -> None:
        out = pd._bib_escape(r"A & B \write18{x} 50% #1 a_b {y}")
        # No raw command sequence survives, and every special is backslash-escaped.
        self.assertNotIn(r"\write18", out)
        self.assertEqual(out.count("&"), out.count(r"\&"))   # no bare &
        self.assertEqual(out.count("%"), out.count(r"\%"))   # no bare %
        self.assertEqual(out.count("{"), out.count("}"))     # braces balanced
        self.assertIn(r"\textbackslash{}", out)

    def test_control_chars_stripped(self) -> None:
        self.assertNotIn("\x00", pd._bib_escape("a\x00b"))


class SampleIndicesTest(unittest.TestCase):
    def test_small_population_returns_all(self) -> None:
        self.assertEqual(pd._sample_indices(3, 8), [0, 1, 2])

    def test_even_spacing_and_distinct(self) -> None:
        idx = pd._sample_indices(100, 8)
        self.assertEqual(len(idx), len(set(idx)))
        self.assertTrue(all(0 <= i < 100 for i in idx))
        self.assertEqual(idx, sorted(idx))


class BuildRefsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name)

    def test_builds_bib_metadata_report(self) -> None:
        refs = [
            {"key": "smith2020", "title": "Title One", "authors": ["Smith, J.", "Lee, K."],
             "year": "2020", "doi": "10.1/x", "verified": True},
            {"key": "smith2020", "title": "Dup key", "authors": "Solo", "year": 2021,
             "doi": "10.2/y", "verified": True},  # duplicate key -> deduped
        ]
        n = pd.build_refs_from_verified(self.run_dir, refs)
        self.assertEqual(n, 2)
        bib = (self.run_dir / "references.bib").read_text()
        self.assertIn("@article{smith2020,", bib)
        self.assertIn("@article{smith2020_2,", bib)
        self.assertIn("author = {Smith, J. and Lee, K.}", bib)
        meta = json.loads((self.run_dir / "metadata.json").read_text())
        self.assertEqual({m["key"] for m in meta}, {"smith2020", "smith2020_2"})
        self.assertTrue(all(m["status"] == "verified_by_b" for m in meta))
        self.assertTrue((self.run_dir / "doi_verification_report.md").is_file())


class SpotCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name)
        self.refs = [
            {"key": f"r{i}", "title": f"T{i}", "doi": f"10.1/{i}", "verified": True}
            for i in range(20)
        ]
        pd.build_refs_from_verified(self.run_dir, self.refs)

    def test_clean_sample_accepts_b_without_full_audit(self) -> None:
        with mock.patch.object(pd.doi_audit, "check_crossref", return_value=True) as cc, \
             mock.patch.object(pd.time, "sleep"), \
             mock.patch.object(pd, "doi_gate") as full:
            res = pd.doi_gate_spotcheck(self.run_dir, self.refs, sample_n=5)
        self.assertTrue(res["passed"])
        self.assertEqual(res["mode"], "spotcheck")
        self.assertEqual(cc.call_count, 5)        # only the sample
        full.assert_not_called()                   # no full re-verify
        audit = json.loads((self.run_dir / "doi_audit.json").read_text())
        self.assertEqual(audit["sampled"], 5)

    def test_failing_sample_escalates_to_full_gate(self) -> None:
        with mock.patch.object(pd.doi_audit, "check_crossref", return_value=False), \
             mock.patch.object(pd.time, "sleep"), \
             mock.patch.object(pd, "doi_gate",
                               return_value={"passed": False, "real_existence_rate": 0.0}) as full:
            res = pd.doi_gate_spotcheck(self.run_dir, self.refs, sample_n=5)
        full.assert_called_once()
        self.assertFalse(res["passed"])
        self.assertIn("escalated_from_spotcheck", res)

    def test_network_undetermined_sample_trusts_b(self) -> None:
        with mock.patch.object(pd.doi_audit, "check_crossref", return_value=None), \
             mock.patch.object(pd.time, "sleep"), \
             mock.patch.object(pd, "doi_gate") as full:
            res = pd.doi_gate_spotcheck(self.run_dir, self.refs, sample_n=5)
        self.assertTrue(res["passed"])
        self.assertIsNone(res["real_existence_rate"])
        full.assert_not_called()


if __name__ == "__main__":
    unittest.main()
