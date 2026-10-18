"""Independent literal maps, interval paths and candidate failure controls."""

import copy
import json
import sys
import unittest
from pathlib import Path

from benchmarks.recoding import edit_maps as m

FIXTURES = json.loads(
    Path("benchmarks/recoding/synthetic-edit-fixtures.json").read_bytes()
)["cases"]
IDENTITY = {
    name + "_sha256": char * 64
    for name, char in zip(
        ("model", "settings", "backend", "calibration"), "1234", strict=True
    )
}


def candidate(name, base, status="ok", score=1.0, strand="+"):
    return {
        "id": name,
        "base": base,
        "strand": strand,
        "status": status,
        "score": score,
    }


class EditMapTest(unittest.TestCase):
    def test_literal_maps_and_all_interval_paths(self):
        for fixture in FIXTURES:
            document = fixture["input"]
            mapping = m.build_map(document)
            self.assertEqual(
                mapping["current_to_recoded"], fixture["expected_current_to_recoded"]
            )
            self.assertEqual(
                mapping["recoded_to_current"], fixture["expected_recoded_to_current"]
            )
            for i, j in enumerate(mapping["current_to_recoded"]):
                if j is not None:
                    self.assertEqual(mapping["recoded_to_current"][j], i)
                    if not mapping["current_declared_edited"][i]:
                        self.assertEqual(
                            document["current"]["sequence"][i],
                            document["recoded"]["sequence"][j],
                        )
            for side in ("current", "recoded"):
                values = mapping[
                    "current_to_recoded" if side == "current" else "recoded_to_current"
                ]
                target_length = len(
                    document["recoded" if side == "current" else "current"]["sequence"]
                )
                circular = mapping["topology"] == "circular"
                for start in range(len(values)):
                    for count in range(
                        (len(values) if circular else len(values) - start) + 1
                    ):
                        for strand in ("+", "-"):
                            expected = [
                                values[(start + i) % len(values)] for i in range(count)
                            ]
                            if strand == "-":
                                expected.reverse()
                            result = m.map_interval(
                                mapping, side, start, start + count, strand
                            )
                            self.assertEqual(result["mapped_bases"], expected)
                            flattened = [
                                i
                                for a, b in result["mapped_runs"]
                                for i in (
                                    range(a, b)
                                    if strand == "+"
                                    else range(b - 1, a - 1, -1)
                                )
                            ]
                            self.assertEqual(
                                flattened, [x for x in expected if x is not None]
                            )
                            self.assertEqual(
                                result["unmatched_bases"], expected.count(None)
                            )
                            self.assertEqual(
                                result["complete_base_mapping"], None not in expected
                            )
                            step = 1 if strand == "+" else -1
                            contiguous = None not in expected and all(
                                (b - a == step)
                                or (
                                    circular
                                    and (b - a) % target_length == step % target_length
                                )
                                for a, b in zip(expected, expected[1:], strict=False)
                            )
                            self.assertEqual(
                                result["contiguous_target_path"], contiguous
                            )
        identity = m.build_map(FIXTURES[0]["input"])
        self.assertEqual(
            m.map_interval(identity, "current", 4, 4, "+")["mapped_runs"], []
        )

    def test_validation_rejections(self):
        base = FIXTURES[0]["input"]
        for field, value in (
            ("schema_version", "wrong"),
            ("pair_id", ""),
            ("pair_id", 7),
            ("pair_id", "x" * 129),
            ("topology", "unknown"),
            ("edits", {}),
            ("edits", [{}] * (m.MAX_BASES + 1)),
            ("extra", 1),
        ):
            broken = dict(base, **{field: value})
            with (
                self.subTest(field=field, value=str(value)[:50]),
                self.assertRaises(ValueError),
            ):
                m.build_map(broken)
        for value in (None, "", "acgt", "ACGU", "A" * (m.MAX_BASES + 1)):
            broken = copy.deepcopy(base)
            broken["current"]["sequence"] = value
            with self.assertRaises(ValueError):
                m.build_map(broken)
        for edit in (
            {"id": "e", "start": True, "end": 1, "replacement": "A"},
            {"id": "e", "start": -1, "end": 1, "replacement": "A"},
            {"id": "e", "start": 3, "end": 2, "replacement": "A"},
            {"id": "e", "start": 0, "end": 0, "replacement": ""},
            {"id": "e", "start": 0, "end": 1, "replacement": "T"},
        ):
            with self.assertRaises(ValueError):
                m.build_map(dict(base, edits=[edit]))
        e = {"id": "e", "start": 0, "end": 2, "replacement": "AC"}
        for other in (dict(e), dict(e, id="e2"), dict(e, id="e2", start=1)):
            with self.assertRaises(ValueError):
                m.build_map(dict(base, edits=[e, other]))
        mapping = m.build_map(base)
        for args in (
            ("bad", 0, 1, "+"),
            ("current", 0, 1, "?"),
            ("current", 0, 5, "+"),
            ("current", True, 2, "+"),
        ):
            with self.assertRaises(ValueError):
                m.map_interval(mapping, *args)

    def test_projection_exhaustive_and_rejections(self):
        for size in range(1, 11):
            for origin in range(size):
                for sequence_strand in ("+", "-"):
                    step = 1 if sequence_strand == "+" else -1
                    for length in range(1, size + 1):
                        crossing = not 0 <= origin + step * (length - 1) < size
                        projection = {
                            "contig": "s",
                            "contig_length": size,
                            "origin": origin,
                            "sequence_strand": sequence_strand,
                            "topology": "circular",
                            "origin_crossing": crossing,
                        }
                        for local in range(length):
                            for strand in ("+", "-"):
                                result = m.project_base(
                                    projection, local, strand, length
                                )
                                self.assertEqual(
                                    result["base"],
                                    list(range(size))[((origin + step * local) % size)],
                                )
                                self.assertEqual(
                                    result["strand"],
                                    "+" if strand == sequence_strand else "-",
                                )
        valid = {
            "contig": "s",
            "contig_length": 10,
            "origin": 0,
            "sequence_strand": "+",
            "topology": "linear",
            "origin_crossing": False,
        }
        self.assertEqual(m.project_base(valid, 2, "-", 3)["base"], 2)
        for key, value in (
            ("sequence_strand", "x"),
            ("topology", "x"),
            ("origin_crossing", None),
            ("origin_crossing", True),
            ("origin", 11),
            ("contig_length", 0),
        ):
            with self.assertRaises(ValueError):
                m.project_base(dict(valid, **{key: value}), 1, "+", 3)
        with self.assertRaises(ValueError):
            m.project_base(valid, 0, "?", 1)
        with self.assertRaises(ValueError):
            m.project_base(dict(valid, origin=9, origin_crossing=True), 0, "+", 3)


