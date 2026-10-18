"""Hand-checked genome-grid coordinates and explicit label projection."""

import contextlib
import copy
import hashlib
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from benchmarks.promoter import native_inputs as n

COMPLEMENT = {"A": "T", "C": "G", "G": "C", "T": "A"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def revcomp(text):
    return "".join(COMPLEMENT[base] for base in reversed(text))


def pattern(length):
    return "".join("ACGT"[(i * 7 + i // 3) % 4] for i in range(length))


def genome(sequence, topology="linear"):
    return {
        "sequence": sequence,
        "sequence_sha256": sha(sequence),
        "accession": "synthetic",
        "assembly": "synthetic-v1",
        "annotation": "synthetic-annotation-v1",
        "topology": topology,
    }


def envelope(genomes, records=()):
    return {
        "schema_version": n.ENVELOPE_SCHEMA,
        "genomes": genomes,
        "records": list(records),
    }


def encoded(value):
    raw = json.dumps(value).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def build(genomes, width, cap, records=(), seed="test-seed"):
    raw, digest = encoded(envelope(genomes, records))
    loaded = n.load_envelope(raw, digest)
    return (
        loaded,
        digest,
        n.build_queries(loaded, digest, n.grid_settings(width, cap, seed)),
    )


def by_id(document):
    return {query["query_id"]: query for query in document["queries"]}


class JsonAndIdentityTest(unittest.TestCase):
    def test_canonical_and_hash_identity(self):
        self.assertEqual(n.canonical_bytes({"b": 1, "a": [2]}), b'{"a":[2],"b":1}\n')
        self.assertEqual(
            n.document_sha256({"a": 1}), hashlib.sha256(b'{"a":1}\n').hexdigest()
        )
        self.assertEqual(
            n.tool_sha256(),
            hashlib.sha256(Path(n.__file__).read_bytes()).hexdigest(),
        )
        with self.assertRaises(ValueError):
            n.canonical_bytes({"x": float("nan")})

    def test_strict_json(self):
        self.assertEqual(n.strict_json(b'{"a": 1.5, "b": [1]}'), {"a": 1.5, "b": [1]})
        for bad in (
            b'{"a": 1, "a": 2}',
            b'{"a": NaN}',
            b'{"a": Infinity}',
            b'{"a": -Infinity}',
            b'{"a": 1e999}',
        ):
            with self.assertRaises(ValueError, msg=bad):
                n.strict_json(bad)

    def test_read_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "x"
            path.write_bytes(b"12345")
            self.assertEqual(n.read_bounded(path, 5), b"12345")
            with self.assertRaisesRegex(ValueError, "exceeds 4 bytes"):
                n.read_bounded(path, 4)

    def test_checked_hash(self):
        good = "a" * 64
        self.assertEqual(n.checked_hash(good), good)
        for bad in (None, "A" * 64, "a" * 63, "g" * 64, 5):
            with self.assertRaises(ValueError):
                n.checked_hash(bad)


class EnvelopeTest(unittest.TestCase):
    def check_rejects(self, value, message):
        raw, digest = encoded(value)
        with self.assertRaisesRegex(ValueError, message):
            n.load_envelope(raw, digest)

    def test_valid_and_file_hash(self):
        value = envelope({"g": genome("ACGT")}, [{"id": "r"}])
        raw, digest = encoded(value)
        self.assertEqual(n.load_envelope(raw, digest), value)
        with self.assertRaisesRegex(ValueError, "file SHA-256 mismatch"):
            n.load_envelope(raw, "0" * 64)
        with self.assertRaisesRegex(ValueError, "lowercase 64-hex"):
            n.load_envelope(raw, "bad")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            bad = b'{"schema_version": "x", "schema_version": "y"}'
            n.load_envelope(bad, hashlib.sha256(bad).hexdigest())

    def test_schema_and_genomes(self):
        self.check_rejects([], "Envelope schema")
        self.check_rejects({"schema_version": "other"}, "Envelope schema")
        self.check_rejects(envelope([]), "1..64 genomes")
        self.check_rejects(envelope({}), "1..64 genomes")
        with mock.patch.object(n, "MAX_GENOMES", 1):
            self.check_rejects(
                envelope({"a": genome("A"), "b": genome("C")}), "1..1 genomes"
            )
        self.check_rejects(envelope({"": genome("A")}), "Incomplete genome")
        self.check_rejects(envelope({"g": "ACGT"}), "Incomplete genome")
        for field in n.GENOME_FIELDS:
            missing = genome("ACGT")
            del missing[field]
            self.check_rejects(envelope({"g": missing}), "Incomplete genome")
            empty = genome("ACGT")
            empty[field] = ""
            self.check_rejects(envelope({"g": empty}), "Incomplete genome")
        number = genome("ACGT")
        number["assembly"] = 3
        self.check_rejects(envelope({"g": number}), "Incomplete genome")
        for sequence in ("acgt", "ACGN", "ACGU"):
            self.check_rejects(envelope({"g": genome(sequence)}), "normalized ACGT")
        with mock.patch.object(n, "MAX_GENOME_LENGTH", 3):
            self.check_rejects(envelope({"g": genome("ACGT")}), "normalized ACGT")
        wrong = genome("ACGT")
        wrong["sequence_sha256"] = sha("ACGA")
        self.check_rejects(envelope({"g": wrong}), "sequence SHA-256 mismatch")
        self.check_rejects(envelope({"g": genome("ACGT", "plasmid")}), "topology")

    def test_records(self):
        genomes = {"g": genome("ACGT")}
        self.check_rejects(
            {"schema_version": n.ENVELOPE_SCHEMA, "genomes": genomes}, "records"
        )
        with mock.patch.object(n, "MAX_RECORDS", 1):
            self.check_rejects(
                envelope(genomes, [{"id": "a"}, {"id": "b"}]), "at most 1"
            )
        for records in (
            ["row"],
            [{}],
            [{"id": ""}],
            [{"id": 1}],
            [{"id": "a"}, {"id": "a"}],
        ):
            self.check_rejects(envelope(genomes, records), "record identity")


class SettingsTest(unittest.TestCase):
    def test_defaults_are_pinned(self):
        settings = n.grid_settings()
        self.assertEqual(
            settings,
            {
                "tile_width": 1000,
                "max_tiles_per_genome_strand": 128,
                "seed": "wave5-tan-grid-v1",
                "upstream_nt": 67,
                "downstream_nt": 19,
                "strands": ["+", "-"],
                "selection": (
                    "sha256(canonical [seed, genome_sha256, strand, tile]) ascending"
                ),
            },
        )
        self.assertEqual(
            n.document_sha256(settings),
            "cb40bb489a5e7ed5f63bf8b796bca773e1a6392a38ee9d6c67369aecc2b05e04",
        )

    def test_invalid(self):
        for width in (0, -1, True, 1.0, n.MAX_TILE_WIDTH + 1):
            with self.assertRaisesRegex(ValueError, "tile_width"):
                n.grid_settings(tile_width=width)
        for cap in (0, False, "1", n.MAX_TILES_PER_GENOME_STRAND + 1):
            with self.assertRaisesRegex(ValueError, "max_tiles"):
                n.grid_settings(max_tiles_per_genome_strand=cap)
        for seed in ("", 5, "x" * (n.MAX_SEED_LENGTH + 1)):
            with self.assertRaisesRegex(ValueError, "seed"):
                n.grid_settings(seed=seed)
        self.assertEqual(
            n.grid_settings(1, 1, "x" * n.MAX_SEED_LENGTH)["tile_width"], 1
        )

    def test_selection_key(self):
        material = f'["s","{"b" * 64}","-",3]\n'
        self.assertEqual(
            n.selection_key("s", "b" * 64, "-", 3),
            hashlib.sha256(material.encode()).hexdigest(),
        )


class CoordinateTest(unittest.TestCase):
    def test_padding(self):
        # Linear interior, then each clipped edge in transcript orientation.
        self.assertEqual(n.padding(1000, "linear", "+", 100, 200), (67, 19))
        self.assertEqual(n.padding(1000, "linear", "+", 0, 100), (0, 19))
        self.assertEqual(n.padding(1000, "linear", "+", 900, 990), (67, 10))
        self.assertEqual(n.padding(1000, "linear", "-", 900, 990), (10, 19))
        self.assertEqual(n.padding(1000, "linear", "-", 5, 100), (67, 5))
        # Circular: full padding, short allowance keeps downstream first, none.
        self.assertEqual(n.padding(1000, "circular", "+", 0, 100), (67, 19))
        self.assertEqual(n.padding(130, "circular", "-", 0, 100), (11, 19))
        self.assertEqual(n.padding(110, "circular", "+", 0, 100), (0, 10))
        self.assertEqual(n.padding(50, "circular", "+", 0, 50), (0, 0))

    def test_segments_and_mapping(self):
        plain = n.segments(100, "+", 10, 20)
        self.assertEqual(
            plain, [{"local": [0, 10], "genomic": [10, 20], "oriented": [10, 20]}]
        )
        wrapped = n.segments(100, "+", -3, 4)
        self.assertEqual(
            wrapped,
            [
                {"local": [0, 3], "genomic": [97, 100], "oriented": [97, 100]},
                {"local": [3, 7], "genomic": [0, 4], "oriented": [0, 4]},
            ],
        )
        self.assertEqual(
            [n.local_to_genomic("+", wrapped, i) for i in range(7)],
            [97, 98, 99, 0, 1, 2, 3],
        )
        minus = n.segments(100, "-", 96, 103)
        self.assertEqual(
            minus,
            [
                {"local": [0, 3], "genomic": [0, 3], "oriented": [97, 100]},
                {"local": [3, 7], "genomic": [96, 100], "oriented": [0, 4]},
            ],
        )
        self.assertEqual(
            [n.local_to_genomic("-", minus, i) for i in range(7)],
            [2, 1, 0, 99, 98, 97, 96],
        )
        # Oriented reverse-complement coordinate t is L - 1 - g.
        for i in range(7):
            g = n.local_to_genomic("-", minus, i)
            segment = next(s for s in minus if s["local"][0] <= i < s["local"][1])
            self.assertEqual(segment["oriented"][0] + i - segment["local"][0], 99 - g)
        with self.assertRaisesRegex(ValueError, "outside"):
            n.local_to_genomic("+", plain, 10)
        self.assertEqual(
            n.oriented_sequence("AACCGT", "-", [{"genomic": [1, 4]}]), "GGT"
        )


class QueryTest(unittest.TestCase):
    def test_plus_minus_linear_with_partial_terminal_tile(self):
        sequence = pattern(250)
        _, digest, document = build({"g": genome(sequence)}, 100, 128)
        queries = by_id(document)
        self.assertEqual(len(queries), 6)
        middle = queries["promoter-grid:g:plus:1"]
        self.assertEqual(middle["candidate_genomic_interval"], [100, 200])
        self.assertEqual(middle["candidate_local_range"], [67, 167])
        self.assertEqual(middle["sequence"], sequence[33:219])
        self.assertEqual(middle["sequence_sha256"], sha(sequence[33:219]))
        self.assertEqual(middle["context_status"], "complete")
        self.assertEqual(middle["full_state_support_local_range"], [67, 167])
        first = queries["promoter-grid:g:plus:0"]
        self.assertEqual(first["sequence"], sequence[0:119])
        self.assertEqual(first["candidate_local_range"], [0, 100])
        self.assertEqual(first["context_status"], "clipped")
        self.assertEqual(first["full_state_support_local_range"], [67, 100])
        self.assertEqual(first["n_candidates_full_state_support"], 33)
        self.assertEqual(
            first["context"],
            {
                "upstream_pad_nt": 0,
                "downstream_pad_nt": 19,
                "upstream_shortfall_nt": 67,
                "downstream_shortfall_nt": 0,
                "limit_reason": "linear_edge",
            },
        )
        last = queries["promoter-grid:g:plus:2"]
        self.assertEqual(last["candidate_genomic_interval"], [200, 250])
        self.assertEqual(last["sequence"], sequence[133:250])
        self.assertEqual(last["full_state_support_local_range"], [67, 98])
        minus_last = queries["promoter-grid:g:minus:2"]
        self.assertEqual(minus_last["sequence"], revcomp(sequence[181:250]))
        self.assertEqual(minus_last["candidate_local_range"], [0, 50])
        self.assertEqual(minus_last["context_status"], "no_full_state_support")
        self.assertEqual(minus_last["n_candidates_full_state_support"], 0)
        self.assertEqual(n.local_to_genomic("-", minus_last["segments"], 0), 249)
        minus_first = queries["promoter-grid:g:minus:0"]
        self.assertEqual(minus_first["sequence"], revcomp(sequence[0:167]))
        self.assertEqual(minus_first["candidate_local_range"], [67, 167])
        self.assertEqual(minus_first["full_state_support_local_range"], [67, 148])
        self.assertEqual(minus_first["context_status"], "clipped")
        self.assertEqual(minus_first["context"]["downstream_shortfall_nt"], 19)
        self.assertEqual(
            document["grid"]["g"]["+"],
            {
                "n_grid_tiles": 3,
                "n_selected_tiles": 3,
                "n_not_selected_tiles": 0,
                "n_grid_points": 250,
                "n_selected_points": 250,
                "n_not_selected_points": 0,
            },
        )
        self.assertEqual(document["source"]["file_sha256"], digest)
        self.assertEqual(
            document["context_status_counts"],
            {"clipped": 4, "complete": 1, "no_full_state_support": 1},
        )

    def test_circular_origin_wraps_once(self):
        sequence = pattern(250)
        _, _, document = build({"c": genome(sequence, "circular")}, 100, 128)
        queries = by_id(document)
        origin = queries["promoter-grid:c:plus:0"]
        self.assertEqual(origin["sequence"], sequence[183:] + sequence[:119])
        self.assertEqual(origin["context_status"], "complete")
        self.assertEqual(n.local_to_genomic("+", origin["segments"], 66), 249)
        self.assertEqual(n.local_to_genomic("+", origin["segments"], 67), 0)
        minus = queries["promoter-grid:c:minus:2"]
        self.assertEqual(minus["sequence"], revcomp(sequence[181:250] + sequence[:67]))
        self.assertEqual(n.local_to_genomic("-", minus["segments"], 66), 0)
        self.assertEqual(n.local_to_genomic("-", minus["segments"], 67), 249)
        self.assertEqual(
            [s["oriented"] for s in minus["segments"]], [[183, 250], [0, 69]]
        )

    def test_tiny_genomes_never_repeat_bases(self):
        sequence = pattern(50)
        _, _, document = build(
            {"c": genome(sequence, "circular"), "l": genome(sequence)}, 1000, 128
        )
        for query in document["queries"]:
            self.assertEqual(query["sequence_length"], 50)
            self.assertEqual(query["candidate_local_range"], [0, 50])
            self.assertEqual(query["context_status"], "no_full_state_support")
            self.assertIsNone(query["full_state_support_local_range"])
            reason = (
                "linear_edge"
                if query["genome_id"] == "l"
                else "circular_no_repeat_limit"
            )
            self.assertEqual(query["context"]["limit_reason"], reason)
        circular = by_id(document)["promoter-grid:c:minus:0"]
        self.assertEqual(circular["sequence"], revcomp(sequence))
        # A short circular allowance clips padding rather than duplicating bases.
        _, _, short = build({"c": genome(pattern(130), "circular")}, 100, 128)
        tile = by_id(short)["promoter-grid:c:plus:0"]
        self.assertEqual(tile["context"]["upstream_pad_nt"], 11)
        self.assertEqual(tile["context"]["downstream_pad_nt"], 19)
        self.assertEqual(tile["sequence_length"], 130)
        points = [n.local_to_genomic("+", tile["segments"], i) for i in range(130)]
        self.assertEqual(sorted(points), list(range(130)))

    def test_every_local_base_maps_to_reference(self):
        sequence = pattern(333)
        for topology in ("linear", "circular"):
            _, _, document = build({"g": genome(sequence, topology)}, 70, 128)
            covered = {"+": [], "-": []}
            for query in document["queries"]:
                for i, base in enumerate(query["sequence"]):
                    g = n.local_to_genomic(query["strand"], query["segments"], i)
                    expected = (
                        sequence[g]
                        if query["strand"] == "+"
                        else COMPLEMENT[sequence[g]]
                    )
                    self.assertEqual(base, expected)
                lower, upper = query["candidate_local_range"]
                covered[query["strand"]] += [
                    n.local_to_genomic(query["strand"], query["segments"], i)
                    for i in range(lower, upper)
                ]
            for points in covered.values():
                self.assertEqual(sorted(points), list(range(333)))

    def test_cap_order_and_determinism(self):
        sequence = pattern(1000)
        loaded, digest, document = build({"g": genome(sequence)}, 100, 3, seed="s1")
        keys = sorted(
            (
                hashlib.sha256(
                    f'["s1","{sha(sequence)}","+",{k}]\n'.encode()
                ).hexdigest(),
                k,
            )
            for k in range(10)
        )
        plus = [q for q in document["queries"] if q["strand"] == "+"]
        self.assertEqual([q["tile_ordinal"] for q in plus], [k for _, k in keys[:3]])
        self.assertEqual([q["selection_rank"] for q in plus], [0, 1, 2])
        self.assertEqual(document["grid"]["g"]["+"]["n_not_selected_tiles"], 7)
        self.assertEqual(document["grid"]["g"]["+"]["n_not_selected_points"], 700)
        self.assertEqual(document["grid_totals"]["n_grid_tiles"], 20)
        self.assertEqual(document["grid_totals"]["n_selected_tiles"], 6)
        again = n.build_queries(loaded, digest, n.grid_settings(100, 3, "s1"))
        self.assertEqual(n.canonical_bytes(again), n.canonical_bytes(document))
        other = n.build_queries(loaded, digest, n.grid_settings(100, 3, "s2"))
        self.assertNotEqual(other["settings_sha256"], document["settings_sha256"])
        self.assertEqual(
            document["queries_sha256"], n.document_sha256(document["queries"])
        )

    def test_queries_ignore_labels(self):
        sequence = pattern(400)
        records = [
            {
                "id": "tss-secret-1",
                "genome_id": "g",
                "strand": "+",
                "tss_zero_based": 150,
                "conditions": {"control": [987654, 123457]},
                "tss_type": "gTSS",
            },
            {
                "id": "tss-secret-2",
                "genome_id": "g",
                "strand": "-",
                "tss_zero_based": 9,
            },
        ]
        _, _, labelled = build({"g": genome(sequence)}, 100, 2, records)
        moved = copy.deepcopy(records)
        moved[0]["tss_zero_based"] = 350
        _, _, shifted = build({"g": genome(sequence)}, 100, 2, moved)
        _, _, empty = build({"g": genome(sequence)}, 100, 2)
        self.assertEqual(labelled["queries"], shifted["queries"])
        self.assertEqual(labelled["queries"], empty["queries"])
        self.assertNotIn("tss-secret", json.dumps(labelled))
        for query in labelled["queries"]:
            self.assertFalse({"tss", "label", "count", "conditions"} & set(query))
        with mock.patch.object(n, "project_labels", side_effect=AssertionError):
            build({"g": genome(sequence)}, 100, 2, records)
        # Envelope-level measurement metadata and extra genome fields stay out.
        value = envelope({"g": dict(genome(sequence), tss_counts=[987654])}, records)
        value["audit"] = {"n_s1": 987654}
        value["conditions_note"] = "counts"
        raw, digest = encoded(value)
        loaded = n.load_envelope(raw, digest)
        document = n.build_queries(loaded, digest, n.grid_settings(100, 2, "test-seed"))
        self.assertEqual(document["queries"], labelled["queries"])
        text = json.dumps(document)
        for forbidden in ("987654", "123457", "records", "audit", "conditions", "gTSS"):
            self.assertNotIn(forbidden, text)

    def test_resource_bounds(self):
        loaded, digest, _ = build({"g": genome(pattern(100))}, 10, 128)
        with mock.patch.object(n, "MAX_GRID_TILES", 19):
            with self.assertRaisesRegex(ValueError, "grid exceeds"):
                n.build_queries(loaded, digest, n.grid_settings(10, 128))
        with mock.patch.object(n, "MAX_QUERY_NT", 20 * 96 - 1):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                n.build_queries(loaded, digest, n.grid_settings(10, 128))
        with mock.patch.object(n, "MAX_QUERY_NT", 20 * 96):
            n.build_queries(loaded, digest, n.grid_settings(10, 128))

    def test_pinned_fixture_hash(self):
        _, _, document = build(
            {"c": genome(pattern(250), "circular"), "l": genome(pattern(120))}, 100, 2
        )
        self.assertEqual(
            document["queries_sha256"],
            "969329f8605c351568b7c027b67137c4c2a52ac0e648cba1c1c4f12928542100",
        )
        self.assertEqual(
            [q["query_id"] for q in document["queries"]],
            [
                "promoter-grid:c:plus:2",
                "promoter-grid:c:plus:1",
                "promoter-grid:c:minus:0",
                "promoter-grid:c:minus:2",
                "promoter-grid:l:plus:0",
                "promoter-grid:l:plus:1",
                "promoter-grid:l:minus:1",
                "promoter-grid:l:minus:0",
            ],
        )


class LabelProjectionTest(unittest.TestCase):
    def setUp(self):
        self.sequence = pattern(300)
        self.records = [
            {
                "id": "b-dark",
                "genome_id": "g",
                "strand": "+",
                "tss_zero_based": 120,
                "original_tss_one_based": 121,
                "tss_type": "gTSS",
                "conditions": {"dark": [3, 4]},
                "warnings": ["source_current_start_disagreement"],
                "mapping_status": "matched",
                "cds_start_zero_based": 150,
                "leader_length_nt": 30,
                "source_flags": [{"leaderless": True}],
                "translation_start_evidence": "annotation",
            },
            {
                "id": "a-control",
                "genome_id": "g",
                "strand": "+",
                "tss_zero_based": 120,
                "tss_type": "aTSS",
                "conditions": {"control": [1, 0]},
            },
            {"id": "minus", "genome_id": "g", "strand": "-", "tss_zero_based": 120},
            {
                "id": "unmeasured",
                "genome_id": "g",
                "strand": "+",
                "tss_zero_based": None,
            },
            {"id": "far", "genome_id": "g", "strand": "+", "tss_zero_based": 5},
        ]

    def project(self, records, cap=2):
        loaded, digest, document = build(
            {"g": genome(self.sequence)}, 100, cap, records
        )
        return document, n.project_labels(loaded, digest, document)

    def test_projection(self):
        document, labels = self.project(self.records)
        plus_tiles = {
            q["tile_ordinal"] for q in document["queries"] if q["strand"] == "+"
        }
        minus_tiles = {
            q["tile_ordinal"] for q in document["queries"] if q["strand"] == "-"
        }
        by_label = {label["label_id"]: label for label in labels["labels"]}
        self.assertEqual(list(by_label), ["tss:g:+:5", "tss:g:+:120", "tss:g:-:120"])
        shared = by_label["tss:g:+:120"]
        self.assertEqual(
            [row["id"] for row in shared["source_rows"]], ["a-control", "b-dark"]
        )
        self.assertEqual(shared["source_rows"][1]["conditions"], {"dark": [3, 4]})
        self.assertEqual(
            shared["source_rows"][1]["warnings"], ["source_current_start_disagreement"]
        )
        self.assertEqual(set(shared["source_rows"][0]), set(n.PRESERVED_ROW_FIELDS))
        text = json.dumps(labels)
        for forbidden in ("cds_start", "leader_length", "source_flags", "translation"):
            self.assertNotIn(forbidden, text)
        for label in labels["labels"]:
            tile = label["tss_zero_based"] // 100
            tiles = plus_tiles if label["strand"] == "+" else minus_tiles
            if tile in tiles:
                self.assertEqual(label["window_status"], "in_selected_query")
                query = by_id(document)[label["query_id"]]
                self.assertEqual(
                    n.local_to_genomic(
                        label["strand"], query["segments"], label["local_index"]
                    ),
                    label["tss_zero_based"],
                )
            else:
                self.assertEqual(label["window_status"], "out_of_window")
                self.assertIsNone(label["local_index"])
        rows = {row["record_id"]: row for row in labels["rows"]}
        self.assertEqual(rows["unmeasured"]["window_status"], "no_measured_tss")
        self.assertIsNone(rows["unmeasured"]["label_id"])
        self.assertEqual(rows["a-control"]["label_id"], rows["b-dark"]["label_id"])
        self.assertEqual(labels["counts"]["n_records"], 5)
        self.assertEqual(labels["counts"]["n_labels"], 3)
        self.assertEqual(
            labels["counts"]["n_labels_in_selected_query"]
            + labels["counts"]["n_labels_out_of_window"],
            3,
        )
        self.assertEqual(sum(labels["counts"]["row_window_status"].values()), 5)
        self.assertEqual(labels["query_document_sha256"], n.document_sha256(document))
        _, all_tiles = self.project(self.records, cap=128)
        self.assertEqual(all_tiles["counts"]["n_labels_out_of_window"], 0)

    def test_rejections(self):
        for change, message in (
            ({"genome_id": "missing"}, "known genome"),
            ({"strand": "."}, "known genome/strand"),
            ({"tss_zero_based": 300}, "outside"),
            ({"tss_zero_based": -1}, "outside"),
            ({"tss_zero_based": 1.0}, "outside"),
            ({"tss_zero_based": True}, "outside"),
            ({"original_tss_one_based": 120}, "disagreement"),
        ):
            records = [dict(self.records[0], **change)]
            with self.assertRaisesRegex(ValueError, message):
                self.project(records)
        loaded, digest, document = build({"g": genome(self.sequence)}, 100, 2)
        tampered = copy.deepcopy(document)
        tampered["queries"][0]["candidate_local_range"] = [0, 1]
        with self.assertRaisesRegex(ValueError, "not reproduced"):
            n.project_labels(loaded, digest, tampered)

    def test_overlapping_universe_rejected(self):
        _, _, document = build({"g": genome(self.sequence)}, 100, 2)
        twice = [document["queries"][0], dict(document["queries"][0], query_id="x")]
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            n.candidate_index(twice)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        value = envelope(
            {"g": genome(pattern(260))},
            [{"id": "r", "genome_id": "g", "strand": "+", "tss_zero_based": 130}],
        )
        self.raw, self.digest = encoded(value)
        (self.path / "env.json").write_bytes(self.raw)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = n.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def test_build_and_project(self):
        queries = self.path / "queries.json"
        code, out, _ = self.run_main(
            "build-queries",
            self.path / "env.json",
            queries,
            "--source-sha256",
            self.digest,
            "--tile-width",
            100,
            "--max-tiles-per-genome-strand",
            2,
            "--seed",
            "cli",
        )
        self.assertEqual(code, 0)
        raw = queries.read_bytes()
        summary = json.loads(out)
        self.assertEqual(summary["output_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(summary["n_queries"], 4)
        document = json.loads(raw)
        self.assertEqual(n.canonical_bytes(document), raw)
        labels = self.path / "labels.json"
        code, out, _ = self.run_main(
            "project-labels",
            self.path / "env.json",
            queries,
            labels,
            "--source-sha256",
            self.digest,
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["n_records"], 1)
        self.assertEqual(os.stat(labels).st_mode & 0o777, 0o600)
        code, _, err = self.run_main(
            "project-labels",
            self.path / "env.json",
            queries,
            labels,
            "--source-sha256",
            self.digest,
        )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_failures_are_nonzero(self):
        output = self.path / "q.json"
        for argv in (
            [
                "build-queries",
                self.path / "env.json",
                output,
                "--source-sha256",
                "0" * 64,
            ],
            [
                "build-queries",
                self.path / "missing.json",
                output,
                "--source-sha256",
                self.digest,
            ],
            [
                "build-queries",
                self.path / "env.json",
                output,
                "--source-sha256",
                self.digest,
                "--tile-width",
                0,
            ],
        ):
            code, out, err = self.run_main(*argv)
            self.assertEqual((code, out), (1, ""))
            self.assertTrue(err.startswith("error:"))
        self.assertFalse(output.exists())
        (self.path / "bad.json").write_text('{"a": 1, "a": 2}')
        code, _, err = self.run_main(
            "project-labels",
            self.path / "env.json",
            self.path / "bad.json",
            self.path / "labels.json",
            "--source-sha256",
            self.digest,
        )
        self.assertEqual(code, 1)
        self.assertIn("Duplicate JSON key", err)

    def test_module_entry_point(self):
        argv = [
            "native_inputs",
            "build-queries",
            str(self.path / "env.json"),
            str(self.path / "m.json"),
            "--source-sha256",
            "0" * 64,
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "benchmarks.promoter.native_inputs", run_name="__main__"
                )
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
