"""Source parity expectations use no runtime scoring implementation."""

import copy
import hashlib
import json
import unittest
from pathlib import Path

import jsonschema

from benchmarks.promoter import source_parity as p


class SourceParityPanelTest(unittest.TestCase):
    def test_frozen_panel_reproduction_schema_and_geometry(self):
        request_bytes, expected_bytes = p.build_panel()
        self.assertEqual(
            request_bytes, (p.ROOT / "source-parity-request.json").read_bytes()
        )
        self.assertEqual(
            expected_bytes, (p.ROOT / "source-parity-expectations.json").read_bytes()
        )
        request, expected = json.loads(request_bytes), json.loads(expected_bytes)
        schema = json.loads(
            Path("schemas/promoter-request-1.0.schema.json").read_bytes()
        )
        jsonschema.Draft202012Validator(schema).validate(request)
        self.assertEqual(
            expected["request_sha256"], hashlib.sha256(request_bytes).hexdigest()
        )
        self.assertEqual((expected["n_records"], expected["n_states"]), (22, 424))
        for record, row in zip(
            request["records"], expected["expectations"], strict=True
        ):
            projection = record["projection"]
            length = len(record["sequence"])
            direction = 1 if projection["sequence_strand"] == "+" else -1
            tss = row["tss"]["oriented_base"]
            self.assertEqual(
                row["state_count"],
                sum(
                    tss >= 37 + d + s and tss + 20 <= length
                    for d in range(6, 11)
                    for s in range(15, 21)
                ),
            )
            self.assertEqual(
                row["genomic"]["base"],
                (projection["origin"] + direction * row["tss"]["forward_base"])
                % projection["contig_length"],
            )
            selected = [state for state in row["states"] if state["selected"]]
            self.assertEqual(len(selected), int(row["state_count"] > 0))
            for state in row["states"]:
                for name, window in state["oriented_intervals"].items():
                    a, b = window
                    forward = (
                        list(range(a, b))
                        if row["strand"] == "+"
                        else [length - 1 - base for base in range(a, b)]
                    )
                    points = [
                        (projection["origin"] + direction * base)
                        % projection["contig_length"]
                        for base in forward
                    ]
                    reverse_genomic = row["genomic"]["strand"] == "-"
                    actual = [
                        base
                        for x, y in state["genomic_intervals"][name]
                        for base in (
                            range(y - 1, x - 1, -1) if reverse_genomic else range(x, y)
                        )
                    ]
                    self.assertEqual(actual, points, (row["id"], name))
            if row["id"].startswith("A200"):
                self.assertEqual(row["tie_count"], 5)
                self.assertEqual(
                    (
                        row["selected"]["discriminator_length"],
                        row["selected"]["spacer_length"],
                    ),
                    (6, 17),
                )
        for first, second in zip(
            expected["expectations"][::2], expected["expectations"][1::2], strict=True
        ):
            self.assertEqual(
                [s["terms"] for s in first["states"]],
                [s["terms"] for s in second["states"]],
            )

    def test_changed_frozen_expectations_rejected(self):
        fixtures = json.loads((p.ROOT / "reference-fixtures.json").read_bytes())
        parameters = json.loads((p.ROOT / "reference-parameters.json").read_bytes())
        broken = copy.deepcopy(fixtures)
        broken["cases"][0]["expected_states"][0]["terms"]["dG_total"] += 1
        with self.assertRaisesRegex(ValueError, "fixture/parameter"):
            p.build_records(broken, parameters)
