"""Independent scalar invariants for the admitted conditional-model fixtures."""

import json
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "other-calculators"


class OtherCalculatorFixturesTest(unittest.TestCase):
    """Check declared algebra without importing a calculator or source model."""

    def test_ratios_and_limiting_cases(self):
        """Use independent floating arithmetic against the Decimal fixtures."""
        fixture = json.loads((ROOT / "riboswitch-scalar-fixtures.json").read_text())
        cases = {row["id"]: row for row in fixture["cases"]}
        self.assertEqual(len(cases), 5)
        for row in cases.values():
            beta = float(row["beta"])
            off = math.exp(-beta * float(row["score_off"]))
            on = math.exp(-beta * float(row["score_on"]))
            fraction = float(row["assumed_bound_fraction"])
            concentration_ratio = ((1 - fraction) * off + fraction * on) / off
            cost = float(row["switching_score"])
            actual = concentration_ratio
            if cost > 0:
                # Equivalent two-state expression, without copying fixture generation.
                actual = (math.exp(beta * cost) + concentration_ratio) / (
                    math.exp(beta * cost) + 1
                )
            for field, expected in (
                ("maximum_ratio", on / off),
                ("concentration_ratio", concentration_ratio),
                ("actual_ratio", actual),
            ):
                self.assertTrue(math.isclose(float(row[field]), expected, rel_tol=1e-13))
        self.assertEqual(float(cases["equal_states"]["actual_ratio"]), 1)
        self.assertEqual(float(cases["no_bound"]["actual_ratio"]), 1)
        self.assertEqual(
            cases["all_bound"]["actual_ratio"], cases["all_bound"]["maximum_ratio"]
        )
        self.assertLess(
            float(cases["metastable"]["actual_ratio"]),
            float(cases["quarter_bound"]["actual_ratio"]),
        )

    def test_component_scope(self):
        """The schema smoke cannot be mislabelled a complete prediction."""
        receipt = json.loads((ROOT / "stability-feature-smoke.json").read_text())
        self.assertEqual(receipt["results"]["steady_state"]["columns"], 5 * 92)
        self.assertEqual(receipt["results"]["decay"]["columns"], 5 * 92 + 5)
        self.assertIn("No prediction or training executed", receipt["not_established"])
