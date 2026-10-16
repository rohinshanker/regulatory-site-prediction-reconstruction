"""Historical audit and command contracts use synthetic, independently known data."""

import contextlib
import io
import json
import math
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.rbs import audit, datasets
from benchmarks.rbs.__main__ import main


def historical_rows():
    rows = [["", "", i, math.exp(i / 20)] for i in range(77)]
    rows[17][0], rows[47][0] = "Reverse engineered", "Forward engineered"
    return rows


def flow_rows():
    measurements, predictions = [[None] * 49], [[None] * 22]
    for key, group, observed, predicted in [
        (1, "A", 1, 1),
        (2, "A", 4, 1),
        (3, "B", 1, 2),
    ]:
        row, pred = [None] * 49, [None] * 22
        row[0], row[1], row[46] = key, group, observed
        pred[0], pred[20], pred[21] = key, predicted, observed / predicted
        measurements.append(row)
        predictions.append(pred)
    stats = [
        ["RBS Calculator v2.1"],
        ["header"],
        ["A+context"] + [0] * 12,
        ["B+context"] + [0] * 12,
    ]
    return measurements, predictions, stats


class AuditTest(unittest.TestCase):
    def test_salis_metric_and_group_counts(self):
        result = audit.salis_metrics(historical_rows())
        self.assertEqual(result["existing_2B"]["n"], 28)
        self.assertEqual(result["designed_2E"]["n"], 29)
        self.assertAlmostEqual(
            result["designed_2E"]["pearson_r2_energy_vs_ln_fluorescence"], 1
        )
        self.assertIsNone(audit.squared_correlation([1], [1]))
        rows = historical_rows()
        rows[17][0] = "wrong group"
        with self.assertRaises(ValueError):
            audit.salis_metrics(rows)

    def test_standby_labels_and_noise(self):
        records = [
            dict(
                figure_labels="2-G, 5-A",
                published_dg_total=i,
                observed=math.exp(i),
                observed_sd=math.exp(i) / 4,
                published_dg_standby=i,
                apparent_dg_standby=i + 1,
                replicates=3,
            )
            for i in (1, 2, 3)
        ]
        result = audit.standby_metrics(records)
        self.assertEqual(result["figure_2G"]["n"], 3)
        self.assertEqual(result["figure_5A"]["standby_mae_kcal_mol"], 1)
        self.assertEqual(result["measurement_noise"]["median_cv"], 0.25)

    def test_historical_fractions_and_join_failures(self):
        measurements, predictions, stats = flow_rows()
        result = audit.flowseq_metrics(measurements, predictions, stats)
        self.assertEqual(result["A"]["within_2fold"]["all_case_fraction"], 0.5)
        self.assertEqual(
            result["A"]["reproduced_mislabelled_fractions"]["below_6fold"], 1
        )
        self.assertEqual(result["B"]["max_cached_ratio_residual"], 0)
        for obs, pred in [
            (measurements + measurements[1:2], predictions),
            (measurements, predictions + predictions[1:2]),
            (measurements, predictions[:-1]),
        ]:
            with self.assertRaises(ValueError):
                audit.flowseq_metrics(obs, pred, stats)

    def test_audit_orchestration(self):
        rows = historical_rows()
        sheet = Mock(nrows=len(rows), row_values=lambda i: rows[i])
        xls = Mock()
        xls.open_workbook.return_value.sheet_by_name.return_value = sheet
        xls.open_workbook.return_value.sheet_by_index.return_value = sheet
        measures, predictions, stats = flow_rows()
        book = {
            "FS": types.SimpleNamespace(values=measures),
            "RBS Calculator v2.1": types.SimpleNamespace(values=predictions),
            "Statistics": types.SimpleNamespace(values=stats),
        }
        xlsx_book = Mock()
        xlsx_book.__getitem__ = Mock(side_effect=book.__getitem__)
        xlsx = Mock(load_workbook=Mock(return_value=xlsx_book))
        with (
            patch.dict(sys.modules, xlrd=xls, openpyxl=xlsx),
            patch.object(audit, "source_path", return_value=Path("source")),
            patch.object(audit, "standby_records", return_value=[]),
            patch.object(
                audit, "standby_metrics", return_value={"validated_separately": True}
            ),
        ):
            result = audit.audit("cache")
        self.assertEqual(result["salis2009"]["existing_2B"]["n"], 28)
        xlsx_book.close.assert_called_once()

    def test_prepare_private_boundary_counts_and_outputs(self):
        dev = [
            dict(
                id=f"d{i}",
                sequence="ATGAAAA",
                start=0,
                source_row=i,
                family="d",
                observed=10,
            )
            for i in range(136)
        ]
        heldout = [
            dict(
                id=f"h{i}",
                sequence="CCCCCCC",
                start=0,
                source_row=i,
                family="h",
                observed=99,
            )
            for i in range(27)
        ]
        xls, xlsx = Mock(), Mock()
        xls.open_workbook.return_value.sheet_by_index.return_value.nrows = 0
        workbook = Mock()
        workbook.__getitem__ = Mock(return_value=types.SimpleNamespace(values=[]))
        xlsx.load_workbook.return_value = workbook
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(sys.modules, xlrd=xls, openpyxl=xlsx),
            patch.object(datasets, "source_path", return_value=Path("source")),
            patch.object(datasets, "standby_records", return_value=dev),
            patch.object(
                datasets, "footprint_records", return_value=heldout
            ) as extract,
        ):
            root = Path(temporary)
            with self.assertRaises(ValueError):
                datasets.prepare(
                    root, root, Path(datasets.__file__).resolve().parents[2]
                )
            result = datasets.prepare(root, root / "public", root / "private")
            self.assertEqual(result["development"], 136)
            private = root / "private/footprint2017.json"
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                json.loads(private.read_text())["records"][0]["observed"], 99
            )
            split = json.loads((root / "public/experimental-split.json").read_text())
            self.assertNotIn("observed", json.dumps(split))
            extract.return_value = []
            with self.assertRaises(ValueError):
                datasets.prepare(root, root / "public", root / "private")


