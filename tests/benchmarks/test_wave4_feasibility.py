"""Feasibility output never includes invented or real per-case outcomes."""

import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.wave4_feasibility import main, simulate


class FeasibilityTest(unittest.TestCase):
    def test_reproducible_cli_and_hash_boundary(self):
        source = {
            "records": [
                {"id": str(i), "group": str(i // 2), "study": "Cambray2018"}
                for i in range(16)
            ]
        }
        source["records"].append({"study": "Kuo2020"})
        protocol = {
            "input_file_sha256": digest(json.dumps(source)),
            "bootstrap": {
                "draws": 20,
                "seed": 7,
                "minimum_usable_draws": 10,
                "minimum_common_rows": 2,
                "minimum_common_blocks": 2,
            },
            "advancement": {"minimum_coverage": 0.95, "minimum_rank_gain": 0.05},
        }
        result = simulate(source, protocol)
        self.assertEqual(result, simulate(source, protocol))
        self.assertEqual(result["n_inputs"], 16)
        self.assertFalse(result["uses_experimental_labels"])
        self.assertEqual(result["results"]["identical"]["comparison"]["rank_gain"], 0)
        self.assertIsNone(result["results"]["constant"]["comparison"]["rank_gain"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs.json"
            spec = root / "protocol.json"
            output = root / "output.json"
            inputs.write_text(json.dumps(source))
            spec.write_text(json.dumps(protocol))
            main(list(map(str, (inputs, spec, output))))
            self.assertEqual(json.loads(output.read_text()), result)
            output.unlink()
            with patch.object(
                sys, "argv", ["wave4_feasibility", str(inputs), str(spec), str(output)]
            ):
                runpy.run_module(
                    "benchmarks.rbs.wave4_feasibility", run_name="__main__"
                )
            inputs.write_text("{}")
            with self.assertRaises(ValueError):
                main(list(map(str, (inputs, spec, output))))


if __name__ == "__main__":
    unittest.main()
