"""Public-interface bridge tests; synthetic outputs contain no fitted internals."""

import copy
import hashlib
import io
import json
import runpy
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.rbs import wave4_predict as p


class PredictionBridgeTest(unittest.TestCase):
    def setUp(self):
        self.request = dict(
            id="toy",
            sequence="CCCATGAAA",
            start_positions=[3],
            strand="+",
            anti_sd="ACCUCCUUA",
            temperature_c=37,
            host="synthetic",
        )
        self.args = Namespace(
            kind="mechanistic",
            engine="synthetic-root",
            profile="historical",
            backend_variant="synthetic-backend",
            expected_model="toy-model",
            expected_artifact="toy-artifact",
            model="synthetic-model.json",
            rebeca_root="synthetic-rebeca",
            seconds=60,
        )
        self.supplied = dict(self.request, oriented_sequence=self.request["sequence"])
        self.core = dict(
            id="toy",
            status="ok",
            reason=None,
            input=self.supplied,
            model={"id": "toy-model"},
            sites=[dict(oriented_start=3, status="ok", tir=12.5, reason=None)],
        )
        self.learned = dict(
            id="toy",
            status="ok",
            reason=None,
            input=self.supplied,
            artifact_sha256="toy-artifact",
            feature_kind="sequence-v1",
            score_scale="log2_assay_response",
            mechanistic_reference=None,
            score_log2=-1.25,
            start_codon=dict(start=3, end=6, strand="+"),
        )

    def normalized(self, result, kind="mechanistic"):
        return p.normalize_core(result, self.request, kind, "toy-model", "toy-artifact")

    def test_request_guards(self):
        p.input_check(self.request)
        for key, value in (
            ("id", 1),
            ("id", ""),
            ("sequence", 3),
            ("sequence", "NNN"),
            ("start_positions", (3,)),
            ("start_positions", []),
            ("start_positions", [True]),
            ("start_positions", [-1]),
            ("start_positions", [7]),
            ("strand", "-"),
            ("anti_sd", "ACCU"),
            ("temperature_c", 36),
            ("temperature_c", "37"),
            ("host", None),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                p.input_check(dict(self.request, **{key: value}))

    def test_admission_manifest_preserves_pinned_source_identities(self):
        root = Path(__file__).resolve().parents[2]
        admission = json.loads(
            (root / "benchmarks/rbs/wave4-comparator-admission.json").read_text()
        )
        for name, expected in admission["manifest_pins"].items():
            self.assertEqual(
                hashlib.sha256((root / name).read_bytes()).hexdigest(), expected
            )
        self.assertEqual(admission["input_features"]["Cambray2018"]["n_unique_utrs"], 1)
        self.assertEqual(
            admission["input_features"]["Kuo2020"]["contexts"],
            {"arti": 87, "dmsC": 87, "fepB": 87},
        )
        smokes = admission["synthetic_bridge_smokes"]
        self.assertEqual(len(smokes), 4)
        self.assertEqual(len({r["input_sha256"] for r in smokes}), 1)
        self.assertTrue(all(r["status"] == "ok" for r in smokes))

    def test_runtime_identity_and_input_guards(self):
        self.assertEqual(self.normalized(self.core)["predicted"], 12.5)
        changed = copy.deepcopy(self.core)
        changed["input"]["start_positions"] = (3,)
        changed["input"]["oriented_sequence"] = "CCCAUGAAA"
        self.assertEqual(self.normalized(changed)["predicted"], 12.5)
        for key, value in (("id", "different"), ("status", "mystery")):
            with self.assertRaises(ValueError):
                self.normalized(dict(self.core, **{key: value}))
        for key, value in (
            ("oriented_sequence", "AAAATGAAA"),
            ("start_positions", [0]),
            ("strand", "-"),
            ("anti_sd", "ACCU"),
            ("temperature_c", 30),
            ("host", "different"),
        ):
            changed = copy.deepcopy(self.core)
            changed["input"][key] = value
            with self.assertRaises(ValueError):
                self.normalized(changed)
        with self.assertRaises(ValueError):
            self.normalized(dict(self.core, model={"id": "different"}))
        for sites in (
            self.core["sites"] * 2,
            [dict(self.core["sites"][0], oriented_start=0)],
            [],
            [dict(self.core["sites"][0], status="failed")],
            [dict(self.core["sites"][0], tir=None)],
            [dict(self.core["sites"][0], tir=0)],
        ):
            with self.assertRaises(ValueError):
                self.normalized(dict(self.core, sites=sites))
        with self.assertRaises(ValueError):
            self.normalized(dict(self.core, input=None))
        for sites in (
            [],
            [dict(self.core["sites"][0], tir=None, reason="site failed")],
        ):
            result = self.normalized(dict(self.core, status="failed", sites=sites))
            self.assertIsNone(result["predicted"])
        with self.assertRaises(ValueError):
            self.normalized(dict(self.core, status="failed"))
        result = self.normalized(
            dict(self.core, status="invalid_input", input=None, sites=[])
        )
        self.assertIsNone(result["predicted"])

    def test_learned_output_contract(self):
        self.assertEqual(self.normalized(self.learned, "learned")["predicted"], -1.25)
        for key, value in (
            ("artifact_sha256", "other"),
            ("feature_kind", "new"),
            ("score_scale", "exp"),
            ("mechanistic_reference", {}),
            ("start_codon", {"start": 3, "end": 5, "strand": "+"}),
            ("score_log2", float("nan")),
            ("score_log2", None),
        ):
            with self.assertRaises(ValueError):
                self.normalized(dict(self.learned, **{key: value}), "learned")
        failed = dict(self.learned, status="failed", score_log2=None, start_codon=None)
        self.assertIsNone(self.normalized(failed, "learned")["predicted"])

    def test_external_comparators_use_unchanged_public_adapter(self):
        for kind in ("ostir", "rebeca"):
            self.args.kind = kind
            engine = Mock()
            raw = dict(status="ok", predicted=3, native_log_prediction=1)
            with (
                patch.object(
                    p.comparators, kind + "_engine", return_value=engine
                ) as build,
                patch.object(p.comparators, "predict", return_value=raw) as predict,
            ):
                result, upstream = p.infer(self.args, self.request)
            self.assertEqual(result, dict(status="ok", predicted=3, reason=""))
            self.assertIs(upstream, raw)
            predict.assert_called_once_with(dict(self.request, start=3), kind, engine)
            if kind == "rebeca":
                build.assert_called_once_with("synthetic-rebeca")
            else:
                build.assert_called_once_with()

    def test_mechanistic_public_api_and_frozen_variant(self):
        backend = Mock(identity={"variant": "synthetic-backend"})
        with (
            patch("regsite.backend.RnaStructure.open", return_value=backend) as opened,
            patch("regsite.rbs.predict", return_value=self.core) as predicted,
        ):
            result, raw = p.infer(self.args, self.request)
            self.assertEqual(result["predicted"], 12.5)
            self.assertIs(raw, self.core)
            opened.assert_called_once_with("synthetic-root")
            predicted.assert_called_once_with(
                self.request, backend, profile="historical", seconds=60
            )
            backend.identity["variant"] = "changed"
            with self.assertRaises(ValueError):
                p.infer(self.args, self.request)

    def test_learned_cli_and_failures(self):
        self.args.kind = "learned"

        def cli(argv):
            from pathlib import Path

            self.assertEqual(json.loads(Path(argv[1]).read_text()), self.request)
            self.assertEqual(argv[0], "synthetic-model.json")
            print(json.dumps({"results": [self.learned]}))
            return 0

        with patch("regsite.learned_cli.main", side_effect=cli):
            result, _ = p.infer(self.args, self.request)
        self.assertEqual(result["predicted"], -1.25)
        with patch("regsite.learned_cli.main", return_value=2):
            with self.assertRaises(ValueError):
                p.infer(self.args, self.request)

        def bad_count(argv):
            print('{"results": []}')
            return 1

        with patch("regsite.learned_cli.main", side_effect=bad_count):
            with self.assertRaises(ValueError):
                p.infer(self.args, self.request)

    def test_cli_identity_and_entrypoint(self):
        packet = json.dumps(self.request).encode()
        incoming = Mock(buffer=io.BytesIO(packet))
        raw = {"synthetic": True}
        result = dict(status="ok", predicted=2, reason="")
        with (
            patch.object(p, "infer", return_value=(result, raw)),
            patch.object(sys, "stdin", incoming),
            patch.object(sys, "stdout", new_callable=io.StringIO) as out,
        ):
            p.main(["ostir"])
        actual = json.loads(out.getvalue())
        self.assertEqual(actual["input_sha256"], hashlib.sha256(packet).hexdigest())
        self.assertEqual(actual["upstream_result"], raw)
        for argv in (
            ["mechanistic"],
            ["ostir", "--seconds", "nan"],
            ["ostir", "--seconds", "0"],
        ):
            with (
                patch.object(sys, "stderr", io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                p.main(argv)
        with (
            patch.object(sys, "argv", ["wave4_predict", "ostir"]),
            patch.object(sys, "stdin", Mock(buffer=io.BytesIO(packet))),
            patch.object(sys, "stdout", io.StringIO()),
            patch.object(p.comparators, "ostir_engine", return_value=Mock()),
            patch.object(p.comparators, "predict", return_value=result),
        ):
            runpy.run_module("benchmarks.rbs.wave4_predict", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
