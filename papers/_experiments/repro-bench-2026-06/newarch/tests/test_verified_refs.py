from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import paper_driver as pd


def _contract(lit: dict) -> dict:
    return {"contract_version": 2, "job_id": "j", "topic": "t", "literature": lit}


class DoiCandidatesTest(unittest.TestCase):
    def test_v1_contract_has_no_candidates(self) -> None:
        self.assertEqual(pd.contract_doi_candidates({"topic": "t"}), [])

    def test_accepts_verified_refs_and_doi_list_strings(self) -> None:
        c = _contract({
            "verified_refs": [{"key": "a", "doi": "10.1/a", "verified": False}],
            "doi_list": ["10.2/b", {"key": "c", "doi": "10.3/c"}],
        })
        out = pd.contract_doi_candidates(c)
        self.assertEqual([x["doi"] for x in out], ["10.1/a", "10.2/b", "10.3/c"])

    def test_dedups_by_doi_and_ignores_dois_without_value(self) -> None:
        c = _contract({"doi_list": ["10.1/x", "10.1/X", {"doi": ""}, "  "]})
        out = pd.contract_doi_candidates(c)
        self.assertEqual([x["doi"] for x in out], ["10.1/x"])


class BibEscapeTest(unittest.TestCase):
    def test_latex_specials_neutralised(self) -> None:
        out = pd._bib_escape(r"A & B \write18{x} 50% #1 a_b {y}")
        self.assertNotIn(r"\write18", out)
        self.assertEqual(out.count("&"), out.count(r"\&"))   # no bare &
        self.assertEqual(out.count("%"), out.count(r"\%"))   # no bare %
        self.assertEqual(out.count("{"), out.count("}"))     # braces balanced
        self.assertIn(r"\textbackslash{}", out)

    def test_control_chars_stripped(self) -> None:
        self.assertNotIn("\x00", pd._bib_escape("a\x00b"))


def _meta(title: str, authors: list[str], year: str, journal: str = "J") -> tuple[str, dict]:
    return ("ok", {"title": title, "authors": authors, "year": year, "journal": journal})


class BuildRefsVerifyCompleteTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name)

    def test_completes_metadata_and_verifies(self) -> None:
        cands = [{"key": "smith", "doi": "10.1/a"}, {"key": None, "doi": "10.2/b"}]
        results = {
            "10.1/a": _meta("Real Title", ["Smith, John"], "2020"),
            "10.2/b": _meta("Second", ["Lee, K", "Wang, M"], "2021"),
        }
        with mock.patch.object(pd.doi_audit, "fetch_crossref_meta",
                               side_effect=lambda d, **k: results[d]), \
             mock.patch.object(pd.time, "sleep"):
            audit = pd.build_refs_from_doi_list(self.run_dir, cands)
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["crossref_real"], 2)
        self.assertEqual(audit["real_existence_rate"], 1.0)
        bib = (self.run_dir / "references.bib").read_text()
        self.assertIn("title = {Real Title}", bib)          # completed from CrossRef
        self.assertIn("author = {Smith, John}", bib)
        self.assertIn("journal = {J}", bib)
        meta = json.loads((self.run_dir / "metadata.json").read_text())
        self.assertTrue(all(m["status"] == "crossref_real" for m in meta))
        # citekey synthesized when contract omitted it
        self.assertIn("lee2021", {m["key"] for m in meta})

    def test_fabricated_doi_dropped_and_can_fail_floor(self) -> None:
        cands = [{"key": "good", "doi": "10.1/a"}, {"key": "fake", "doi": "10.9/zzz"}]
        results = {"10.1/a": _meta("Good", ["A"], "2020"), "10.9/zzz": ("404", None)}
        with mock.patch.object(pd.doi_audit, "fetch_crossref_meta",
                               side_effect=lambda d, **k: results[d]), \
             mock.patch.object(pd.time, "sleep"):
            audit = pd.build_refs_from_doi_list(self.run_dir, cands)
        self.assertEqual(audit["kept"], 1)                  # fake dropped
        self.assertEqual(audit["suspicious_404"], 1)
        self.assertEqual(audit["real_existence_rate"], 0.5)
        self.assertFalse(audit["passed"])                   # 0.5 < 0.80 floor
        self.assertIn("10.9/zzz", audit["suspicious_dois"])
        bib = (self.run_dir / "references.bib").read_text()
        self.assertNotIn("10.9/zzz", bib)

    def test_arxiv_404_kept_not_counted_as_fabrication(self) -> None:
        cands = [{"key": "v", "doi": "10.48550/arXiv.1706.03762"},
                 {"key": "r", "doi": "10.1/real"}]
        results = {"10.48550/arXiv.1706.03762": ("404", None),
                   "10.1/real": _meta("R", ["X"], "2019")}
        with mock.patch.object(pd.doi_audit, "fetch_crossref_meta",
                               side_effect=lambda d, **k: results[d]), \
             mock.patch.object(pd.time, "sleep"):
            audit = pd.build_refs_from_doi_list(self.run_dir, cands)
        self.assertEqual(audit["arxiv_on_datacite"], 1)
        self.assertEqual(audit["kept"], 2)                  # arXiv kept
        self.assertEqual(audit["real_existence_rate"], 1.0)  # arXiv not in denominator
        self.assertTrue(audit["passed"])

    def test_all_undetermined_does_not_fail_closed(self) -> None:
        cands = [{"key": "a", "doi": "10.1/a"}]
        with mock.patch.object(pd.doi_audit, "fetch_crossref_meta",
                               return_value=("undet", None)), \
             mock.patch.object(pd.time, "sleep"):
            audit = pd.build_refs_from_doi_list(self.run_dir, cands)
        self.assertIsNone(audit["real_existence_rate"])
        self.assertTrue(audit["passed"])                    # absence of evidence != fabrication


if __name__ == "__main__":
    unittest.main()
