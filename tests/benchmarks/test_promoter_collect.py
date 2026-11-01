"""Synthetic frozen-plan collection; never invokes Promoter or folding."""

import contextlib
import copy
import errno
import io
import json
import os
import resource
import runpy
import signal
import subprocess
import sys
import tempfile
import time
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
        recovery = c.recover(self.output)
        self.assertTrue(recovery["finalized"])
        self.assertFalse(recovery["truncated"])
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


class JournalTest(FixtureMixin, unittest.TestCase):
    def events(self):
        return [
            json.loads(line)
            for line in (self.output / c.JOURNAL_NAME).read_bytes().splitlines()
        ]

    def write_events(self, events, tail=b""):
        (self.output / c.JOURNAL_NAME).write_bytes(
            b"".join(canonical_bytes(event) for event in events) + tail
        )

    def assert_roster(self, recovery):
        self.assertEqual(recovery["plan_sha256"], digest(self.plan.read_bytes()))
        self.assertEqual(
            recovery["planned_batches"],
            [
                {key: value for key, value in batch.items() if key != "request"}
                for batch in self.fixture.plan["batches"]
            ],
        )
        self.assertEqual(len(recovery["batches"]), 4)
        self.assertEqual(
            recovery["identities"]["admission_sha256"],
            digest(self.admission.read_bytes()),
        )

    def test_keyboard_interrupt_second_attempt_preserves_unknown_actual_exit(self):
        def runner(argv, **kwargs):
            if not self.calls:
                # The start is already durable and visible before any command.
                recovery = c.recover(self.output)
                self.assertEqual(
                    recovery["batches"][0]["status"], "interrupted_unknown"
                )
                return self.fake(argv, **kwargs)
            self.calls.append((argv, kwargs))
            kwargs["stdout"].write(b"partial second attempt")
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.invoke(runner=runner)
        self.assertEqual(len(self.calls), 2)
        recovery = c.recover(self.output)
        self.assert_roster(recovery)
        self.assertEqual(
            [row["status"] for row in recovery["batches"]],
            ["completed", "interrupted_unknown", "not_run", "not_run"],
        )
        self.assertEqual(recovery["batches"][0]["actual_exit_code"], 0)
        unknown = recovery["batches"][1]
        self.assertIsNone(unknown["actual_exit_code"])
        self.assertIsNone(unknown["timeout_seconds"])
        self.assertGreater(unknown["timeout_ceiling_seconds"], 0)
        self.assertEqual(unknown["process_status"], "interrupted_unknown")
        self.assertIsNone(unknown["exit_code"])
        self.assertIsNone(unknown["synthetic_exit_code"])
        self.assertTrue(unknown["argv"])
        self.assertFalse(recovery["finalized"])
        self.assertTrue(recovery["normal_adaptation_blocked"])
        self.assertFalse((self.output / "collection.json").exists())
        self.assertEqual(self.events()[0]["plan"], self.fixture.plan)

    def test_enospc_second_request_retains_full_roster_and_first_completion(self):
        real = c._open_private

        def open_file(path):
            if path.name == "request-000001.json":
                raise OSError(errno.ENOSPC, "synthetic disk full")
            return real(path)

        with (
            mock.patch.object(c, "_open_private", open_file),
            self.assertRaises(OSError),
        ):
            self.invoke()
        recovery = c.recover(self.output)
        self.assert_roster(recovery)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            [row["status"] for row in recovery["batches"]],
            ["completed", "not_run", "not_run", "not_run"],
        )
        self.assertTrue(recovery["normal_adaptation_blocked"])

    def test_final_artifact_write_failures_do_not_lose_completed_attempts(self):
        real = c.write_exclusive
        for name in ("collection.json", "execution-receipt.json"):
            self.output = self.root / name.replace(".", "-")
            self.calls = []

            def write(path, value, mode, name=name):
                if path.name == name:
                    raise OSError(errno.ENOSPC, "synthetic disk full")
                real(path, value, mode)

            with (
                mock.patch.object(c, "write_exclusive", write),
                self.assertRaises(OSError),
            ):
                self.invoke()
            recovery = c.recover(self.output)
            self.assert_roster(recovery)
            self.assertEqual(len(self.calls), 4)
            self.assertTrue(
                all(row["status"] == "completed" for row in recovery["batches"])
            )
            self.assertFalse(recovery["finalized"])
            self.assertTrue(recovery["normal_adaptation_blocked"])

    def test_journal_persistence_failure_stops_before_any_new_launch(self):
        real = c._append_event
        for kind, index, launches, status in (
            ("initialized", None, 0, None),
            ("started", 0, 0, "not_run"),
            ("observed", 1, 2, "interrupted_unknown"),
            ("finished", 1, 2, "returned_unvalidated"),
            ("finalized", None, 4, "completed"),
        ):
            self.output = self.root / kind
            self.calls = []

            def append(stream, event, kind=kind, index=index):
                if event["event"] == kind and event.get("batch_index") == index:
                    raise OSError(errno.ENOSPC, "synthetic journal failure")
                real(stream, event)

            with (
                mock.patch.object(c, "_append_event", append),
                self.assertRaises(OSError),
            ):
                self.invoke()
            self.assertEqual(len(self.calls), launches)
            if kind == "initialized":
                with self.assertRaisesRegex(
                    ValueError, "No complete journal initialization"
                ):
                    c.recover(self.output)
            else:
                recovery = c.recover(self.output)
                self.assert_roster(recovery)
                self.assertEqual(recovery["batches"][index or 0]["status"], status)
                self.assertTrue(recovery["normal_adaptation_blocked"])
                if kind == "finished":
                    self.assertEqual(recovery["batches"][1]["actual_exit_code"], 0)
                    self.assertIsNone(recovery["batches"][1]["result_sha256"])
                    self.assertEqual(
                        recovery["batches"][1]["validation_state"], "unfinished"
                    )

    def test_return_is_recorded_before_output_sync_or_diagnostic_failure(self):
        real_sync = c._sync_file
        for where in ("sync", "diagnostic"):
            self.output = self.root / where
            self.calls = []

            def sync(stream):
                stdout = self.output / "stdout-000000.bin"
                if (
                    stdout.exists()
                    and os.fstat(stream.fileno()).st_ino == stdout.stat().st_ino
                ):
                    raise OSError(errno.ENOSPC, "synthetic stream fsync failure")
                real_sync(stream)

            target = "_sync_file" if where == "sync" else "_diagnostic"
            action = (
                sync
                if where == "sync"
                else mock.Mock(side_effect=OSError("diagnostics unavailable"))
            )
            with mock.patch.object(c, target, action), self.assertRaises(OSError):
                self.invoke()
            recovery = c.recover(self.output)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(recovery["batches"][0]["status"], "returned_unvalidated")
            self.assertEqual(recovery["batches"][0]["actual_exit_code"], 0)
            self.assertTrue(recovery["normal_adaptation_blocked"])

    def test_fsync_every_event_and_outputs_before_hash_completion(self):
        synced = set()
        real_sync, real_append = c.os.fsync, c._append_event

        def sync(descriptor):
            synced.add(os.fstat(descriptor).st_ino)
            return real_sync(descriptor)

        def append(stream, event):
            if event["event"] == "finished":
                for name in ("stdout", "stderr"):
                    path = self.output / event["detail"][name]["path"]
                    self.assertIn(path.stat().st_ino, synced)
            real_append(stream, event)
            self.assertIn(os.fstat(stream.fileno()).st_ino, synced)

        with (
            mock.patch.object(c.os, "fsync", sync),
            mock.patch.object(c, "_append_event", append),
        ):
            self.assertTrue(self.invoke())
        recovery = c.recover(self.output)
        self.assertTrue(recovery["adaptation_ready"])
        self.assertIn(self.output.stat().st_ino, synced)
        self.assertIn(self.output.parent.stat().st_ino, synced)
        self.assertEqual((self.output / c.JOURNAL_NAME).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        for name in ("collection.json", "execution-receipt.json"):
            self.assertIn((self.output / name).stat().st_ino, synced)

    def test_journal_byte_cap_refuses_before_launch_and_never_truncates(self):
        with (
            mock.patch.object(c, "MAX_JOURNAL_BYTES", 1),
            self.assertRaisesRegex(ValueError, "Journal exceeds"),
        ):
            self.invoke()
        self.assertFalse(self.calls)
        self.assertEqual((self.output / c.JOURNAL_NAME).read_bytes(), b"")
        path = self.root / "bounded-journal"
        with c._open_private(path) as stream:
            c._append_event(stream, dict(event="synthetic"))
            before = path.read_bytes()
            with (
                mock.patch.object(c, "MAX_JOURNAL_BYTES", len(before)),
                self.assertRaises(ValueError),
            ):
                c._append_event(stream, dict(event="too large"))
        self.assertEqual(path.read_bytes(), before)

    def test_initial_file_and_directory_fsync_failure_never_launches(self):
        real = c.os.fsync
        for fail_at in (1, 2, 3):
            self.output = self.root / f"fsync-{fail_at}"
            count = 0

            def sync(descriptor, fail_at=fail_at):
                nonlocal count
                count += 1
                if count == fail_at:
                    raise OSError(errno.EINVAL, "synthetic unsupported fsync")
                real(descriptor)

            with mock.patch.object(c.os, "fsync", sync), self.assertRaises(OSError):
                self.invoke()
            self.assertFalse(self.calls)

    def test_recovery_is_read_only_and_final_artifacts_are_required(self):
        self.invoke()
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with mock.patch.object(
            c.subprocess, "run", side_effect=AssertionError("no launch")
        ):
            recovery = c.recover(self.output)
        self.assert_roster(recovery)
        self.assertTrue(recovery["adaptation_ready"])
        self.assertEqual(
            before, {path.name: path.read_bytes() for path in self.output.iterdir()}
        )
        self.assertNotEqual(recovery["schema_version"], a.COLLECTION_SCHEMA)
        receipt = self.output / "execution-receipt.json"
        receipt.write_bytes(b"corrupted")
        self.assertEqual(
            c.recover(self.output)["blocking_reason"],
            "final_artifacts_missing_or_mismatched",
        )
        receipt.unlink()
        self.assertFalse(c.recover(self.output)["adaptation_ready"])
        with (
            mock.patch.object(c, "MAX_JOURNAL_BYTES", 1),
            self.assertRaises(ValueError),
        ):
            c.recover(self.output)
        event = self.events()[-1]
        with mock.patch.object(c, "read_bounded", side_effect=ValueError("oversize")):
            self.assertFalse(c._final_artifacts(self.output, event))

    def test_recovery_checks_artifacts_in_the_directory_being_recovered(self):
        self.invoke()
        archive = self.root / "archive"
        archive.mkdir()
        for path in self.output.iterdir():
            (archive / path.name).write_bytes(path.read_bytes())
        (self.output / "collection.json").unlink()
        self.assertTrue(c.recover(archive)["adaptation_ready"])
        self.assertFalse(c.recover(self.output)["adaptation_ready"])
        (archive / "execution-receipt.json").write_bytes(b"damaged archive")
        self.assertFalse(c.recover(archive)["adaptation_ready"])

    def test_truncated_tail_preserves_prefix_and_blocks_adaptation(self):
        self.invoke()
        original = self.events()
        for count in (1, 2, 3, 4, len(original)):
            self.write_events(original[:count], b'{"unfinished')
            recovery = c.recover(self.output)
            self.assertTrue(recovery["truncated"])
            self.assertEqual(recovery["blocking_reason"], "truncated_journal")
            self.assertFalse(recovery["adaptation_ready"])
            self.assert_roster(recovery)
        self.write_events(original[:2], canonical_bytes(original[2]).rstrip(b"\n"))
        row = c.recover(self.output)["batches"][0]
        self.assertEqual(row["status"], "interrupted_unknown")
        self.assertIsNone(row["actual_exit_code"])
        self.write_events([], b'{"partial initialization')
        with self.assertRaises(ValueError):
            c.recover(self.output)

    def test_invalid_and_out_of_order_journals_are_refused(self):
        self.invoke()
        original = self.events()

        def mutate(index, **changes):
            events = copy.deepcopy(original)
            events[index].update(changes)
            return events

        cases = [
            mutate(0, schema_version="bad"),
            mutate(0, extra=1),
            mutate(0, executable="relative"),
            mutate(0, output=[]),
            mutate(1, batch_index=True),
            mutate(1, argv=["wrong"]),
            mutate(1, timeout_ceiling_seconds=0),
            mutate(1, timeout_ceiling_seconds=3601),
            mutate(1, extra=True),
            mutate(2, actual_exit_code=None),
            mutate(2, synthetic_exit_code=-9),
            mutate(2, duration_seconds=-1),
            mutate(2, reason="unknown"),
            mutate(2, reason="timeout"),
            mutate(
                2, reason="timeout", actual_exit_code=None, synthetic_exit_code=True
            ),
            mutate(2, reason="timeout", actual_exit_code=None, synthetic_exit_code=-1),
            mutate(3, validation_failure=1),
            mutate(3, validation_failure=""),
            mutate(-1, collection_sha256="0" * 64),
            mutate(-1, receipt_sha256="0" * 64),
            mutate(-1, stop_reason="stage_expired"),
            mutate(-1, duration_seconds=-1),
            original[:1] + [original[2]],  # observed without start
            original[:1] + [original[3]],  # finished without observation
            original[:2] + [original[1]],  # duplicate start
            original[:2] + [original[-1]],  # finalize an unmatched start
            original[:4] + [original[2]],  # duplicate old batch
            original + [original[-1]],  # duplicate finalization
            original + [original[1]],  # work after finalization
            original[:-1] + [dict(event="unknown", batch_index=4)],
            original[:1] + [dict(event="unknown", batch_index=0)],
            original[:1] + [[]],
        ]
        for key, value in (
            ("plan_sha256", "0" * 64),
            ("manifest_sha256", "0" * 64),
            ("admission_sha256", "bad"),
            ("stage_seconds", 0),
            ("process_grace_seconds", -1),
            ("diagnostic_byte_cap", 0),
        ):
            events = copy.deepcopy(original)
            events[0]["receipt"][key] = value
            cases.append(events)
        for key, value in (
            ("status", "not_run"),
            ("argv", []),
            ("result_sha256", "0" * 64),
            ("reason", "wrong"),
            ("exit_code", 1),
        ):
            events = copy.deepcopy(original)
            events[3]["detail"][key] = value
            cases.append(events)
        for key, value in (
            ("path", "wrong"),
            ("sha256", "bad"),
            ("bytes", -1),
            ("bytes", c.MAX_OUTPUT_BYTES + 1),
        ):
            events = copy.deepcopy(original)
            events[3]["detail"]["stdout"][key] = value
            cases.append(events)
        events = copy.deepcopy(original)
        events[3]["detail"]["stdout"].update(bytes=c.MAX_OUTPUT_BYTES + 1, sha256=None)
        cases.append(events)
        for number, events in enumerate(cases):
            self.write_events(events)
            with self.subTest(case=number), self.assertRaises(ValueError):
                c.recover(self.output)
        self.write_events(original[:1], b"{}\n")
        with self.assertRaises(ValueError):
            c.recover(self.output)
        (self.output / c.JOURNAL_NAME).write_bytes(
            json.dumps(original[0], indent=2).encode() + b"\n"
        )
        with self.assertRaises(ValueError):
            c.recover(self.output)

    def test_start_after_a_recorded_stop_is_refused(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1)

        self.invoke(runner=runner)
        events = self.events()
        start = copy.deepcopy(events[1])
        start["batch_index"] = 1
        self.write_events(events[:-1] + [start])
        with self.assertRaisesRegex(ValueError, "after a stop"):
            c.recover(self.output)

    def test_empty_complete_line_and_wrong_jsonl_encoding_are_refused(self):
        self.invoke()
        events = self.events()
        self.write_events(events[:1], b"\n")
        with self.assertRaises(ValueError):
            c.recover(self.output)
        self.write_events(events[:1], b' {"event":"started"}\n')
        with self.assertRaisesRegex(ValueError, "canonical"):
            c.recover(self.output)


class DeadlineTest(FixtureMixin, unittest.TestCase):
    @contextlib.contextmanager
    def delayed_sync(self, event_delay, directory_delay, *, real_time=False):
        state = dict(now=0, pending=False, intents=0)
        real_append, real_directory = c._append_event, c._sync_directory

        def delay(seconds):
            if real_time:
                time.sleep(seconds)
            else:
                state["now"] += seconds

        def append(stream, event):
            real_append(stream, event)
            if event["event"] == "started":
                state["intents"] += 1
                state["pending"] = True
                delay(event_delay)

        def directory(path):
            real_directory(path)
            if state["pending"]:
                state["pending"] = False
                delay(directory_delay)

        with (
            mock.patch.object(c, "_append_event", append),
            mock.patch.object(c, "_sync_directory", directory),
        ):
            yield state

    def events(self):
        return [
            json.loads(line)
            for line in (self.output / c.JOURNAL_NAME).read_bytes().splitlines()
        ]

    def write_events(self, events):
        (self.output / c.JOURNAL_NAME).write_bytes(
            b"".join(canonical_bytes(event) for event in events)
        )

    def assert_cancelled(self):
        collection, receipt = self.documents()
        recovery = c.recover(self.output)
        events = self.events()
        self.assertEqual(
            [event["event"] for event in events],
            ["initialized", "started", "cancelled", "finalized"],
        )
        self.assertEqual(
            events[2],
            dict(
                event="cancelled", batch_index=0, reason="stage_expired", launched=False
            ),
        )
        self.assertTrue(recovery["adaptation_ready"])
        self.assertEqual(recovery["batches"][0]["validation_state"], "not_launched")
        self.assertEqual(recovery["batches"][0]["process_status"], "not_run")
        self.assertTrue(
            all(row["status"] == "not_run" for row in collection["batches"])
        )
        self.assertEqual(receipt["stop_reason"], "stage_expired")
        self.assertEqual(receipt["batches"][0]["reason"], "stage_expired")
        for row in recovery["batches"]:
            self.assertIsNone(row["actual_exit_code"])
            self.assertIsNone(row["synthetic_exit_code"])
            self.assertIsNone(row["exit_code"])
            self.assertIsNone(row["timeout_seconds"])
            self.assertIsNone(row["duration_seconds"])
            self.assertIsNone(row["result_sha256"])
        self.assertEqual(receipt["batches"][1]["reason"], "not_started")
        # Cancellation adds no cohort attempt or invented result to adaptation.
        scores, _ = self.fixture.adapt(collection, {})
        self.assertTrue(
            all(row["runtime_status"] == "not_run" for row in scores["results"])
        )
        self.assertEqual(
            len(scores["results"]), self.fixture.plan["totals"]["n_requests"]
        )
        for row in scores["results"]:
            self.assertTrue(
                all(
                    candidate["status"] == "not_run" and candidate["score"] is None
                    for candidate in row["candidates"]
                )
            )

    def test_sync_exhausting_stage_cancels_without_launch_or_retry(self):
        for number, (event_delay, directory_delay) in enumerate(
            ((5, 0), (0, 5), (2, 3), (0, 6))
        ):
            self.output = self.root / f"expiry-{number}"
            runner = mock.Mock(side_effect=AssertionError("no launch after deadline"))
            with self.delayed_sync(event_delay, directory_delay) as state:
                self.assertTrue(
                    self.invoke(
                        stage_seconds=5, clock=lambda: state["now"], runner=runner
                    )
                )
            runner.assert_not_called()
            self.assertEqual(state["intents"], 1)
            self.assert_cancelled()

    def test_partial_sync_reduces_actual_timeout_and_preserves_frozen_settings(self):
        for number, (event_delay, directory_delay) in enumerate(
            ((2, 0), (0, 2), (1, 1))
        ):
            self.output = self.root / f"partial-{number}"
            seen = []
            with self.delayed_sync(event_delay, directory_delay) as state:

                def runner(argv, seen=seen, state=state, **kwargs):
                    seen.append((argv, kwargs["timeout"]))
                    self.assertEqual(kwargs["timeout"], 3)
                    self.assertEqual(kwargs["timeout"], 5 - state["now"])
                    state["now"] = 5
                    return subprocess.CompletedProcess(argv, 2)

                self.assertTrue(
                    self.invoke(
                        stage_seconds=5, clock=lambda: state["now"], runner=runner
                    )
                )
            self.assertEqual(len(seen), 1)
            self.assertEqual(state["intents"], 1)
            collection, receipt = self.documents()
            events = self.events()
            self.assertEqual(events[1]["timeout_ceiling_seconds"], 5)
            self.assertNotIn("timeout_seconds", events[1])
            self.assertEqual(events[2]["timeout_seconds"], 3)
            detail = receipt["batches"][0]
            self.assertEqual(detail["timeout_ceiling_seconds"], 5)
            self.assertEqual(detail["timeout_seconds"], 3)
            self.assertEqual(detail["argv"], events[1]["argv"])
            self.assertEqual(detail["argv"], seen[0][0])
            self.assertEqual(
                detail["argv"][-4:],
                ["--seconds-per-record", "30.0", "--seconds-per-batch", "300.0"],
            )
            recovery = c.recover(self.output)
            self.assertEqual(recovery["batches"][0]["timeout_seconds"], 3)
            self.assertEqual(recovery["batches"][0]["timeout_ceiling_seconds"], 5)
            self.assertEqual(
                [row["status"] for row in collection["batches"]],
                ["setup_failed", "not_run", "not_run", "not_run"],
            )
            scores, _ = self.fixture.adapt(collection, {})
            self.assertEqual(scores["results"][0]["runtime_status"], "setup_failed")
            self.assertTrue(
                all(row["runtime_status"] == "not_run" for row in scores["results"][1:])
            )

    def test_second_intent_expiry_preserves_first_completed_batch_without_retry(self):
        with self.delayed_sync(0, 0) as state:
            real = c._sync_directory

            def directory(path):
                real(path)
                if state["intents"] == 2:
                    state["now"] = 5

            with mock.patch.object(c, "_sync_directory", directory):
                self.assertTrue(
                    self.invoke(stage_seconds=5, clock=lambda: state["now"])
                )
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(state["intents"], 2)
        collection, receipt = self.documents()
        self.assertEqual(
            [row["status"] for row in collection["batches"]],
            ["completed", "not_run", "not_run", "not_run"],
        )
        self.assertEqual(receipt["batches"][1]["reason"], "stage_expired")
        self.assertIsNone(receipt["batches"][1]["timeout_seconds"])
        self.assertEqual(self.events()[-2]["event"], "cancelled")
        recovery = c.recover(self.output)
        self.assertEqual(recovery["batches"][1]["validation_state"], "not_launched")
        self.assertTrue(recovery["adaptation_ready"])
        raw = (self.output / "stdout-000000.bin").read_bytes()
        scores, _ = self.fixture.adapt(collection, {digest(raw): raw})
        self.assertEqual(scores["results"][0]["runtime_status"], "ok")
        self.assertTrue(
            all(row["runtime_status"] == "not_run" for row in scores["results"][1:])
        )

    def test_actual_timeout_also_respects_batch_plus_grace_ceiling(self):
        self.fixture = Fixture(
            queries=self.fixture.queries,
            limits=dict(CEILINGS, records_per_batch=1),
            seconds_per_batch=2.0,
        )
        self.plan.write_bytes(canonical_bytes(self.fixture.plan))
        with self.delayed_sync(1, 1) as state:

            def runner(argv, **kwargs):
                self.calls.append(kwargs["timeout"])
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

            self.assertTrue(
                self.invoke(
                    stage_seconds=10,
                    process_grace_seconds=1,
                    clock=lambda: state["now"],
                    runner=runner,
                )
            )
        self.assertEqual(self.calls, [3.0])
        _, receipt = self.documents()
        self.assertEqual(receipt["batches"][0]["timeout_ceiling_seconds"], 3.0)
        self.assertEqual(receipt["batches"][0]["timeout_seconds"], 3.0)
        row = c.recover(self.output)["batches"][0]
        self.assertIsNone(row["actual_exit_code"])
        self.assertEqual(row["synthetic_exit_code"], -9)
        self.assertEqual(row["timeout_seconds"], 3.0)

    def test_real_monotonic_delayed_sync_exhaustion_cancels(self):
        runner = mock.Mock(side_effect=AssertionError("no launch after sync delay"))
        with self.delayed_sync(0, 0.4, real_time=True) as state:
            self.assertTrue(self.invoke(stage_seconds=0.3, runner=runner))
        runner.assert_not_called()
        self.assertEqual(state["intents"], 1)
        self.assert_cancelled()

    def test_real_monotonic_partial_delay_uses_fresh_budget_immediately(self):
        readings, passed = [], []

        def clock():
            value = time.monotonic()
            readings.append(value)
            return value

        def runner(argv, **kwargs):
            actual = kwargs["timeout"]
            ceiling = self.events()[1]["timeout_ceiling_seconds"]
            self.assertGreater(actual, 0)
            self.assertLess(actual, ceiling)
            self.assertEqual(actual, min(ceiling, readings[0] + 2 - readings[-1]))
            passed.append(actual)
            raise subprocess.TimeoutExpired(argv, actual)

        with self.delayed_sync(0.05, 0.05, real_time=True):
            self.assertTrue(self.invoke(stage_seconds=2, clock=clock, runner=runner))
        self.assertEqual(len(passed), 1)
        row = c.recover(self.output)["batches"][0]
        self.assertEqual(row["timeout_seconds"], passed[0])
        self.assertLess(row["timeout_seconds"], row["timeout_ceiling_seconds"])

    def test_cancel_persistence_failure_keeps_intent_unknown_and_never_launches(self):
        runner = mock.Mock()
        with self.delayed_sync(0, 5) as state:
            real = c._append_event

            def append(stream, event):
                if event["event"] == "cancelled":
                    raise OSError(errno.ENOSPC, "synthetic cancel journal failure")
                real(stream, event)

            with (
                mock.patch.object(c, "_append_event", append),
                self.assertRaises(OSError),
            ):
                self.invoke(stage_seconds=5, clock=lambda: state["now"], runner=runner)
        runner.assert_not_called()
        row = c.recover(self.output)["batches"][0]
        self.assertEqual(row["status"], "interrupted_unknown")
        self.assertIsNone(row["timeout_seconds"])
        self.assertIsNone(row["actual_exit_code"])
        self.assertEqual(row["timeout_ceiling_seconds"], 5)
        self.assertFalse(c.recover(self.output)["adaptation_ready"])

    def test_durable_cancellation_survives_final_ledger_failure(self):
        runner = mock.Mock()
        with (
            self.delayed_sync(5, 0) as state,
            mock.patch.object(
                c, "write_exclusive", side_effect=OSError(errno.ENOSPC, "final ledger")
            ),
            self.assertRaises(OSError),
        ):
            self.invoke(stage_seconds=5, clock=lambda: state["now"], runner=runner)
        runner.assert_not_called()
        recovery = c.recover(self.output)
        row = recovery["batches"][0]
        self.assertEqual(row["status"], "not_run")
        self.assertEqual(row["validation_state"], "not_launched")
        self.assertIsNone(row["timeout_seconds"])
        self.assertIsNone(row["actual_exit_code"])
        self.assertFalse(recovery["adaptation_ready"])
        self.assertEqual(recovery["blocking_reason"], "unfinished_journal")

    def test_recovery_rejects_invalid_cancellation_and_actual_timeout_evidence(self):
        with self.delayed_sync(5, 0) as state:
            self.invoke(stage_seconds=5, clock=lambda: state["now"])
        cancelled = self.events()
        self.output = self.root / "observed"
        self.invoke()
        observed = self.events()
        for number, events in enumerate(
            (
                cancelled[:1] + [cancelled[2]],
                cancelled[:3] + [cancelled[2]],
                cancelled[:3] + [observed[2]],
                cancelled[:3] + [observed[3]],
                cancelled[:3] + [cancelled[1]],
                observed[:3] + [cancelled[2]],
            )
        ):
            self.write_events(events)
            with self.subTest(order=number), self.assertRaises(ValueError):
                c.recover(self.output)
        for changes in (
            dict(launched=True),
            dict(launched=0),
            dict(reason="timeout"),
            dict(extra=1),
        ):
            events = copy.deepcopy(cancelled)
            events[2].update(changes)
            self.write_events(events)
            with self.subTest(cancel=changes), self.assertRaises(ValueError):
                c.recover(self.output)
        for value in (0, None, True, -1, 301):
            events = copy.deepcopy(observed)
            events[2]["timeout_seconds"] = value
            self.write_events(events)
            with self.subTest(timeout=value), self.assertRaises(ValueError):
                c.recover(self.output)
        for field in ("timeout_seconds", "timeout_ceiling_seconds"):
            events = copy.deepcopy(observed)
            events[3]["detail"][field] = 0
            self.write_events(events)
            with self.subTest(detail=field), self.assertRaises(ValueError):
                c.recover(self.output)
        events = copy.deepcopy(observed)
        del events[2]["timeout_seconds"]
        self.write_events(events)
        with self.assertRaises(ValueError):
            c.recover(self.output)
        events = copy.deepcopy(observed)
        events[0]["schema_version"] = "promoter-execution-journal-1"
        self.write_events(events)
        with self.assertRaisesRegex(ValueError, "journal schema"):
            c.recover(self.output)


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

    def test_io_failure_reports_errno_without_raw_outcomes(self):
        with mock.patch.object(
            c, "collect", side_effect=OSError(errno.EINVAL, "unsupported")
        ):
            code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("errno 22", err)
        self.assertIn("journal may be incomplete", err)

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
