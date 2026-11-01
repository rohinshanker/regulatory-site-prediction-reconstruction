"""Final-label exclusion and immutable split checks."""

import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import development
from benchmarks.rbs.datasets import digest


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        rows = []
        for identity, partition, eligible in [
            ("train", "development_train", True),
            ("validation", "development_validation", True),
            ("heldout", "final", True),
            ("ineligible", "development_train", False),
        ]:
            rows.append(
                {
                    "id": identity,
                    "partition": partition,
                    "primary_eligible": eligible,
                    "group": identity,
                    "sequence": "ATG",
                    "sequence_sha256": digest("ATG"),
                    "start_position": 0,
                    "host": "fixture",
                    "temperature_celsius": 30,
                    "anti_sd": "ACCUCCUUU",
                    "warnings": [],
                    "source_row": 4,
                    "source_file_sha256": "source",
                }
            )
        self.inputs = json.dumps({"records": rows}).encode()
        self.splits = {
            "records": deepcopy(rows),
            "input_envelope_sha256": digest(self.inputs),
        }
        self.outcomes = [
            {
                "id": row["id"] + ":" + condition,
                "input_id": row["id"],
                "condition": condition,
                "observed": 12345 if row["id"] == "heldout" else 1,
            }
            for row in rows
            for condition in ("HC", "LC")
        ]

    def test_only_primary_hc_development_values_are_released(self):
        result = development.release(self.inputs, self.outcomes, self.splits)
        self.assertEqual(
            [row["id"] for row in result["records"]], ["train", "validation"]
        )
        self.assertNotIn("12345", json.dumps(result))
        self.assertEqual(
            [row["source_measurement_id"] for row in result["records"]],
            ["train:HC", "validation:HC"],
        )
        self.outcomes[0]["observed"] = 0
        self.assertEqual(
            development.release(self.inputs, self.outcomes, self.splits)["records"][0][
                "measurement_status"
            ],
            "reported_zero",
        )

    def test_input_hash_identity_sets_and_duplicates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "envelope"):
            development.release(self.inputs + b" ", self.outcomes, self.splits)
        for problem in ("duplicate_input", "duplicate_split", "missing_split"):
            inputs = json.loads(self.inputs)
            splits = deepcopy(self.splits)
            if problem == "duplicate_input":
                inputs["records"].append(inputs["records"][0])
            elif problem == "duplicate_split":
                splits["records"].append(splits["records"][0])
            else:
                splits["records"].pop()
            raw = json.dumps(inputs).encode()
            splits["input_envelope_sha256"] = digest(raw)
            with self.assertRaisesRegex(ValueError, "identity set"):
                development.release(raw, self.outcomes, splits)

    def test_private_outcome_identity_validation(self):
        for problem in ("duplicate", "unknown", "condition", "double_hc", "missing"):
            outcomes = deepcopy(self.outcomes)
            if problem == "duplicate":
                outcomes.append(outcomes[0])
            elif problem == "unknown":
                outcomes[0]["input_id"] = "unknown"
            elif problem == "condition":
                outcomes[0]["condition"] = "other"
            elif problem == "double_hc":
                outcomes[1]["condition"] = "HC"
            else:
                outcomes.pop(0)
            with self.assertRaises(ValueError):
                development.release(self.inputs, outcomes, self.splits)

    def test_inconsistent_frozen_metadata_is_rejected(self):
        for key, value in [
            ("partition", "other"),
            ("sequence_sha256", "wrong"),
            ("primary_eligible", False),
        ]:
            splits = deepcopy(self.splits)
            splits["records"][0][key] = value
            with self.assertRaisesRegex(ValueError, "metadata"):
                development.release(self.inputs, self.outcomes, splits)

    def test_blinded_inputs_strip_source_order_without_mutation(self):
        original = json.loads(self.inputs)
        result = development.blinded_inputs(self.inputs)
        self.assertEqual(
            [row["id"] for row in result["records"]],
            sorted(row["id"] for row in original["records"]),
        )
        self.assertTrue(all("source_row" not in row for row in result["records"]))
        self.assertTrue(all("source_row" in row for row in original["records"]))
        self.assertEqual(result["original_input_envelope_sha256"], digest(self.inputs))

    def test_cli_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                Path(directory) / name
                for name in ("inputs.json", "outcomes.json", "splits.json", "dev.json")
            ]
            paths[0].write_bytes(self.inputs)
            paths[1].write_text(json.dumps(self.outcomes))
            paths[2].write_text(json.dumps(self.splits))
            with redirect_stdout(io.StringIO()) as result:
                development.main([str(path) for path in paths])
            self.assertEqual(json.loads(result.getvalue())["n_development"], 2)
            self.assertEqual(
                json.loads(paths[3].read_text())["split_sha256"],
                digest(paths[2].read_bytes()),
            )
            blinded = Path(directory) / "blinded.json"
            with redirect_stdout(io.StringIO()):
                development.main(
                    [str(path) for path in paths] + ["--inputs-output", str(blinded)]
                )
            self.assertEqual(
                json.loads(blinded.read_text()), development.blinded_inputs(self.inputs)
            )
        with (
            patch.object(sys, "argv", ["development", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.development", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
