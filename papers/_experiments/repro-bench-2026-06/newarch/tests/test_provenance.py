from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import paper_driver as pd


_V2_EXPERIMENT = {
    "contract_version": 2, "job_id": "j", "topic": "t",
    "experiment": {"recipe_id": "hupd_classical_ml_v1"},
}


def _good_result() -> dict:
    return {
        "status": "completed", "simulated": False,
        "tasks": ["acceptance", "cpc_section"],
        "models": ["LogisticRegression"], "features": ["tfidf"],
        "benchmark": {}, "statistical_tests": {"mcnemar": {}},
        "random_state": 42, "source": "HUPD/hupd sample-jan-2016", "rows": 2000,
    }


class ValidateExperimentResultTest(unittest.TestCase):
    def test_v1_contract_skips_validation(self) -> None:
        self.assertIsNone(pd.validate_experiment_result({"topic": "t"}, _good_result()))

    def test_satisfying_result_has_no_errors(self) -> None:
        self.assertEqual(pd.validate_experiment_result(_V2_EXPERIMENT, _good_result()), [])

    def test_simulated_result_is_flagged(self) -> None:
        bad = _good_result()
        bad["simulated"] = True
        errs = pd.validate_experiment_result(_V2_EXPERIMENT, bad)
        self.assertTrue(any("simulated" in e for e in errs))

    def test_missing_task_is_flagged(self) -> None:
        bad = _good_result()
        bad["tasks"] = ["acceptance"]  # missing cpc_section
        errs = pd.validate_experiment_result(_V2_EXPERIMENT, bad)
        self.assertTrue(any("cpc_section" in e for e in errs))


class ProvenanceTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name)
        (self.run_dir / "real_experiments").mkdir()
        self.real = _good_result()
        (self.run_dir / "real_experiments" / "real_results.json").write_text(
            json.dumps(self.real), encoding="utf-8")

    def test_provenance_record_shape(self) -> None:
        prov = pd.write_provenance(self.run_dir, {"job_id": "abc", "schema_hash": "deadbeef"})
        self.assertEqual(prov["job_id"], "abc")
        self.assertEqual(prov["seed"], 42)
        self.assertEqual(prov["data_rows"], 2000)
        self.assertFalse(prov["real_results_simulated"])
        self.assertEqual(len(prov["real_results_sha256"]), 64)
        self.assertEqual(prov["a_schema_hash"], pd.capabilities.schema_hash())
        self.assertIn("python", prov["deps"])
        on_disk = json.loads((self.run_dir / "provenance.json").read_text())
        self.assertEqual(on_disk, prov)

    def test_provenance_without_results_is_still_written(self) -> None:
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(empty, ignore_errors=True))
        prov = pd.write_provenance(empty, {"job_id": "x"})
        self.assertIsNone(prov["real_results_sha256"])
        self.assertIsNone(prov["seed"])
        self.assertTrue((empty / "provenance.json").is_file())


if __name__ == "__main__":
    unittest.main()
