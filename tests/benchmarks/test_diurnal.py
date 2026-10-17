"""Independent condition-ratio arithmetic and frozen original-boundary admission."""

import gzip
import io
import json
import runpy
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

from benchmarks.rbs import diurnal
from benchmarks.rbs.datasets import digest


class DiurnalTests(unittest.TestCase):
    def setUp(self):
        self.header = ["Name"] + ["Mean_log2RPKM_" + x for x in diurnal.PHASES]
        self.rna = [self.header, ["old", 1, 2, 3, 4, 5]]
        self.rpf = [self.header, ["old", 2, 3, 4, 5, 6]]
        self.sequence = "C" * 100 + "ATG" + "C" * 200
        self.genomes = {
            "NC_000911.1": {
                "sequence": self.sequence,
                "sequence_sha256": digest(self.sequence),
            }
        }
        self.features = [
            {"type": "gene", "attributes": {"locus_tag": "g", "old_locus_tag": "old"}},
            {
                "type": "CDS",
                "replicon": "NC_000911.1",
                "interval": [100, 160],
                "strand": "+",
                "start_zero_based": 100,
                "phase": "0",
                "attributes": {"locus_tag": "g"},
            },
        ]
        self.coordinates = {"old": ("NC_000911.1", 101, 160, "+", 60)}
        self.splits = {
            "groups": [{"id": "family", "partition": "final", "members": ["g"]}]
        }
        self.tsv = (
            "Name\tSequence\tStart\tEnd\tstrand\tLength\n"
            "old\tNC_000911.1\t101\t160\t+\t60\n"
        )

    def test_repeated_source_coordinates_are_exact(self):
        self.assertEqual(diurnal.source_coordinates(self.tsv), self.coordinates)
        self.assertEqual(
            diurnal.source_coordinates(self.tsv + self.tsv.splitlines()[1] + "\n"),
            self.coordinates,
        )
        with self.assertRaises(ValueError):
            diurnal.source_coordinates(
                self.tsv + self.tsv.splitlines()[1].replace("101", "102") + "\n"
            )

    def test_condition_geometric_ratio_not_mean_of_ratios(self):
        rows = diurnal.source_measurements(self.rna, self.rpf)
        self.assertEqual(len(rows), 5)
        self.assertEqual([r["observed"] for r in rows], [2] * 5)
        self.assertEqual([r["condition"] for r in rows], list(diurnal.PHASES))
        self.assertTrue(all(not r["paired_replicate_ratio"] for r in rows))
        self.rna[1][1] = None
        self.assertIsNone(
            diurnal.source_measurements(self.rna, self.rpf)[0]["observed"]
        )
        self.rna[1][1] = -1
        self.assertEqual(
            diurnal.source_measurements(self.rna, self.rpf)[0]["observed"], 8
        )

    def test_source_measurement_validation(self):
        for kind in (
            "header",
            "duplicate_rna",
            "duplicate_rpf",
            "mismatch",
            "bool",
            "overflow",
            "underflow",
        ):
            rna, rpf = deepcopy(self.rna), deepcopy(self.rpf)
            if kind == "header":
                rna[0][0] = "other"
            elif kind == "duplicate_rna":
                rna.append(rna[1])
            elif kind == "duplicate_rpf":
                rpf.append(rpf[1])
            elif kind == "mismatch":
                rpf[1][0] = "other"
            elif kind == "bool":
                rna[1][1] = True
            elif kind == "overflow":
                rpf[1][1] = 2000.0
            else:
                rpf[1][1] = -2000.0
            with self.assertRaises(ValueError):
                diurnal.source_measurements(rna, rpf)

    def test_exact_boundaries_inherit_frozen_groups(self):
        row = diurnal.input_records(
            ["old"], self.coordinates, self.genomes, self.features, self.splits
        )[0]
        self.assertEqual(row["mapping_status"], "exact_source_and_current_cds")
        self.assertTrue(row["primary_eligible"])
        self.assertEqual(row["partition"], "final")
        self.assertEqual(row["group"], "family")
        self.assertEqual(row["sequence"][100:103], "ATG")
        direct = diurnal.input_records(
            ["g"],
            {"g": self.coordinates["old"]},
            self.genomes,
            self.features,
            self.splits,
        )[0]
        self.assertEqual(direct["mapping_status"], "exact_source_and_current_cds")
        features = deepcopy(self.features)
        features[1]["replicon"] = "plasmid"
        row = diurnal.input_records(
            ["old"],
            {"old": ("plasmid", 101, 160, "+", 60)},
            {"plasmid": self.genomes["NC_000911.1"]},
            features,
            self.splits,
        )[0]
        self.assertFalse(row["primary_eligible"])

    def test_mapping_failures_are_retained(self):
        self.assertEqual(
            diurnal.input_records(
                ["unknown"], {}, self.genomes, self.features, self.splits
            )[0]["mapping_status"],
            "unmatched_identifier",
        )
        features = deepcopy(self.features)
        features.append(
            {"type": "gene", "attributes": {"locus_tag": "g2", "old_locus_tag": "old"}}
        )
        self.assertEqual(
            diurnal.input_records(
                ["old"], self.coordinates, self.genomes, features, self.splits
            )[0]["mapping_status"],
            "ambiguous_identifier",
        )
        with self.assertRaisesRegex(ValueError, "frozen"):
            diurnal.input_records(
                ["old"], self.coordinates, self.genomes, self.features, {"groups": []}
            )
        self.assertEqual(
            diurnal.input_records(
                ["old"], self.coordinates, self.genomes, self.features[:1], self.splits
            )[0]["mapping_status"],
            "nonunique_or_absent_current_cds",
        )
        self.assertEqual(
            diurnal.input_records(
                ["old"], {}, self.genomes, self.features, self.splits
            )[0]["mapping_status"],
            "source_current_bounds_disagree",
        )
        for key, value in [
            ("pseudo", "true"),
            ("partial", "true"),
            ("exception", "source_exception"),
            ("phase", "1"),
        ]:
            features = deepcopy(self.features)
            if key == "phase":
                features[1]["phase"] = value
            else:
                features[1]["attributes"][key] = value
            self.assertEqual(
                diurnal.input_records(
                    ["old"], self.coordinates, self.genomes, features, self.splits
                )[0]["mapping_status"],
                "exceptional_current_cds",
            )

    def test_private_prepare_and_hash_checks(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("Table_1.xlsx", b"synthetic workbook")
        library = MagicMock()
        workbook = library.load_workbook.return_value
        workbook.__getitem__.side_effect = lambda name: type(
            "Sheet", (), {"values": self.rna if name == "RNA seq" else self.rpf}
        )()
        gff = (
            "NC_000911.1\ttest\tgene\t101\t160\t.\t+\t.\t"
            "locus_tag=g;old_locus_tag=old\n"
            "NC_000911.1\ttest\tCDS\t101\t160\t.\t+\t0\tlocus_tag=g\n"
        )
        sources = {
            "diurnal2021-supp.zip": archive.getvalue(),
            "diurnal2021-source-coordinates.tab": self.tsv.encode(),
            "pcc6803-genomic.gff.gz": gzip.compress(gff.encode()),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs.json"
            inputs.write_text(json.dumps({"genomes": self.genomes}))
            splits = root / "splits.json"
            splits.write_text(json.dumps(self.splits))
            output = root / "private"
            with (
                patch.dict(sys.modules, {"openpyxl": library}),
                patch.object(
                    diurnal, "checked_source", side_effect=lambda _, name: sources[name]
                ),
                patch.object(diurnal, "WORKBOOK_SHA256", digest(b"synthetic workbook")),
            ):
                result = diurnal.prepare(root, inputs, splits, output)
                self.assertEqual(result["n_primary_genes"], 1)
                self.assertEqual(result["n_condition_records"], 5)
                self.assertEqual(
                    (output / "diurnal-outcomes-private.json").stat().st_mode & 0o777,
                    0o600,
                )
                genomes = deepcopy(self.genomes)
                genomes["NC_000911.1"]["sequence_sha256"] = "wrong"
                inputs.write_text(json.dumps({"genomes": genomes}))
                with self.assertRaisesRegex(ValueError, "Genome"):
                    diurnal.prepare(root, inputs, splits, output)
                with (
                    patch.object(diurnal, "WORKBOOK_SHA256", "wrong"),
                    self.assertRaisesRegex(ValueError, "workbook"),
                ):
                    diurnal.prepare(root, inputs, splits, output)

    def test_cli_and_entrypoint(self):
        with (
            patch.object(
                diurnal, "prepare", return_value={"n_primary_genes": 1}
            ) as prepare,
            redirect_stdout(io.StringIO()) as output,
        ):
            diurnal.main(["raw", "inputs", "splits", "private"])
        self.assertEqual(json.loads(output.getvalue()), {"n_primary_genes": 1})
        prepare.assert_called_once_with(
            Path("raw"), Path("inputs"), Path("splits"), Path("private")
        )
        with (
            patch.object(sys, "argv", ["diurnal", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.diurnal", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
