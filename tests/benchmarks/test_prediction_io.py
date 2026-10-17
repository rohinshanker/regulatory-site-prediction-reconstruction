"""Public result boundary checks with hand-specified input and site identities."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import prediction_io
from benchmarks.rbs.datasets import digest


class PredictionIoTests(unittest.TestCase):
    def setUp(self):
        sequence = "CCCATGCCC"
        rna = sequence.replace("T", "U")
        row = {
            "id": "a",
            "sequence": sequence,
            "sequence_sha256": digest(sequence),
            "start_position": 3,
            "temperature_celsius": 30,
            "anti_sd": "ACCUCCUUU",
        }
        self.inputs = {"records": [row]}
        self.result = {
            "mode": "supplied_start",
            "execution": {},
            "results": [
                {
                    "id": "a",
                    "evidence": deepcopy(row),
                    "status": "ok",
                    "prediction": {
                        "input": {
                            "oriented_sequence": rna,
                            "oriented_sha256": digest(rna),
                            "strand": "+",
                            "start_positions": [3],
                            "temperature_c": 30,
                            "anti_sd": "ACCUCCUUU",
                        },
                        "prediction_id": "pinned-output",
                        "sites": [{"oriented_start": 3, "status": "ok", "tir": 4}],
                    },
                }
            ],
        }

    def test_success_and_original_wrapper_failures_are_preserved(self):
        rows = prediction_io.native_predictions(self.inputs, self.result)
        self.assertEqual(rows[0]["predicted"], 4)
        self.assertEqual(rows[0]["source_prediction_id"], "pinned-output")
        for status in ("failed", "unsupported", "no_candidate", "invalid_input"):
            result = deepcopy(self.result)
            result["results"][0]["status"] = status
            row = prediction_io.native_predictions(self.inputs, result)[0]
            self.assertIsNone(row["predicted"])
            self.assertEqual(
                row["status"], "failed" if status == "invalid_input" else status
            )
        self.result["results"][0].update(status="unsupported", prediction=None)
        self.assertIsNone(
            prediction_io.native_predictions(self.inputs, self.result)[0][
                "source_prediction_id"
            ]
        )

    def test_input_and_evidence_drift_rejected(self):
        for kind in ("mode", "ids", "status", "evidence_id", "evidence_hash"):
            result = deepcopy(self.result)
            if kind == "mode":
                result["mode"] = "scan"
            elif kind == "ids":
                result["results"][0]["id"] = "other"
            elif kind == "status":
                result["results"][0]["status"] = "other"
            elif kind == "evidence_id":
                result["results"][0]["evidence"]["id"] = "other"
            else:
                result["results"][0]["evidence"]["sequence_sha256"] = "wrong"
            with self.assertRaises(ValueError):
                prediction_io.native_predictions(self.inputs, result)
        for key, value in (
            ("oriented_sequence", "CCC"),
            ("oriented_sha256", "wrong"),
            ("strand", "-"),
            ("start_positions", [4]),
            ("temperature_c", 37),
            ("anti_sd", "ACCUCCUUA"),
        ):
            result = deepcopy(self.result)
            result["results"][0]["prediction"]["input"][key] = value
            with self.assertRaises(ValueError):
                prediction_io.native_predictions(self.inputs, result)
        self.inputs["records"][0]["sequence"] = None
        with self.assertRaises(ValueError):
            prediction_io.native_predictions(self.inputs, self.result)

    def test_site_success_and_coordinate_boundary(self):
        for kind in (
            "duplicate",
            "coordinate",
            "empty",
            "failed",
            "zero",
            "bool",
            "absent",
        ):
            result = deepcopy(self.result)
            core = result["results"][0]["prediction"]
            if kind == "duplicate":
                core["sites"] *= 2
            elif kind == "coordinate":
                core["sites"][0]["oriented_start"] = 4
            elif kind == "empty":
                core["sites"] = []
            elif kind == "failed":
                core["sites"][0]["status"] = "failed"
            elif kind == "zero":
                core["sites"][0]["tir"] = 0
            elif kind == "bool":
                core["sites"][0]["tir"] = True
            else:
                result["results"][0]["prediction"] = None
            with self.assertRaises(ValueError):
                prediction_io.native_predictions(self.inputs, result)
        self.result["results"][0]["status"] = "no_candidate"
        self.result["results"][0]["prediction"]["sites"] = []
        self.assertIsNone(
            prediction_io.native_predictions(self.inputs, self.result)[0]["predicted"]
        )

    def test_cli_byte_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, predictions, output = (
                root / n for n in ("inputs", "predictions", "output")
            )
            inputs.write_text(json.dumps(self.inputs))
            predictions.write_text(json.dumps(self.result))
            args = [
                str(inputs),
                str(predictions),
                str(output),
                "--input-sha256",
                digest(inputs.read_bytes()),
                "--prediction-sha256",
                digest(predictions.read_bytes()),
            ]
            with (
                patch.object(sys, "argv", ["prediction_io", *args]),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module("benchmarks.rbs.prediction_io", run_name="__main__")
            self.assertEqual(
                json.loads(output.read_text())["records"][0]["predicted"], 4
            )
            for index in (4, 6):
                invalid = list(args)
                invalid[index] = "wrong"
                with self.assertRaises(ValueError):
                    prediction_io.main(invalid)


if __name__ == "__main__":
    unittest.main()
