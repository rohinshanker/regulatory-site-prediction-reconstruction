"""Independent tiny source tables exercise data integrity and outcome blindness."""

import copy
import csv
import io
import itertools
import json
import random
import runpy
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import new_data as n
from benchmarks.rbs.metrics import edit_distance as matrix_distance


def kuo_rows(values=None):
    return iter(
        [[], [], [], ["Genotype", "Fitness (Log(GFP))", "", "", "Mean Fitness"], []]
        + (values or [["AAAAAAAAA", "1", "", "3", "2"], ["CCCCCCCCC", "", "", "", ""]])
    )


def cambray_spec():
    return {
        "prefix": "CCCATG",
        "start": 3,
        "variable_length": 6,
        "partition": "reserved_final",
        "rows": 4,
        "families_per_seed": 1,
    }


def cambray_designs():
    return [
        {
            "": f"1_{family}_{rep}",
            "seed": "1",
            "combi": family,
            "rep": rep,
            "gs.sequence": seq,
        }
        for family, rep, seq in (
            ("11", "1", "AAAAAA"),
            ("11", "2", "AAAAAC"),
            ("22", "1", "CCCCCC"),
            ("22", "2", "CCCCCA"),
        )
    ]


class NewDataTest(unittest.TestCase):
    def test_exclusive_reservations_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / "first.json", root / "second.json"
            with self.assertRaises(FileExistsError):
                n.write_new_outputs([(first, {}), (first, {})])
            self.assertFalse(first.exists())
            with self.assertRaises(ValueError):
                n.write_new_outputs([(first, {"bad": float("nan")}), (second, {})])
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            original_open = Path.open

            @contextmanager
            def fail_on_close(path, *args, **kwargs):
                with original_open(path, *args, **kwargs) as stream:
                    yield stream
                raise OSError("buffered close failure")

            with patch.object(Path, "open", fail_on_close):
                with self.assertRaisesRegex(OSError, "buffered close"):
                    n.write_new_outputs([(first, {}), (second, {})])
            self.assertFalse(first.exists())
            self.assertFalse(second.exists())
            first.write_text("preexisting data")
            with self.assertRaises(FileExistsError):
                n.write_new_outputs([(first, {})])
            self.assertEqual(first.read_text(), "preexisting data")

    def test_selected_source_completeness_without_outcome_release(self):
        frozen = {"records": [{"id": str(i), "study": "Cambray2018"} for i in range(5)]}
        outcomes = [
            {"id": str(i), "observed": mean, "replicates": reps}
            for i, (mean, reps) in enumerate(
                (
                    (2, [1, 3]),
                    (None, [None, None]),
                    (0, [0, 0]),
                    (4, [1, 3]),
                    (None, [1, None]),
                )
            )
        ]
        result = n.selected_completeness(outcomes, frozen)["Cambray2018"]
        self.assertEqual(
            result,
            {
                "selected_inputs": 5,
                "observed_mean_present": 3,
                "mean_missing": 2,
                "mean_nonpositive": 1,
                "replicate_count_2": 3,
                "replicate_count_0": 1,
                "replicate_count_1": 1,
                "mean_rounding_mismatch": 1,
            },
        )
        with self.assertRaisesRegex(ValueError, "identity"):
            n.selected_completeness(outcomes[:-1], frozen)

    def test_committed_split_and_audit_identities(self):
        root = Path(__file__).resolve().parents[2] / "benchmarks/rbs"
        split_bytes = (root / "new-evaluation-split.json").read_bytes()
        split = json.loads(split_bytes)
        admission = json.loads((root / "new-data-admission-audit.json").read_text())
        overlap = json.loads((root / "new-data-overlap-audit.json").read_text())
        self.assertEqual(
            split["manifest_sha256"],
            n.digest(json.dumps(self.real_manifest(), sort_keys=True)),
        )
        self.assertEqual(admission["split_file_sha256"], n.digest(split_bytes))
        self.assertEqual(
            split["input_envelope_sha256"], admission["input_envelope_sha256"]
        )
        self.assertEqual(
            split["input_envelope_sha256"], overlap["input_envelope_sha256"]
        )
        self.assertEqual(len({r["id"] for r in split["records"]}), 596)
        self.assertEqual(
            split["partition_counts"], {"reserved_final": 335, "exposed_secondary": 261}
        )
        self.assertTrue(
            all(
                set(row)
                <= {
                    "id",
                    "study",
                    "group",
                    "design_family",
                    "partition",
                    "sequence_sha256",
                    "start",
                }
                for row in split["records"]
            )
        )
        cambray = [r for r in split["records"] if r["study"] == "Cambray2018"]
        self.assertEqual(len({r["group"] for r in cambray}), 56)
        self.assertEqual(len({r["design_family"] for r in cambray}), 112)
        self.assertFalse(split["selection_uses_outcomes"])
        self.assertTrue(admission["no_model_predictions"])

    def test_previous_input_field_maps(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = [
                {"id": "x", "sequence": "CCCATGAA", "start": [3]},
                {"id": "missing", "sequence": None},
            ]
            asset = {
                "path": "inputs.json",
                "records_key": "records",
                "start_field": "start",
            }

            def save(data):
                (root / "inputs.json").write_text(json.dumps(data))
                asset["sha256"] = n.digest((root / "inputs.json").read_bytes())

            save({"records": rows})
            result, report = n.previous_inputs(root, asset)
            self.assertEqual(result, [{"id": "x", "sequence": "CCCATGAA", "start": 3}])
            self.assertEqual(
                report, {"source_rows": 2, "usable_rows": 1, "missing_sequence": 1}
            )
            asset.update(records_key=None, start_field=None, start_value=3)
            save(rows)
            self.assertEqual(n.previous_inputs(root, asset)[0], result)
            asset["start_field"] = "start"
            for bad in ([1, 2], True, 0, 9):
                rows[0]["start"] = bad
                save(rows)
                with self.assertRaises(ValueError):
                    n.previous_inputs(root, asset)
            rows[0]["start"] = 3
            save([rows[0], rows[0]])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                n.previous_inputs(root, asset)

    def test_bit_vectors_against_independent_matrix_and_overlap(self):
        strings = [
            "".join(s)
            for length in range(4)
            for s in itertools.product("ACGT", repeat=length)
        ]
        for left in strings:
            for right in strings:
                self.assertEqual(
                    n.edit_distance(left, right), matrix_distance(left, right)
                )
        rng = random.Random(240)
        for length in (64, 65, 105, 188, 257):
            left = "".join(rng.choices("ACGT", k=length))
            right = "".join(rng.choices("ACGT", k=length + 7))
            self.assertEqual(n.edit_distance(left, right), matrix_distance(left, right))
        new = [{"id": "new", "sequence": "CCCATGAAAA", "start": 3}]
        previous = [{"id": "old", "sequence": "GGCCCATGAAAATT", "start": 5}]
        hit = n.overlap(new, previous)[0]
        self.assertEqual(
            (hit["window"], hit["edit_distance"], hit["length"]), ([-3, 7], 0, 10)
        )
        previous[0]["sequence"] = "GGTTTATGTTTTTT"
        self.assertEqual(n.overlap(new, previous), [])
        previous[0]["start"] = 0
        with self.assertRaises(ValueError):
            n.overlap(new, previous)

    def test_cambray_family_selection_is_outcome_blind(self):
        rows, spec = cambray_designs(), cambray_spec()
        selected, audit = n.select_cambray(iter(rows), spec, "fixed")
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({r["design_family"] for r in selected}), 1)
        self.assertEqual({r["design_replicate"] for r in selected}, {"1", "2"})
        self.assertEqual(audit["rows"], 4)
        for row in rows:
            row["clean.lin.prot.mean"] = "arbitrary outcome ignored"
        self.assertEqual(
            n.select_cambray(reversed(rows), spec, "fixed"), (selected, audit)
        )
        for mode in (
            "length",
            "seed",
            "combi",
            "rep",
            "id",
            "start",
            "duplicate-id",
            "duplicate-seq",
            "count",
        ):
            changed, settings = copy.deepcopy(rows), dict(spec)
            if mode == "length":
                changed[0]["gs.sequence"] = "A"
            if mode == "seed":
                changed[0]["seed"] = "x"
            if mode == "combi":
                changed[0]["combi"] = ""
            if mode == "rep":
                changed[0]["rep"] = "0"
            if mode == "id":
                changed[0][""] = "different"
            if mode == "start":
                settings["start"] = 0
            if mode == "duplicate-id":
                changed[1] = changed[0]
            if mode == "duplicate-seq":
                changed[1]["gs.sequence"] = changed[0]["gs.sequence"]
            if mode == "count":
                settings["rows"] = 5
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                n.select_cambray(changed, settings, "fixed")

    def test_generated_kuo_panel_and_prefix_contracts(self):
        spec = self.real_manifest()["kuo2020"]
        spec["genotypes_per_gc_count"] = 1
        records = n.select_kuo(spec, "fixed")
        groups = {}
        for row in records:
            self.assertEqual(len(row["sequence"]), 73)
            self.assertEqual(row["sequence"][30:33], "ATG")
            groups.setdefault(row["context"], set()).add(row["genotype"])
        self.assertEqual(groups["arti"], groups["fepB"])
        self.assertEqual(groups["arti"], groups["dmsC"])
        self.assertEqual(
            {sum(base in "GC" for base in seq) for seq in groups["arti"]},
            set(range(10)),
        )
        for field in ("cds_prefix_sha256", "start"):
            bad = copy.deepcopy(spec)
            bad[field] = "wrong" if field.endswith("sha256") else 29
            with self.assertRaises(ValueError):
                n.select_kuo(bad, "fixed")

    @staticmethod
    def real_manifest():
        return json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "benchmarks/rbs/new-data-manifest.json"
            ).read_text()
        )

    def test_kuo_missingness_rounding_and_universe(self):
        records = list(n.kuo_outcomes(kuo_rows(), {"rows_per_context": 2}))
        self.assertEqual(
            records, [("AAAAAAAAA", [1, None, 3, 2]), ("CCCCCCCCC", [None] * 4)]
        )
        self.assertEqual(n.measurement("-1"), -1)
        self.assertEqual(n.measurement("0"), 0)
        self.assertIsNone(n.measurement("NA"))
        for value in ("NaN", "inf", "#VALUE!"):
            with self.assertRaises(ValueError):
                n.measurement(value)
        for mode in (
            "header",
            "columns",
            "length",
            "alphabet",
            "duplicate",
            "missing",
            "mean",
            "count",
        ):
            rows = list(kuo_rows())
            count = 2
            if mode == "header":
                rows[3] = []
            if mode == "columns":
                rows[-1].pop()
            if mode == "length":
                rows[-1][0] = "A"
            if mode == "alphabet":
                rows[-1][0] = "NNNNNNNNN"
            if mode == "duplicate":
                rows[-1] = rows[-2]
            if mode == "missing":
                rows[-1][-1] = "1"
            if mode == "mean":
                rows[-2][-1] = "2.1"
            if mode == "count":
                count = 3
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                list(n.kuo_outcomes(iter(rows), {"rows_per_context": count}))

    def make_sources(self, root):
        spec = cambray_spec()
        spec.update(
            path="source.zip",
            member="table.csv",
            unit="linear protein",
            primary_replicates=["rep1", "rep2"],
            primary_quantity="mean",
            secondary_quantity="facilitated",
        )
        rows = cambray_designs()
        for row in rows:
            row.update(rep1="1", rep2="3", mean="2", facilitated="4")
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        with zipfile.ZipFile(root / "source.zip", "w") as archive:
            archive.writestr("table.csv", text.getvalue())
        spec["sha256"] = n.digest((root / "source.zip").read_bytes())
        with (root / "kuo.csv").open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\r").writerows(kuo_rows())
        kuo = {
            "rows_per_context": 2,
            "unit": "source Log(GFP)",
            "contexts": {
                "arti": {
                    "path": "kuo.csv",
                    "sha256": n.digest((root / "kuo.csv").read_bytes()),
                }
            },
        }
        return {"selection_seed": "fixed", "cambray2018": spec, "kuo2020": kuo}

    def test_hash_gated_freeze_private_extraction_and_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.make_sources(root)
            with self.assertRaisesRegex(RuntimeError, "reader failure"):
                with n.cambray_rows(root / "source.zip", "table.csv") as rows:
                    next(rows)
                    raise RuntimeError("reader failure")
            manifest_path, input_path = root / "manifest.json", root / "inputs.json"
            manifest_path.write_text(json.dumps(manifest))
            selected = [
                {"id": "kuo2020:arti:" + seq, "partition": "exposed_secondary"}
                for seq in ("AAAAAAAAA", "CCCCCCCCC")
            ]
            with patch.object(n, "select_kuo", return_value=selected):
                frozen = n.freeze(root, manifest)
                self.assertFalse(frozen["selection_uses_outcomes"])
                public = n.public_split(frozen)
                self.assertTrue(all("sequence" not in r for r in public["records"]))
                self.assertEqual(len(public["records"]), len(frozen["records"]))
                outcomes, audit = n.extract(root, manifest, frozen)
                self.assertEqual(len(outcomes), 4)
                self.assertEqual(
                    audit["kuo2020:arti"]["source_replicate_coverage"], {0: 1, 2: 1}
                )
                self.assertNotIn("observed", json.dumps(frozen))
                with patch.object(n, "select_kuo", return_value=selected[:1]):
                    smaller = n.freeze(root, manifest)
                    subset, _ = n.extract(root, manifest, smaller)
                    self.assertEqual(len(subset), 3)
                with self.assertRaisesRegex(ValueError, "frozen"):
                    n.extract(root, manifest, {})
                with patch.object(
                    n,
                    "freeze",
                    return_value={
                        **frozen,
                        "records": [*frozen["records"], {"id": "absent"}],
                    },
                ):
                    with self.assertRaisesRegex(ValueError, "identity set"):
                        n.extract(root, manifest, n.freeze(root, manifest))
                n.main(["freeze", str(root), str(manifest_path), str(input_path)])
                collision = root / "collision.json"
                for alias in (
                    collision,
                    root / "unused-parent" / ".." / "collision.json",
                ):
                    with self.assertRaisesRegex(ValueError, "distinct"):
                        n.main(
                            [
                                "freeze",
                                str(root),
                                str(manifest_path),
                                str(collision),
                                "--split-output",
                                str(alias),
                            ]
                        )
                    self.assertFalse(collision.exists())
                # Exercise the actual filesystem's case behavior, not a mock.
                probe = root / "case-probe"
                probe.write_text("")
                insensitive = (root / "CASE-PROBE").exists()
                probe.unlink()
                arguments = [
                    "freeze",
                    str(root),
                    str(manifest_path),
                    str(collision),
                    "--split-output",
                    str(root / "COLLISION.JSON"),
                ]
                if insensitive:
                    with self.assertRaises(FileExistsError):
                        n.main(arguments)
                    self.assertFalse(collision.exists())
                    self.assertFalse((root / "COLLISION.JSON").exists())
                else:
                    n.main(arguments)
                    self.assertEqual(json.loads(collision.read_text()), frozen)
                    self.assertEqual(
                        json.loads((root / "COLLISION.JSON").read_text()), public
                    )
                split_path = root / "split.json"
                n.main(
                    [
                        "freeze",
                        str(root),
                        str(manifest_path),
                        str(root / "other-inputs.json"),
                        "--split-output",
                        str(split_path),
                    ]
                )
                self.assertEqual(json.loads(split_path.read_text()), public)
                with self.assertRaises(FileExistsError):
                    n.main(
                        [
                            "freeze",
                            str(root),
                            str(manifest_path),
                            str(root / "unused.json"),
                            "--split-output",
                            str(split_path),
                        ]
                    )
                self.assertFalse((root / "unused.json").exists())
                with self.assertRaises(FileExistsError):
                    n.main(["freeze", str(root), str(manifest_path), str(input_path)])
                with self.assertRaisesRegex(ValueError, "private-output"):
                    n.main(["extract", str(root), str(manifest_path), str(input_path)])
                private = root / "private"
                n.main(
                    [
                        "extract",
                        str(root),
                        str(manifest_path),
                        str(input_path),
                        "--private-output",
                        str(private),
                    ]
                )
                self.assertEqual(private.stat().st_mode & 0o777, 0o700)
                self.assertEqual(
                    (private / "outcomes.json").stat().st_mode & 0o777, 0o600
                )
                with self.assertRaises(FileExistsError):
                    n.private_write(private, outcomes, audit)
            bad = dict(manifest["cambray2018"], sha256="changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                n.checked(root, bad)

    def test_module_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self.make_sources(root)
            # Use the real generated selection for the entrypoint, input-only.
            manifest["kuo2020"] = self.real_manifest()["kuo2020"]
            (root / "manifest.json").write_text(json.dumps(manifest))
            with patch(
                "sys.argv",
                [
                    "new_data",
                    "freeze",
                    str(root),
                    str(root / "manifest.json"),
                    str(root / "inputs.json"),
                ],
            ):
                runpy.run_path(n.__file__, run_name="__main__")
            self.assertTrue((root / "inputs.json").is_file())
