"""Independently enumerate supplied transcript geometry; never import a scorer."""

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "benchmarks/operon/organization-fixtures.json"


class OrganizationFixturesTest(unittest.TestCase):
    """Literal fixtures distinguish annotation, RNA boundaries and genomic paths."""

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_bytes())

    def test_frozen_identity(self):
        self.assertEqual(
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "cb9fd2eeb8a1927c5d8bba41bd8ed63fb9c5d44398e65571c8a350b3cbd14e10",
        )
        self.assertEqual(len(self.data["cases"]), 12)
        self.assertEqual(len({c["id"] for c in self.data["cases"]}), 12)

    def test_transcript_and_cds_geometry(self):
        for case in self.data["cases"]:
            with self.subTest(case=case["id"]):
                supplied, expected = case["input"], case["expected"]
                sequence = supplied["sequence"]
                left, right = supplied["transcript_range"]
                # Enumerated construct positions supply an independent point oracle.
                transcript = list(range(len(sequence)))[left:right]
                self.assertEqual(len(transcript), expected["transcript_length"])
                self.assertEqual(
                    "".join(sequence[p] for p in transcript),
                    expected["transcript_sequence"],
                )
                for index, cds in enumerate(supplied["cds"]):
                    start, end = cds["range"]
                    self.assertTrue(0 <= start < end <= len(sequence))
                    self.assertEqual(
                        start - left, expected["signed_start_offsets"][index]
                    )
                    codon = list(range(start, start + 3))
                    admitted = all(p in transcript for p in codon)
                    self.assertEqual(admitted, expected["eligible"][index])
                    self.assertEqual(
                        transcript.index(start) if admitted else None,
                        expected["rbs_start_positions"][index],
                    )
                    self.assertEqual(
                        end > right, expected["downstream_annotation_clipped"][index]
                    )
                    if admitted:
                        self.assertIsNone(expected["reasons"][index])
                    else:
                        self.assertIn(
                            expected["reasons"][index],
                            {
                                "start_before_transcript",
                                "start_after_transcript",
                                "start_codon_after_transcript",
                            },
                        )

    def test_genomic_points_and_segment_order(self):
        for case in self.data["cases"]:
            supplied, expected = case["input"], case["expected"]
            projection = supplied["projection"]
            if projection is None:
                self.assertIsNone(expected["transcript_genomic_segments"])
                self.assertEqual(
                    expected["start_codon_genomic_points"],
                    [None] * len(supplied["cds"]),
                )
                continue
            with self.subTest(case=case["id"]):
                size = projection["length"]
                # Walk one base at a time from the declared first genomic base.
                genome = list(range(size))
                origin = projection["origin"]
                if projection["sequence_strand"] == "+":
                    path = genome[origin:] + genome[:origin]
                else:
                    path = list(reversed(genome[: origin + 1])) + list(
                        reversed(genome[origin + 1 :])
                    )
                path = path[: len(supplied["sequence"])]
                left, right = supplied["transcript_range"]
                reconstructed = []
                for a, b in expected["transcript_genomic_segments"]:
                    segment = list(range(a, b))
                    if projection["sequence_strand"] == "-":
                        segment.reverse()
                    reconstructed.extend(segment)
                self.assertEqual(reconstructed, path[left:right])
                for cds, points in zip(
                    supplied["cds"], expected["start_codon_genomic_points"], strict=True
                ):
                    self.assertEqual(
                        path[cds["range"][0] : cds["range"][0] + 3], points
                    )

    def test_isoform_context_and_overlap_are_explicit(self):
        cases = {case["id"]: case for case in self.data["cases"]}
        first = cases["monocistronic"]
        alternative = cases["alternative_transcript"]
        self.assertEqual(first["input"]["sequence"], alternative["input"]["sequence"])
        self.assertEqual(first["input"]["cds"], alternative["input"]["cds"])
        self.assertNotEqual(
            first["expected"]["transcript_sequence"],
            alternative["expected"]["transcript_sequence"],
        )
        self.assertEqual(first["expected"]["rbs_start_positions"], [10])
        self.assertEqual(alternative["expected"]["rbs_start_positions"], [2])
        a, b = cases["overlapping_cistrons"]["input"]["cds"]
        self.assertEqual(b["range"][0] - a["range"][1], -5)

    def test_component_accounting_retains_every_entry(self):
        accounting = self.data["accounting"]
        for case in accounting["cases"]:
            with self.subTest(case=case["id"]):
                states = case["statuses"]
                self.assertEqual(len(states), len(accounting["roster"]))
                expected = case["expected"]
                self.assertEqual(expected["planned"], len(states))
                for field, status in [
                    ("completed", "ok"),
                    ("failed", "failed"),
                    ("not_run", "not_run"),
                    ("incompatible", "incompatible"),
                ]:
                    self.assertEqual(expected[field], states.count(status))
                self.assertEqual(
                    expected["all_components_complete"], all(s == "ok" for s in states)
                )
                self.assertEqual(
                    sum(
                        expected[k]
                        for k in ("completed", "failed", "not_run", "incompatible")
                    ),
                    len(states),
                )
