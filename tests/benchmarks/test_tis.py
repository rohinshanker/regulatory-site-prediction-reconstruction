"""Synthetic source rows exercise private TIS parsing without restricted data."""

import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmarks.rbs import tis
from benchmarks.rbs.datasets import digest


class TisTests(unittest.TestCase):
    def setUp(self):
        sequence = "CCC" * 5 + "TAA" + "ATGAAAGTGCCCTGA" + "CCC" * 1200
        reverse = sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]
        self.genomes = {
            key: {"sequence": value, "sequence_sha256": digest(value)}
            for key, value in [("plus", sequence), ("minus", reverse)]
        }
        self.row = [None] * 70
        self.row[0] = "plus:19-33:+"
        self.row[2:7] = [19, 33, "+", "fixture_locus", None]
        self.row[41] = "yes"
        self.row[66] = "ATG"
        self.row[67] = "TGA"
        self.row[69] = "ATGAAAGTGCCCTGA"
        self.reverse = deepcopy(self.row)
        left = len(sequence) - 33 + 1
        right = len(sequence) - 18
        self.reverse[0] = f"minus:{left}-{right}:-"
        self.reverse[2:5] = [left, right, "-"]

    def test_exact_source_coordinates_and_blinded_queries(self):
        queries, labels, audit = tis.extract([self.row, self.reverse], self.genomes)
        self.assertEqual(audit["plain_verified_sequence"], 2)
        self.assertEqual([r["starts"] for r in labels], [[100], [100]])
        self.assertTrue(all(r["tier"] == "positive" for r in labels))
        self.assertTrue(all(r["start_positions"] == [100, 106] for r in queries))
        self.assertTrue(
            all(
                "source_row" not in r
                and "source_identifier" not in r
                and "source_locus_tag" not in r
                for r in queries
            )
        )
        changed = deepcopy(self.row)
        changed[41] = "no"
        self.assertEqual(
            tis.extract([changed], self.genomes)[0],
            tis.extract([self.row], self.genomes)[0],
        )

    def test_weak_missing_unlabelled_and_invalid_stop(self):
        for flag, tier in [("yes (weak)", "weak"), ("No", "unlabelled")]:
            row = deepcopy(self.row)
            row[41] = flag
            _, labels, audit = tis.extract([row], self.genomes)
            self.assertEqual(labels[0]["source_tier"], tier)
            self.assertEqual(audit[tier], 1)
        row = deepcopy(self.row)
        row[69] = None
        self.assertEqual(tis.extract([row], self.genomes)[1][0]["tier"], "unlabelled")
        genomes = deepcopy(self.genomes)
        sequence = genomes["plus"]["sequence"]
        genomes["plus"]["sequence"] = sequence[:30] + "CCC" + sequence[33:]
        row = deepcopy(self.row)
        row[69] = "ATGAAAGTGCCCCCC"
        row[41] = "no"
        queries, labels, audit = tis.extract([row], genomes)
        self.assertEqual(audit["unsupported_nonstop_source_anchor"], 1)
        self.assertEqual(queries[0]["start_positions"], [])
        self.assertEqual(labels[0]["starts"], [])
        self.assertFalse(labels[0]["source_sequence_verified"])

    def test_nontriplet_and_outside_universe_remain_explicit(self):
        row = deepcopy(self.row)
        row[0] = "plus:18-33:+"
        row[2] = 18
        row[69] = self.genomes["plus"]["sequence"][17:33]
        row[66] = row[69][:3]
        self.assertFalse(
            tis.extract([row], self.genomes)[1][0]["source_sequence_verified"]
        )
        row = deepcopy(self.row)
        row[0] = "plus:19-30:+"
        row[3] = 30
        row[69] = "ATGTAAGTGTGA"
        genomes = deepcopy(self.genomes)
        sequence = genomes["plus"]["sequence"]
        genomes["plus"]["sequence"] = sequence[:18] + row[69] + sequence[30:]
        self.assertEqual(
            tis.extract([row], genomes)[2]["positive_outside_candidates"], 1
        )

    def test_source_identity_schema_and_tier_fail_closed(self):
        for change in (
            {0: "bad"},
            {2: 20},
            {0: "plus:1-99999:+", 2: 1, 3: 99999},
            {41: "maybe"},
        ):
            row = deepcopy(self.row)
            for key, value in change.items():
                row[key] = value
            with self.assertRaises(ValueError):
                tis.extract([row], self.genomes)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            tis.extract([self.row, self.row], self.genomes)

    def test_private_preparation_and_source_hashes(self):
        library = MagicMock()
        workbook = library.load_workbook.return_value
        workbook.__getitem__.return_value.values = [[None] * 70] * 3 + [self.row]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.xlsx"
            source.write_bytes(b"synthetic workbook")
            inputs = root / "genomes.json"
            inputs.write_text(json.dumps({"genomes": self.genomes}))
            output = root / "private"
            with (
                patch.dict(sys.modules, {"openpyxl": library}),
                patch.object(tis, "SOURCE_SHA256", digest(source.read_bytes())),
            ):
                result = tis.prepare(source, inputs, output)
                self.assertEqual(result["n_queries"], 1)
                self.assertEqual(result["n_candidates"], 2)
                self.assertEqual(
                    (output / "tis-labels-private.json").stat().st_mode & 0o777, 0o600
                )
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                genomes = deepcopy(self.genomes)
                genomes["plus"]["sequence_sha256"] = "wrong"
                inputs.write_text(json.dumps({"genomes": genomes}))
                with self.assertRaisesRegex(ValueError, "Genome"):
                    tis.prepare(source, inputs, output)
            with (
                patch.dict(sys.modules, {"openpyxl": library}),
                self.assertRaisesRegex(ValueError, "workbook"),
            ):
                tis.prepare(source, inputs, output)

    def test_cli_and_entrypoint(self):
        with (
            patch.object(tis, "prepare", return_value={"n_queries": 1}) as prepare,
            redirect_stdout(io.StringIO()) as output,
        ):
            tis.main(["source.xlsx", "genomes.json", "private"])
        self.assertEqual(json.loads(output.getvalue()), {"n_queries": 1})
        prepare.assert_called_once_with(
            Path("source.xlsx"), Path("genomes.json"), Path("private")
        )
        with (
            patch.object(sys, "argv", ["tis", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.tis", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
