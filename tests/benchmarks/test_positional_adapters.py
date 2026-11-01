"""Independent coordinate and failure-denominator checks for external adapters."""

import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import positional_adapters as adapter
from benchmarks.rbs.datasets import digest


class PositionalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.queries = [
            {
                "id": "plus",
                "start_positions": [10, 13],
                "genome_id": "g",
                "genomic_strand": "+",
                "genomic_stop_first_zero_based": 30,
                "oriented_first_genomic_zero_based": 0,
            },
            {
                "id": "minus",
                "start_positions": [20, 23],
                "genome_id": "g",
                "genomic_strand": "-",
                "genomic_stop_first_zero_based": 42,
                "oriented_first_genomic_zero_based": 80,
            },
            {"id": "unsupported", "start_positions": []},
        ]

    def test_expansion_and_regroup_preserve_all_cases(self):
        expanded = adapter.expand(self.queries)
        self.assertEqual(len(expanded), 4)
        self.assertEqual(expanded[0]["id"], "plus:candidate:10")
        predictions = [
            {"id": expanded[0]["id"], "status": "ok", "predicted": 7},
            {"id": expanded[1]["id"], "status": "failed", "predicted": None},
        ]
        result = adapter.regroup(self.queries, predictions)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["candidates"][0]["score"], 7)
        self.assertEqual(result[1]["candidates"][0]["status"], "not_evaluated")
        self.assertEqual(result[2]["candidates"], [])

    def test_invalid_identity_universe_and_scores(self):
        for rows in ([{"id": ""}], [{"id": 1}], [{"id": "x"}] * 2):
            with self.assertRaises(ValueError):
                adapter.unique(rows)
        for starts in ([1, 1], [-1], [True]):
            with self.assertRaises(ValueError):
                adapter.expand([{"id": "x", "start_positions": starts}])
        for prediction in (
            {"id": "unknown"},
            {"id": "plus:candidate:10", "status": "other"},
            {"id": "plus:candidate:10", "status": "ok", "predicted": 0},
            {"id": "plus:candidate:10", "status": "ok", "predicted": True},
        ):
            with self.assertRaises(ValueError):
                adapter.regroup(self.queries, [prediction])

    def test_one_based_inclusive_strand_projection(self):
        text = (
            "# comment\n\n"
            "g\tProdigal\tCDS\t13\t33\t.\t+\t0\tpartial=00;ID=1;\n"
            "g\tProdigal\tCDS\t41\t61\t.\t-\t0\tpartial=00\n"
            "g\tProdigal\tCDS\t1\t12\t.\t+\t0\tpartial=10\n"
        )
        with self.assertRaisesRegex(ValueError, "multiple of three"):
            adapter.parse_prodigal(text.replace("\t13\t33", "\t14\t33"), {"g": 100})
        calls, partial = adapter.parse_prodigal(text, {"g": 100})
        self.assertEqual(partial, 1)
        self.assertEqual(calls, {("g", "+", 30): 12, ("g", "-", 42): 60})
        self.queries[0]["start_positions"] = [12, 15]
        results = adapter.project_prodigal(self.queries, calls, {"g": 100})
        self.assertEqual([r["selected_start"] for r in results], [12, 20, None])
        self.assertEqual([r["score"] for r in results[0]["candidates"]], [1, 0])
        self.assertEqual([r["score"] for r in results[1]["candidates"]], [1, 0])

    def test_missing_or_outside_universe_is_never_a_successful_zero_tie(self):
        for calls in ({}, {("g", "+", 30): 1}):
            result = adapter.project_prodigal(self.queries, calls, {"g": 100})
            self.assertEqual(result[0]["candidates"][0]["status"], "unsupported")
            self.assertIsNone(result[0]["candidates"][0]["score"])
        self.queries[0].update(
            oriented_first_genomic_zero_based=95, start_positions=[7]
        )
        result = adapter.project_prodigal(self.queries, {("g", "+", 30): 2}, {"g": 100})
        self.assertEqual(result[0]["selected_start"], 7)

    def test_gff_validation(self):
        valid = "g\tP\tCDS\t1\t9\t.\t+\t0\tpartial=00"
        invalid = [
            "bad",
            valid.replace("CDS", "gene"),
            valid.replace("g\t", "unknown\t", 1),
            valid.replace("\t1\t9", "\t0\t9"),
            valid.replace("\t1\t9", "\t1\t101"),
            valid.replace("\t+\t", "\t?\t"),
            valid.replace("\t0\t", "\t1\t"),
            valid.replace("partial=00", "partial=unknown"),
            valid + "\n" + valid,
        ]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                adapter.parse_prodigal(text, {"g": 100})

    def test_cli_pins_and_both_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs, output, predictions = (
                root / n for n in ("input", "output", "pred")
            )
            raw = json.dumps({"records": self.queries}).encode()
            inputs.write_bytes(raw)
            predictions.write_text('{"records": []}')
            common = [str(inputs), str(output), "--input-sha256", digest(raw)]
            with (
                patch.object(sys, "argv", ["positional_adapters", "expand", *common]),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module(
                    "benchmarks.rbs.positional_adapters", run_name="__main__"
                )
            self.assertEqual(len(json.loads(output.read_text())["records"]), 4)
            adapter.main(["regroup", *common, "--predictions", str(predictions)])
            self.assertEqual(len(json.loads(output.read_text())["records"]), 3)
            with self.assertRaises(ValueError):
                adapter.main(["expand", *common[:-1], "wrong"])
            with contextlib.redirect_stderr(io.StringIO()):
                for args in (
                    ["expand", *common, "--predictions", str(predictions)],
                    ["regroup", *common],
                ):
                    with self.assertRaises(SystemExit):
                        adapter.main(args)


if __name__ == "__main__":
    unittest.main()
