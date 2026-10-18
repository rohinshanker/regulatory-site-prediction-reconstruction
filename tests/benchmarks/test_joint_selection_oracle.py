"""Independent exact-decimal finite-state oracle, no runtime model imports."""

import json
import unittest
from decimal import Decimal as D
from pathlib import Path


class JointOracleTest(unittest.TestCase):
    def test_finite_states_and_coordinates(self):
        path = (
            Path(__file__).parents[2] / "benchmarks/rbs/joint-selection-fixtures.json"
        )
        fixture = json.loads(path.read_text())
        for case in fixture["cases"]:
            evaluated = []
            for candidate in case["candidates"]:
                states = []
                for index, state in enumerate(candidate["states"]):
                    penalty = (
                        max(D(0), D(state["after"]) - D(candidate["before"]))
                        + D(state["distortion"])
                        + D(state["sliding"])
                    )
                    states.append(
                        (
                            penalty,
                            state["opened"],
                            state["module"],
                            state["core"],
                            index,
                        )
                    )
                chosen = min(states)
                total = (
                    D(candidate["before"])
                    + D(candidate["spacing"])
                    + D(case["start"])
                    - D(case["unbound"])
                    + chosen[0]
                )
                evaluated.append((total, candidate["index"], chosen[-1]))
            expected = case["expected"]
            greedy = min(
                case["candidates"],
                key=lambda c: (D(c["cofold"]) + D(c["spacing"]), c["index"]),
            )["index"]
            winner = min(evaluated)
            self.assertEqual(
                [x[0] for x in evaluated], list(map(D, expected["candidate_totals"]))
            )
            self.assertEqual(
                (winner[0], winner[1], winner[2]),
                (D(expected["total"]), expected["winner"], expected["state"]),
            )
            self.assertEqual(greedy, expected["greedy"])
            self.assertEqual(
                next(x[0] for x in evaluated if x[1] == greedy),
                D(expected["greedy_total"]),
            )
            self.assertLessEqual(winner[0], D(expected["greedy_total"]))
        for row in fixture["coordinates"]:
            a, b = [x + row["window_start"] for x in row["window_interval"]]
            mapped = (
                [a, b]
                if row["strand"] == "+"
                else [row["length"] - b, row["length"] - a]
            )
            self.assertEqual(mapped, row["expected_interval"])
        row = fixture["start_mapping"]
        self.assertEqual(
            row["length"] - 1 - row["oriented_start"], row["reverse_forward_base"]
        )
        self.assertEqual(
            [
                row["length"] - row["oriented_start"] - 3,
                row["length"] - row["oriented_start"],
            ],
            row["reverse_start_codon_interval"],
        )
        for row in fixture["circular"]:
            bases = [
                (row["oriented_first_base"] + row["step"] * i) % row["genome_length"]
                for i in range(*row["interval"])
            ]
            self.assertEqual(bases, row["expected_bases"])
            segments = [
                x
                for a, b in row["expected_segments"]
                for x in (range(a, b) if row["step"] == 1 else range(b - 1, a - 1, -1))
            ]
            self.assertEqual(bases, segments)


if __name__ == "__main__":
    unittest.main()
