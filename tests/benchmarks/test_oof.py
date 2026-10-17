"""Public OOF audit arithmetic, group identity and deterministic tie checks."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import oof


class OofTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "records": [
                {"id": "a", "family": "one", "observed": 1},
                {"id": "b", "family": "two", "observed": 4},
            ]
        }
        self.selection = {
            "record_ids": ["a", "b"],
            "groups": ["one", "two"],
            "n_records": 2,
            "n_groups": 2,
            "configurations": [
                {
                    "out_of_fold_log2": [1, 3],
                    "penalty_per_observation": 1,
                    "family_mae_log2": 1,
                    "row_rmse_log2": 1,
                },
                {
                    "out_of_fold_log2": [1, 3],
                    "penalty_per_observation": 10,
                    "family_mae_log2": 1,
                    "row_rmse_log2": 1,
                },
            ],
            "selected_index": 1,
        }

    def test_exact_metrics_and_stronger_penalty_tie(self):
        result = oof.audit(self.data, self.selection)
        self.assertEqual(result["selected_index"], 1)
        self.assertEqual(result["configurations"][0]["metrics"]["mae_log2"], 1)

    def test_identity_family_count_and_metric_validation(self):
        for change in (
            {"record_ids": ["a"]},
            {"record_ids": ["a", "a"]},
            {"record_ids": ["a", "c"]},
            {"groups": ["one"]},
            {"groups": ["one", "one"]},
            {"n_records": 3},
            {"n_groups": 1},
            {"selected_index": 0},
            {"selected_index": True},
            {"configurations": []},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                oof.audit(self.data, {**self.selection, **change})
        for change in (
            {"out_of_fold_log2": [1]},
            {"out_of_fold_log2": [True, 3]},
            {"family_mae_log2": 2},
            {"row_rmse_log2": 2},
        ):
            selected = deepcopy(self.selection)
            selected["configurations"][0].update(change)
            with self.assertRaises(ValueError):
                oof.audit(self.data, selected)

    def test_public_cli_records_input_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, selection, output = (
                root / n for n in ("data", "selection", "output")
            )
            data.write_text(json.dumps(self.data))
            selection.write_text(json.dumps(self.selection))
            with (
                patch.object(
                    sys, "argv", ["oof", str(data), str(selection), str(output)]
                ),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module("benchmarks.rbs.oof", run_name="__main__")
            result = json.loads(output.read_text())
            self.assertEqual(len(result["dataset_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
