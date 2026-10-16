"""Verify independent fixture arithmetic and provenance, without a scoring engine."""

import hashlib
import json
import math
import unittest
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "benchmarks/rbs"


class EvidenceTest(unittest.TestCase):
    def test_high_precision_source_equations(self):
        fixtures = json.loads((ROOT / "scalar-fixtures.json").read_text())
        with localcontext() as context:
            context.prec = 50
            for row in fixtures["spacing"]:
                spacing = Decimal(row["aligned_spacing"])
                if spacing < 5:
                    value = (
                        Decimal("12.2")
                        / (1 + (Decimal("2.5") * (spacing - 3)).exp()) ** 3
                    )
                else:
                    value = Decimal("0.048") * (spacing - 5) ** 2 + Decimal("0.24") * (
                        spacing - 5
                    )
                self.assertTrue(
                    math.isclose(
                        float(value),
                        row["expected_kcal_mol"],
                        abs_tol=1e-10,
                        rel_tol=1e-12,
                    )
                )
            for row in fixtures["rates"]:
                energy = Decimal(row["total_energy_kcal_mol"])
                for label, exponent in [
                    ("salis_v1_expected", -energy / Decimal("2.222")),
                    ("idog_expected", -energy * Decimal("0.45")),
                ]:
                    self.assertTrue(
                        math.isclose(
                            float(2500 * exponent.exp()), row[label], rel_tol=1e-12
                        )
                    )
            for row in fixtures["assembly"]:
                total = sum(
                    Decimal(str(row[key])) * sign
                    for key, sign in [
                        ("complex_with_spacing", 1),
                        ("start", 1),
                        ("unbound_mrna", -1),
                        ("standby_upstream_signed", -1),
                    ]
                )
                self.assertEqual(total, Decimal(str(row["expected_total"])))

    def test_backend_table_manifest_identity(self):
        fixture = json.loads((ROOT / "rnastructure-smoke-fixtures.json").read_text())
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "rnastructure-tables.json").read_bytes()
            ).hexdigest(),
            fixture["table_manifest_sha256"],
        )
        self.assertEqual(
            fixture["source_archive_sha256"],
            "1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3",
        )

    def test_live_accounting_and_frozen_input_identity(self):
        panel = (ROOT / "live-diagnostic-panel.json").read_bytes()
        record = json.loads((ROOT / "live-acquisition.json").read_text())
        self.assertEqual(hashlib.sha256(panel).hexdigest(), record["panel_sha256"])
        self.assertEqual(
            record["n_submitted"] + record["n_unsubmitted"], record["n_planned"]
        )
        self.assertEqual(record["n_finished_exported"], len(record["jobs"]))
        inputs = {r["id"]: r for r in json.loads(panel)["records"]}
        for row in record["jobs"]:
            self.assertEqual(row["input_sha256"], inputs[row["id"]]["sequence_sha256"])
            self.assertTrue(row["exports"])
            self.assertNotIn("job_id", row)


if __name__ == "__main__":
    unittest.main()
