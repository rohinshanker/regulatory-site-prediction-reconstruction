"""Offline independent arithmetic and optional-runner contract regressions."""

import copy
import io
import json
import math
import runpy
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from benchmarks.promoter import reference_oracle as o
from benchmarks.promoter import reference_run as r

ROOT = Path(__file__).resolve().parents[2] / "benchmarks/promoter"
PARAMETERS = json.loads((ROOT / "reference-parameters.json").read_text())
FIXTURES = json.loads((ROOT / "reference-fixtures.json").read_text())


def source_record(state):
    """Public source-output shape for plumbing tests; no predictor emulation."""
    output = dict(state["terms"], Tx_rate=state["Tx_rate"], TSS=state["tss"])
    output.update(state["features"])
    output.update({k + "_position": v for k, v in state["intervals"].items()})
    return output


class OracleTest(unittest.TestCase):
    def test_all_frozen_states_and_denominators(self):
        total = 0
        for case in FIXTURES["cases"]:
            actual = o.states(
                case["sequence"], case["tss"], PARAMETERS, case["organism"]
            )
            reduced = [
                {k: row[k] for k in ("discriminator", "spacer", "terms", "Tx_rate")}
                for row in actual
            ]
            self.assertEqual(reduced, case["expected_states"])
            total += len(actual)
            chosen = o.winner(actual)
            self.assertEqual(chosen is None, not actual)
        self.assertEqual(total, 212)
        self.assertEqual(
            sum(bool(o.states("A" * 200, t, PARAMETERS)) for t in range(200)), 123
        )

    def test_hand_decimal_homopolymer_terms_and_unused_coefficients(self):
        state = next(
            row
            for row in o.states("A" * 200, 100, PARAMETERS)
            if (row["discriminator"], row["spacer"]) == (6, 17)
        )
        self.assertEqual(state["raw_numericals"][:2], [30, 30])
        self.assertAlmostEqual(state["raw_numericals"][2], -5.6)
        self.assertAlmostEqual(state["raw_numericals"][3], 25.2)
        c = [Decimal(str(v)) for v in PARAMETERS["coefficients"]]
        expected = c[0] + c[64] + c[128] + c[192] + c[256] + c[320]
        expected += Decimal(30) / Decimal(256) * c[339]
        expected += Decimal(30) / Decimal(255) * c[340]
        expected += (
            Decimal("-5.6") / Decimal(str(PARAMETERS["normalizers"][2])) * c[341]
        )
        expected += (
            Decimal("25.2") / Decimal(str(PARAMETERS["normalizers"][3])) * c[342]
        )
        expected += Decimal("-0.0924") + Decimal(str(PARAMETERS["intercept"]))
        self.assertAlmostEqual(state["terms"]["dG_total"], float(expected), places=12)
        self.assertEqual(
            (
                o.winner(o.states("A" * 200, 100, PARAMETERS))["discriminator"],
                o.winner(o.states("A" * 200, 100, PARAMETERS))["spacer"],
            ),
            (6, 17),
        )
        changed = copy.deepcopy(PARAMETERS)
        changed["coefficients"][336:339] = [1e20, -1e20, 1e20]
        self.assertEqual(
            o.states("A" * 200, 100, changed), o.states("A" * 200, 100, PARAMETERS)
        )

    def test_exact_coordinate_and_category_controls(self):
        windows = o.intervals(100, 6, 17)
        self.assertEqual(windows["UP"], [40, 64])
        self.assertEqual(windows["gap"], [64, 65])
        self.assertEqual(windows["hex35"], [65, 71])
        self.assertEqual(windows["extended10"], [85, 87])
        self.assertEqual(windows["ITR"], [100, 120])
        reverse = o.project_reverse(200, 100, windows)
        self.assertEqual((reverse["legacy_key"], reverse["forward_base"]), (100, 99))
        self.assertEqual(reverse["forward_intervals"]["UP"], [136, 160])
        self.assertEqual(reverse["forward_intervals"]["ITR"], [80, 100])
        self.assertEqual(
            [o.kmer_index(word) for word in ("AAA", "AAC", "ACG", "TTT")], [0, 1, 6, 63]
        )
        default = o.states("A" * 200, 100, PARAMETERS)
        self.assertEqual(
            default, o.states("A" * 200, 100, PARAMETERS, "unvalidated organism")
        )
        invitro = o.states("A" * 200, 100, PARAMETERS, "in vitro")
        self.assertEqual(default[0]["terms"], invitro[0]["terms"])
        self.assertNotEqual(default[0]["Tx_rate"], invitro[0]["Tx_rate"])
        self.assertAlmostEqual(
            math.log(invitro[0]["Tx_rate"] / 42),
            -0.81632623 * invitro[0]["terms"]["dG_total"],
        )


class ReferenceRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "upstream/Promoter_Calculator"
        self.directory.mkdir(parents=True)
        self.original = self.directory / "Promoter_Calculator_v1_0.py"
        self.utility = self.directory / "util.py"
        self.original.write_text(
            "\n".join(before for before, _ in r.PRINT_REPLACEMENTS)
        )
        self.utility.write_text("OneHotEncoder(sparse=False)\n" * 2)
        self.manifest = {
            "sources": [
                {"path": str(p.relative_to(self.root)), "sha256": r.sha(p.read_bytes())}
                for p in (self.original, self.utility)
            ]
        }

    def test_hash_gated_compatibility_patch(self):
        sources = r.compatibility_sources(self.root, self.manifest)
        self.assertEqual(sources["util.py"].count("sparse_output=False"), 2)
        for _, after in r.PRINT_REPLACEMENTS:
            self.assertIn(after, sources["Promoter_Calculator_v1_0.py"])
        self.original.write_text("changed")
        with self.assertRaises(ValueError):
            r.compatibility_sources(self.root, self.manifest)
        with self.assertRaises(ValueError):
            r.compatibility_sources(self.root, {"sources": []})
        self.original.write_text(
            "\n".join(before for before, _ in r.PRINT_REPLACEMENTS)
        )
        self.utility.write_text("changed")
        with self.assertRaises(ValueError):
            r.compatibility_sources(self.root, {"sources": []})

    def test_historical_import_restores_module_state(self):
        sources = {
            "util.py": "answer = 12",
            "Promoter_Calculator_v1_0.py": "import util\nanswer = util.answer",
        }
        with patch.dict(sys.modules):
            sys.modules.pop("util", None)
            module = r.historical_module(self.root, sources)
            self.assertEqual(module.answer, 12)
            self.assertNotIn("util", sys.modules)
            old = SimpleNamespace(answer=99)
            sys.modules["util"] = old
            self.assertEqual(r.historical_module(self.root, sources).answer, 12)
            self.assertIs(sys.modules["util"], old)

    def test_output_and_environment_guards(self):
        state = o.states("A" * 78, 58, PARAMETERS)[0]
        actual = source_record(state)
        r.check_state(actual, state)
        for key, value in (
            ("TSS", 59),
            ("dG_total", 99),
            ("UP", "C" * 24),
            ("UP_position", [0, 23]),
        ):
            with self.assertRaises(ValueError):
                r.check_state(dict(actual, **{key: value}), state)
        with self.assertRaises(ValueError):
            r.equal_number(float("nan"), 1)
        fake = SimpleNamespace(__file__=str(self.original))
        manifest = {
            "fork_files": [
                {
                    "path": self.original.name,
                    "sha256": r.sha(self.original.read_bytes()),
                }
            ],
            "distributions": [
                {"name": "toy", "version": "1", "metadata_sha256": r.sha(b"metadata")}
            ],
        }
        distribution = Mock(version="1")
        distribution.read_text.return_value = "metadata"
        with patch.object(
            r.importlib.metadata, "distribution", return_value=distribution
        ):
            r.verify_environment(fake, manifest)
        distribution.version = "2"
        with (
            patch.object(
                r.importlib.metadata, "distribution", return_value=distribution
            ),
            self.assertRaises(ValueError),
        ):
            r.verify_environment(fake, manifest)
        distribution.version = "1"
        distribution.read_text.return_value = "changed"
        with (
            patch.object(
                r.importlib.metadata, "distribution", return_value=distribution
            ),
            self.assertRaises(ValueError),
        ):
            r.verify_environment(fake, manifest)
        self.original.write_text("changed")
        with self.assertRaises(ValueError):
            r.verify_environment(fake, manifest)

    def test_parameter_conversion_identity(self):
        module = Mock()
        model = module.Promoter_Calculator.return_value
        model.model.tolist.return_value = PARAMETERS["coefficients"]
        model.inters.tolist.return_value = [PARAMETERS["intercept"]]
        module.util = SimpleNamespace(**PARAMETERS["tables"])
        r.verify_parameters(module, module, PARAMETERS)
        for which in ("coefficients", "intercept", "tables"):
            changed = copy.deepcopy(PARAMETERS)
            if which == "coefficients":
                changed[which][336] += 1
            elif which == "intercept":
                changed[which] += 1
            else:
                changed[which]["groove_access"]["AA"] += 1
            with self.assertRaises(ValueError):
                r.verify_parameters(module, module, changed)

    def modules(self, case):
        states = o.states(case["sequence"], case["tss"], PARAMETERS, case["organism"])
        tss = case["tss"]
        rows = {(s["discriminator"], s["spacer"]): source_record(s) for s in states}
        chosen = o.winner(states)
        minima = {tss: source_record(chosen)} if chosen else {}
        old = Mock()
        new = Mock()
        old.predict.return_value = (minima, {tss: rows})
        new.predict.return_value = (
            minima,
            {tss: {(chosen["discriminator"], chosen["spacer"]): source_record(chosen)}}
            if chosen
            else {},
        )
        new.worker.return_value = [[tss, d, s, value] for (d, s), value in rows.items()]
        old_module = Mock(Promoter_Calculator=Mock(return_value=old))
        new_module = Mock(Promoter_Calculator=Mock(return_value=new))
        old_module.linear_free_energy_model.side_effect = [
            (0, s["terms"]["dG_apparent"]) for s in states
        ]
        new_module.linear_free_energy_model.side_effect = [
            SimpleNamespace(dg_apparent=s["terms"]["dG_apparent"]) for s in states
        ]
        return old_module, new_module, old, new

    def test_source_state_and_selection_join(self):
        for case in (FIXTURES["cases"][0], FIXTURES["cases"][2]):
            old_module, new_module, _, _ = self.modules(case)
            result = r.execute_fixtures(
                old_module, new_module, {"cases": [case]}, PARAMETERS
            )
            self.assertEqual(result[0]["states_checked"], len(case["expected_states"]))
        case = FIXTURES["cases"][0]
        for alteration in (
            "fixture",
            "historical_count",
            "fork_count",
            "order",
            "all_states",
        ):
            old_module, new_module, old, new = self.modules(case)
            changed = copy.deepcopy(case)
            if alteration == "fixture":
                changed["expected_states"] = []
            elif alteration == "historical_count":
                old.predict.return_value[1][case["tss"]].clear()
            elif alteration == "fork_count":
                new.worker.return_value.pop()
            elif alteration == "order":
                new.worker.return_value[0][1] = 9
            else:
                new.predict.return_value[1][case["tss"]].clear()
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                r.execute_fixtures(
                    old_module, new_module, {"cases": [changed]}, PARAMETERS
                )
        case = FIXTURES["cases"][2]
        old_module, new_module, old, _ = self.modules(case)
        old.predict.return_value[0][57] = {}
        with self.assertRaises(ValueError):
            r.execute_fixtures(old_module, new_module, {"cases": [case]}, PARAMETERS)

    def test_legacy_behavior_guards(self):
        for failure in (None, "reverse", "gap"):
            module = Mock()
            model = module.Promoter_Calculator.return_value
            model.output.return_value = {
                "Forward_Predictions_per_TSS": {100: {"Tx_rate": 3}},
                "Reverse_Predictions_per_TSS": {101: {"TSS": 99}},
            }
            module.scan_arbitrary.return_value = (None, {(1, 2, 57): {}})
            if failure == "reverse":
                model.output.return_value["Reverse_Predictions_per_TSS"] = {}
            elif failure == "gap":
                module.scan_arbitrary.return_value = (None, {})
            if failure:
                with self.assertRaises(ValueError):
                    r.source_behavior_checks(module, module)
            else:
                result = r.source_behavior_checks(module, module)
                self.assertEqual(
                    result["barrick_unmodified"]["arbitrary_corrected_tss"], 58
                )

    def test_cli_exclusive_output_and_module_entry(self):
        output = self.root / "result.json"
        patches = (
            patch.object(
                r, "compatibility_sources", return_value={"synthetic": "source"}
            ),
            patch.object(r, "historical_module", return_value=Mock()),
            patch.object(r.importlib, "import_module", return_value=Mock()),
            patch.object(r, "verify_environment"),
            patch.object(r, "verify_parameters"),
            patch.object(r, "execute_fixtures", return_value=[{"states_checked": 1}]),
            patch.object(r, "source_behavior_checks", return_value={}),
        )
        from contextlib import ExitStack

        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            stack.enter_context(patch.object(sys, "stdout", io.StringIO()))
            r.main([str(self.root), str(output)])
            with self.assertRaises(FileExistsError):
                r.main([str(self.root), str(output)])
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertFalse(
            json.loads(output.read_text())["biological_accuracy_evaluated"]
        )
        # Entry dispatch without requiring optional source dependencies in CI.
        with (
            patch.object(sys, "argv", ["reference_run", "--help"]),
            patch.object(sys, "stdout", io.StringIO()),
            self.assertRaises(SystemExit) as stopped,
        ):
            runpy.run_module("benchmarks.promoter.reference_run", run_name="__main__")
        self.assertEqual(stopped.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
