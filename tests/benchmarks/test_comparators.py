"""Upstream adapter boundaries; real optional environments have separate smokes."""

import io
import json
import math
import runpy
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmarks.rbs import comparators
from benchmarks.rbs.datasets import digest


class ComparatorTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "synthetic",
            "sequence": "ACGTATGGCT",
            "start": 4,
            "anti_sd": "ACCUCCUUU",
            "temperature_celsius": 30,
        }

    def test_explicit_coordinates_and_sequence_validation(self):
        self.assertEqual(comparators.supplied_input(self.row), ("ACGTATGGCT", 4))
        row = {"sequence": "acguauggcu", "start_position": 4}
        self.assertEqual(comparators.supplied_input(row), ("ACGTATGGCT", 4))
        for value in (None, "", 1, "ACGNATG"):
            with self.assertRaises(ValueError):
                comparators.supplied_input({**self.row, "sequence": value})
        for value in (None, True, -1, 8):
            with self.assertRaises(ValueError):
                comparators.supplied_input({**self.row, "start": value})
        result = comparators.predict({"id": "unmapped"}, "rebeca", None)
        self.assertEqual(result["status"], "unsupported")
        with self.assertRaises(ValueError):
            comparators.predict(self.row, "other", None)

    def test_rebeca_units_utr_and_failure(self):
        engine = MagicMock(return_value=math.log(8))
        result = comparators.predict(self.row, "rebeca", engine)
        engine.assert_called_once_with("ACGT")
        self.assertAlmostEqual(result["predicted"], 8)
        self.assertEqual(result["native_unit"], "mean_ln_fluorescence")
        for value in (True, math.nan, 1000, -1000):
            self.assertEqual(
                comparators.predict(self.row, "rebeca", lambda _, value=value: value)[
                    "status"
                ],
                "failed",
            )
        engine.side_effect = RuntimeError("upstream")
        self.assertEqual(
            comparators.predict(self.row, "rebeca", engine)["reason"], "RuntimeError"
        )

    def test_ostir_coordinates_fixed_temperature_and_failures(self):
        engine = MagicMock(return_value=[{"start_position": 5, "expression": 8}])
        result = comparators.predict(self.row, "ostir", engine)
        engine.assert_called_once_with(
            "ACGTATGGCT",
            start=5,
            end=5,
            name="synthetic",
            aSD="ACCUCCUUU",
            threads=1,
            decimal_places=8,
            circular=False,
        )
        self.assertEqual(result["predicted"], 8)
        self.assertEqual(result["temperature_celsius"], 37)
        self.assertEqual(result["requested_temperature_celsius"], 30)
        for output in (
            [],
            [{"start_position": 4, "expression": 8}],
            [{"start_position": 5, "expression": 8}] * 2,
            [{"start_position": 5, "expression": 0}],
            [{}],
        ):
            engine.return_value = output
            self.assertIn(
                comparators.predict(self.row, "ostir", engine)["status"],
                {"no_candidate", "failed"},
            )
        for asd in (None, "short", "NNNNNNNNN"):
            self.assertEqual(
                comparators.predict({**self.row, "anti_sd": asd}, "ostir", engine)[
                    "status"
                ],
                "failed",
            )

    def test_hash_checks_and_explicit_module_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fixture.py"
            source.write_text("value = 17\n")
            comparators.verify_files(root, {"fixture.py": digest(source.read_bytes())})
            self.assertEqual(
                comparators.load_module("synthetic_upstream", source).value, 17
            )
            with self.assertRaises(ValueError):
                comparators.verify_files(root, {"fixture.py": "wrong"})

    def test_ostir_version_gate(self):
        upstream = types.SimpleNamespace(run_ostir=object())
        with (
            patch.dict(sys.modules, {"ostir": upstream}),
            patch.object(comparators, "verify_files"),
            patch.object(comparators.importlib.metadata, "distribution"),
            patch.object(
                comparators.importlib.metadata,
                "version",
                side_effect=["1.1.3", "2.7.2"],
            ),
        ):
            self.assertIs(comparators.ostir_engine(), upstream.run_ostir)
        for versions in (["other"], ["1.1.3", "other"]):
            with (
                patch.object(
                    comparators.importlib.metadata, "version", side_effect=versions
                ),
                self.assertRaises(ValueError),
            ):
                comparators.ostir_engine()

    def test_pinned_rebeca_loading_and_output_shape(self):
        torch, pandas, yaml = MagicMock(), MagicMock(), MagicMock()
        config = {
            "architecture": {"name": "Model"},
            "param_architecture": {"size": 1},
            "dataset": "Dataset",
        }
        yaml.safe_load.return_value = config
        architecture, encoding = MagicMock(), MagicMock()
        model = architecture.Model.return_value
        output = model.return_value
        output.shape = (1, 1)
        output.item.return_value = 2.5
        tensor = MagicMock()
        encoding.Dataset.return_value.__getitem__.return_value = (tensor, None, "ACGU")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "experiments/exp_67_true/config.yml"
            path.parent.mkdir(parents=True)
            path.write_text("config")
            with (
                patch.dict(
                    sys.modules, {"torch": torch, "pandas": pandas, "yaml": yaml}
                ),
                patch.object(comparators, "verify_files") as verify,
                patch.object(
                    comparators, "load_module", side_effect=[architecture, encoding]
                ),
            ):
                infer = comparators.rebeca_engine(root)
                verify.assert_called_once_with(root, comparators.REBECA_FILES)
                self.assertEqual(infer("ACGU"), 2.5)
                self.assertTrue(torch.load.call_args.kwargs["weights_only"])
                self.assertTrue(model.load_state_dict.call_args.kwargs["strict"])
                output.shape = (1, 8)
                with self.assertRaisesRegex(ValueError, "scalar"):
                    infer("ACGU")

    def test_cli_records_hashes_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "inputs.json"
            output = root / "output.json"
            source.write_text(json.dumps({"records": [self.row]}))
            for name in ("rebeca", "ostir"):
                value = (
                    math.log(8)
                    if name == "rebeca"
                    else [{"start_position": 5, "expression": 8}]
                )
                with (
                    patch.object(
                        comparators,
                        name + "_engine",
                        return_value=MagicMock(return_value=value),
                    ),
                    redirect_stdout(io.StringIO()),
                ):
                    comparators.main(
                        [name, str(source), str(output), "--rebeca-root", str(root)]
                    )
                result = json.loads(output.read_text())
                self.assertEqual(result["input_sha256"], digest(source.read_bytes()))
                self.assertEqual(result["records"][0]["status"], "ok")
            with (
                redirect_stdout(io.StringIO()),
                patch("sys.stderr", new_callable=io.StringIO),
                self.assertRaises(SystemExit),
            ):
                comparators.main(["rebeca", str(source), str(output)])
            source.write_text(json.dumps({"records": [self.row, self.row]}))
            with (
                patch.object(comparators, "ostir_engine"),
                self.assertRaisesRegex(ValueError, "Duplicate"),
            ):
                comparators.main(["ostir", str(source), str(output)])
        with (
            patch.object(sys, "argv", ["comparators", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.comparators", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
