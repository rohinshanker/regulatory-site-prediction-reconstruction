"""Numerical expectations use hand-computable examples, never engine outputs."""

import math
import unittest

from benchmarks.rbs.evaluation import evaluate
from benchmarks.rbs.metrics import (
    cluster_mae_interval,
    correlation,
    cross_partition_overlap,
    edit_distance,
    ranks,
    summary,
    wilson,
)


def pair(key, observed, predicted, status="ok", group="a"):
    return dict(
        id=key, observed=observed, predicted=predicted, status=status, group=group
    )


class MetricsTest(unittest.TestCase):
    def test_correlations_and_ties(self):
        self.assertEqual(ranks([30, 10, 10, 20]), [4, 1.5, 1.5, 3])
        self.assertEqual(ranks([]), [])
        self.assertEqual(correlation([1, 2, 3], [6, 4, 2]), -1)
        self.assertIsNone(correlation([], []))
        self.assertIsNone(correlation([1, 1], [2, 3]))
        for left, right in [([1], []), ([math.nan], [1]), ([1], [math.inf])]:
            with self.assertRaises(ValueError):
                correlation(left, right)
        for value in [True, False, "1", None, math.nan, math.inf]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                correlation([value], [1])
            with self.subTest(value=value), self.assertRaises(ValueError):
                ranks([value])

    def test_metrics_count_failures_and_fold_boundaries(self):
        rows = [
            pair("a", 1, 2),
            pair("b", 4, 2),
            pair("c", 1, 5),
            pair("d", 1, None, "failed"),
        ]
        result = summary(rows)
        self.assertEqual(result["coverage"], 0.75)
        self.assertEqual(result["failures"], {"failed": 1})
        self.assertEqual(result["within_2fold"]["n"], 2)
        self.assertEqual(result["within_2fold"]["all_case_fraction"], 0.5)
        self.assertEqual(result["within_2fold"]["successful_pair_fraction"], 2 / 3)
        self.assertEqual(result["within_5fold"]["n"], 3)
        self.assertAlmostEqual(
            result["rmse_log2"], math.sqrt((2 + math.log2(5) ** 2) / 3)
        )
        self.assertAlmostEqual(result["bias_log2"], math.log2(5) / 3)
        self.assertEqual(summary([])["coverage"], None)
        self.assertIsNone(summary([pair("a", 1, None, "no_candidate")])["mae_log2"])

    def test_invalid_rows_fail_closed(self):
        bad = [
            [pair("", 1, 1)],
            [pair("a", 1, 1), pair("a", 2, 2)],
            [pair("a", 0, 1)],
            [pair("a", math.inf, 1)],
            [pair("a", "1", 1)],
            [pair("a", 1, 0)],
            [pair("a", 1, math.nan)],
            [pair("a", 1, "1")],
            [pair("a", True, 1)],
            [pair("a", False, 1)],
            [pair("a", 1, True)],
            [pair("a", 1, False)],
            [pair("a", 1, None, "silent_skip")],
        ]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                summary(rows)

    def test_spearman_is_not_pearson(self):
        result = summary(
            [pair(str(i), 2**i, 2**j) for i, j in enumerate([0, 1, 3, 2, 10])]
        )
        self.assertAlmostEqual(result["spearman_rho"], 0.9)
        self.assertNotAlmostEqual(result["spearman_rho"], result["pearson_r_log"])

    def test_wilson(self):
        self.assertIsNone(wilson(0, 0))
        self.assertAlmostEqual(wilson(5, 10)[0], 0.236593090512564)
        self.assertAlmostEqual(wilson(5, 10)[1], 0.763406909487436)
        for values in [(2, 1), (-1, 1), (0, -1), (True, 1), (0, False), (0.5, 1)]:
            with self.assertRaises(ValueError):
                wilson(*values)

    def test_family_bootstrap(self):
        rows = [
            pair("a", 1, 2, group="x"),
            pair("b", 1, 4, group="y"),
            pair("c", 1, None, "failed", "z"),
        ]
        self.assertEqual(cluster_mae_interval(rows, 100), [1, 2])
        self.assertIsNone(cluster_mae_interval(rows[:1]))
        with self.assertRaises(ValueError):
            cluster_mae_interval(rows, 1)
        for count in [True, 2.5, "100"]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                cluster_mae_interval(rows, count)

    def test_sequence_overlap(self):
        self.assertEqual(edit_distance("", "AG"), 2)
        self.assertEqual(edit_distance("GATTACA", "GATACA"), 1)
        a = [dict(id="a", sequence="ACGTACGT", start=0)]
        b = [dict(id="b", sequence="ACGTACGA", start=0)]
        self.assertEqual(cross_partition_overlap(a, b)[0]["window_similarity"], 0.875)
        self.assertEqual(cross_partition_overlap(a, b, 0.9), [])
        self.assertTrue(cross_partition_overlap(a, a)[0]["exact_sequence"])
        with self.assertRaises(ValueError):
            cross_partition_overlap(a, b, 2)
        for threshold in [True, None, math.nan]:
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                cross_partition_overlap(a, b, threshold)
        with self.assertRaises(ValueError):
            cross_partition_overlap(a, [dict(id="b", sequence="", start=0)])

    def test_evaluation_joins_and_fixed_control(self):
        records = [
            dict(id="a", observed=2, family="x"),
            dict(id="b", observed=4, family="y"),
            dict(id="c", observed=8, family="z"),
        ]
        predictions = [
            dict(id="b", predicted=200, status="ok"),
            dict(id="a", predicted=100, status="ok"),
        ]
        result = evaluate(records, predictions, "a")
        self.assertEqual(result["metrics"]["mae_log2"], 0)
        self.assertEqual(result["metrics"]["failures"], {"not_evaluated": 1})
        self.assertEqual(result["constant_relative_rate_baseline"]["mae_log2"], 1)
        self.assertNotIn(
            "constant_relative_rate_baseline", evaluate(records, predictions)
        )
        self.assertEqual(records[0]["observed"], 2)  # Caller data not mutated.
        for obs, pred, ref in [
            (records * 2, predictions, None),
            (records, predictions * 2, None),
            (records, [dict(id="unknown")], None),
            (records, predictions, "c"),
        ]:
            with self.assertRaises(ValueError):
                evaluate(obs, pred, ref)

    def test_measurement_eligibility_is_explicit(self):
        records = [
            dict(id="a", observed=2, family="x"),
            dict(id="b", observed="N/A", family="x", measurement_status="not_measured"),
        ]
        result = evaluate(records, [])
        self.assertEqual(result["n_constructs"], 2)
        self.assertEqual(result["n_measurement_eligible"], 1)
        self.assertEqual(result["exclusions"], {"source_not_measured": ["b"]})
        self.assertEqual(result["metrics"]["failures"], {"not_evaluated": 1})
        records[1]["observed"] = 3
        with self.assertRaises(ValueError):
            evaluate(records, [])
        records[1]["measurement_status"] = "low_signal_skip"
        with self.assertRaises(ValueError):
            evaluate(records, [])


if __name__ == "__main__":
    unittest.main()
