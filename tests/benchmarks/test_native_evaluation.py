"""Frozen report selection, calibration isolation, source identity and CLI tests."""

import json
import runpy
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import native_evaluation as evaluation
from benchmarks.rbs.datasets import digest


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "id": str(i),
                "group": str(i),
                "observed": 2 ** (i % 5),
                "partition": partition,
                "subgroups": ["all"],
            }
            for i, partition in enumerate(
                ["development_train"] * 5
                + ["development_validation"] * 5
                + ["final"] * 40
            )
        ]
        self.models = {
            name: [
                {"id": r["id"], "status": "ok", "predicted": r["observed"] * 2}
                for r in self.records
            ]
            for name in ("champion", "baseline", "upstream")
        }
        for row in self.models["baseline"][10:] + self.models["upstream"][10:]:
            row["predicted"] *= 4
        self.models["constant"] = [
            {"id": r["id"], "status": "ok", "predicted": 1} for r in self.records
        ]
        self.config = {
            "champion": "champion",
            "baseline": "baseline",
            "upstream": "upstream",
            "historical": "baseline",
            "original_upstream": "upstream",
            "constant": "constant",
            "final_roster_frozen": True,
            "bootstrap_repetitions": 20,
            "bootstrap_seed": 17,
        }

    def test_development_and_final_gates(self):
        result = evaluation.report(self.records, self.models, self.config)
        self.assertEqual(result["n_evaluated"], 5)
        self.assertEqual(result["champion_contrasts"], {})
        result = evaluation.report(self.records, self.models, self.config, "final")
        self.assertEqual(result["n_evaluated"], 40)
        self.assertEqual(result["descriptive_champion_contrasts"], {})
        self.assertEqual(result["models"]["champion"]["calibration"]["offset_log2"], -1)
        self.assertEqual(result["champion_contrasts"]["baseline"]["mae_log2_gain"], 2)
        self.assertTrue(
            result["champion_contrasts"]["baseline"]["all_prespecified_gates_pass"]
        )
        # Mutating final labels cannot change a training-only calibration.
        for row in self.records[10:]:
            row["observed"] *= 8
        changed = evaluation.report(self.records, self.models, self.config, "final")
        self.assertEqual(
            changed["models"]["champion"]["calibration"]["offset_log2"], -1
        )
        self.assertFalse(
            changed["champion_contrasts"]["baseline"]["all_prespecified_gates_pass"]
        )

    def test_missingness_and_small_strata_are_not_passes(self):
        self.records[10]["observed"] = None
        for row in self.records[10:]:
            row["subgroups"] = [row["id"]]
        result = evaluation.report(self.records, self.models, self.config, "final")
        self.assertFalse(result["champion_contrasts"]["baseline"]["subgroup_gate"])
        self.assertEqual(
            result["models"]["champion"]["evaluation"]["assay_exclusions"],
            {"missing": 1},
        )

    def test_report_rejects_unfrozen_or_invalid_contracts(self):
        for stage in ("unknown", "development_train"):
            with self.assertRaises(ValueError):
                evaluation.report(self.records, self.models, self.config, stage)
        for value in (False, 1, None):
            with self.assertRaises(ValueError):
                evaluation.report(
                    self.records,
                    self.models,
                    {**self.config, "final_roster_frozen": value},
                    "final",
                )
        for models in ({}, {"": []}):
            with self.assertRaises(ValueError):
                evaluation.report(self.records, models, self.config)
        for change in ({"champion": "absent"}, {"upstream": "baseline"}):
            with self.assertRaises(ValueError):
                evaluation.report(self.records, self.models, {**self.config, **change})
        with self.assertRaises(ValueError):
            evaluation.report(self.records[:5], self.models, self.config)
        rows = deepcopy(self.records)
        rows[0]["partition"] = "unknown"
        with self.assertRaises(ValueError):
            evaluation.report(rows, self.models, self.config)
        self.models["champion"].append({"id": "unknown"})
        with self.assertRaises(ValueError):
            evaluation.report(self.records, self.models, self.config)

    def test_constant_reference_has_undefined_rank_and_original_rank_safeguards(self):
        config = {**self.config, "baseline": "constant"}
        result = evaluation.report(self.records, self.models, config, "final")
        contrast = result["champion_contrasts"]["constant"]
        self.assertIsNone(contrast["reference_spearman_common"])
        self.assertIsNone(contrast["spearman_gate"])
        self.assertTrue(contrast["historical_spearman_gate"])
        self.assertTrue(contrast["upstream_spearman_gate"])
        self.assertIn("baseline", result["descriptive_champion_contrasts"])
        self.assertFalse(
            result["descriptive_champion_contrasts"]["baseline"]["confirmatory"]
        )
        with self.assertRaises(ValueError):
            evaluation.report(
                self.records, self.models, {**config, "upstream": "constant"}
            )
        self.models["constant"][0]["predicted"] = 2
        with self.assertRaisesRegex(ValueError, "constant model"):
            evaluation.report(self.records, self.models, config)

    def test_validation_reports_crossed_success_sets_before_selection(self):
        self.records = self.records[:5] + self.records[10:]
        for row in self.records[5:]:
            row["partition"] = "development_validation"
        identities = {r["id"] for r in self.records}
        self.models = {
            name: [r for r in rows if r["id"] in identities]
            for name, rows in self.models.items()
        }
        for row in self.models["baseline"]:
            if row["id"] in {"10", "11"}:
                row.update(status="failed", predicted=None)
        for row in self.models["champion"]:
            if row["id"] == "12":
                row.update(status="failed", predicted=None)
        result = evaluation.report(self.records, self.models, self.config)
        paired = result["historical_common_case_diagnostics"]["champion"]
        self.assertEqual(
            (
                paired["n_historical_success"],
                paired["n_contender_success"],
                paired["n_common_success"],
            ),
            (38, 39, 37),
        )
        self.assertEqual(paired["historical_valid_cases_dropped"], 1)
        self.assertFalse(paired["reference_selection_coverage_eligible"])
        self.assertEqual(paired["historical_common_metrics"]["n_submitted"], 37)
        self.assertEqual(paired["contender_common_metrics"]["mae_log2"], 0)
        for row in self.records[5:]:
            row["observed"] = None
        result = evaluation.report(self.records, self.models, self.config)
        self.assertFalse(
            result["historical_common_case_diagnostics"]["constant"][
                "reference_selection_coverage_eligible"
            ]
        )

    def source(self):
        inputs = [
            {
                "id": str(i),
                "primary_eligible": i != 2,
                "sequence_sha256": str(i),
                "strand": "+",
                "start_codon": "ATG" if i == 0 else "CTG",
                "warnings": []
                if i == 0
                else ["source_uniprot_length_differs_from_current_protein"],
            }
            for i in range(3)
        ]
        raw = json.dumps({"records": inputs}).encode()
        splits = {
            "input_envelope_sha256": digest(raw),
            "records": [
                {
                    "id": r["id"],
                    "primary_eligible": r["primary_eligible"],
                    "sequence_sha256": r["sequence_sha256"],
                    "group": r["id"],
                    "partition": "final",
                }
                for r in inputs
            ],
        }
        outcomes = [
            {"id": r["id"] + c, "input_id": r["id"], "condition": c, "observed": 2}
            for r in inputs
            for c in ("HC", "LC")
        ]
        return raw, outcomes, splits

    def test_native_case_memberships_are_input_only(self):
        raw, outcomes, splits = self.source()
        result = evaluation.native_cases(raw, outcomes, splits)
        self.assertEqual(len(result), 2)
        self.assertIn("start_codon:ATG", result[0]["subgroups"])
        self.assertIn("start_codon:other", result[1]["subgroups"])
        self.assertIn("protein_length:discrepant", result[1]["subgroups"])
        self.assertEqual(result, evaluation.native_cases(raw, outcomes, splits, "LC"))

    def test_source_contract_rejection(self):
        for kind in (
            "condition",
            "hash",
            "identities",
            "duplicate_mapping",
            "unknown_input",
            "unknown_condition",
            "missing",
            "partition",
            "sequence",
            "eligibility",
        ):
            raw, outcomes, splits = self.source()
            condition = "HC"
            if kind == "condition":
                condition = "unknown"
            elif kind == "hash":
                splits["input_envelope_sha256"] = "wrong"
            elif kind == "identities":
                splits["records"].pop()
            elif kind == "duplicate_mapping":
                outcomes.append({**outcomes[0], "id": "different"})
            elif kind == "unknown_input":
                outcomes[0]["input_id"] = "absent"
            elif kind == "unknown_condition":
                outcomes[0]["condition"] = "other"
            elif kind == "missing":
                outcomes.pop()
            elif kind == "partition":
                splits["records"][0]["partition"] = "other"
            elif kind == "sequence":
                splits["records"][0]["sequence_sha256"] = "wrong"
            else:
                splits["records"][0]["primary_eligible"] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evaluation.native_cases(raw, outcomes, splits, condition)

    def test_manifest_cli_checks_every_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def artifact(name, records):
                raw = json.dumps({"records": records}).encode()
                (root / name).write_bytes(raw)
                return {"path": name, "sha256": digest(raw)}

            manifest = {
                "cases": artifact("cases", self.records),
                "configuration": self.config,
                "models": {
                    name: artifact(name, rows) for name, rows in self.models.items()
                },
            }
            path, output = root / "manifest", root / "report"
            path.write_text(json.dumps(manifest))
            with (
                patch.object(
                    sys,
                    "argv",
                    ["native_evaluation", str(path), str(output), "--stage", "final"],
                ),
                self.assertWarns(RuntimeWarning),
            ):
                runpy.run_module(
                    "benchmarks.rbs.native_evaluation", run_name="__main__"
                )
            result = json.loads(output.read_text())
            self.assertEqual(result["manifest_sha256"], digest(path.read_bytes()))
            (root / "champion").write_text("{}")
            with self.assertRaises(ValueError):
                evaluation.main([str(path), str(output), "--stage", "final"])


if __name__ == "__main__":
    unittest.main()
