"""Decimal arithmetic for source equations, not a competing RBS engine."""

import json
import unittest
from decimal import Decimal
from pathlib import Path


class AnalyticFixtureTest(unittest.TestCase):
    def test_scalar_geometry_and_joint_optimization(self):
        path = (
            Path(__file__).resolve().parents[2]
            / "benchmarks/rbs/standby-analytic-fixtures.json"
        )
        data = json.loads(path.read_text())
        a, b, c = map(Decimal, data["polynomial_coefficients"])
        for row in data["raw_polynomial"]:
            x = Decimal(row["surface_area"])
            self.assertEqual(a * x * x + b * x + c, Decimal(row["energy"]))
        simple, capped, branched = data["geometry"]
        h = Decimal(simple["stem_pairs"]) + Decimal(simple["loop_bases"]) / 2
        self.assertEqual(h, Decimal(simple["height"]))
        self.assertEqual(
            15 + simple["distal"] + simple["proximal"] - h,
            Decimal(simple["surface_area"]),
        )
        h = min(Decimal(capped["raw_height"]), Decimal(15))
        self.assertEqual(h, Decimal(capped["height_for_area"]))
        self.assertEqual(
            15 + capped["distal"] + capped["proximal"] - h,
            Decimal(capped["surface_area"]),
        )
        hs = list(map(Decimal, branched["orientation_heights"]))
        self.assertEqual(sum(hs) / len(hs), Decimal(branched["expected_mean_height"]))
        for row in data["sliding"]:
            self.assertEqual(
                Decimal("0.2") * sum(map(Decimal, row["downstream_heights"])),
                Decimal(row["expected_energy"]),
            )
        landscape = data["synthetic_unfolding_landscape"]
        for row in landscape["candidates"]:
            k = row["opened_pairs"]
            x = Decimal(15 + (1 + k) + (1 + k) - (12 - k))
            self.assertEqual(x, Decimal(row["surface_area"]))
            distortion = a * x * x + b * x + c
            self.assertEqual(distortion, Decimal(row["distortion"]))
            self.assertEqual(
                distortion + Decimal(row["unfolding_cost"]), Decimal(row["total"])
            )
        selected = min(landscape["candidates"], key=lambda row: Decimal(row["total"]))
        self.assertEqual(
            selected["opened_pairs"], landscape["expected_selected_opened_pairs"]
        )


if __name__ == "__main__":
    unittest.main()