class CandidatePairTest(unittest.TestCase):
    def setUp(self):
        self.mapping = m.build_map(FIXTURES[2]["input"])

    def pair(self, current, recoded, after_identity=IDENTITY):
        return m.pair_candidates(
            self.mapping, current, recoded, IDENTITY, after_identity
        )

    def test_complete_rosters_controls_and_unmatched(self):
        current = [
            candidate("c0", 0),
            candidate("c2", 2),
            candidate("cm", 3, strand="-"),
        ]
        recoded = [
            candidate("r0", 0, score=2),
            candidate("r2", 2),
            candidate("rm", 5, strand="-"),
        ]
        result = self.pair(current, recoded)
        self.assertEqual(
            (
                result["matched_pairs"],
                result["unmatched_current"],
                result["unmatched_recoded"],
            ),
            (2, 1, 1),
        )
        self.assertEqual(
            [r["reason"] for r in result["results"]],
            [None, "mapped_anchor_absent", None, "inserted_coordinate"],
        )
        self.assertEqual(
            [r["delta"] for r in result["results"]], [1.0, None, 0.0, None]
        )
        self.assertFalse(result["biological_gain_loss_evaluated"])
        self.assertEqual(self.pair([], [])["results"], [])
        self.mapping = m.build_map(FIXTURES[3]["input"])
        result = self.pair([candidate("deleted", 2)], [candidate("unpaired", 0)])
        self.assertEqual(
            [r["reason"] for r in result["results"]],
            ["deleted_coordinate", "mapped_anchor_absent"],
        )
        self.mapping = m.build_map(FIXTURES[0]["input"])
        row = candidate("same", 1, score=0.0)
        self.assertEqual(self.pair([row], [row])["results"][0]["delta"], 0.0)
        for field in IDENTITY:
            incompatible = dict(IDENTITY, **{field: "f" * 64})
            result = self.pair([row], [row], incompatible)["results"][0]
            self.assertEqual(
                (result["status"], result["delta"]), ("incomparable", None)
            )

    def test_failure_and_numeric_propagation(self):
        for side in ("current", "recoded"):
            for status in ("failed", "unsupported", "not_run", "no_candidate"):
                current, after = candidate("c", 0), candidate("r", 0)
                row = current if side == "current" else after
                row.update(status=status, score=None)
                result = self.pair([current], [after])["results"][0]
                self.assertEqual(
                    (result["status"], result["delta"]), ("incomplete", None)
                )
        result = self.pair(
            [candidate("c", 0, score=-sys.float_info.max)],
            [candidate("r", 0, score=sys.float_info.max)],
        )["results"][0]
        self.assertEqual(result["reason"], "nonfinite_delta")
        for value in (True, None, float("nan"), float("inf"), 10**400):
            with self.assertRaises(ValueError):
                self.pair([candidate("c", 0, score=value)], [])
        with self.assertRaises(ValueError):
            self.pair([candidate("c", 0, status="failed", score=0)], [])

    def test_roster_and_identity_rejections(self):
        for rows in (
            None,
            [{}] * (2 * m.MAX_BASES + 1),
            [candidate("c", 0, status="bad")],
            [candidate("c", 0, strand="?")],
            [candidate("c", 0), candidate("c", 1)],
            [candidate("c", 0), candidate("other", 0)],
        ):
            with self.assertRaises(ValueError):
                self.pair(rows, [])
        for value in (
            {},
            dict(IDENTITY, model_sha256="x"),
            dict(IDENTITY, model_sha256="G" * 64),
            dict(IDENTITY, model_sha256=None),
        ):
            with self.assertRaises(ValueError):
                self.pair([], [], value)
