from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import job_runner
import router


def hupd_contract(job_id: str = "job-test") -> dict[str, object]:
    return {
        "job_id": job_id,
        "source": "paper-mcp",
        "level": "master",
        "tier": "free",
        "topic": "CPU-only HUPD classical ML benchmark",
        "research_question": "Can a complete real-data CPU benchmark lift the patent paper above the reject ceiling?",
        "contribution": "A fail-closed, reproducible HUPD patent benchmark using classical sklearn models.",
        "data_source": {
            "name": "HUPD/hupd",
            "type": "dataset",
            "probe_required": True,
        },
        "target_journal": "Scientometrics",
        "model_policy": "free_only",
    }


class RouterTest(unittest.TestCase):
    def test_paper_mcp_free_routes_to_big_pickle_no_paid_fallback(self) -> None:
        decision = router.route_contract(hupd_contract())
        self.assertEqual(decision["model_chain"], ["big-pickle"])
        self.assertEqual(decision["driver"], "hermes")
        self.assertEqual(decision["lane"], "mvp/CPU-real")
        self.assertEqual(decision["level"], "master")
        self.assertEqual(decision["content_threshold"], 7.5)  # member tier policy
        self.assertEqual(decision["review_depth"], "7dim")
        self.assertFalse(decision["needs_real_experiment_lane"])
        self.assertFalse(decision["fallback_policy"]["paid_fallback"])

    def test_paper_mcp_vip_phd_routes_with_phd_threshold(self) -> None:
        contract = hupd_contract()
        contract["level"] = "phd"
        contract["tier"] = "vip"
        contract["model_policy"] = "vip"
        decision = router.route_contract(contract)
        self.assertEqual(decision["model_chain"], ["big-pickle"])  # Route A: all lanes hermes+big-pickle
        self.assertEqual(decision["level"], "phd")
        self.assertEqual(decision["content_threshold"], 8.0)  # vip tier policy
        self.assertEqual(decision["review_depth"], "7dim+elite")
        self.assertTrue(decision["needs_real_experiment_lane"])
        self.assertTrue(decision["fallback_policy"]["paid_fallback"])

    def test_free_tier_cannot_request_vip_policy(self) -> None:
        contract = hupd_contract()
        contract["model_policy"] = "vip"
        with self.assertRaises(ValueError):
            router.route_contract(contract)

    def test_free_tier_capped_to_master_level(self) -> None:
        contract = hupd_contract()
        contract["level"] = "phd"  # tier stays free
        with self.assertRaises(ValueError):
            router.route_contract(contract)

    def test_gpu_requires_vip(self) -> None:
        contract = hupd_contract()
        contract["method"] = {"compute": "gpu"}
        with self.assertRaises(ValueError):
            router.route_contract(contract)

    def test_vip_gpu_flags_manual_approval(self) -> None:
        contract = hupd_contract()
        contract.update(level="phd", tier="vip", model_policy="vip", method={"compute": "gpu"})
        decision = router.route_contract(contract)
        self.assertTrue(decision["needs_gpu"])
        self.assertTrue(decision["needs_manual_approval"])

    def test_output_language_validated_and_propagated(self) -> None:
        contract = hupd_contract()
        contract["output_language"] = "zh"
        self.assertEqual(router.route_contract(contract)["output_language"], "zh")
        contract["output_language"] = "fr"
        with self.assertRaises(ValueError):
            router.route_contract(contract)

    def test_level_is_required(self) -> None:
        contract = hupd_contract()
        del contract["level"]
        with self.assertRaises(ValueError):
            router.route_contract(contract)

    def test_journal_level_uses_target_q_and_tier_policy(self) -> None:
        contract = hupd_contract()
        contract["level"] = "journal"
        contract["tier"] = "vip"
        contract["model_policy"] = "vip"
        contract["target_journal_q"] = "q1"
        decision = router.route_contract(contract)
        self.assertEqual(decision["content_threshold"], 8.0)
        self.assertEqual(decision["review_depth"], "full-3-layer")
        self.assertEqual(decision["model_chain"], ["big-pickle"])  # Route A: hermes+big-pickle
        self.assertTrue(decision["needs_real_experiment_lane"])


