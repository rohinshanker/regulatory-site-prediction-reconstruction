"""Hand-counted coordinate identities, independent of the runtime adapter."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "benchmarks/rbs"


class NativeFixtureTest(unittest.TestCase):
    def test_segments_points_and_strands(self):
        fixture = json.loads((ROOT / "native-coordinate-fixtures.json").read_text())
        complement = str.maketrans("ACGT", "TGCA")
        for row in fixture["records"]:
            with self.subTest(identity=row["id"]):
                self.assertEqual(row["tss_one_based"] - 1, row["tss_zero_based"])
                self.assertEqual(
                    row["cds_start_one_based"] - 1, row["cds_start_zero_based"]
                )
                genome = row["genome"]
                lower, upper = row["expected_start_interval"]
                codon = genome[lower:upper]
                if row["strand"] == "-":
                    codon = codon.translate(complement)[::-1]
                self.assertEqual(codon, "ATG")
                if row["leader_length_nt"] < 0:
                    self.assertIsNone(row["expected_sequence"])
                    self.assertEqual(row["expected_segments"], [])
                    continue
                parts = [genome[a:b] for a, b in row["expected_segments"]]
                if row["strand"] == "-":
                    parts = [part.translate(complement)[::-1] for part in parts]
                sequence = "".join(parts)
                self.assertEqual(sequence, row["expected_sequence"])
                start = row["expected_start"]
                self.assertEqual(
                    start, min(row["leader_length_nt"], row["upstream_limit_nt"])
                )
                self.assertEqual(sequence[start : start + 3], "ATG")
                self.assertEqual(len(sequence) - start, row["downstream_length_nt"])


if __name__ == "__main__":
    unittest.main()
