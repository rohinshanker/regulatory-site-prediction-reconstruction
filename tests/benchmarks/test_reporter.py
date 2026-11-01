"""Synthetic typography, construct-table and absent-outcome checks."""

import io
import json
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import reporter


class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.xml = (
            """<article><sec><title>Generating the RBS library</title><p>5′-"""
            + "A" * 23
            + "TTTT"
            + """-3′</p></sec><table-wrap id="Tab2"><table><tbody>
<tr><td>X<break/><italic>TTTT</italic>AAAAAAAAAAAAAAAAAA<bold>ATG</bold></td></tr>
<tr><td>A<break/>AAAAAAAAAAAAAAAAAAAAAA<bold>ATG</bold></td></tr>
</tbody></table></table-wrap></article>"""
        )
        self.insert = "ATGCAT" + "CCC" * 237 + "TAA" + "GCTAGC" + "C" * 782 + "CTCGAG"
        self.assertEqual(len(self.insert), 1514)

    def test_typography_and_start_counted_once(self):
        rbs = reporter.parse_rbs(self.xml)
        self.assertEqual(rbs["X"]["leader"], "A" * 23 + "TTTT" + "A" * 18)
        self.assertEqual(rbs["X"]["upstream22"], "TTTT" + "A" * 18)
        gfp, meta = reporter.parse_insert(
            "title\n" + self.insert[:900] + "\n" + self.insert[900:] + "\n"
        )
        self.assertEqual(len(gfp), 720)
        self.assertEqual(meta["gfp_interval"], [0, 720])
        rows = reporter.construct_records(
            rbs, gfp, "header\n\nX y(X) g(X)\nA y(A) g(A) e(A)\n"
        )
        self.assertEqual(len(rows), 5)
        self.assertTrue(
            all(
                r["observed"] is None and r["full_transcript_sequence"] is None
                for r in rows
            )
        )
        gfp_rows = [r for r in rows if r["reporter"] == "GFPmut3b"]
        self.assertTrue(
            all(
                r["sequence"][r["start"] : r["start"] + 6] == "ATGCAT" for r in gfp_rows
            )
        )
        self.assertTrue(all(len(r["window_35up_70cds"]) == 105 for r in gfp_rows))
        self.assertEqual(sum(r["borrowed_series"] for r in rows), 3)

    def test_malformed_source_typography_and_missing_method(self):
        variants = [
            self.xml.replace("Generating the RBS library", "Other"),
            self.xml.replace("A" * 23 + "TTTT", "short"),
            self.xml.replace(
                "<tbody>",
                "<tbody><tr><td>X<break/>" + "A" * 22 + "<bold>ATG</bold></td></tr>",
            ),
            self.xml.replace("TTTT</italic>", "GGGG</italic>"),
            self.xml.replace("<bold>ATG</bold>", "<bold>AAA</bold>"),
            self.xml.replace('id="Tab2"', 'id="other"'),
        ]
        for xml in variants:
            with self.assertRaises(ValueError):
                reporter.parse_rbs(xml)

    def test_insert_boundary_and_internal_stop_rejection(self):
        for sequence in (
            self.insert[:-1],
            "AAAAAA" + self.insert[6:],
            self.insert[:720] + "CCCCCC" + self.insert[726:],
            self.insert[:6] + "TGA" + self.insert[9:],
        ):
            with self.assertRaises(ValueError):
                reporter.parse_insert(sequence)

    def test_construct_duplicates_column_count_and_literal_names(self):
        rbs = reporter.parse_rbs(self.xml)
        for text in (
            "X y(X)",
            "X y(X) g(X) e(X) extra",
            "X y(X) g(X)\nX y(X) g(X)",
            "X y(Z) g(X)",
        ):
            with self.assertRaises(ValueError):
                reporter.construct_records(rbs, self.insert[:720], text)

    def test_preparation_checks_pins_and_published_universe(self):
        records = [
            {"id": str(i), "reporter": name}
            for name, n in [("sYFP2", 13), ("GFPmut3b", 13), ("efe", 6)]
            for i in range(n)
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "contexts.json"
            with (
                patch.object(
                    reporter, "checked_source", return_value=b"xml"
                ) as checked,
                patch.object(reporter.subprocess, "check_output", return_value="text"),
                patch.object(
                    reporter, "parse_rbs", return_value={str(i): {} for i in range(13)}
                ),
                patch.object(reporter, "parse_insert", return_value=("ATG", {})),
                patch.object(reporter, "construct_records", return_value=records),
            ):
                result = reporter.prepare(Path(directory), output)
                self.assertEqual(checked.call_count, 8)
                self.assertEqual(result["n_constructs"], 32)
                self.assertEqual(
                    json.loads(output.read_text())["admission"],
                    "context/provenance only; no exact tabulated strength outcomes",
                )
                with (
                    patch.object(reporter, "construct_records", return_value=[]),
                    self.assertRaisesRegex(ValueError, "universe"),
                ):
                    reporter.prepare(Path(directory), output)
                with (
                    patch.object(reporter, "parse_rbs", return_value={}),
                    self.assertRaisesRegex(ValueError, "universe"),
                ):
                    reporter.prepare(Path(directory), output)

    def test_cli_and_entrypoint(self):
        with (
            patch.object(
                reporter, "prepare", return_value={"n_constructs": 32}
            ) as prepare,
            redirect_stdout(io.StringIO()) as result,
        ):
            reporter.main(["raw", "out.json"])
        self.assertEqual(json.loads(result.getvalue()), {"n_constructs": 32})
        prepare.assert_called_once_with(Path("raw"), Path("out.json"))
        with (
            patch.object(sys, "argv", ["reporter", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.reporter", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