class JobRunnerTest(unittest.TestCase):
    def test_submit_persists_contract_route_and_submitted_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "contract.json"
            contract_path.write_text(json.dumps(hupd_contract("persisted")), encoding="utf-8")

            submitted = job_runner.submit(contract_path, Path(tmp) / "jobs", start_worker=False)
            state = job_runner.status(submitted["job_id"], Path(tmp) / "jobs")

            self.assertEqual(submitted["job_id"], "persisted")
            self.assertEqual(state["status"], "submitted")
            self.assertEqual(state["routing_decision"]["model_chain"], ["big-pickle"])
            self.assertTrue((Path(tmp) / "jobs" / "persisted" / "contract.json").is_file())
            self.assertTrue((Path(tmp) / "jobs" / "persisted" / "routing_decision.json").is_file())

    def test_fail_closed_unsupported_data_source_blocks_before_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract = hupd_contract("blocked")
            contract["project_id"] = "proj_blocked"
            contract["repo_url"] = "https://github.com/acme/paperlab-proj_blocked"
            contract["proposal_markdown"] = "# Proposal\n\nSkeleton"
            contract["data_source"] = {
                "name": "missing-private-corpus",
                "type": "dataset",
                "probe_required": True,
            }
            job_dir = Path(tmp) / "jobs" / "blocked"
            job_dir.mkdir(parents=True)
            (job_dir / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
            (job_dir / "routing_decision.json").write_text(
                json.dumps(router.route_contract(contract)),
                encoding="utf-8",
            )
            job_runner.write_state(
                job_dir,
                job_runner.initial_state("blocked", contract, router.route_contract(contract)),
            )

            with (
                mock.patch.object(job_runner, "run_pipeline", side_effect=AssertionError("pipeline must not run")),
                mock.patch.object(job_runner, "sync_project_repo", return_value={"status": "disabled"}) as sync_repo,
            ):
                output = job_runner.run_job("blocked", Path(tmp) / "jobs")

            self.assertEqual(output["status"], "blocked")
            self.assertIn("no execution lane", output["blockers"][0])
            self.assertGreaterEqual(sync_repo.call_count, 2)
            self.assertEqual(sync_repo.call_args_list[0].args[1], "skeleton")
            self.assertEqual(sync_repo.call_args_list[-1].args[1], "blocked")
            state = job_runner.status("blocked", Path(tmp) / "jobs")
            self.assertEqual(state["status"], "blocked")
            self.assertEqual(state["repo_sync"]["status"], "disabled")

    def test_completion_updates_repo_and_records_email_todo_without_smtp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contract = hupd_contract("complete")
            contract["project_id"] = "proj_complete"
            contract["repo_url"] = "https://github.com/acme/paperlab-proj_complete"
            contract["notify_email"] = "reader@example.com"
            contract["proposal_markdown"] = "# Proposal\n\nSkeleton"
            job_dir = Path(tmp) / "jobs" / "complete"
            run_dir = job_dir / "run"
            run_dir.mkdir(parents=True)
            (job_dir / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
            route = router.route_contract(contract)
            (job_dir / "routing_decision.json").write_text(json.dumps(route), encoding="utf-8")
            job_runner.write_state(job_dir, job_runner.initial_state("complete", contract, route))

            with (
                mock.patch.object(job_runner, "probe_data_source", return_value={"status": "available"}),
                mock.patch.object(job_runner, "run_pipeline", return_value=[{"returncode": 0}]),
                mock.patch.object(job_runner, "extract_output", return_value={
                    "job_id": "complete",
                    "status": "done",
                    "run_dir": str(run_dir),
                    "level": "master",
                    "content_score": 6.5,
                    "content_threshold": 6.0,
                    "meets_threshold": True,
                    "desk_reject": 0.2,
                    "above_5_5": True,
                    "gates": {},
                    "doi_real_rate": 1.0,
                    "pdf_path": None,
                    "real_vs_simulated": {},
                    "blockers": [],
                }),
                mock.patch.object(job_runner, "sync_project_repo", return_value={"status": "disabled"}) as sync_repo,
                mock.patch.dict("os.environ", {}, clear=True),
            ):
                output = job_runner.run_job("complete", Path(tmp) / "jobs")

            self.assertEqual(output["status"], "done")
            self.assertEqual(sync_repo.call_args_list[0].args[1], "skeleton")
            self.assertEqual(sync_repo.call_args_list[-1].args[1], "done")
            state = job_runner.status("complete", Path(tmp) / "jobs")
            self.assertEqual(state["notification"]["status"], "not_configured")
            self.assertIn("SMTP_HOST", state["notification"]["todo"])

    def test_extract_output_maps_validated_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "final_content_review_deterministic.json").write_text(json.dumps({
                "mean_7dim": 7.57,
                "elite": {"desk_reject_probability": 0.389},
                "p0_count": 0,
                "p1_count": 0,
                "problems": [],
            }), encoding="utf-8")
            (run_dir / "gate_report.json").write_text(json.dumps({
                "no_p0": True,
                "p1_count": 0,
                "real_status": "completed",
            }), encoding="utf-8")
            (run_dir / "newarch_trace.json").write_text(json.dumps({
                "real_status": "completed",
                "data_availability_status": "available",
                "simulated_markers_final": 0,
                "gate_probe": {"blocked": False},
            }), encoding="utf-8")
            (run_dir / "real_experiments").mkdir()
            (run_dir / "real_experiments" / "real_results.json").write_text(json.dumps({
                "status": "completed",
                "simulation_markers": 0,
                "simulated": False,
            }), encoding="utf-8")
            (run_dir / "metadata.json").write_text(json.dumps([
                {"doi": "10.1/x", "status": "ok"},
                {"doi": "10.2/y", "status": "ok"},
            ]), encoding="utf-8")
            (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
            output = job_runner.extract_output("done", run_dir, [], {"level": "master", "content_threshold": 6.0})
            self.assertEqual(output["content_score"], 7.57)
            self.assertTrue(output["above_5_5"])
            self.assertEqual(output["level"], "master")
            self.assertEqual(output["content_threshold"], 6.0)
            self.assertTrue(output["meets_threshold"])
            self.assertEqual(output["doi_real_rate"], 1.0)
            self.assertEqual(output["real_vs_simulated"]["simulated_markers_final"], 0)
            self.assertEqual(output["real_vs_simulated"]["simulation_markers"], 0)
            self.assertTrue(output["pdf_path"].endswith("paper_draft_v0.pdf"))

    def test_same_score_passes_master_and_fails_phd_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "final_content_review_deterministic.json").write_text(json.dumps({
                "mean_7dim": 6.58,
                "elite": {"desk_reject_probability": 0.42},
                "p0_count": 0,
                "p1_count": 0,
                "problems": [],
            }), encoding="utf-8")
            (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)

            master = job_runner.extract_output(
                "master-done",
                run_dir,
                [],
                {"level": "master", "content_threshold": 6.0},
            )
            phd = job_runner.extract_output(
                "phd-done",
                run_dir,
                [],
                {"level": "phd", "content_threshold": 7.0},
            )

            self.assertEqual(master["content_score"], 6.58)
            self.assertTrue(master["meets_threshold"])
            self.assertFalse(phd["meets_threshold"])


if __name__ == "__main__":
    unittest.main()
