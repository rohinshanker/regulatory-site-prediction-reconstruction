"""Hand-calculated calibration, paired resampling and failure-selection safeguards."""

import math
import unittest
from copy import deepcopy

from benchmarks.rbs import strength


class StrengthTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "id": str(i),
                "observed": 2**i,
                "group": str(i),
                "partition": "development_train",
            }
            for i in range(4)
        ]
        self.predictions = [
            {"id": str(i), "predicted": 2 ** (i + 2), "status": "ok"} for i in range(4)
        ]

    def test_train_only_median_calibration(self):
        fit = strength.fit_intercept(self.records, self.predictions)
        self.assertEqual(fit["offset_log2"], -2)
        self.assertEqual(fit["n_fitted"], 4)
        result = strength.evaluate(self.records, self.predictions, fit["offset_log2"])
        self.assertEqual(result["metrics"]["mae_log2"], 0)
        self.assertEqual(result["metrics"]["within_2fold"]["all_case_fraction"], 1)
        for partition in ("final", "development_validation"):
            records = deepcopy(self.records)
            records[0]["partition"] = partition
            with self.assertRaisesRegex(ValueError, "train only"):
                strength.fit_intercept(records, self.predictions)
        with self.assertRaises(ValueError):
            strength.fit_intercept([], [])
        with self.assertRaisesRegex(ValueError, "successful"):
            strength.fit_intercept(self.records, [])

    def test_zero_missing_and_failures_remain_distinct(self):
        self.records[0]["observed"] = 0
        self.records[1]["observed"] = None
        predictions = [{"id": "2", "status": "unsupported", "predicted": None}]
        result = strength.evaluate(self.records, predictions)
        self.assertEqual(result["n_source_cases"], 4)
        self.assertEqual(result["assay_exclusions"], {"missing": 1, "reported_zero": 1})
        self.assertEqual(
            result["metrics"]["failures"], {"not_evaluated": 1, "unsupported": 1}
        )
        self.assertEqual(result["metrics"]["coverage"], 0)
        self.assertIsNone(result["metrics"]["mae_log2"])
        records = deepcopy(self.records)
        records[0]["observed"] = True
        with self.assertRaises(ValueError):
            strength.evaluate(records, [])

    def test_affine_scale_compression_is_train_only_and_named(self):
        for i, row in enumerate(self.predictions):
            row["predicted"] = 2 ** (2 * i + 2)
        fit = strength.fit_affine(self.records, self.predictions)
        self.assertEqual((fit["slope_log2"], fit["intercept_log2"]), (0.5, -1))
        adapted = strength.apply_affine(self.predictions, fit)
        self.assertEqual([r["predicted"] for r in adapted], [1, 2, 4, 8])
        self.assertEqual(adapted[0]["uncalibrated_prediction"], 4)
        self.records[0]["partition"] = "final"
        with self.assertRaises(ValueError):
            strength.fit_affine(self.records, self.predictions)
        self.records[0]["partition"] = "development_train"
        for row in self.predictions:
            row["predicted"] = 1
        with self.assertRaisesRegex(ValueError, "nonconstant"):
            strength.fit_affine(self.records, self.predictions)

    def test_affine_invalid_parameters_and_range_failures_remain_counted(self):
        self.predictions[0].update(status="failed", predicted=None)
        for intercept in (2000, -2000):
            result = strength.apply_affine(
                self.predictions, {"slope_log2": 1, "intercept_log2": intercept}
            )
            self.assertEqual(len(result), 4)
            self.assertTrue(all(r["status"] == "failed" for r in result))
            self.assertEqual(result[1]["reason"], "affine_numeric_range")
        for key in ("slope_log2", "intercept_log2"):
            for value in (True, math.inf, math.nan):
                with self.assertRaises(ValueError):
                    strength.apply_affine(
                        self.predictions,
                        {"slope_log2": 1, "intercept_log2": 0, key: value},
                    )

    def test_invalid_join_and_group(self):
        for kind in (
            "duplicate_source",
            "duplicate_prediction",
            "unknown",
            "empty",
            "non_string",
            "group",
        ):
            records, predictions = deepcopy(self.records), deepcopy(self.predictions)
            if kind == "duplicate_source":
                records.append(records[0])
            elif kind == "duplicate_prediction":
                predictions.append(predictions[0])
            elif kind == "unknown":
                predictions[0]["id"] = "other"
            elif kind == "empty":
                records[0]["id"] = ""
            elif kind == "non_string":
                records[0]["id"] = 1
            else:
                records[0]["group"] = ""
            with self.assertRaises(ValueError):
                strength.pairs(records, predictions)
        for offset in (True, float("nan"), -2000, 2000):
            with self.assertRaises(ValueError):
                strength.pairs(self.records, self.predictions, offset)
        self.predictions[0]["predicted"] = float("inf")
        with self.assertRaises(ValueError):
            strength.pairs(self.records, self.predictions)

    def test_exact_paired_gain_and_seed_reproduction(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        contender, _ = strength.pairs(self.records, self.predictions, -2)
        result = strength.paired_comparison(reference, contender, repetitions=100)
        self.assertEqual(result["mae_log2_gain"], 2)
        self.assertEqual(result["paired_group_bootstrap_interval"], [2, 2])
        self.assertTrue(result["coverage_gate"])
        self.assertTrue(result["statistical_and_practical_gain"])
        self.assertTrue(result["spearman_gate"])
        self.assertEqual(
            result, strength.paired_comparison(reference, contender, repetitions=100)
        )

    def test_failure_selection_cannot_win(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        contender, _ = strength.pairs(self.records, self.predictions, -2)
        contender[0].update(status="failed", predicted=None)
        result = strength.paired_comparison(reference, contender, repetitions=20)
        self.assertEqual(result["baseline_valid_cases_dropped"], 1)
        self.assertFalse(result["coverage_gate"])
        self.assertEqual(result["n_common_success"], 3)
        reference[0].update(status="failed", predicted=None)
        result = strength.paired_comparison(reference, contender, repetitions=20)
        self.assertEqual(result["baseline_valid_cases_dropped"], 0)
        self.assertFalse(result["coverage_gate"])

    def test_group_resampling_and_undefined_cases(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        contender, _ = strength.pairs(self.records, self.predictions, -2)
        for row in reference + contender:
            row["group"] = "one"
        self.assertIsNone(
            strength.paired_comparison(reference, contender)[
                "paired_group_bootstrap_interval"
            ]
        )
        result = strength.paired_comparison([], [], repetitions=2)
        self.assertIsNone(result["mae_log2_gain"])
        self.assertFalse(result["spearman_gate"])
        for row in contender:
            row.update(status="failed", predicted=None)
        self.assertFalse(
            strength.paired_comparison(reference, contender)[
                "statistical_and_practical_gain"
            ]
        )

    def test_contrast_validation(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        for key, value in [("id", "other"), ("observed", 4), ("group", "other")]:
            contender = deepcopy(reference)
            contender[0][key] = value
            with self.assertRaisesRegex(ValueError, "identical"):
                strength.paired_comparison(reference, contender)
        for kwargs in (
            {"repetitions": True},
            {"repetitions": 1},
            {"confidence": 0},
            {"confidence": 1},
            {"confidence": math.nan},
            {"worthwhile_gain": -1},
            {"worthwhile_gain": True},
        ):
            with self.assertRaises(ValueError):
                strength.paired_comparison(reference, reference, **kwargs)

    def test_subgroup_denominators_and_tolerance(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        contender, _ = strength.pairs(self.records, self.predictions, -2)
        membership = {
            str(i): ["all", "singleton"] if i == 0 else ["all"] for i in range(4)
        }
        result = strength.subgroup_gates(reference, contender, membership, minimum_n=2)
        self.assertTrue(result["all"]["gate"])
        self.assertIsNone(result["singleton"]["gate"])
        self.assertEqual(result["all"]["mae_increase_log2"], -2)
        result = strength.subgroup_gates(contender, reference, membership, minimum_n=2)
        self.assertFalse(result["all"]["gate"])
        for row in contender:
            row.update(status="failed", predicted=None)
        self.assertIsNone(
            strength.subgroup_gates(reference, contender, membership)["all"][
                "mae_increase_log2"
            ]
        )

    def test_subgroup_validation(self):
        reference, _ = strength.pairs(self.records, self.predictions)
        membership = {str(i): ["all"] for i in range(4)}
        for kwargs in (
            {"minimum_n": True},
            {"minimum_n": 0},
            {"tolerance": -1},
            {"tolerance": math.nan},
        ):
            with self.assertRaises(ValueError):
                strength.subgroup_gates(reference, reference, membership, **kwargs)
        with self.assertRaises(ValueError):
            strength.subgroup_gates(reference, [], membership)
        with self.assertRaises(ValueError):
            strength.subgroup_gates(reference, reference, {})
        for bad in ("all", ["all", "all"], [""], [1]):
            membership["0"] = bad
            with self.assertRaises(ValueError):
                strength.subgroup_gates(reference, reference, membership)


if __name__ == "__main__":
    unittest.main()
