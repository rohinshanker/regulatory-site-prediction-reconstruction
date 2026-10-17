"""Synthetic end-to-end evaluation and pre-label integrity-failure checks."""

import copy
import io
import json
import runpy
import sys
import unittest
from unittest.mock import patch

import test_wave4_collect as collection_tests

from benchmarks.rbs import wave4_collect as c
from benchmarks.rbs import wave4_evaluate as e
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.new_data import public_split


class EvaluationTest(unittest.TestCase):
    def setUp(self):
        h = collection_tests.CollectionTest()
        h.setUp()
        self.addCleanup(h.doCleanups)
        self.h = h
        for row in h.inputs["records"]:
            if row["study"] == "Kuo2020":
                row["context"] = "arti"
        h.input_path.write_bytes(c.encoded(h.inputs))
        h.split_path.write_bytes(c.encoded(public_split(h.inputs)))
        h.receipt.update(
            inputs=h.pin(h.input_path),
            split=h.pin(h.split_path),
            software_resource_gates=True,
        )
        self.outcomes = [
            dict(
                id=r["id"],
                observed=None if r["id"] == "3" else float(r["id"]),
                facilitated_observed=123456,
            )
            for r in h.inputs["records"]
        ]
        self.outcome_path = h.root / "outcomes.json"
        self.outcome_path.write_bytes(c.encoded(self.outcomes))
        h.protocol.update(
            input_file_sha256=h.receipt["inputs"]["sha256"],
            split_file_sha256=h.receipt["split"]["sha256"],
            private_outcomes_sha256=digest(self.outcome_path.read_bytes()),
        )
        h.protocol["primary_endpoint"].update(n_inputs=4, n_observed=3, n_blocks=2)
        h.protocol["secondary_endpoints"].update(
            Kuo2020=["arti"], n_inputs_per_context=2
        )
        h.protocol["bootstrap"].update(
            draws=100,
            minimum_usable_draws=10,
            minimum_common_rows=2,
            minimum_common_blocks=2,
        )
        h.protocol["subgroups"]["minimum_common_rows_to_display_rank_difference"] = 2
        h.script.write_text(
            "import sys,json,hashlib\nraw=sys.stdin.buffer.read();r=json.loads(raw)\n"
            "print(json.dumps(dict(id=r['id'],input_sha256=hashlib.sha256(raw).hexdigest(),"
            "status='ok',predicted=int(sys.argv[1])*int(r['id']),reason='')))\n"
        )
        for config, factor in zip(h.receipt["configurations"], [-1, 1], strict=True):
            config["command"] = [*config["command"][:2], str(factor)]
            config["artifacts"] = [h.pin(h.script)]
        h.receipt["configurations"].append({"id": "constant", "kind": "constant"})
        h.save()
        self.directory = h.root / "collection"
        self.collection = c.collect(h.receipt_path, self.directory)
        self.manifest = {
            name: h.pin(path)
            for name, path in dict(
                protocol=h.protocol_path,
                inputs=h.input_path,
                split=h.split_path,
                receipt=h.receipt_path,
                collection=self.directory / "collection.json",
                outcomes=self.outcome_path,
            ).items()
        }

    def test_end_to_end_and_explicit_incomplete_gate(self):
        result = e.evaluate(self.manifest)
        self.assertTrue(result["primary"]["advancement"]["advance"])
        self.assertEqual(result["primary"]["comparison"]["rank_gain"], 2)
        self.assertEqual(result["primary"]["models"]["contender"]["n_observed"], 3)
        self.assertIsNone(result["primary"]["models"]["constant"]["spearman_rho"])
        self.assertFalse(result["facilitated_cambray_evaluated"])
        self.assertEqual(
            result["descriptive_coding_gc_strata"]["high"]["primary_pair"]["rank_gain"],
            2,
        )
        changed = copy.deepcopy(self.collection)
        changed["complete"] = False
        report = e.report(
            self.h.inputs, self.outcomes, changed, self.h.receipt, self.h.protocol
        )
        self.assertFalse(report["primary"]["advancement"]["advance"])
        self.assertIn(
            "collection_incomplete", report["primary"]["advancement"]["reasons"]
        )
        changed = copy.deepcopy(self.outcomes)
        for row in changed:
            row["facilitated_observed"] = -987654321
        original = e.report(
            self.h.inputs,
            self.outcomes,
            self.collection,
            self.h.receipt,
            self.h.protocol,
        )
        self.assertEqual(
            original,
            e.report(
                self.h.inputs, changed, self.collection, self.h.receipt, self.h.protocol
            ),
        )

    def test_denominator_and_roster_guards(self):
        bad = copy.deepcopy(self.collection)
        del bad["records_by_configuration"]["constant"]
        with self.assertRaises(ValueError):
            e.report(self.h.inputs, self.outcomes, bad, self.h.receipt, self.h.protocol)
        for key in ("n_inputs", "n_observed", "n_blocks"):
            spec = copy.deepcopy(self.h.protocol)
            spec["primary_endpoint"][key] += 1
            with self.assertRaises(ValueError):
                e.report(
                    self.h.inputs, self.outcomes, self.collection, self.h.receipt, spec
                )
        spec = copy.deepcopy(self.h.protocol)
        spec["secondary_endpoints"]["n_inputs_per_context"] = 3
        with self.assertRaises(ValueError):
            e.report(
                self.h.inputs, self.outcomes, self.collection, self.h.receipt, spec
            )

    def test_gc_and_small_or_constant_points(self):
        for sequence, label in (
            ("ATGAAAA", "low"),
            ("ATGGCAA", "middle"),
            ("ATGGGGC", "high"),
        ):
            self.assertEqual(e.gc_stratum({"sequence": sequence, "start": 0}), label)
        reference = [
            dict(id="a", observed=1, predicted=2, status="ok"),
            dict(id="b", observed=2, predicted=1, status="ok"),
        ]
        contender = [dict(reference[0], predicted=1), dict(reference[1], predicted=2)]
        self.assertEqual(e.common_point(reference, contender, 2)["rank_gain"], 2)
        self.assertIsNone(e.common_point(reference, contender, 3)["rank_gain"])
        self.assertIsNone(
            e.common_point(reference, [dict(r, predicted=1) for r in contender], 2)[
                "rank_gain"
            ]
        )
        self.assertIsNone(
            e.common_point([dict(r, predicted=1) for r in reference], contender, 2)[
                "rank_gain"
            ]
        )
        self.assertEqual(
            e.common_point(
                reference,
                [dict(r, status="failed", predicted=None) for r in contender],
                2,
            )["n_common_measured"],
            0,
        )

    def test_per_job_artifact_checks(self):
        for config_missing in (True, False):
            bad = copy.deepcopy(self.collection)
            if config_missing:
                del bad["records_by_configuration"]["constant"]
            else:
                bad["records_by_configuration"]["constant"].pop()
            with self.assertRaises(ValueError):
                e.audit_prediction_receipts(
                    self.h.inputs, bad, self.h.receipt, self.directory
                )
        for key in ("input_sha256", "configuration_sha256"):
            bad = copy.deepcopy(self.collection)
            bad["records_by_configuration"]["constant"][0][key] = "wrong"
            with self.assertRaises(ValueError):
                e.audit_prediction_receipts(
                    self.h.inputs, bad, self.h.receipt, self.directory
                )
        path = self.directory / "job-000000.json"
        raw = path.read_bytes()
        path.write_text("{}")
        with self.assertRaises(ValueError):
            e.audit_prediction_receipts(
                self.h.inputs, self.collection, self.h.receipt, self.directory
            )
        path.write_bytes(raw)
        path = self.directory / "job-000000.stdout"
        path.write_text("altered")
        with self.assertRaises(ValueError):
            e.audit_prediction_receipts(
                self.h.inputs, self.collection, self.h.receipt, self.directory
            )

    def test_freeze_failures_precede_label_access(self):
        protocol = self.h.protocol
        inputs = self.h.inputs
        split = public_split(inputs)
        receipt = self.h.receipt
        collection = self.collection
        variants = []
        for field in (
            "input_file_sha256",
            "split_file_sha256",
            "private_outcomes_sha256",
        ):
            p = copy.deepcopy(protocol)
            p[field] = "wrong"
            variants.append([p, inputs, split, receipt, collection])
        s = copy.deepcopy(split)
        s["selection_seed"] = "wrong"
        variants.append([protocol, inputs, s, receipt, collection])
        for field in ("freeze_sha256", "protocol_sha256", "input_sha256"):
            data = copy.deepcopy(collection)
            data[field] = "wrong"
            variants.append([protocol, inputs, split, receipt, data])
        for field in ("protocol", "inputs"):
            r = copy.deepcopy(receipt)
            r[field]["sha256"] = "wrong"
            data = copy.deepcopy(collection)
            data["freeze_sha256"] = digest(c.encoded(r))
            variants.append([protocol, inputs, split, r, data])
        for field, value in (
            ("evaluation_authorized", False),
            ("acknowledgements", {"A_protocol": "", "B_candidate": "ok"}),
        ):
            r = copy.deepcopy(receipt)
            r[field] = value
            data = copy.deepcopy(collection)
            data["freeze_sha256"] = digest(c.encoded(r))
            variants.append([protocol, inputs, split, r, data])
        for values in variants:
            with patch.object(
                e, "checked_bytes", side_effect=[c.encoded(v) for v in values]
            ) as read:
                with self.assertRaises(ValueError):
                    e.evaluate(self.manifest)
                self.assertEqual(read.call_count, 5)

    def test_cli_emits_aggregate_summary_only(self):
        path = self.h.root / "evaluation.json"
        path.write_bytes(c.encoded(self.manifest))
        output = self.h.root / "report.json"
        with patch("sys.stdout", new_callable=io.StringIO) as printed:
            e.main([str(path), str(output)])
        self.assertEqual(
            set(json.loads(printed.getvalue())), {"advance", "aggregate_sha256"}
        )
        self.assertTrue(json.loads(output.read_text())["panel_consumed"])
        with (
            patch.object(
                sys,
                "argv",
                ["wave4_evaluate", str(path), str(self.h.root / "module.json")],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            runpy.run_module("benchmarks.rbs.wave4_evaluate", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
