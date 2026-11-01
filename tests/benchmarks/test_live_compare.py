"""Synthetic export integrity, empty-result and complete-denominator fixtures."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import live_compare
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.live import COLUMNS


class LiveComparisonTests(unittest.TestCase):
    def setUp(self):
        self.sequence = "CCCATGCCC"
        self.panel = {
            "records": [
                {
                    "id": name,
                    "sequence": self.sequence,
                    "sequence_sha256": digest(self.sequence),
                    "selected_start_zero_based": 3,
                }
                for name in ("export", "empty", "rejected")
            ]
        }
        self.raw = json.dumps(self.panel).encode()
        self.csv = (",".join(COLUMNS) + "\n3,1,4,0,0,0,0,0,0,0,\n").encode()
        self.settings = {"rrna_displayed": "ACCUCCUUA", "temperature_c": 37}
        self.acquisition = {
            "panel_sha256": digest(self.raw),
            "returned_settings": self.settings,
            "jobs": [
                {
                    "id": row["id"],
                    "input_sha256": digest(self.sequence),
                    "status": status,
                    "exports": [
                        {
                            "file": "live.csv",
                            "bytes": len(self.csv),
                            "sha256": digest(self.csv),
                        }
                    ]
                    if status == "finished_exported"
                    else [],
                }
                for row, status in zip(
                    self.panel["records"],
                    ("finished_exported", "finished_empty", "form_rejected"),
                    strict=True,
                )
            ],
        }
        self.predictions = [
            {
                "id": "export",
                "input": {
                    "oriented_sha256": digest(self.sequence.replace("T", "U")),
                    "oriented_sequence": self.sequence.replace("T", "U"),
                    "strand": "+",
                    "anti_sd": "ACCUCCUUA",
                    "temperature_c": 37,
                },
                "status": "ok",
                "sites": [{"oriented_start": 3, "status": "ok", "tir": 2}],
            }
        ]

    def references(self, root):
        (root / "live.csv").write_bytes(self.csv)
        return live_compare.references(self.raw, self.acquisition, root)

    def test_rate_compatibility_and_empty_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = self.references(Path(directory))
            result = live_compare.compare(reference, self.predictions, self.settings)
            self.assertEqual(result["all_live_candidates"]["mae_log2"], 1)
            self.assertEqual(result["declared_targets"]["n_success"], 1)
            self.assertEqual(result["counts"]["finished_empty"], 1)
            self.assertEqual(result["counts"]["explicit_empty_agreements"], 0)
            self.predictions.append(
                {
                    **self.predictions[0],
                    "id": "empty",
                    "sites": [],
                    "status": "no_candidate",
                }
            )
            result = live_compare.compare(reference, self.predictions, self.settings)
            self.assertEqual(result["counts"]["explicit_empty_agreements"], 1)
            self.predictions[0]["sites"] = []
            result = live_compare.compare(reference, self.predictions, self.settings)
            self.assertEqual(
                result["all_live_candidates"]["failures"], {"not_evaluated": 1}
            )
            self.assertEqual(
                live_compare.compare(reference, [], self.settings)[
                    "all_live_candidates"
                ]["coverage"],
                0,
            )

    def test_extra_sites_and_non_target_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = self.references(Path(directory))
            reference[0]["selected_start_zero_based"] = None
            self.predictions[0]["sites"].append(
                {"oriented_start": 6, "status": "failed", "tir": None}
            )
            result = live_compare.compare(reference, self.predictions, self.settings)
            self.assertEqual(result["counts"]["extra_returned_starts"], 1)
            self.assertEqual(result["declared_targets"]["n_submitted"], 0)

    def test_null_input_failure_preserves_mixed_batch_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = self.references(Path(directory))
            reference.append({**reference[0], "id": "failure"})
            failure = {
                "id": "failure",
                "status": "invalid_input",
                "input": None,
                "sites": [],
            }
            self.predictions.append(failure)
            result = live_compare.compare(reference, self.predictions, self.settings)
            self.assertEqual(result["all_live_candidates"]["n_submitted"], 2)
            self.assertEqual(result["all_live_candidates"]["n_success"], 1)
            self.assertEqual(
                result["all_live_candidates"]["failures"], {"invalid_input": 1}
            )
            self.assertEqual(result["counts"]["scenario_verification_unavailable"], 1)
            failure["status"] = "ok"
            with self.assertRaises(ValueError):
                live_compare.compare(reference, self.predictions, self.settings)
            failure["status"] = "failed"
            failure["sites"] = [{"status": "ok"}]
            with self.assertRaises(ValueError):
                live_compare.compare(reference, self.predictions, self.settings)

    def test_scenario_and_identity_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = self.references(Path(directory))
            with self.assertRaises(ValueError):
                live_compare.compare(reference, [{"id": "unknown"}], self.settings)
            for key, value in (
                ("oriented_sha256", "wrong"),
                ("oriented_sequence", "CCC"),
                ("strand", "-"),
                ("anti_sd", "ACCUCCUUU"),
                ("temperature_c", 30),
            ):
                predictions = deepcopy(self.predictions)
                predictions[0]["input"][key] = value
                with self.assertRaises(ValueError):
                    live_compare.compare(reference, predictions, self.settings)
            self.predictions[0]["sites"] *= 2
            with self.assertRaises(ValueError):
                live_compare.compare(reference, self.predictions, self.settings)

    def test_reference_pin_status_and_path_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.references(root)
            for kind in (
                "panel",
                "identity",
                "sequence",
                "hash",
                "length",
                "path",
                "status",
                "no_csv",
                "duplicate_csv",
                "empty_csv",
                "unexpected_csv",
            ):
                acquisition = deepcopy(self.acquisition)
                if kind == "panel":
                    acquisition["panel_sha256"] = "wrong"
                elif kind == "identity":
                    acquisition["jobs"].pop()
                elif kind == "sequence":
                    acquisition["jobs"][0]["input_sha256"] = "wrong"
                elif kind in {"hash", "length", "path"}:
                    acquisition["jobs"][0]["exports"][0][
                        {"hash": "sha256", "length": "bytes", "path": "file"}[kind]
                    ] = {"hash": "wrong", "length": 0, "path": "../outside"}[kind]
                elif kind == "status":
                    acquisition["jobs"][0]["status"] = "queued"
                elif kind == "no_csv":
                    acquisition["jobs"][0]["exports"] = []
                elif kind == "duplicate_csv":
                    acquisition["jobs"][0]["exports"] *= 2
                elif kind == "empty_csv":
                    raw = (",".join(COLUMNS) + "\n").encode()
                    (root / "empty.csv").write_bytes(raw)
                    acquisition["jobs"][0]["exports"] = [
                        {"file": "empty.csv", "bytes": len(raw), "sha256": digest(raw)}
                    ]
                else:
                    acquisition["jobs"][1]["exports"] = acquisition["jobs"][0][
                        "exports"
                    ]
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    live_compare.references(self.raw, acquisition, root)
            raw = b"saved rendered evidence"
            (root / "render.txt").write_bytes(raw)
            self.acquisition["jobs"][0]["exports"].append(
                {"file": "render.txt", "bytes": len(raw), "sha256": digest(raw)}
            )
            self.assertEqual(
                len(live_compare.references(self.raw, self.acquisition, root)), 3
            )

    def test_cli_preserves_only_aggregate_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.references(root)
            panel, acquisition, predictions, output = (
                root / name
                for name in ("panel", "acquisition", "predictions", "output")
            )
            panel.write_bytes(self.raw)
            acquisition.write_text(json.dumps(self.acquisition))
            predictions.write_text(json.dumps({"results": self.predictions}))
            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "live_compare",
                        str(panel),
                        str(acquisition),
                        str(root),
                        str(predictions),
                        str(output),
                    ],
                ),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module("benchmarks.rbs.live_compare", run_name="__main__")
            result = json.loads(output.read_text())
            self.assertEqual(result["panel_sha256"], digest(self.raw))
            self.assertNotIn("live_rates", result)


if __name__ == "__main__":
    unittest.main()
