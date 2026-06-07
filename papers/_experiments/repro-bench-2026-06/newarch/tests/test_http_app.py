from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

import http_app
import job_runner
import router


def b_contract(job_id: str = "http-master", level: str = "master", tier: str = "free") -> dict[str, object]:
    return {
        "job_id": job_id,
        "source": "paper-mcp",
        "level": level,
        "tier": tier,
        "topic": "CPU-only HUPD classical ML benchmark",
        "research_question": "Can a complete real-data CPU benchmark lift the patent paper above the reject ceiling?",
        "contribution_type": "benchmark",
        "data_source": {
            "name": "HUPD/hupd",
            "type": "dataset",
            "probe_status": "available",
            "evidence": "HUPD probe passed in planning gate",
        },
        "method": {"approach": "classical sklearn benchmark", "compute": "cpu"},
        "target_journal": "Scientometrics",
        "innovation_point": "A fail-closed, reproducible real-data patent benchmark.",
    }


class HttpAppTest(unittest.TestCase):
    def test_dry_run_accepts_b_contract_and_derives_master_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(http_app.create_app(Path(tmp) / "jobs"))
            response = client.post("/jobs/dry-run", json=b_contract())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["research_contract"]["contribution"], "benchmark: A fail-closed, reproducible real-data patent benchmark.")
        self.assertTrue(payload["research_contract"]["data_source"]["probe_required"])
        self.assertEqual(payload["routing_decision"]["level"], "master")
        self.assertEqual(payload["routing_decision"]["content_threshold"], 6.0)
        self.assertEqual(payload["routing_decision"]["review_depth"], "7dim")
        self.assertFalse(payload["routing_decision"]["needs_real_experiment_lane"])

    def test_dry_run_derives_phd_policy_from_b_contract(self) -> None:
        contract = b_contract("http-phd", level="phd", tier="vip")
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(http_app.create_app(Path(tmp) / "jobs"))
            response = client.post("/jobs/dry-run", json=contract)

        self.assertEqual(response.status_code, 200)
        decision = response.json()["routing_decision"]
        self.assertEqual(decision["level"], "phd")
        self.assertEqual(decision["content_threshold"], 7.0)
        self.assertEqual(decision["review_depth"], "7dim+elite")
        self.assertTrue(decision["needs_real_experiment_lane"])
        self.assertEqual(decision["model_chain"], ["agy", "codex"])

    def test_post_jobs_requires_and_reuses_idempotency_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            client = TestClient(http_app.create_app(jobs_dir, start_worker=False))

            missing = client.post("/jobs", json=b_contract("idem-1"))
            self.assertEqual(missing.status_code, 400)

            with mock.patch.object(job_runner, "submit", wraps=job_runner.submit) as submit:
                first = client.post("/jobs", json=b_contract("idem-1"), headers={"Idempotency-Key": "same-key"})
                second = client.post("/jobs", json=b_contract("idem-1"), headers={"Idempotency-Key": "same-key"})

            self.assertEqual(first.status_code, 202)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.json()["job_id"], "idem-1")
            self.assertEqual(second.json()["job_id"], "idem-1")
            self.assertTrue(second.json()["idempotent_replay"])
            self.assertEqual(submit.call_count, 1)

    def test_status_and_result_map_runner_state_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            job_dir = jobs_dir / "mapped"
            job_dir.mkdir(parents=True)
            contract = http_app.normalize_contract(b_contract("mapped"))
            route = router.route_contract(contract)
            job_runner.write_state(
                job_dir,
                {
                    **job_runner.initial_state("mapped", contract, route),
                    "status": "done",
                    "run_dir": str(job_dir / "run"),
                    "output": {
                        "job_id": "mapped",
                        "status": "done",
                        "run_dir": str(job_dir / "run"),
                        "level": "master",
                        "content_score": 6.58,
                        "content_threshold": 6.0,
                        "meets_threshold": True,
                        "desk_reject": 0.389,
                        "above_5_5": True,
                        "gates": {"data_availability": "available"},
                        "doi_real_rate": 1.0,
                        "pdf_path": str(job_dir / "run" / "paper_draft_v0.pdf"),
                        "real_vs_simulated": {"simulated": False},
                        "blockers": [],
                    },
                },
            )
            client = TestClient(http_app.create_app(jobs_dir))

            status = client.get("/jobs/mapped/status")
            result = client.get("/jobs/mapped/result")

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "done")
        self.assertEqual(status.json()["level"], "master")
        self.assertEqual(status.json()["content_threshold"], 6.0)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["content_score"], 6.58)
        self.assertTrue(result.json()["meets_threshold"])
        self.assertEqual(result.json()["pdf"], result.json()["pdf_path"])

    def test_paper_endpoint_returns_job_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            job_dir = jobs_dir / "paper-ready"
            run_dir = job_dir / "run"
            run_dir.mkdir(parents=True)
            pdf = run_dir / "paper_draft_v0.pdf"
            pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
            contract = http_app.normalize_contract(b_contract("paper-ready"))
            job_runner.write_state(
                job_dir,
                {
                    **job_runner.initial_state("paper-ready", contract, router.route_contract(contract)),
                    "status": "done",
                    "run_dir": str(run_dir),
                },
            )
            client = TestClient(http_app.create_app(jobs_dir))

            response = client.get("/jobs/paper-ready/paper")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))

    def test_paper_endpoint_404s_when_pdf_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            job_dir = jobs_dir / "paper-missing"
            run_dir = job_dir / "run"
            run_dir.mkdir(parents=True)
            contract = http_app.normalize_contract(b_contract("paper-missing"))
            job_runner.write_state(
                job_dir,
                {
                    **job_runner.initial_state("paper-missing", contract, router.route_contract(contract)),
                    "status": "done",
                    "run_dir": str(run_dir),
                },
            )
            client = TestClient(http_app.create_app(jobs_dir))

            response = client.get("/jobs/paper-missing/paper")

        self.assertEqual(response.status_code, 404)

    def test_probe_data_source_uses_runner_gate(self) -> None:
        contract = b_contract("probe-blocked")
        contract["data_source"] = {
            "name": "missing-private-corpus",
            "type": "dataset",
            "probe_status": "available",
        }
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(http_app.create_app(Path(tmp) / "jobs", start_worker=False))
            response = client.post("/jobs/probe-data-source", json=contract)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("probe-verified", payload["reason"])


if __name__ == "__main__":
    unittest.main()
