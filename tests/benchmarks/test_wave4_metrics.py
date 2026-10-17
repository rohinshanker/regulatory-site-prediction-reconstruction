"""Independent hand-calculations and full-block resampling edge cases."""

import copy
import random
import unittest

from benchmarks.rbs import wave4_metrics as m


class Wave4MetricsTest(unittest.TestCase):
    def setUp(self):
        self.inputs = [{"id": str(i), "group": str(i // 2)} for i in range(8)]
        self.labels = [{"id": str(i), "observed": i // 2} for i in range(8)]
        self.predictions = [
            {
                "id": str(i),
                "predicted": i // 2,
                "status": "ok",
                "seconds": i / 10,
                "reason": "",
            }
            for i in range(8)
        ]
        self.settings = dict(
            draws=100,
            seed=7,
            minimum_usable_draws=95,
            minimum_common_rows=2,
            minimum_common_blocks=2,
        )
        self.gate = dict(minimum_coverage=0.95, minimum_rank_gain=0.05)

    def rows(self):
        return m.join(self.inputs, self.labels, self.predictions)

    def test_identity_validation(self):
        for rows in ([{"id": ""}], [{"id": True}], [{"id": "a"}, {"id": "a"}]):
            with self.assertRaises(ValueError):
                m.indexed(rows)
        with self.assertRaises(ValueError):
            m.join(self.inputs, self.labels[:-1], self.predictions)
        with self.assertRaises(ValueError):
            m.join(self.inputs, self.labels, self.predictions[:-1])

    def test_join_validation_and_no_metadata_overwrite(self):
        for value in (True, float("nan"), "1"):
            labels = copy.deepcopy(self.labels)
            labels[0]["observed"] = value
            with self.assertRaises(ValueError):
                m.join(self.inputs, labels, self.predictions)
        for key, value in [
            ("status", "unknown"),
            ("predicted", None),
            ("predicted", True),
            ("seconds", -1),
            ("seconds", True),
            ("reason", None),
        ]:
            predictions = copy.deepcopy(self.predictions)
            predictions[0][key] = value
            with self.assertRaises(ValueError):
                m.join(self.inputs, self.labels, predictions)
        predictions = copy.deepcopy(self.predictions)
        predictions[0].update(status="failed", predicted=0)
        with self.assertRaises(ValueError):
            m.join(self.inputs, self.labels, predictions)
        for value in ("", True):
            inputs = copy.deepcopy(self.inputs)
            inputs[0]["group"] = value
            with self.assertRaises(ValueError):
                m.join(inputs, self.labels, self.predictions)
        predictions = copy.deepcopy(self.predictions)
        predictions[0].update(group="wrong", observed=1000)
        self.assertEqual(
            m.join(self.inputs, self.labels, predictions)[0]["observed"], 0
        )
        self.assertEqual(m.join(self.inputs, self.labels, predictions)[0]["group"], "0")

    def test_ties_missing_failures_and_runtime(self):
        self.assertAlmostEqual(m.rho([1, 1, 2, 3], [1, 2, 2, 3]), 5 / 6)
        self.assertIsNone(m.rho([1, 1], [2, 3]))
        self.assertIsNone(m.rho([], []))
        self.labels[0]["observed"] = None
        self.predictions[1].update(
            status="timeout", predicted=None, reason="record_deadline"
        )
        self.predictions[2].update(
            status="not_run", predicted=None, reason="collection_deadline", seconds=0
        )
        result = m.summarize(self.rows())
        self.assertEqual(
            (
                result["n_inputs"],
                result["n_observed"],
                result["n_success"],
                result["n_paired"],
            ),
            (8, 7, 6, 5),
        )
        self.assertEqual(result["coverage"], 0.75)
        self.assertEqual(result["runtime_seconds"]["n_executed"], 7)
        self.assertEqual(result["runtime_seconds"]["p95_nearest_rank"], 0.7)
        self.assertEqual(
            result["failure_reasons"], {"collection_deadline": 1, "record_deadline": 1}
        )
        empty = m.summarize([])
        self.assertIsNone(empty["coverage"])
        self.assertIsNone(empty["runtime_seconds"]["median"])
        self.assertEqual(
            m.summarize(
                [dict(r, status="not_run", predicted=None) for r in self.rows()]
            )["runtime_seconds"]["sum"],
            0,
        )

    def test_paired_recomputed_multiplicity_and_empty_blocks(self):
        reference = self.rows()
        contender = copy.deepcopy(reference)
        for i, row in enumerate(reference):
            row["predicted"] = [0, 0, 3, 2, 2, 1, 3, 1][i]
        reference[0].update(status="failed", predicted=None)
        reference[1].update(status="failed", predicted=None)
        contender[7].update(status="failed", predicted=None)
        result = m.paired(reference, contender, self.settings)
        self.assertEqual(result["n_blocks"], 4)
        self.assertEqual(result["n_common_blocks"], 3)
        self.assertEqual(result["lost_reference_successes"], 1)
        self.assertEqual(result["n_common_measured"], 5)
        rng = random.Random(7)
        estimates = []
        # Independent literal group-index sampling includes empty block zero.
        for _ in range(100):
            sampled_groups = [rng.choice([0, 1, 2, 3]) for _ in range(4)]
            ids = [
                i for g in sampled_groups for i in range(2 * g, 2 * g + 2) if 2 <= i < 7
            ]
            a = m.rho(
                [reference[i]["observed"] for i in ids],
                [reference[i]["predicted"] for i in ids],
            )
            b = m.rho(
                [contender[i]["observed"] for i in ids],
                [contender[i]["predicted"] for i in ids],
            )
            if a is not None and b is not None:
                estimates.append(b - a)
        self.assertEqual(result["usable_draws"], len(estimates))
        self.assertEqual(result["undefined_draws"], 100 - len(estimates))
        self.assertEqual(result["interval_status"], "insufficient_usable_draws")
        settings = {**self.settings, "minimum_usable_draws": 1}
        complete = m.paired(reference, contender, settings)
        values = sorted(estimates)
        n = len(values)
        import math

        self.assertEqual(
            complete["interval95"],
            [values[math.floor(0.025 * (n - 1))], values[math.ceil(0.975 * (n - 1))]],
        )
        self.assertEqual(complete, m.paired(reference, contender, settings))

    def test_paired_constant_support_and_bad_inputs(self):
        rows = self.rows()
        same = m.paired(rows, rows, self.settings)
        self.assertEqual(same["rank_gain"], 0)
        self.assertEqual(same["interval95"], [0, 0])
        constant = [dict(r, predicted=1) for r in rows]
        self.assertEqual(
            m.paired(rows, constant, self.settings)["interval_status"],
            "undefined_point_correlation",
        )
        self.assertEqual(
            m.paired(rows, rows, {**self.settings, "minimum_common_rows": 10})[
                "interval_status"
            ],
            "insufficient_support",
        )
        self.assertEqual(
            m.paired(rows, rows, {**self.settings, "minimum_common_blocks": 10})[
                "interval_status"
            ],
            "insufficient_support",
        )
        with self.assertRaises(ValueError):
            m.paired(rows, rows[:-1], self.settings)
        for key, value in [("group", "changed"), ("observed", None)]:
            changed = copy.deepcopy(rows)
            changed[0][key] = value
            with self.assertRaises(ValueError):
                m.paired(rows, changed, self.settings)
        for key, value in [
            ("draws", True),
            ("draws", 1),
            ("minimum_usable_draws", 0),
            ("minimum_usable_draws", 101),
            ("minimum_common_rows", 1),
            ("minimum_common_blocks", 1),
        ]:
            with self.assertRaises(ValueError):
                m.paired(rows, rows, {**self.settings, key: value})

    def test_fixed_gate_boundaries(self):
        comparison = dict(
            interval95=[0.001, 0.1], rank_gain=0.05, lost_reference_successes=0
        )
        self.assertEqual(
            m.advancement(comparison, {"coverage": 0.95}, self.gate, True, True),
            {"advance": True, "reasons": []},
        )
        failed = m.advancement(
            dict(interval95=None, rank_gain=None, lost_reference_successes=1),
            {"coverage": None},
            self.gate,
            False,
            False,
        )
        self.assertFalse(failed["advance"])
        self.assertEqual(len(failed["reasons"]), 6)
        for change in ({"rank_gain": 0.049999}, {"interval95": [0, 0.1]}):
            self.assertFalse(
                m.advancement(
                    {**comparison, **change}, {"coverage": 1}, self.gate, True, True
                )["advance"]
            )
        self.assertFalse(
            m.advancement(comparison, {"coverage": 0.949}, self.gate, True, True)[
                "advance"
            ]
        )


if __name__ == "__main__":
    unittest.main()
