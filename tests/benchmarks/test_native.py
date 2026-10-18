"""Independent source parser and boundary fixtures, without scoring imports."""

import gzip
import io
import json
import runpy
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.rbs import native
from benchmarks.rbs.datasets import digest

REPLICON = "NZ_CP006471.1"
DNA = "TTACCGGATGAAATTTCCGG"


def gff(
    kind="CDS", lower=8, upper=13, strand="+", attrs="locus_tag=g", replicon=REPLICON
):
    return "\t".join(
        [replicon, "test", kind, str(lower), str(upper), ".", strand, ".", attrs]
    )


def source_row(kind="gTSS", strand="+", position=4, distance=4, locus="g"):
    row = [None] * 30
    row[:5] = [f"{kind}{strand}{position}", "CP006471", kind, strand, position]
    row[8:11] = ["C", distance, locus]
    row[20:28] = list(range(8))
    return row


def tables(rows=None):
    return [
        [None] * 30,
        native.S1_HEADERS + [f"quality{i}" for i in range(25)],
        *(rows or [source_row()]),
    ], [[None] * 21, native.S2_HEADERS + [None] * 16]


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sequences = {REPLICON: DNA}
        self.features = native.gff_features(gff(), self.sequences)

    def test_real_manifest_has_unique_pins(self):
        source = native.manifest()
        self.assertEqual(
            len({row["id"] for row in source["sources"]}), len(source["sources"])
        )
        self.assertTrue(all(len(row["sha256"]) == 64 for row in source["sources"]))

    def test_fetch_verifies_new_and_existing_bytes(self):
        source = {
            "id": "test",
            "name": "test.bin",
            "bytes": 3,
            "sha256": digest(b"abc"),
            "url": "https://example.invalid/test",
        }
        response = io.BytesIO(b"abc")
        with (
            patch.object(native, "manifest", return_value={"sources": [source]}),
            patch.object(native, "urlopen", return_value=response) as opener,
        ):
            self.assertEqual(native.fetch_sources(self.root), {"n_verified": 1})
            self.assertEqual(native.fetch_sources(self.root), {"n_verified": 1})
            opener.assert_called_once_with(source["url"], timeout=30)
            self.assertEqual(native.checked_source(self.root, "test"), b"abc")
            for bad in (b"abd", b"ab"):
                (self.root / "test.bin").write_bytes(bad)
                with self.assertRaisesRegex(ValueError, "Native source identity"):
                    native.checked_source(self.root, "test")
                (self.root / "test.bin").unlink()
                with patch.object(native, "urlopen", return_value=io.BytesIO(bad)):
                    with self.assertRaisesRegex(
                        ValueError, "Downloaded source identity"
                    ):
                        native.fetch_sources(self.root)
                self.assertFalse((self.root / "test.bin").exists())

    def test_fetch_keeps_raw_files_outside_repository(self):
        repository = Path(native.__file__).resolve().parents[2]
        for path in (repository, repository / "raw"):
            with self.assertRaisesRegex(ValueError, "outside"):
                native.fetch_sources(path)

    def test_unordered_metadata_canonicalization_retains_raw_receipt(self):
        canonical = b"id\tvalue\na\t1\nb\t2\n"
        raw = b"id\tvalue\nb\t2\na\t1\n"
        source = {
            "id": "metadata",
            "name": "metadata.tsv",
            "url": "https://example.invalid/metadata",
            "bytes": len(canonical),
            "sha256": digest(canonical),
            "canonicalization": "tsv_header_sort_data_lines_v1",
        }
        with (
            patch.object(native, "manifest", return_value={"sources": [source]}),
            patch.object(native, "urlopen", return_value=io.BytesIO(raw)),
        ):
            self.assertEqual(native.fetch_sources(self.root), {"n_verified": 1})
            self.assertEqual((self.root / "metadata.tsv").read_bytes(), raw)
            self.assertEqual(native.checked_source(self.root, "metadata"), canonical)
            receipt = json.loads(
                (self.root / "metadata.tsv.retrieval.json").read_text()
            )
            self.assertEqual(receipt["raw_sha256"], digest(raw))
            self.assertEqual(receipt["canonical_sha256"], digest(canonical))
            self.assertEqual(native.fetch_sources(self.root), {"n_verified": 1})
        for invalid in (b"", b"header", b"\na\n", b"id\tvalue\na\n", b"id\tvalue\n\n"):
            with self.assertRaisesRegex(ValueError, "TSV"):
                native.canonical_source(invalid, source)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            native.canonical_source(raw, {"canonicalization": "other"})

    def test_fasta_valid_and_invalid(self):
        self.assertEqual(
            native.fasta_records("\n>x description\nacgt\nTT\n>y\nAAA\n"),
            {"x": "ACGTTT", "y": "AAA"},
        )
        for text in ("", ">x\n", ">\nACG", ">x\nACG\n>x\nA", "ACG", ">x\nACN"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                native.fasta_records(text)

    def test_gff_coordinates_reverse_and_escaped_attributes(self):
        text = (
            "##gff-version 3\n\n"
            + gff("exon")
            + "\n"
            + gff(strand="-", attrs="locus_tag=g;product=hello%20world;")
        )
        rows = native.gff_features(text, self.sequences)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["interval"], [7, 13])
        self.assertEqual(rows[0]["segments"], [[7, 13]])
        self.assertEqual(rows[0]["start_zero_based"], 12)
        self.assertEqual(rows[0]["attributes"]["product"], "hello world")

    def test_gff_circular_origin_is_explicit(self):
        region = gff("region", 1, 20, attrs="Is_circular=true")
        for strand, expected, start in (
            ("+", [[17, 20], [0, 4]], 17),
            ("-", [[0, 4], [17, 20]], 3),
        ):
            # Region deliberately follows feature: input order must not infer topology.
            rows = native.gff_features(
                gff(lower=18, upper=24, strand=strand) + "\n" + region, self.sequences
            )
            self.assertEqual(rows[0]["segments"], expected)
            self.assertEqual(rows[0]["start_zero_based"], start)
            self.assertEqual(rows[0]["interval"], [17, 24])
        for text in (
            gff(lower=18, upper=24),
            gff("region", 1, 24, attrs="Is_circular=true"),
        ):
            with self.assertRaisesRegex(ValueError, "circular|interval"):
                native.gff_features(text, self.sequences)

    def test_gff_rejects_invalid_coordinates_and_schema(self):
        invalid = [
            "not nine columns",
            gff(replicon="missing"),
            gff(strand="."),
            gff(lower=0),
            gff(lower=21, upper=22),
            gff(lower=9, upper=8),
            gff(lower=18, upper=40),
        ]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                native.gff_features(text, self.sequences)

    def test_rrna_tail_strands_and_short_features(self):
        attrs = "locus_tag=rrna;product=16S%20ribosomal%20RNA"
        for strand, expected in (("+", "AAAUUUCCG"), ("-", "AUCCGGUAA")):
            features = native.gff_features(
                gff("rRNA", 1, 19, strand, attrs), self.sequences
            )
            evidence = native.rrna_tail_evidence(self.sequences, features)
            self.assertEqual(evidence[0]["anti_sd"], expected)
            self.assertEqual(len(evidence[0]["rrna_sha256"]), 64)
        other = native.gff_features(
            gff("rRNA", attrs="product=23S ribosomal RNA"), self.sequences
        )
        self.assertEqual(
            native.rrna_tail_evidence(self.sequences, self.features + other), []
        )
        short = native.gff_features(gff("rRNA", 1, 8, attrs=attrs), self.sequences)
        with self.assertRaisesRegex(ValueError, "shorter"):
            native.rrna_tail_evidence(self.sequences, short)

    def test_tan_preserves_all_source_types_conditions_and_proposals(self):
        s1, s2 = tables(
            [source_row(kind=kind) for kind in ("gTSS", "aTSS", "iTSS", "nTSS")]
        )
        s2.extend(
            [
                ["gTSS", 4, "g", "product", 4, "yes", "no", 80, 5, 10] + [None] * 11,
                [None] * 21,
                ["footnote"] + [None] * 20,
            ]
        )
        records, audit = native.tan_contexts(s1, s2, self.sequences, self.features)
        self.assertEqual(audit["n_s1"], 4)
        self.assertEqual(audit["n_s2_proposals"], 1)
        self.assertEqual(audit["s2_notes"], [{"source_row": 5, "text": "footnote"}])
        self.assertEqual(records[0]["source_flags"][0]["homology_hit_count"], 10)
        self.assertEqual(records[0]["conditions"]["control"], [0, 1])
        self.assertEqual(records[0]["cds_start_zero_based"], 7)
        self.assertEqual(records[0]["leader_length_nt"], 4)
        self.assertEqual(records[0]["current_cds_segments"], [[7, 13]])
        self.assertEqual(records[0]["warnings"], [])
        self.assertEqual(audit["mapping_status"], {"matched": 1, "non_gene_tss": 3})

    def test_tan_reverse_origin_leaderless_and_internal_are_distinct(self):
        scenarios = [
            ("-", 17, 4, 8, 13, 4, False, "matched"),
            ("+", 19, 9, 8, 13, 9, True, "matched"),
            ("+", 8, 0, 8, 13, 0, False, "matched"),
            ("+", 9, 0, 8, 13, -1, False, "tss_inside_current_cds"),
        ]
        for (
            strand,
            position,
            distance,
            lower,
            upper,
            leader,
            origin,
            status,
        ) in scenarios:
            row = source_row(strand=strand, position=position, distance=distance)
            row[8] = (
                DNA[position - 1].translate(native.COMPLEMENT)
                if strand == "-"
                else DNA[position - 1]
            )
            s1, s2 = tables([row])
            features = native.gff_features(
                gff(lower=lower, upper=upper, strand=strand), self.sequences
            )
            records, audit = native.tan_contexts(s1, s2, self.sequences, features)
            self.assertEqual(records[0]["leader_length_nt"], leader)
            self.assertEqual(records[0]["origin_crossing"], origin)
            self.assertEqual(records[0]["mapping_status"], status)
            self.assertEqual(audit["n_tss_nucleotide_disagreements"], 0)
            if leader == 0:
                self.assertIn("leaderless_current_annotation", records[0]["warnings"])
            if leader < 0:
                self.assertIn(
                    "source_current_start_disagreement", records[0]["warnings"]
                )

    def test_tan_mapping_failures_are_retained(self):
        s1, s2 = tables()
        wrong_strand = deepcopy(self.features)
        wrong_strand[0]["strand"] = "-"
        wrong_replicon = deepcopy(self.features)
        wrong_replicon[0]["replicon"] = "other"
        pseudogene = deepcopy(self.features)
        pseudogene[0]["attributes"]["pseudo"] = "true"
        for features, status in [
            ([], "source_locus_absent_from_current_cds"),
            (self.features * 2, "multiple_current_cds_segments_or_models"),
            (wrong_strand, "current_replicon_or_strand_disagreement"),
            (wrong_replicon, "current_replicon_or_strand_disagreement"),
            (pseudogene, "current_pseudogene"),
        ]:
            records, _ = native.tan_contexts(s1, s2, self.sequences, features)
            self.assertEqual(records[0]["mapping_status"], status)
        no_locus = deepcopy(self.features)
        no_locus[0]["attributes"] = {}
        s1[2][10] = None
        records, _ = native.tan_contexts(s1, s2, self.sequences, no_locus)
        self.assertEqual(
            records[0]["mapping_status"], "source_locus_absent_from_current_cds"
        )

    def test_tan_nucleotide_disagreement_is_not_repaired(self):
        s1, s2 = tables()
        s1[2][8] = "A"
        records, audit = native.tan_contexts(s1, s2, self.sequences, self.features)
        self.assertEqual(audit["n_tss_nucleotide_disagreements"], 1)
        self.assertEqual(records[0]["source_tss_nucleotide"], "A")
        self.assertEqual(records[0]["reference_tss_nucleotide"], "C")
        self.assertIn(
            "source_tss_nucleotide_disagrees_with_reference", records[0]["warnings"]
        )

    def test_tan_rejects_bad_schema_coordinates_and_duplicate_identity(self):
        for which in (0, 1):
            sheets = list(tables())
            sheets[which][1][0] = "changed"
            with self.assertRaisesRegex(ValueError, "schema"):
                native.tan_contexts(*sheets, self.sequences, self.features)
        changes = [
            (0, "mismatch"),
            (1, "unknown"),
            (2, "TIS"),
            (3, "."),
            (4, True),
            (4, 0),
            (4, 21),
            (9, -1),
            (9, True),
        ]
        for index, value in changes:
            s1, s2 = tables()
            s1[2][index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                native.tan_contexts(s1, s2, self.sequences, self.features)
        s1, s2 = tables([source_row(), source_row()])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            native.tan_contexts(s1, s2, self.sequences, self.features)

    def prepare_environment(self):
        s1, s2 = tables()
        sheets = {"Table S1": Mock(), "Table S2": Mock()}
        sheets["Table S1"].iter_rows.return_value = s1
        sheets["Table S2"].iter_rows.return_value = s2
        workbook = Mock()
        workbook.__getitem__ = Mock(side_effect=sheets.__getitem__)
        module = types.SimpleNamespace(load_workbook=Mock(return_value=workbook))
        annotation = "\n".join(
            [
                gff(),
                gff("region", 1, 20, attrs="Is_circular=true"),
                gff("rRNA", 1, 19, attrs="locus_tag=r;product=16S ribosomal RNA"),
            ]
        )
        raw = {
            "utex-genomic.fna.gz": gzip.compress(f">{REPLICON}\n{DNA}\n".encode()),
            "utex-genomic.gff.gz": gzip.compress(annotation.encode()),
            "tan2018.xlsx": b"workbook",
        }
        source = {
            "utex_identity": {
                "replicons": {REPLICON: 20},
                "assembly": "test.1",
                "annotation": "test annotation",
            }
        }
        return raw, source, module, workbook

    def test_prepare_tan_envelope_and_identity(self):
        raw, source, module, workbook = self.prepare_environment()
        target = self.root / "contexts.json"
        with (
            patch.object(native, "manifest", return_value=source),
            patch.object(
                native,
                "checked_source",
                side_effect=lambda root, identity: raw[identity],
            ),
            patch.dict(sys.modules, {"openpyxl": module}),
        ):
            audit = native.prepare_tan(self.root, target)
        data = json.loads(target.read_text())
        self.assertEqual(audit["n_s1"], 1)
        self.assertEqual(data["records"][0]["source_file_sha256"], digest(b"workbook"))
        self.assertEqual(data["records"][0]["anti_sd"], "AAAUUUCCG")
        self.assertEqual(data["genomes"][REPLICON]["sequence_sha256"], digest(DNA))
        workbook.close.assert_called_once()

    def test_prepare_rejects_assembly_tail_and_topology_conflicts(self):
        for problem in ("length", "tail", "missing_region", "linear"):
            raw, source, module, _ = self.prepare_environment()
            if problem == "length":
                source["utex_identity"]["replicons"][REPLICON] = 21
            else:
                text = gzip.decompress(raw["utex-genomic.gff.gz"]).decode()
                if problem == "tail":
                    text = text.replace("16S ribosomal RNA", "23S ribosomal RNA")
                elif problem == "missing_region":
                    text = "\n".join(
                        line for line in text.splitlines() if "\tregion\t" not in line
                    )
                else:
                    text = text.replace("Is_circular=true", "Is_circular=false")
                raw["utex-genomic.gff.gz"] = gzip.compress(text.encode())
            with (
                patch.object(native, "manifest", return_value=source),
                patch.object(
                    native,
                    "checked_source",
                    side_effect=lambda root, identity, raw=raw: raw[identity],
                ),
                patch.dict(sys.modules, {"openpyxl": module}),
                self.assertRaises(ValueError),
            ):
                native.prepare_tan(self.root, self.root / "bad.json")
            self.assertFalse((self.root / "bad.json").exists())

    def test_cli_and_module_entrypoint(self):
        for argv, operation in (
            (["fetch", str(self.root)], "fetch_sources"),
            (["prepare-tan", str(self.root), str(self.root / "out")], "prepare_tan"),
        ):
            with (
                patch.object(native, operation, return_value={"ok": True}) as call,
                redirect_stdout(io.StringIO()) as output,
            ):
                native.main(argv)
            self.assertEqual(json.loads(output.getvalue()), {"ok": True})
            call.assert_called_once()
        with (
            patch.object(sys, "argv", ["native", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.native", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
