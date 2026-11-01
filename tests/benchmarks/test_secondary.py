"""Condition transfer fixtures distinguish inherited calibration from new labels."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import secondary
from benchmarks.rbs.datasets import digest, write_json


class SecondaryTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "id": name,
                "observed": value,
                "group": name,
                "partition": part,
                "condition": phase,
            }
            for phase, mult in [("early", 1), ("late", 2)]
            for name, value, part in [
                ("a", 2 * mult, "development_train"),
                ("b", 4 * mult, "development_validation"),
                ("c", 4 * mult, "final"),
                ("d", 8 * mult, "final"),
            ]
        ]
        self.models = {
            "fixed": [
                {"id": name, "status": "ok", "predicted": value}
                for name, value in [("a", 1), ("b", 2), ("c", 2), ("d", 4)]
            ]
        }
        self.offsets = {"fixed": 1}

    def call(self, records=None, models=None, offsets=None, conditions=None):
        return secondary.report(
            self.records if records is None else records,
            self.models if models is None else models,
            self.offsets if offsets is None else offsets,
            ["early", "late"] if conditions is None else conditions,
            repetitions=20,
        )

    def test_condition_calibration_and_final_labels_do_not_change_fits(self):
        result = self.call()["conditions"]
        self.assertEqual(
            result["early"]["models"]["fixed"]["frozen_HC_transfer"]["metrics"][
                "mae_log2"
            ],
            0,
        )
        late = result["late"]["models"]["fixed"]
        self.assertEqual(late["frozen_HC_transfer"]["metrics"]["mae_log2"], 1)
        self.assertEqual(late["condition_train_intercept"]["metrics"]["mae_log2"], 0)
        self.assertEqual(late["condition_training_calibration"]["offset_log2"], 2)
        changed = deepcopy(self.records)
        for row in changed:
            if row["partition"] == "final":
                row["observed"] *= 100
        self.assertEqual(
            self.call(changed)["conditions"]["late"]["models"]["fixed"][
                "condition_training_calibration"
            ],
            late["condition_training_calibration"],
        )
        models = deepcopy(self.models)
        models["fixed"][-1].update(status="failed", predicted=None)
        self.assertEqual(
            self.call(models=models)["conditions"]["late"]["models"]["fixed"][
                "frozen_HC_transfer"
            ]["metrics"]["coverage"],
            0.5,
        )

    def test_frozen_roster_partition_and_identity_rejections(self):
        for conditions in ([], ["early", "early"], ["early"]):
            with self.assertRaises(ValueError):
                self.call(conditions=conditions)
        for offsets in ({}, {"fixed": True}):
            with self.assertRaises(ValueError):
                self.call(offsets=offsets)
        with self.assertRaises(ValueError):
            self.call(models={}, offsets={})
        for kind in (
            "unknown_partition",
            "changed_group",
            "changed_ids",
            "cross_partition",
            "no_train",
            "no_final",
            "duplicate",
        ):
            records = deepcopy(self.records)
            if kind == "unknown_partition":
                records[0]["partition"] = "unknown"
            elif kind == "changed_group":
                records[0]["group"] = "other"
            elif kind == "changed_ids":
                records.pop()
            elif kind == "cross_partition":
                for row in records:
                    row["group"] = "same"
            elif kind in ("no_train", "no_final"):
                for row in records:
                    if row["partition"] == (
                        "development_train" if kind == "no_train" else "final"
                    ):
                        row["partition"] = "development_validation"
            else:
                records.append(deepcopy(records[0]))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.call(records)
        models = deepcopy(self.models)
        models["fixed"].append({"id": "unknown"})
        with self.assertRaises(ValueError):
            self.call(models=models)

    def test_frozen_manifest_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "cases", {"records": self.records})
            write_json(root / "model", {"records": self.models["fixed"]})

            def spec(name):
                return {"path": name, "sha256": digest((root / name).read_bytes())}

            manifest = {
                "cases": spec("cases"),
                "models": {"fixed": spec("model")},
                "final_roster_frozen": True,
                "conditions": ["early", "late"],
                "frozen_HC_offsets_log2": self.offsets,
                "bootstrap_repetitions": 20,
            }
            write_json(root / "manifest", manifest)
            with (
                patch.object(
                    sys,
                    "argv",
                    ["secondary", str(root / "manifest"), str(root / "output")],
                ),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module("benchmarks.rbs.secondary", run_name="__main__")
            self.assertEqual(
                json.loads((root / "output").read_text())["conditions"]["late"][
                    "n_final"
                ],
                2,
            )
            manifest["final_roster_frozen"] = False
            write_json(root / "manifest", manifest)
            with self.assertRaises(ValueError):
                secondary.main([str(root / "manifest"), str(root / "output")])


if __name__ == "__main__":
    unittest.main()
