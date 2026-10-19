"""Synthetic frozen-plan collection; never invokes Promoter or folding."""

import contextlib
import copy
import io
import json
import resource
import runpy
import signal
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from benchmarks.promoter import collect as c
from benchmarks.promoter import runtime_adapter as a
from benchmarks.promoter.native_inputs import canonical_bytes, digest
from tests.benchmarks.test_promoter_runtime_adapter import (
    CEILINGS,
    Fixture,
    query_document,
)


class FixtureMixin:
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.fixture = Fixture(
            queries=query_document({"fake": (200, "circular")}, width=100),
            limits=dict(CEILINGS, records_per_batch=1),
        )
        self.plan = self.root / "plan.json"
        self.plan.write_bytes(canonical_bytes(self.fixture.plan))
        self.admission = self.root / "admission.json"
        self.admission.write_bytes(b'{"opaque synthetic approval":"reviewed"}')
        self.executable = self.root / "fake-cli"
        self.executable.write_text("#!/bin/sh\nexit 2\n")
        self.executable.chmod(0o700)
        self.output = self.root / "private"
        self.calls = []

    def invoke(self, **overrides):
        options = dict(
            plan_path=self.plan,
            plan_sha256=digest(self.plan.read_bytes()),
            executable=self.executable,
            executable_sha256=digest(self.executable.read_bytes()),
            admission_path=self.admission,
            admission_sha256=digest(self.admission.read_bytes()),
            acknowledge_reviewed_admission=True,
            stage_seconds=3600.0,
            process_grace_seconds=0.0,
            output=self.output,
            runner=self.fake,
        )
        options.update(overrides)
        return c.collect(**options)

    def fake(self, argv, **kwargs):
        index = len(self.calls)
        self.calls.append((argv, kwargs))
        result = self.fixture.result(index)
        kwargs["stdout"].write(json.dumps(result).encode())
        kwargs["stderr"].write(b"private diagnostic")
        return subprocess.CompletedProcess(argv, 0)

    def documents(self):
        return tuple(
            json.loads((self.output / name).read_bytes())
            for name in (
                "collection.json",
                "execution-receipt.json",
            )
        )

    def rewrite(self, mutate):
        plan = copy.deepcopy(self.fixture.plan)
        mutate(plan)
        self.plan.write_bytes(canonical_bytes(plan))


