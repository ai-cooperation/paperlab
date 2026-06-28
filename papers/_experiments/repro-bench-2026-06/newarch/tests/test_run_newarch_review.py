from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import run_newarch


def full_real_result() -> dict[str, object]:
    return {
        "status": "completed",
        "rows": 240,
        "task_summaries": {
            "acceptance": {"n_rows": 160},
            "cpc_section": {"n_rows": 240},
        },
        "benchmark": [
            {
                "task": "acceptance",
                "feature": "TF-IDF",
                "model": "LinearSVC",
                "holdout": {"f1_macro": 0.72},
            },
            {
                "task": "cpc_section",
                "feature": "bag-of-words",
                "model": "LogisticRegression",
                "holdout": {"f1_macro": 0.61},
            },
        ],
    }


def fake_refs() -> list[dict[str, str]]:
    return [{"key": f"ref{i:02d}"} for i in range(45)]


def fake_tables() -> dict[str, str]:
    return {
        "main": "| Task | Feature | Model |\n|---|---|---|\n| acceptance | TF-IDF | LinearSVC |\n",
        "stats": "| Task | Model A | Model B |\n|---|---|---|\n| acceptance | TF-IDF + LinearSVC | bag-of-words + LogisticRegression |\n",
        "ablation": "| Task | Train fraction | Holdout Macro-F1 |\n|---|---:|---:|\n| acceptance | 1.00 | 0.720 |\n",
        "cpc": "| CPC section | Count | Proportion |\n|---|---:|---:|\n| A | 100 | 0.417 |\n",
        "rates": "| CPC section | Accepted | Rejected | Binary n | Acceptance rate |\n|---|---:|---:|---:|---:|\n| A | 60 | 40 | 100 | 0.600 |\n",
    }


class DeterministicReviewTest(unittest.TestCase):
    def test_full_real_skeleton_is_blocked_by_prose_completeness_gate(self) -> None:
        skeleton = """# Abstract
This complete real CPU benchmark contains a critical synthesis, TF-IDF, bag-of-words, LogisticRegression, LinearSVC, RandomForest, GradientBoosting, MultinomialNB, McNemar, bootstrap, training-size ablation, CPC section distribution, does not propose a new model, and names the single HUPD sample.

# Introduction
This section is only a placeholder sentence.

# Related Work
This section is only a placeholder sentence.

# Methods
This section is only a placeholder sentence.

# Results
This section is only a placeholder sentence.

# Scientometric Analysis
This section is only a placeholder sentence.

# Discussion
This section is only a placeholder sentence.

# Limitations
This section is only a placeholder sentence.

# Conclusion
This section is only a placeholder sentence.
"""

        review = run_newarch.deterministic_review(skeleton, full_real_result())

        self.assertLess(review["mean_7dim"], 6.0)
        self.assertGreater(review["p0_count"], 0)
        self.assertIn(
            "P0_PROSE_COMPLETENESS_SKELETON",
            {problem["id"] for problem in review["problems"]},
        )

    def test_full_real_revised_draft_passes_prose_completeness_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "real_experiments").mkdir()
            real_result = full_real_result()
            (run_dir / "real_experiments" / "real_results.json").write_text(
                json.dumps(real_result),
                encoding="utf-8",
            )
            single = run_newarch.qmd_text(
                run_dir,
                fake_refs(),
                fake_tables(),
                real=True,
                model_note="This CPU-only design is reproducible but not externally validated.",
                revised=False,
            )

            revised, _history = run_newarch.run_revision_loop(
                run_dir,
                fake_refs(),
                fake_tables(),
                real_result,
                "This CPU-only design is reproducible but not externally validated.",
                single,
            )
            review = run_newarch.deterministic_review(revised, real_result)

        self.assertTrue(review["prose_completeness"]["passed"])
        self.assertEqual(review["p0_count"], 0)


if __name__ == "__main__":
    unittest.main()
