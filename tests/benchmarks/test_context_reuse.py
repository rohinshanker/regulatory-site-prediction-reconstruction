"""Prediction reuse fixtures forbid success-based parent selection and input drift."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import context_reuse
from benchmarks.rbs.datasets import digest, write_json


class ContextReuseTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "a",
            "sequence": "CCCATGCCC",
            "start_position": 3,
            "sequence_sha256": digest("CCCATGCCC"),
            "strand": "+",
            "anti_sd": "ACCUCCUUU",
            "temperature_celsius": 30,
            "primary_eligible": True,
            "host": "original host",
        }
        self.parents = [
            self.row,
            {**self.row, "id": "b"},
            {**self.row, "id": "null", "sequence": None},
        ]
        self.targets = [
            {**self.row, "id": "target", "host": "target host"},
            {**self.row, "id": "new", "temperature_celsius": 31},
            {**self.row, "id": "excluded", "primary_eligible": False},
        ]
        self.old = [
            {
                "id": row["id"],
                "status": "failed" if row["id"] == "a" else "ok",
                "predicted": None if row["id"] == "a" else 4,
            }
            for row in self.parents
        ]
        self.new = [{"id": "new", "status": "ok", "predicted": 7}]

    def test_exact_input_only_plan_and_failed_parent_preserved(self):
        mapping, new = context_reuse.plan(self.targets, list(reversed(self.parents)))
        self.assertEqual([r["kind"] for r in mapping], ["reused", "new", "unsupported"])
        self.assertEqual(mapping[0]["parent_id"], "a")
        self.assertEqual(new, [self.targets[1]])
        out = context_reuse.combine(self.targets, self.parents, self.old, self.new)
        self.assertEqual([r["status"] for r in out], ["failed", "ok", "unsupported"])
        self.assertEqual(out[0]["context_reuse"]["original_host"], "original host")
        self.assertEqual(out[0]["context_reuse"]["target_host"], "target host")
        self.assertEqual(out[1]["predicted"], 7)
        for old, new in ((self.old[:-1], self.new), (self.old, [])):
            with self.assertRaises(ValueError):
                context_reuse.combine(self.targets, self.parents, old, new)

    def test_scenario_boundaries(self):
        for key, value in (
            ("sequence_sha256", "wrong"),
            ("strand", "-"),
            ("start_position", True),
            ("start_position", 99),
            ("temperature_celsius", True),
            ("anti_sd", None),
            ("anti_sd", ""),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                context_reuse.scenario({**self.row, key: value})
        self.assertEqual(
            context_reuse.scenario({**self.row, "strand": "-"}, strand_is_genomic=True),
            context_reuse.scenario(self.row),
        )
        self.assertIsNone(context_reuse.scenario({**self.row, "sequence": None}))
        self.assertEqual(
            context_reuse.plan([{**self.row, "sequence": None}], [])[1], []
        )

    def test_cli_hashes_metadata_and_argument_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                n: root / n for n in ("targets", "parents", "output", "old", "new")
            }
            for name, rows in (("targets", self.targets), ("parents", self.parents)):
                write_json(paths[name], {"records": rows})
            args = [str(paths[n]) for n in ("targets", "parents", "output")]
            args += [
                "--target-sha256",
                digest(paths["targets"].read_bytes()),
                "--parent-sha256",
                digest(paths["parents"].read_bytes()),
            ]
            context_reuse.main(["prepare", *args])
            prepared_hash = digest(paths["output"].read_bytes())
            common = {
                "model": "test",
                "adapter_sha256": "fixed",
                "upstream_artifacts": {},
            }
            old = {
                **common,
                "input_sha256": digest(paths["parents"].read_bytes()),
                "records": self.old,
            }
            new = {**common, "input_sha256": prepared_hash, "records": self.new}
            write_json(paths["old"], old)
            write_json(paths["new"], new)
            combine = [
                "combine",
                *args,
                "--parent-predictions",
                str(paths["old"]),
                "--new-predictions",
                str(paths["new"]),
                "--parent-prediction-sha256",
                digest(paths["old"].read_bytes()),
                "--new-prediction-sha256",
                digest(paths["new"].read_bytes()),
            ]
            with (
                patch.object(sys, "argv", ["context_reuse", *combine]),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module("benchmarks.rbs.context_reuse", run_name="__main__")
            self.assertEqual(len(json.loads(paths["output"].read_text())["records"]), 3)
            for name, value in (("old", old), ("new", new)):
                changed = deepcopy(value)
                changed["records"][-1]["predicted"] = 1024
                write_json(paths[name], changed)
                with self.assertRaisesRegex(ValueError, "prediction hash mismatch"):
                    context_reuse.main(combine)
                write_json(paths[name], value)
            for key in (
                "input_sha256",
                "model",
                "adapter_sha256",
                "upstream_artifacts",
            ):
                changed = deepcopy(new)
                changed[key] = "wrong"
                write_json(paths["new"], changed)
                combine[-1] = digest(paths["new"].read_bytes())
                with self.assertRaises(ValueError):
                    context_reuse.main(combine)
            write_json(paths["new"], new)
            combine[-1] = digest(paths["new"].read_bytes())
            changed = deepcopy(old)
            changed["input_sha256"] = "wrong"
            write_json(paths["old"], changed)
            combine[-3] = digest(paths["old"].read_bytes())
            with self.assertRaises(ValueError):
                context_reuse.main(combine)
            for index in (4, 6):
                changed = list(args)
                changed[index] = "wrong"
                with self.assertRaises(ValueError):
                    context_reuse.main(["prepare", *changed])
            for bad in (
                ["combine", *args],
                ["combine", *args, "--parent-predictions", str(paths["old"])],
                ["prepare", *args, "--new-predictions", str(paths["new"])],
                ["prepare", *args, "--parent-predictions", str(paths["old"])],
            ):
                with patch("sys.stderr"), self.assertRaises(SystemExit):
                    context_reuse.main(bad)


if __name__ == "__main__":
    unittest.main()