class CommandTest(unittest.TestCase):
    def test_dispatch(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            contextlib.redirect_stdout(io.StringIO()),
            patch("benchmarks.rbs.fetch.fetch", return_value={}) as fetch,
            patch("benchmarks.rbs.__main__.prepare", return_value={}) as prep,
            patch("benchmarks.rbs.audit.audit", return_value={}) as historical,
        ):
            main(["fetch", temporary, "--sources", "salis2009"])
            fetch.assert_called_once()
            main(["prepare", temporary, temporary, temporary])
            prep.assert_called_once()
            main(["audit", temporary, temporary + "/audit.json"])
            historical.assert_called_once()

    def test_score_command_and_mandatory_identity(self):
        with (
            tempfile.TemporaryDirectory() as temporary,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(temporary)
            datasets.write_json(
                root / "obs.json",
                {"records": [dict(id="control", observed=10, family="x")]},
            )
            datasets.write_json(
                root / "pred.json",
                {"records": [dict(id="control", predicted=100, status="ok")]},
            )
            args = [
                "score",
                str(root / "obs.json"),
                str(root / "pred.json"),
                str(root / "out.json"),
                "--comparison",
                "reconstruction-versus-experiment",
                "--prediction-identity",
                "frozen-example",
            ]
            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                main(args)
            main(args + ["--reference", "control"])
            result = json.loads((root / "out.json").read_text())
            self.assertEqual(result["metrics"]["mae_log2"], 0)
            self.assertEqual(
                result["measurements_sha256"],
                datasets.digest((root / "obs.json").read_bytes()),
            )
            args[-1] = " "
            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                main(args + ["--reference", "control"])

    def test_module_entrypoint(self):
        with (
            patch.dict(sys.modules),
            patch.object(sys, "argv", ["benchmarks.rbs", "--help"]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as result,
        ):
            sys.modules.pop("benchmarks.rbs.__main__", None)
            runpy.run_module("benchmarks.rbs", run_name="__main__")
        self.assertEqual(result.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
