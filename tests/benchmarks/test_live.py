"""Test the export validator with synthetic numbers, never private server outputs."""

import contextlib
import csv
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.live import COLUMNS, main, validate_export


def export(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return output.getvalue()


class LiveTest(unittest.TestCase):
    def setUp(self):
        self.case = dict(
            id="test",
            sequence="AAAATGAAA",
            selected_start_zero_based=3,
            sequence_sha256=digest("AAAATGAAA"),
        )
        # Independent arithmetic: -3 + 1 - 1 + 2 - 1 - (-1) = -1.
        self.row = [3, 1, 5, -1, -3, 1, -1, 2, -1, -1, "example warning"]

    def test_valid_export_and_absent_candidates(self):
        content = export([self.row])
        result = validate_export(self.case, content)
        self.assertEqual(result["csv_sha256"], digest(content))
        self.assertEqual(result["candidate_starts_zero_based"], [3])
        self.assertEqual(result["n_candidates_with_warnings"], 1)
        self.assertTrue(result["selected_start_returned"])
        self.assertFalse(
            validate_export(self.case, export([]))["selected_start_returned"]
        )
        self.case["selected_start_zero_based"] = None
        self.assertIsNone(
            validate_export(self.case, export([]))["selected_start_returned"]
        )

    def test_schema_and_integrity_failures(self):
        for content in (
            "wrong\n",
            export([self.row[:-1]]),
            export([self.row + ["extra"]]),
            export([self.row, self.row]),
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_export(self.case, content)
        self.case["sequence_sha256"] = "changed"
        with self.assertRaises(ValueError):
            validate_export(self.case, export([self.row]))

    def test_coordinates_and_numerical_failures(self):
        for column, value in [
            (0, -1),
            (0, 7),
            (0, 0),
            (0, "3.5"),
            (2, 0),
            (2, "NaN"),
            (3, 1),
            (4, "inf"),
        ]:
            row = self.row.copy()
            row[column] = value
            with (
                self.subTest(column=column, value=value),
                self.assertRaises(ValueError),
            ):
                validate_export(self.case, export([row]))

    def test_command_preserves_crlf_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            panel, output = root / "panel.json", root / "export.csv"
            panel.write_text(json.dumps({"records": [self.case]}))
            output.write_bytes(export([self.row]).encode())
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                main([str(panel), "test", str(output)])
            self.assertEqual(
                json.loads(capture.getvalue())["csv_sha256"],
                digest(output.read_bytes()),
            )

    def test_module_entrypoint(self):
        with (
            patch.dict(sys.modules),
            patch.object(sys, "argv", ["benchmarks.rbs.live", "--help"]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as result,
        ):
            sys.modules.pop("benchmarks.rbs.live", None)
            runpy.run_module("benchmarks.rbs.live", run_name="__main__")
        self.assertEqual(result.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
