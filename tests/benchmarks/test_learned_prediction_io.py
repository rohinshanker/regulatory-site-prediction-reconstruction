"""Hand-specified public learned collection checks without feature/model imports."""

import json
import unittest
from copy import deepcopy

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.prediction_io import learned_predictions


class LearnedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source = [
            {
                "id": "a",
                "sequence": "CCCATGCCC",
                "start_position": 3,
                "temperature_celsius": 30,
                "anti_sd": "ACCUCCUUU",
                "host": "host",
            }
        ]
        self.prepared = {
            "records": [
                {
                    "id": "a",
                    "status": "ok",
                    "input": {
                        "id": "a",
                        "sequence": "CCCAUGCCC",
                        "start_positions": [3],
                        "strand": "+",
                        "temperature_c": 30,
                        "anti_sd": "ACCUCCUUU",
                        "host": "host",
                    },
                }
            ]
        }
        self.output = {
            "source_sha256": "",
            "model_sha256": "model",
            "artifact_sha256": "artifact",
            "calibration_applied": False,
            "records": [
                {"id": "a", "status": "ok", "score": 4, "score_log2": 2, "reason": None}
            ],
        }

    def run_case(self, source=None, prepared=None, output=None, bind=True):
        source = self.source if source is None else source
        prepared = self.prepared if prepared is None else prepared
        output = deepcopy(self.output if output is None else output)
        raw = json.dumps(prepared).encode()
        if bind:
            output["source_sha256"] = digest(raw)
        return learned_predictions(source, raw, output, "model", "artifact")

    def test_success_failure_and_null_input(self):
        self.assertEqual(self.run_case()[0]["predicted"], 4)
        del self.prepared["records"][0]["input"]["strand"]
        self.assertEqual(self.run_case()[0]["predicted"], 4)
        for status in ("failed", "unsupported", "no_candidate"):
            self.output["records"][0].update(status=status, score=None, score_log2=None)
            self.assertIsNone(self.run_case()[0]["predicted"])
            self.prepared["records"][0]["input"] = None
            self.assertFalse(self.run_case()[0]["scenario_verified"])

    def test_source_model_and_identity_pins(self):
        for key, value in (
            ("model_sha256", "other"),
            ("artifact_sha256", "other"),
            ("calibration_applied", True),
        ):
            output = deepcopy(self.output)
            output[key] = value
            with self.assertRaises(ValueError):
                self.run_case(output=output)
        with self.assertRaises(ValueError):
            self.run_case(bind=False)
        for target in ("source", "prepared", "output"):
            source, prepared, output = (
                deepcopy(self.source),
                deepcopy(self.prepared),
                deepcopy(self.output),
            )
            (
                source
                if target == "source"
                else (prepared if target == "prepared" else output)["records"]
            )[0]["id"] = "unknown"
            with self.assertRaises(ValueError):
                self.run_case(source, prepared, output)

    def test_every_scenario_field_and_success_boundary(self):
        for key, value in (
            ("id", "other"),
            ("sequence", "AAA"),
            ("strand", "-"),
            ("start_positions", [4]),
            ("temperature_c", 37),
            ("anti_sd", "ACCUCCUUA"),
            ("host", "other"),
        ):
            prepared = deepcopy(self.prepared)
            prepared["records"][0]["input"][key] = value
            with self.assertRaises(ValueError):
                self.run_case(prepared=prepared)
        for kind in (
            "null",
            "prepared_status",
            "bool",
            "zero",
            "log_bool",
            "log_drift",
            "unknown_status",
            "failed_value",
            "failed_log",
        ):
            prepared, output = deepcopy(self.prepared), deepcopy(self.output)
            row = output["records"][0]
            if kind == "null":
                prepared["records"][0]["input"] = None
            elif kind == "prepared_status":
                prepared["records"][0]["status"] = "unsupported"
            elif kind == "bool":
                row["score"] = True
            elif kind == "zero":
                row["score"] = 0
            elif kind == "log_bool":
                row["score_log2"] = True
            elif kind == "log_drift":
                row["score_log2"] = 3
            elif kind == "unknown_status":
                row["status"] = "unknown"
            elif kind == "failed_value":
                row["status"] = "failed"
            else:
                row.update(status="failed", score=None)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.run_case(prepared=prepared, output=output)


if __name__ == "__main__":
    unittest.main()
