"""Independent strand/origin fixtures and positive-only conditional rank arithmetic."""

import unittest
from copy import deepcopy

from benchmarks.rbs import position


class PositionTests(unittest.TestCase):
    def setUp(self):
        self.genome = (
            "CCC" * 5 + "TAA" + "ATG" + "AAA" + "GTG" + "CCC" + "TGA" + "CCC" * 10
        )
        self.queries = [
            {"id": "a", "start_positions": [0, 3, 6]},
            {"id": "b", "start_positions": [0, 3]},
            {"id": "u", "start_positions": []},
        ]
        self.labels = [
            {"id": "a", "tier": "positive", "starts": [3]},
            {"id": "b", "tier": "positive", "starts": [0]},
            {"id": "u", "tier": "unlabelled", "starts": [0]},
        ]
        self.predictions = [
            {
                "id": "a",
                "candidates": [
                    {"start": p, "score": s, "status": "ok"}
                    for p, s in [(0, 1), (3, 4), (6, 2)]
                ],
            },
            {
                "id": "b",
                "candidates": [
                    {"start": p, "score": 2, "status": "ok"} for p in (0, 3)
                ],
            },
        ]

    def test_hand_counted_plus_minus_and_origin(self):
        query = position.stop_query(self.genome, 30, "+", cap=18, flank=3)
        self.assertEqual(query["sequence"], "TAAATGAAAGTGCCCTGACCC")
        self.assertEqual(query["start_positions"], [3, 9])
        self.assertEqual(query["terminal_stop_position"], 15)
        self.assertEqual(query["oriented_first_genomic_zero_based"], 15)
        self.assertTrue(query["prior_stop_found"])
        self.assertEqual(position.true_index(query, 18, len(self.genome)), 3)
        reverse = self.genome.translate(str.maketrans("ACGT", "TGCA"))[::-1]
        reverse_query = position.stop_query(
            reverse, len(reverse) - 1 - 30, "-", cap=18, flank=3
        )
        self.assertEqual(reverse_query["sequence"], query["sequence"])
        self.assertEqual(reverse_query["start_positions"], [3, 9])
        self.assertEqual(
            position.true_index(reverse_query, len(reverse) - 1 - 18, len(reverse)), 3
        )
        shift = 24
        rotated = self.genome[shift:] + self.genome[:shift]
        circular = position.stop_query(rotated, 6, "+", cap=18, flank=3)
        self.assertEqual(circular["sequence"], query["sequence"])
        self.assertEqual(
            position.true_index(circular, (18 - shift) % len(rotated), len(rotated)), 3
        )

    def test_cap_and_empty_candidate_universes_do_not_use_true_start(self):
        query = position.stop_query(self.genome, 30, "+", cap=9, flank=3)
        self.assertFalse(query["prior_stop_found"])
        self.assertEqual(query["start_positions"], [6])
        sequence = "CCC" * 5 + "TAATGA" + "CCC" * 10
        empty = position.stop_query(sequence, 18, "+", cap=9, flank=3)
        self.assertEqual(empty["start_positions"], [])
        self.assertEqual(empty["terminal_stop_position"], 3)

    def test_query_validation(self):
        for kwargs in (
            {"sequence": "N" * 63},
            {"stop": True},
            {"stop": -1},
            {"strand": "x"},
            {"cap": 0},
            {"cap": 4},
            {"cap": True},
            {"flank": -1},
            {"flank": True},
            {"cap": 3000},
            {"stop": 0},
        ):
            values = {
                "sequence": self.genome,
                "stop": 30,
                "strand": "+",
                "cap": 18,
                "flank": 3,
            }
            values.update(kwargs)
            with self.assertRaises(ValueError):
                position.stop_query(**values)
        query = position.stop_query(self.genome, 30, "+", cap=18, flank=3)
        for start in (-1, True, len(self.genome)):
            with self.assertRaises(ValueError):
                position.true_index(query, start, len(self.genome))

    def test_exact_tolerant_and_tie_denominators(self):
        result = position.evaluate(self.queries, self.labels, self.predictions)
        self.assertEqual(result["n_positive"], 2)
        self.assertEqual(result["n_unlabelled"], 1)
        self.assertEqual(result["top1_exact_fraction"], 0.5)
        self.assertEqual(result["top1_tolerant_fraction"], 1)
        self.assertEqual(result["top1_uniform_tie_expected_fraction"], 0.75)
        self.assertEqual(result["mrr_worst_tie_all_positive"], 0.75)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["pr_auc"])
        self.labels[1]["starts"] = [0, 3]
        self.assertEqual(
            position.evaluate(self.queries, self.labels, self.predictions)[
                "mrr_worst_tie_all_positive"
            ],
            1,
        )

    def test_failed_candidates_and_missing_queries_count_against_ranking(self):
        self.predictions[0]["candidates"][0].update(status="unsupported", score=None)
        result = position.evaluate(self.queries, self.labels, self.predictions)
        self.assertEqual(result["all_candidates_scored_fraction"], 0.5)
        self.assertEqual(result["positive_scored_fraction"], 1)
        self.assertEqual(result["top1_exact_fraction"], 0)
        self.assertEqual(result["mrr_worst_tie_all_positive"], 0.25)
        result = position.evaluate(self.queries, self.labels, [])
        self.assertEqual(result["mrr_worst_tie_all_positive"], 0)
        self.assertEqual(result["query_with_any_score_fraction"], 0)
        self.labels[0]["starts"] = [99]
        result = position.evaluate(self.queries, self.labels, self.predictions)
        self.assertEqual(result["truth_in_universe_fraction"], 0.5)
        self.predictions[0]["candidates"][0].update(status="ok", score=1)
        self.assertEqual(
            position.evaluate(self.queries, self.labels, self.predictions)[
                "mrr_worst_tie_all_positive"
            ],
            0.25,
        )

    def test_unlabelled_and_empty_labels_never_become_negatives(self):
        result = position.evaluate(self.queries, [], self.predictions)
        self.assertEqual(result["n_unlabelled"], 3)
        self.assertIsNone(result["mrr_worst_tie_all_positive"])
        self.assertIsNone(result["top1_exact_fraction"])
        self.assertIsNone(result["candidate_count_range"])
        self.assertEqual(position.evaluate([], [], [])["n_queries"], 0)

    def test_identity_label_and_tolerance_validation(self):
        for which in (
            "query",
            "label",
            "prediction",
            "unknown_label",
            "unknown_prediction",
            "empty_id",
            "nonstring",
        ):
            q, labels, p = (
                deepcopy(self.queries),
                deepcopy(self.labels),
                deepcopy(self.predictions),
            )
            if which == "query":
                q.append(q[0])
            elif which == "label":
                labels.append(labels[0])
            elif which == "prediction":
                p.append(p[0])
            elif which == "unknown_label":
                labels[0]["id"] = "unknown"
            elif which == "unknown_prediction":
                p[0]["id"] = "unknown"
            elif which == "empty_id":
                q[0]["id"] = ""
            else:
                q[0]["id"] = 3
            with self.assertRaises(ValueError):
                position.evaluate(q, labels, p)
        for tolerance in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                position.evaluate(self.queries, self.labels, [], tolerance)
        for label in (
            {"tier": "negative", "starts": [0]},
            {"tier": "positive", "starts": []},
            {"tier": "positive", "starts": [True]},
            {"tier": "positive", "starts": [-1]},
        ):
            labels = deepcopy(self.labels)
            labels[0].update(label)
            with self.assertRaises(ValueError):
                position.evaluate(self.queries, labels, [])

    def test_universe_and_prediction_validation(self):
        for starts in ("bad", [0, 0], [True], [-1]):
            queries = deepcopy(self.queries)
            queries[0]["start_positions"] = starts
            with self.assertRaises(ValueError):
                position.evaluate(queries, self.labels, [])
        for candidates in (
            [{"start": 99, "score": 1, "status": "ok"}],
            [{"start": True, "score": 1, "status": "ok"}],
            [{"start": 0, "score": 1, "status": "ok"}] * 2,
            [{"start": 0, "score": True, "status": "ok"}],
            [{"start": 0, "score": 1, "status": "unknown"}],
        ):
            predictions = [{"id": "a", "candidates": candidates}]
            with self.assertRaises(ValueError):
                position.evaluate(self.queries, self.labels, predictions)


if __name__ == "__main__":
    unittest.main()
