from __future__ import annotations

import unittest

import real_patent_experiment as exp


def synthetic_rows(n: int = 90) -> list[dict[str, str]]:
    sections = ["A", "B", "G"]
    rows: list[dict[str, str]] = []
    for i in range(n):
        section = sections[i % len(sections)]
        accepted = i % 2 == 0
        rows.append({
            "patent_number": str(i),
            "decision": "ACCEPTED" if accepted else "REJECTED",
            "title": f"{section} device {'allowed' if accepted else 'rejected'}",
            "abstract": f"{section} technical process with {'stable' if accepted else 'unstable'} result",
            "claims": f"{section} claim {'grant' if accepted else 'objection'} apparatus",
            "cpc_label": f"{section}01",
            "cpc_section": section,
            "filing_date": f"2016-01-{(i % 28) + 1:02d}",
        })
    return rows


class FullPatentExperimentTest(unittest.TestCase):
    def test_full_benchmark_contract(self) -> None:
        result = exp.run_full_benchmark(
            synthetic_rows(),
            cv_splits=3,
            max_features=500,
            bootstrap_samples=20,
            random_state=7,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["simulation_markers"], 0)
        self.assertFalse(result["gpu_used"])
        self.assertEqual(set(result["tasks"]), {"acceptance", "cpc_section"})
        self.assertEqual(set(result["features"]), {"tfidf", "bow"})
        self.assertGreaterEqual(len(result["models"]), 5)
        self.assertGreaterEqual(len(result["benchmark"]), 20)
        self.assertIn("mcnemar", result["statistical_tests"])
        self.assertIn("training_size_curve", result["ablations"])
        self.assertIn("cpc_distribution", result["scientometrics"])
        self.assertIn("acceptance_rate_by_section", result["scientometrics"])


if __name__ == "__main__":
    unittest.main()
