"""Public benchmark arithmetic and source-asset validation; no model imports."""

import copy
import json
import runpy
import struct
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.promoter import audit as a


def npy(values, **changes):
    header = {"descr": "<f8", "fortran_order": False, "shape": (len(values),)}
    header.update(changes)
    encoded = (repr(header) + "\n").encode("ascii")
    return (
        b"\x93NUMPY\x01\x00"
        + struct.pack("<H", len(encoded))
        + encoded
        + struct.pack(f"<{len(values)}d", *values)
    )


def parameters():
    rows = [["region", "value", None]]
    for name, n in (
        ("h10 position 0", 64),
        ("h10 position 3", 64),
        ("h35 position 0", 64),
        ("h35 position 3", 64),
        ("disc 3mer", 64),
        ("10ext 2mer", 16),
    ):
        rows += [[name, repr((str(i), 0)), None] for i in range(n)]
    for name in ("UP Distal", "UP Proximal", "ITR", "Spacer"):
        rows.append([name, repr(("test", 0)), None])
    for n in range(15, 21):
        rows.append(
            [
                "Spacer Length",
                repr((str(n), 0.1463 * n * n - 4.9113 * n + 41.119)),
                None,
            ]
        )
    return rows


class PromoterAuditTest(unittest.TestCase):
    def test_published_metrics_and_explicit_slope(self):
        rows = [
            ["Promoter", a.OBSERVED, a.PREDICTED, "Slope"],
            ["acgt", 2, 1, 2],
            ["ACGT", 4, 2, None],
            ["N", None, 0, None],
            [None, True, 3, None],
            ["", float("nan"), 0, None],
        ]
        report = a.sheet_report(rows)
        self.assertEqual(
            (report["rows"], report["paired_rows"], report["excluded_nonfinite_pairs"]),
            (5, 2, 3),
        )
        self.assertAlmostEqual(report["pearson_squared"], 1)
        self.assertAlmostEqual(report["spearman"], 1)
        self.assertEqual(report["as_supplied_errors"]["mae"], 1.5)
        self.assertEqual(report["worksheet_calibrated_errors"]["mae"], 0)
        self.assertEqual(
            report["sequence_counts"],
            {
                "valid_acgt_rows": 2,
                "unique_strings": 1,
                "invalid_or_missing_rows": 3,
                "length_counts": {4: 2},
            },
        )
        constant = [
            ["Promoter Sequence", a.OBSERVED, a.PREDICTED],
            ["A", 1, 0],
            ["C", 2, 0],
        ]
        self.assertIsNone(a.sheet_report(constant)["pearson_squared"])
        with self.assertRaisesRegex(ValueError, "slope"):
            a.errors([(1, 2)], True)

    def test_bad_worksheet_contracts(self):
        valid = [["Promoter", a.OBSERVED, a.PREDICTED], ["A", 1, 2]]
        for rows in (
            [["x"], [1]],
            [valid[0], [1]],
            [valid[0], ["A", None, 2]],
            [["other", a.OBSERVED, a.PREDICTED], ["A", 1, 2]],
            [[*valid[0], "Slope"], ["A", 1, 2, None]],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                a.sheet_report(rows)

    def test_npy_without_numpy_or_pickle(self):
        self.assertEqual(a.read_npy(npy([1, 2])), (1, 2))
        for raw in (
            b"bad",
            b"\x93NUMPY\x01\x00",
            npy([1], descr="|O"),
            npy([1], fortran_order=True),
            npy([1], shape=[1]),
            npy([1], shape=(1, 1)),
            npy([1], shape=(True,)),
            npy([1], shape=(0,)),
            npy([1])[:-1],
            npy([float("inf")]),
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                a.read_npy(raw)

    def test_every_active_coefficient(self):
        rows = parameters()
        result = a.parameter_report(rows, (0,) * 343, (0,))
        self.assertEqual(result["active_categorical_exact_matches"], 336)
        self.assertEqual(result["workbook_parameter_rows"], 346)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            a.parameter_report(rows, (), (0,))
        for mode in (
            "short",
            "duplicate",
            "categorical",
            "numeric",
            "spacer-domain",
            "spacer-energy",
        ):
            changed = copy.deepcopy(rows)
            if mode == "short":
                changed.pop(1)
            if mode == "duplicate":
                changed[2] = changed[1]
            if mode == "categorical":
                changed[1][1] = repr(("0", 1))
            if mode == "numeric":
                changed[337][1] = repr(("test", 1))
            if mode == "spacer-domain":
                changed[-1][1] = repr(("21", 1))
            if mode == "spacer-energy":
                changed[-1][1] = repr(("20", 1))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                a.parameter_report(changed, (0,) * 343, (0,))

    def test_source_hash_gate_workbook_close_and_cli(self):
        class Workbook(dict):
            closed = False

            def close(self):
                self.closed = True

        rows = [["Promoter", a.OBSERVED, a.PREDICTED], ["A", 2, 1]]
        book = Workbook({name: types.SimpleNamespace(values=rows) for name in a.SHEETS})
        book["Model Parameters (Fig 2E)"] = types.SimpleNamespace(values=parameters())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, raw in [
                ("book.xlsx", b"placeholder"),
                ("coef.npy", npy([0] * 343)),
                ("intercept.npy", npy([0])),
            ]:
                (root / name).write_bytes(raw)
            assets = {
                key: {"path": name, "sha256": a.sha256(root / name)}
                for key, name in [
                    ("workbook", "book.xlsx"),
                    ("coefficients", "coef.npy"),
                    ("intercept", "intercept.npy"),
                ]
            }
            manifest = {"audit_assets": assets}
            (root / "manifest.json").write_text(json.dumps(manifest))
            module = types.SimpleNamespace(load_workbook=lambda *args, **kw: book)
            with patch.dict("sys.modules", openpyxl=module):
                result = a.audit(root, manifest)
                self.assertFalse(result["project_model_executed"])
                self.assertTrue(book.closed)
                a.main([str(root), str(root / "manifest.json"), str(root / "out.json")])
                self.assertEqual(
                    json.loads((root / "out.json").read_text())["schema_version"],
                    "promoter-published-audit-1",
                )
                with patch(
                    "sys.argv",
                    [
                        "audit",
                        str(root),
                        str(root / "manifest.json"),
                        str(root / "module.json"),
                    ],
                ):
                    runpy.run_path(a.__file__, run_name="__main__")
                (root / "book.xlsx").write_text("changed")
                with self.assertRaisesRegex(ValueError, "hash changed"):
                    a.audit(root, manifest)

    def test_source_only_scalar_and_coordinate_fixtures(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "benchmarks/promoter/source-fixtures.json"
        )
        fixtures = {x["name"]: x for x in json.loads(path.read_text())["fixtures"]}
        self.assertAlmostEqual(
            fixtures["spacer_17"]["expected"], 0.1463 * 17**2 - 4.9113 * 17 + 41.119
        )
        self.assertEqual(fixtures["groove_homopolymer_12"]["expected"], 6 * 5)
        self.assertEqual(
            fixtures["rigidity_homopolymer_44"]["expected"], 22 * 50.4 / 44
        )
        self.assertAlmostEqual(
            fixtures["hybrid_homopolymer_20"]["expected"]["difference"],
            7 * (-1) - 7 * (-0.2),
        )
        intervals = fixtures["forward_feature_intervals"]["expected"]
        # Compose independently from TSS backwards using explicit lengths.
        right = 100
        for feature, length in [
            ("disc", 6),
            ("hex10", 6),
            ("spacer", 17),
            ("hex35", 6),
            ("gap", 1),
            ("UP", 24),
        ]:
            self.assertEqual(intervals[feature], [right - length, right])
            right -= length
        self.assertEqual(intervals["ITR"], [100, 120])
        self.assertEqual(
            intervals["extended10"],
            [intervals["spacer"][1] - 3, intervals["spacer"][1] - 1],
        )
        reverse = fixtures["reverse_coordinate_contract"]
        n, t = reverse["input"]["length"], reverse["input"]["oriented_tss"]
        self.assertEqual(
            reverse["expected"]["base_index_on_forward_reference"], n - 1 - t
        )
        self.assertEqual(reverse["expected"]["upstream_dictionary_key"], n - t)
        start, end = reverse["input"]["oriented_interval"]
        self.assertEqual(
            reverse["expected"]["mapped_half_open_interval"], [n - end, n - start]
        )


if __name__ == "__main__":
    unittest.main()
