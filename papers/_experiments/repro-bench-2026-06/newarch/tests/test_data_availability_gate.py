from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import data_availability_gate as gate


class DataAvailabilityGateTest(unittest.TestCase):
    def make_tar(self, rows: list[dict[str, str]]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tar_path = Path(tmp.name) / "sample.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            for index, row in enumerate(rows):
                payload = json.dumps(row).encode("utf-8")
                info = tarfile.TarInfo(f"sample/2016/{index}.json")
                info.size = len(payload)
                tar.addfile(info, fileobj=__import__("io").BytesIO(payload))
        return tar_path

    def test_collect_hupd_rows_requires_schema(self) -> None:
        tar_path = self.make_tar([
            {
                "application_number": "1",
                "decision": "ACCEPTED",
                "title": "A",
                "abstract": "B",
                "main_cpc_label": "G06F0000",
                "filing_date": "2016-01-01",
            },
            {
                "application_number": "2",
                "decision": "",
                "title": "missing decision",
                "abstract": "B",
                "main_cpc_label": "H04L0000",
                "filing_date": "2016-01-02",
            },
        ])
        rows = gate.collect_hupd_sample_rows(10, tar_url=tar_path.as_uri())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "ACCEPTED")
        self.assertEqual(rows[0]["cpc_section"], "G")

    def test_probe_fail_closed_on_loader_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gate, "head_status", return_value={"http_status": 200}), \
                mock.patch.object(gate, "load_hupd_metadata_evidence", side_effect=RuntimeError("bad feather")):
                lock = gate.probe_hupd(Path(tmp), sample_rows=2)
            self.assertEqual(lock["status"], "unavailable")
            self.assertIn("bad feather", lock["reason"])
            saved = json.loads((Path(tmp) / "data_source_lock.json").read_text())
            self.assertEqual(saved["status"], "unavailable")

    def test_require_available_raises_on_unavailable(self) -> None:
        with self.assertRaises(RuntimeError):
            gate.require_available({"status": "unavailable", "reason": "rate limited"})


if __name__ == "__main__":
    unittest.main()
