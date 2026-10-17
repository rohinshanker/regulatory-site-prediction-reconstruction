"""Source-independent TE, identifier and context tests."""

import gzip
import io
import json
import runpy
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.rbs import karlsen
from benchmarks.rbs.datasets import digest

REP = "NC_000911.1"
DNA = "A" * 150 + "ATG" + "A" * 247


def feature(kind="CDS", locus="current", start=150, attrs=None):
    return {
        "type": kind,
        "replicon": REP,
        "strand": "+",
        "start_zero_based": start,
        "interval": [start, start + 99],
        "segments": [[start, start + 99]],
        "phase": "0",
        "attributes": {"locus_tag": locus, "protein_id": "p", **(attrs or {})},
    }


def table(name="old"):
    row = [None] * 37
    row[0] = name
    row[1], row[2], row[4], row[5], row[8], row[9], row[31] = 4, 6, 2, 3, 1.5, 2.5, 33
    return [["legend"], [], karlsen.HEADERS + [None] * 26, row]


class KarlsenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.features = [feature("gene", attrs={"old_locus_tag": "old,"}), feature()]
        self.sequences = {REP: DNA}
        self.proteins = {"p": "A" * 33}

    def extract(self, rows=None, features=None, proteins=None):
        return karlsen.karlsen_records(
            rows or table(),
            self.sequences,
            self.features if features is None else features,
            self.proteins if proteins is None else proteins,
        )

    def test_zero_missing_and_positive_have_different_semantics(self):
        self.assertEqual(
            karlsen.assay_value(0),
            {"value": 0, "status": "reported_zero", "log_eligible": False},
        )
        for missing in (None, "NA"):
            self.assertEqual(karlsen.assay_value(missing)["status"], "missing")
        self.assertTrue(karlsen.assay_value(1.25)["log_eligible"])
        for bad in (True, False, -1, float("nan"), float("inf"), "0", ""):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                karlsen.assay_value(bad)

    def test_alias_index_requires_explicit_annotation_evidence(self):
        items = self.features + [
            feature("pseudogene", "other", attrs={"old_locus_tag": "old"}),
            feature("rRNA"),
        ]
        items.append({"type": "gene", "attributes": {}})
        aliases, cds = karlsen.annotation_index(items)
        self.assertEqual(aliases["old"], {"current", "other"})
        self.assertEqual(set(cds), {"current"})

    def test_hand_counted_forward_reverse_and_circular_contexts(self):
        sequence = "TTACCGGATGAAATTTCCGG"
        self.assertEqual(karlsen.genomic_context(sequence, 7, "+", 2, 6), "GGATGAAA")
        reverse = "CCGGAAATTTCATCCGGTAA"
        self.assertEqual(karlsen.genomic_context(reverse, 12, "-", 2, 6), "GGATGAAA")
        self.assertEqual(
            karlsen.genomic_context(sequence, 1, "+", 3, 3), "GGT TAC".replace(" ", "")
        )
        for start, strand, up, down in [
            (True, "+", 2, 6),
            (-1, "+", 2, 6),
            (20, "+", 2, 6),
            (1, ".", 2, 6),
            (1, "+", True, 6),
            (1, "+", -1, 6),
            (1, "+", 2, False),
            (1, "+", 2, 2),
            (1, "+", 20, 3),
        ]:
            with (
                self.subTest(case=(start, strand, up, down)),
                self.assertRaises(ValueError),
            ):
                karlsen.genomic_context(sequence, start, strand, up, down)

    def test_measurements_are_separate_and_reported_te_is_not_replaced(self):
        inputs, outcomes, audit = self.extract()
        self.assertEqual(audit["n_source_genes"], 1)
        self.assertEqual(audit["n_condition_records"], 2)
        self.assertTrue(inputs[0]["primary_eligible"])
        self.assertEqual(inputs[0]["join_evidence"], "GFF_old_locus_tag")
        self.assertEqual(inputs[0]["start_codon"], "ATG")
        self.assertEqual(inputs[0]["sequence_sha256"], digest(inputs[0]["sequence"]))
        self.assertNotIn("observed", inputs[0])
        self.assertEqual(outcomes[0]["observed"], 1.5)
        self.assertEqual(outcomes[0]["ratio_of_rounded_rpkms"], 2)
        self.assertEqual([row["condition"] for row in outcomes], ["HC", "LC"])
        self.assertEqual(outcomes[0]["biological_replicates_per_endpoint"], 1)
        self.assertIn(
            "assumed_downstream_context_extends_beyond_cds", inputs[0]["warnings"]
        )
        self.assertFalse(inputs[0]["origin_crossing"])
        self.features[1]["interval"][1] += 3
        longer, _, _ = self.extract()
        self.assertNotIn(
            "assumed_downstream_context_extends_beyond_cds", longer[0]["warnings"]
        )

    def test_unmatched_ambiguous_missing_and_multiple_cds_are_retained(self):
        for items, expected in [
            ([], "unmatched_identifier"),
            ([self.features[0]], "annotation_alias_without_cds"),
            (
                self.features
                + [feature("gene", "other", attrs={"old_locus_tag": "old"})],
                "ambiguous_exact_annotation_alias",
            ),
            (self.features + [feature()], "multiple_cds_segments_or_models"),
        ]:
            inputs, outcomes, _ = self.extract(features=items)
            self.assertEqual(inputs[0]["mapping_status"], expected)
            self.assertFalse(inputs[0]["primary_eligible"])
            self.assertEqual(len(outcomes), 2)

    def test_exceptional_pseudogene_and_missing_protein_statuses(self):
        cases = [
            ({"pseudo": "true"}, "0", "current_pseudogene"),
            ({"partial": "true"}, "0", "partial_or_exceptional_current_cds"),
            (
                {"exception": "ribosomal slippage"},
                "0",
                "partial_or_exceptional_current_cds",
            ),
            ({}, "1", "partial_or_exceptional_current_cds"),
        ]
        for attrs, phase, expected in cases:
            f = feature(attrs=attrs)
            f["phase"] = phase
            inputs, _, _ = self.extract(rows=table("current"), features=[f])
            self.assertEqual(inputs[0]["mapping_status"], expected)
            self.assertEqual(inputs[0]["join_evidence"], "current_locus_tag")
            self.assertFalse(inputs[0]["primary_eligible"])
        inputs, _, _ = self.extract(proteins={})
        self.assertEqual(
            inputs[0]["mapping_status"], "current_protein_sequence_missing"
        )
        self.assertIsNone(inputs[0]["protein_sha256"])

    def test_plasmid_length_and_origin_flags_do_not_change_values(self):
        f = feature(start=99)
        f["replicon"] = "plasmid"
        f["strand"] = "-"
        self.sequences["plasmid"] = DNA
        rows = table("current")
        rows[3][31] = 32
        inputs, outcomes, _ = self.extract(rows=rows, features=[f])
        self.assertFalse(inputs[0]["primary_eligible"])
        self.assertFalse(inputs[0]["origin_crossing"])
        self.assertIn("plasmid_secondary_domain", inputs[0]["warnings"])
        self.assertIn(
            "source_uniprot_length_differs_from_current_protein", inputs[0]["warnings"]
        )
        self.assertEqual(outcomes[0]["observed"], 1.5)
        for strand, start in [("+", 99), ("-", 98), ("+", 301), ("-", 300)]:
            f["strand"], f["start_zero_based"] = strand, start
            self.assertTrue(
                self.extract(rows=rows, features=[f])[0][0]["origin_crossing"]
            )
        rows[3][31] = "NA"
        self.assertNotIn(
            "source_uniprot_length_differs_from_current_protein",
            self.extract(rows=rows, features=[f])[0][0]["warnings"],
        )

    def test_schema_identity_and_rpkm_validation(self):
        rows = table()
        rows[2][0] = "changed"
        with self.assertRaisesRegex(ValueError, "schema"):
            self.extract(rows=rows)
        for name in (None, "", 1):
            with self.assertRaisesRegex(ValueError, "identifier"):
                self.extract(rows=table(name))
        rows = table()
        rows.append(rows[-1])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.extract(rows=rows)
        for column, value in [
            (1, True),
            (1, -1),
            (4, False),
            (4, 0),
            (4, float("nan")),
        ]:
            rows = table()
            rows[3][column] = value
            with self.assertRaisesRegex(ValueError, "RPKM"):
                self.extract(rows=rows)

    def test_private_directory_rejects_git_and_sets_permissions(self):
        repository = Path(karlsen.__file__).resolve().parents[2]
        for path in (repository, repository / "private"):
            with self.assertRaisesRegex(ValueError, "outside Git"):
                karlsen.private_directory(path)
        target = karlsen.private_directory(self.root / "private")
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_exact_protein_export_deduplicates_only_identical_locus_sequences(self):
        result = karlsen.protein_fasta(self.features + [feature()], self.proteins)
        self.assertEqual(result, ">current\n" + "A" * 33 + "\n")
        self.assertEqual(
            karlsen.protein_fasta([feature(attrs={"protein_id": "absent"})], {}), ""
        )
        no_locus = feature()
        del no_locus["attributes"]["locus_tag"]
        self.assertEqual(karlsen.protein_fasta([no_locus], self.proteins), "")
        other = feature(attrs={"protein_id": "q"})
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            karlsen.protein_fasta(self.features + [other], {**self.proteins, "q": "C"})

    def environment(self):
        region = feature("region", attrs={"Is_circular": "true"})
        rrna = feature("rRNA", attrs={"product": "16S ribosomal RNA"})
        features = self.features + [region, rrna]
        raw = {
            "pcc6803-genomic.fna.gz": gzip.compress(f">{REP}\n{DNA}\n".encode()),
            "pcc6803-genomic.gff.gz": gzip.compress(b"gff"),
            "pcc6803-protein.faa.gz": gzip.compress(b">p\n" + b"A" * 33),
            "karlsen2018-s2.xlsx": b"xlsx",
        }
        source = {
            "pcc6803_identity": {
                "replicons": {REP: 400},
                "assembly": "asm.1",
                "annotation": "ann.1",
            }
        }
        sheet, workbook = Mock(), Mock()
        sheet.iter_rows.return_value = table()
        workbook.__getitem__ = Mock(return_value=sheet)
        module = types.SimpleNamespace(load_workbook=Mock(return_value=workbook))
        return features, raw, source, module, workbook

    def test_prepare_writes_private_payloads(self):
        features, raw, source, module, workbook = self.environment()
        with (
            patch.object(karlsen, "manifest", return_value=source),
            patch.object(
                karlsen,
                "checked_source",
                side_effect=lambda root, identity: raw[identity],
            ),
            patch.object(karlsen, "gff_features", return_value=features),
            patch.dict(sys.modules, {"openpyxl": module}),
        ):
            audit = karlsen.prepare(self.root, self.root / "output")
        self.assertEqual(audit["n_source_genes"], 1)
        inputs = json.loads((self.root / "output/karlsen-inputs.json").read_text())
        self.assertEqual(inputs["records"][0]["source_file_sha256"], digest(b"xlsx"))
        self.assertEqual(inputs["genomes"][REP]["sequence"], DNA)
        self.assertTrue(
            all(
                path.stat().st_mode & 0o777 == 0o600
                for path in (self.root / "output").iterdir()
            )
        )
        workbook.close.assert_called_once()

    def test_prepare_rejects_source_topology_or_tail_conflicts(self):
        for problem in ("length", "region", "circular", "tail"):
            features, raw, source, module, _ = self.environment()
            if problem == "length":
                source["pcc6803_identity"]["replicons"][REP] = 401
            elif problem == "region":
                features = [f for f in features if f["type"] != "region"]
            elif problem == "circular":
                features[-2]["attributes"]["Is_circular"] = "false"
            else:
                features[-1]["attributes"]["product"] = "23S ribosomal RNA"
            with (
                patch.object(karlsen, "manifest", return_value=source),
                patch.object(
                    karlsen,
                    "checked_source",
                    side_effect=lambda root, identity, raw=raw: raw[identity],
                ),
                patch.object(karlsen, "gff_features", return_value=features),
                patch.dict(sys.modules, {"openpyxl": module}),
                self.assertRaises(ValueError),
            ):
                karlsen.prepare(self.root, self.root / "output")

    def test_cli_and_module_entrypoint(self):
        with (
            patch.object(karlsen, "prepare", return_value={"ok": True}),
            redirect_stdout(io.StringIO()) as output,
        ):
            karlsen.main([str(self.root), str(self.root / "out")])
        self.assertEqual(json.loads(output.getvalue()), {"ok": True})
        with (
            patch.object(sys, "argv", ["karlsen", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.karlsen", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