class CollectionTest(FixtureMixin, unittest.TestCase):
    def test_success_exact_requests_argv_receipt_and_adapter(self):
        self.assertTrue(self.invoke())
        collection, receipt = self.documents()
        self.assertEqual(set(collection), set(a.COLLECTION_KEYS))
        self.assertEqual(
            receipt["admission_sha256"], digest(self.admission.read_bytes())
        )
        self.assertEqual(
            receipt["executable_sha256"], digest(self.executable.read_bytes())
        )
        self.assertEqual(
            receipt["manifest_sha256"], self.fixture.plan["manifest_sha256"]
        )
        self.assertIn("not verified", receipt["package_consistency"])
        self.assertIsNone(receipt["validation_failure"])
        self.assertEqual(
            receipt["collection_sha256"],
            digest((self.output / "collection.json").read_bytes()),
        )
        files = {}
        for index, (entry, detail) in enumerate(
            zip(collection["batches"], receipt["batches"], strict=True)
        ):
            self.assertEqual(set(entry), set(a.COLLECTED_BATCH_KEYS))
            request = self.output / f"request-{index:06d}.json"
            self.assertEqual(
                request.read_bytes(), a.plan_request_bytes(self.fixture.plan, index)
            )
            expected = [
                str(self.executable),
                str(request),
                "--format",
                "json",
                "--seconds-per-record",
                "30.0",
                "--seconds-per-batch",
                "300.0",
            ]
            self.assertEqual(detail["argv"], expected)
            self.assertEqual(self.calls[index][0], expected)
            self.assertFalse(self.calls[index][1]["shell"])
            self.assertFalse(self.calls[index][1]["check"])
            self.assertEqual(detail["timeout_seconds"], 300.0)
            self.assertGreaterEqual(detail["duration_seconds"], 0)
            self.assertEqual(detail["status"], "completed")
            stdout = (self.output / detail["stdout"]["path"]).read_bytes()
            files[digest(stdout)] = stdout
            self.assertEqual(detail["stdout"]["sha256"], entry["result_sha256"])
            self.assertEqual(detail["stdout"]["bytes"], len(stdout))
        scores, _ = self.fixture.adapt(collection, files)
        self.assertEqual(
            len(scores["results"]), self.fixture.plan["totals"]["n_requests"]
        )
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        for path in self.output.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.output.iterdir()}
        )

    def test_optional_flags_and_null_host(self):
        self.fixture = Fixture(
            queries=self.fixture.queries,
            host=None,
            limits=dict(CEILINGS, records_per_batch=1),
            cli_calibration="ecoli_mg1655",
            cli_states="selected",
        )
        self.plan.write_bytes(canonical_bytes(self.fixture.plan))

        # Exit 2 has no result contract, so the fake doesn't need host calibration.
        def runner(argv, **kwargs):
            self.calls.append(argv)
            return subprocess.CompletedProcess(argv, 2)

        self.assertTrue(self.invoke(runner=runner))
        self.assertEqual(
            self.calls[0][-4:],
            ["--calibration", "ecoli_mg1655", "--states", "selected"],
        )

    def test_valid_exit_one_and_process_failures_continue(self):
        codes = [1, 2, 7, -signal.SIGTERM]

        def runner(argv, **kwargs):
            index = len(self.calls)
            self.calls.append(argv)
            code = codes[index]
            if index == 0:
                request_id = self.fixture.plan["batches"][0]["records"][0]["request_id"]
                result = self.fixture.result(
                    0, {request_id: {"status": "invalid_input"}}
                )
                kwargs["stdout"].write(json.dumps(result).encode())
            else:
                kwargs["stdout"].write(b"failed raw output")
            return subprocess.CompletedProcess(argv, code)

        self.assertTrue(self.invoke(runner=runner))
        collection, receipt = self.documents()
        self.assertEqual([row["exit_code"] for row in collection["batches"]], codes)
        self.assertEqual(
            [row["status"] for row in collection["batches"]],
            ["completed", "setup_failed", "execution_failed", "execution_failed"],
        )
        self.assertTrue(
            all(row["result_sha256"] is None for row in collection["batches"][1:])
        )
        self.assertEqual(
            [row["reason"] for row in receipt["batches"]],
            ["record_failure", "setup_failed", "process_exit", "process_signal"],
        )
        self.assertIsNone(receipt["stop_reason"])

    def test_timeout_launch_error_and_preexec_error_stop(self):
        for error, code, reason in (
            (subprocess.TimeoutExpired("fake", 1), -9, "timeout"),
            (OSError("cannot launch"), -1, "launch_error"),
            (subprocess.SubprocessError("preexec failed"), -1, "launch_error"),
        ):
            with self.subTest(error=error):
                self.output = self.root / reason / type(error).__name__
                self.output.parent.mkdir(exist_ok=True)

                def runner(argv, error=error, **kwargs):
                    kwargs["stdout"].write(b"partial private output")
                    raise error

                self.assertTrue(self.invoke(runner=runner))
                collection, receipt = self.documents()
                self.assertEqual(collection["batches"][0]["exit_code"], code)
                self.assertEqual(receipt["stop_reason"], reason)
                self.assertEqual(receipt["batches"][0]["stdout"]["bytes"], 22)
                self.assertTrue(
                    all(row["status"] == "not_run" for row in collection["batches"][1:])
                )

    def test_monotonic_stage_and_process_timeout_bounds(self):
        times = iter([0, 2, 2, 3, 10, 10])
        self.assertTrue(
            self.invoke(
                stage_seconds=10, process_grace_seconds=5, clock=lambda: next(times)
            )
        )
        collection, receipt = self.documents()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1]["timeout"], 8)
        self.assertEqual(receipt["stop_reason"], "stage_expired")
        self.assertEqual(collection["batches"][1]["status"], "not_run")
        self.assertEqual(receipt["batches"][0]["duration_seconds"], 1)

    def test_batch_budget_plus_grace(self):
        self.assertTrue(self.invoke(process_grace_seconds=60))
        self.assertEqual(self.calls[0][1]["timeout"], 360)

    def test_stage_expired_before_first_launch(self):
        times = iter([0, 1, 1])
        self.assertTrue(self.invoke(stage_seconds=1, clock=lambda: next(times)))
        collection, receipt = self.documents()
        self.assertFalse(self.calls)
        self.assertEqual(receipt["stop_reason"], "stage_expired")
        self.assertTrue(
            all(row["status"] == "not_run" for row in collection["batches"])
        )

    def test_malformed_completed_output_stops_without_reinterpreting(self):
        for raw, code in (
            (b"not JSON", 0),
            (b"\xff", 0),
            (b"[]", 0),
            (b'{"schema_version":1,"model":{},"batch":{},"results":[]}', 0),
            (json.dumps(self.fixture.result(0)).encode(), 1),
        ):
            with self.subTest(raw=raw[:30], code=code):
                self.output = self.root / f"malformed-{len(list(self.root.iterdir()))}"
                runner = mock.Mock(
                    side_effect=lambda argv, raw=raw, code=code, **kw: (
                        kw["stdout"].write(raw),
                        subprocess.CompletedProcess(argv, code),
                    )[1]
                )
                self.assertFalse(self.invoke(runner=runner))
                collection, receipt = self.documents()
                runner.assert_called_once()
                first = collection["batches"][0]
                self.assertEqual(
                    (first["status"], first["exit_code"], first["result_sha256"]),
                    ("completed", code, digest(raw)),
                )
                self.assertEqual((self.output / "stdout-000000.bin").read_bytes(), raw)
                self.assertTrue(receipt["validation_failure"])
                self.assertEqual(receipt["stop_reason"], "collector_validation_failed")
                self.assertTrue(
                    all(row["status"] == "not_run" for row in collection["batches"][1:])
                )

    def test_wire_and_authoritative_result_caps(self):
        result = self.fixture.result(0)
        raw = json.dumps(result, separators=(",", ":")).encode()
        for limit, message in (
            (16, "Result exceeds"),
            (len(raw) + 64, "Authoritative"),
        ):
            self.output = self.root / f"cap-{limit}"
            self.fixture.manifest["settings"]["runtime_limits"][
                "max_result_json_bytes"
            ] = limit
            self.fixture.plan = a.prepare(self.fixture.queries, self.fixture.manifest)
            # Rebuild public identities after changing the frozen effective limit.
            result = self.fixture.result(0)
            wire = json.dumps(result, separators=(",", ":")).encode()
            self.plan.write_bytes(canonical_bytes(self.fixture.plan))

            def runner(argv, wire=wire, **kw):
                kw["stdout"].write(wire)
                return subprocess.CompletedProcess(argv, 0)

            self.assertFalse(self.invoke(runner=runner))
            _, receipt = self.documents()
            self.assertIn(message, receipt["validation_failure"])

    def test_exact_authoritative_result_cap_is_allowed(self):
        limit = 64 * 1024 * 1024
        while True:
            self.fixture.manifest["settings"]["runtime_limits"][
                "max_result_json_bytes"
            ] = limit
            self.fixture.plan = a.prepare(self.fixture.queries, self.fixture.manifest)
            results = [
                (
                    json.dumps(self.fixture.result(i), sort_keys=True, indent=2) + "\n"
                ).encode()
                for i in range(len(self.fixture.plan["batches"]))
            ]
            size = max(map(len, results))
            if size == limit:
                break
            limit = size
        self.plan.write_bytes(canonical_bytes(self.fixture.plan))

        def runner(argv, **kwargs):
            index = len(self.calls)
            self.calls.append(argv)
            kwargs["stdout"].write(results[index])
            return subprocess.CompletedProcess(argv, 0)

        self.assertTrue(self.invoke(runner=runner))
        collection, receipt = self.documents()
        self.assertIsNone(receipt["validation_failure"])
        self.assertTrue(
            all(row["status"] == "completed" for row in collection["batches"])
        )

    def test_output_storage_caps_and_signal(self):
        for stream, code in (("stdout", 0), ("stderr", 2), ("stdout", -signal.SIGXFSZ)):
            self.output = self.root / f"storage-{stream}-{code}"

            def runner(argv, stream=stream, code=code, **kwargs):
                kwargs[stream].write(b"x" * (17 if code != -signal.SIGXFSZ else 16))
                return subprocess.CompletedProcess(argv, code)

            with mock.patch.object(c, "MAX_OUTPUT_BYTES", 16):
                self.assertFalse(self.invoke(runner=runner))
            _, receipt = self.documents()
            self.assertIn("collector byte cap", receipt["validation_failure"])
            self.assertEqual(
                receipt["batches"][0][stream]["bytes"],
                17 if code != -signal.SIGXFSZ else 16,
            )

    def test_read_write_failures_do_not_retry_or_overwrite(self):
        target = self.root / "exclusive"
        with c._open_private(target) as stream:
            stream.write(b"keep")
        with self.assertRaises(FileExistsError):
            c._open_private(target)
        self.assertEqual(target.read_bytes(), b"keep")
        with mock.patch.object(c, "write_exclusive", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.invoke()
        self.assertEqual(len(self.calls), len(self.fixture.plan["batches"]))
        with self.assertRaises(FileExistsError):
            self.invoke()


class RefusalTest(FixtureMixin, unittest.TestCase):
    def test_required_acknowledgement_and_time_bounds(self):
        for value in (False, 1, None):
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                self.invoke(acknowledge_reviewed_admission=value)
        for field, values in (
            ("stage_seconds", [True, 0, -1, 3600.01, float("nan"), float("inf"), "1"]),
            ("process_grace_seconds", [True, -1, 60.01, float("nan"), float("-inf")]),
        ):
            for value in values:
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(ValueError),
                ):
                    self.invoke(**{field: value})
        self.assertFalse(self.output.exists())

    def test_hashes_files_and_admission(self):
        for field in ("plan_sha256", "admission_sha256", "executable_sha256"):
            for value in ("0" * 64, "bad"):
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(ValueError),
                ):
                    self.invoke(**{field: value})
        for raw in (b"{}", b"[]", b"null", b"1", b"no", b'{"x":1,"x":2}', b'{"x":NaN}'):
            self.admission.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.invoke()
        self.admission.write_bytes(b'{"reviewed":true}')
        for path in (self.root, self.root / "missing"):
            with self.assertRaisesRegex(ValueError, "executable file"):
                self.invoke(executable=path)
        self.executable.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "executable file"):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_input_read_bounds(self):
        for field, value in (("MAX_ADMISSION_BYTES", 1),):
            with (
                mock.patch.object(c, field, value),
                self.assertRaisesRegex(ValueError, "exceeds"),
            ):
                self.invoke()
        with (
            mock.patch.object(a, "MAX_PLAN_BYTES", 1),
            self.assertRaisesRegex(ValueError, "exceeds"),
        ):
            self.invoke()

    def test_plan_shape_and_identity_rejections(self):
        mutations = [
            lambda p: p.update(schema_version="wrong"),
            lambda p: p.update(extra=True),
            lambda p: p.update(tool_sha256="0" * 64),
            lambda p: p.update(manifest_sha256="0" * 64),
            lambda p: p.update(identity_sha256="0" * 64),
            lambda p: p.update(settings_sha256="0" * 64),
            lambda p: p.update(public_contract_commit="0" * 40),
            lambda p: p.update(expected_calibration={}),
            lambda p: p.update(query_document_sha256="x"),
            lambda p: p.update(request_contract={}),
            lambda p: p.update(totals={}),
            lambda p: p.update(batches=[]),
            lambda p: p.update(batches={}),
            lambda p: p["manifest"].update(settings={}),
            lambda p: p["manifest"]["settings"].update(calibration=[]),
            lambda p: p["batches"][0].update(batch_index=True),
            lambda p: p["batches"][0].update(request_bytes=1),
            lambda p: p["batches"][0].update(batch_id="0" * 64),
            lambda p: p["batches"][0].update(request_sha256="0" * 64),
            lambda p: p["batches"][0].update(records=[]),
            lambda p: p["batches"][0].update(records={}),
            lambda p: p["batches"][0]["request"].update(records=[]),
            lambda p: p["batches"][0]["request"].update(records={}),
            lambda p: p["batches"][0]["request"].update(defaults={"x": 1}),
            lambda p: p["batches"][0]["records"][0].update(query_id=[]),
            lambda p: p["batches"][0]["records"][0].update(query_id=""),
            lambda p: p["batches"][1]["records"][0].update(
                query_id=p["batches"][0]["records"][0]["query_id"]
            ),
            lambda p: p["batches"][0]["records"][0].update(request_id="bad"),
        ]
        for field, value in (
            ("sequence", ""),
            ("sequence", "N"),
            ("sequence", []),
            ("projection", {}),
            ("scan", {}),
            ("calibration", "in_vitro"),
            ("id", "bad"),
            ("output", {}),
        ):
            mutations.append(
                lambda p, field=field, value=value: p["batches"][0]["request"][
                    "records"
                ][0].update({field: value})
            )
        for field, value in (
            ("origin_crossing", 1),
            ("sequence_strand", "x"),
            ("topology", "x"),
        ):
            mutations.append(
                lambda p, field=field, value=value: p["batches"][0]["request"][
                    "records"
                ][0]["projection"].update({field: value})
            )
        for mutate in mutations:
            self.rewrite(mutate)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.invoke()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.calls)

    def test_noncanonical_plan_and_late_corruption_refused_before_execution(self):
        self.plan.write_bytes(json.dumps(self.fixture.plan, indent=2).encode())
        with self.assertRaisesRegex(ValueError, "canonical"):
            self.invoke()
        self.rewrite(lambda p: p["batches"][-1].update(request_sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "request_sha256"):
            self.invoke()
        self.assertFalse(self.calls)
        self.assertFalse(self.output.exists())

    def test_repacking_and_effective_limits_are_refused(self):
        # Change a manifest's packing ceiling while rebinding its hashes: the
        # existing batch membership is no longer the adapter's frozen packing.
        def change(plan):
            plan["manifest"]["settings"]["limits"]["records_per_batch"] = 2
            plan["manifest_sha256"] = a.document_sha256(plan["manifest"])
            plan["settings_sha256"] = a.document_sha256(plan["manifest"]["settings"])
            for batch in plan["batches"]:
                batch["batch_id"] = a.batch_id(
                    batch["request"],
                    plan["manifest"]["settings"],
                    plan["manifest"]["identity"],
                )

        self.rewrite(change)
        with self.assertRaisesRegex(ValueError, "membership"):
            self.invoke()


class ResourceTest(unittest.TestCase):
    def test_child_limit_never_raises_existing_hard_limit(self):
        for hard, expected in (
            (resource.RLIM_INFINITY, c.MAX_OUTPUT_BYTES),
            (100, 100),
            (c.MAX_OUTPUT_BYTES * 2, c.MAX_OUTPUT_BYTES),
        ):
            with (
                mock.patch.object(resource, "getrlimit", return_value=(100, hard)),
                mock.patch.object(resource, "setrlimit") as setter,
            ):
                c._limit_output()
            setter.assert_called_once_with(resource.RLIMIT_FSIZE, (expected, hard))


class CliTest(FixtureMixin, unittest.TestCase):
    def argv(self):
        return [
            str(self.plan),
            str(self.executable),
            str(self.admission),
            str(self.output),
            "--plan-sha256",
            digest(self.plan.read_bytes()),
            "--executable-sha256",
            digest(self.executable.read_bytes()),
            "--admission-sha256",
            digest(self.admission.read_bytes()),
            "--acknowledge-reviewed-admission",
            "--stage-seconds",
            "2",
            "--process-grace-seconds",
            "0",
        ]

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = c.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_real_cli_tiny_fake_subprocess_and_private_streams(self):
        self.executable.write_text(
            "#!/bin/sh\nprintf 'fake private stdout'\n"
            "printf 'fake private stderr' >&2\nexit 2\n"
        )
        result = subprocess.run(
            [sys.executable, "-m", "benchmarks.promoter.collect", *self.argv()],
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(
            (result.returncode, result.stdout, result.stderr), (0, b"", b"")
        )
        collection, receipt = self.documents()
        self.assertTrue(
            all(row["status"] == "setup_failed" for row in collection["batches"])
        )
        self.assertEqual(
            (self.output / "stdout-000000.bin").read_bytes(), b"fake private stdout"
        )
        self.assertEqual(
            (self.output / "stderr-000000.bin").read_bytes(), b"fake private stderr"
        )
        self.assertEqual(receipt["batches"][0]["stdout"]["bytes"], 19)

    def test_real_cli_accepts_synthetic_results_and_refuses_existing_output(self):
        for index in range(len(self.fixture.plan["batches"])):
            (self.root / f"fixture-{index}.json").write_text(
                json.dumps(self.fixture.result(index))
            )
        self.executable.write_text(
            f"#!{sys.executable}\n"
            "import sys\nfrom pathlib import Path\n"
            "index = int(Path(sys.argv[1]).stem.split('-')[1])\n"
            "raw = Path(__file__).with_name(f'fixture-{index}.json').read_bytes()\n"
            "sys.stdout.buffer.write(raw)\n"
        )
        self.assertEqual(self.run_main(self.argv()), (0, "", ""))
        collection, receipt = self.documents()
        self.assertTrue(
            all(row["status"] == "completed" for row in collection["batches"])
        )
        self.assertIsNone(receipt["validation_failure"])
        hashes = {p.name: digest(p.read_bytes()) for p in self.output.iterdir()}
        code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Collection refused", err)
        self.assertEqual(
            hashes, {p.name: digest(p.read_bytes()) for p in self.output.iterdir()}
        )

    def test_cli_failure_is_generic_and_quiet(self):
        self.plan.write_bytes(b"{}")
        code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(
            err, "Collection refused; check private inputs and output permissions.\n"
        )
        with mock.patch.object(c, "collect", return_value=False):
            self.assertEqual(self.run_main(self.argv()), (1, "", ""))

    def test_required_cli_flags(self):
        for flag, count in (
            ("--acknowledge-reviewed-admission", 1),
            ("--process-grace-seconds", 2),
            ("--admission-sha256", 2),
        ):
            args = self.argv()
            index = args.index(flag)
            del args[index : index + count]
            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                c.main(args)
        self.assertFalse(self.output.exists())

    def test_real_fake_timeout_no_children(self):
        # A shell busy loop has no child process for timeout cleanup to orphan.
        self.executable.write_text(
            "#!/bin/sh\nprintf 'before timeout'\nwhile :; do :; done\n"
        )
        self.assertTrue(self.invoke(runner=subprocess.run, stage_seconds=1.0))
        collection, receipt = self.documents()
        self.assertEqual(collection["batches"][0]["exit_code"], -9)
        self.assertEqual(receipt["stop_reason"], "timeout")
        self.assertEqual(
            (self.output / "stdout-000000.bin").read_bytes(), b"before timeout"
        )

    def test_real_fake_storage_bound(self):
        self.executable.write_text(
            f"#!{sys.executable}\nimport os\n"
            "try:\n    os.write(1, b'x' * 4096)\n    os.write(1, b'x')\n"
            "except OSError:\n    pass\n"
        )
        with mock.patch.object(c, "MAX_OUTPUT_BYTES", 4096):
            self.assertFalse(self.invoke(runner=subprocess.run))
        self.assertEqual((self.output / "stdout-000000.bin").stat().st_size, 4096)
        _, receipt = self.documents()
        self.assertEqual(receipt["stop_reason"], "collector_validation_failed")

    def test_module_entry_point(self):
        self.plan.write_bytes(b"{}")
        with (
            mock.patch.object(sys, "argv", ["collect", *self.argv()]),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as result:
                runpy.run_module("benchmarks.promoter.collect", run_name="__main__")
        self.assertEqual(result.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
