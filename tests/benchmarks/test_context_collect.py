"""Artificial executables only: no installed scientific CLI or native outcomes."""

import copy
import io
import json
import os
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.promoter.native_inputs import (
    canonical_bytes,
    document_sha256,
    strict_json,
)
from benchmarks.rbs import context_collect as c
from tests.benchmarks import test_context_metrics as f


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.panel = self.root / "panel-source.json"
        self.panel.write_bytes(f.PANEL_RAW)
        self.backend = self.root / "backend"
        self.backend.mkdir()
        self.artifacts = {"binaries": {}, "tables": {}}
        for name in ("Fold", "bifold", "efn2"):
            self.artifacts["binaries"][name] = self.artifact(name, b"synthetic binary")
        self.artifacts["build_receipt"] = self.artifact("build.json", b"{}\n")
        self.artifacts["tables"]["rna.dat"] = self.artifact(
            "rna.dat", b"synthetic table"
        )
        self.artifacts["table_manifest"] = self.artifact(
            "tables.json",
            canonical_bytes({"rna.dat": self.artifacts["tables"]["rna.dat"]["sha256"]}),
        )
        self.candidate = copy.deepcopy(
            dict(
                candidate_commit=f.COMMIT,
                **copy.deepcopy(f.SETTINGS),
                complete_models={
                    p: f.core("x", f.MODELS[p], "ok", None, [], None)["model"]
                    for p in c.PROFILES
                },
                source_receipt="complete root receipt retained",
            )
        )
        self.candidate["execution"]["backend"].update(
            binary_sha256={
                k: v["sha256"] for k, v in self.artifacts["binaries"].items()
            },
            build_receipt_sha256=self.artifacts["build_receipt"]["sha256"],
            table_manifest_sha256=self.artifacts["table_manifest"]["sha256"],
        )
        self.candidate_path = self.root / "candidate-source.json"
        self.admission = self.root / "admission-source.json"
        self.admission.write_bytes(b'{"root_reviewed":"synthetic receipt"}\n')
        self.executable = self.root / "fake-native"
        self.outputs = {}
        self.configure()
        self.output = self.root / "new-output"

    def artifact(self, name, raw):
        directory = (
            self.backend / "exe"
            if name in ("Fold", "bifold", "efn2")
            else self.backend / "data_tables"
            if name == "rna.dat"
            else self.backend
        )
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_bytes(raw)
        return dict(path=str(path), sha256=f.sha(raw))

    def configure(self, statuses=None, codes=None, script=None):
        self.candidate_path.write_bytes(canonical_bytes(self.candidate))
        self.admission.write_bytes(
            canonical_bytes(
                dict(
                    candidate_commit=self.candidate["candidate_commit"],
                    bound_receipts={
                        "rbs-context-preparation/candidate.json": f.sha(
                            self.candidate_path.read_bytes()
                        )
                    },
                )
            )
        )
        for profile in c.PROFILES:
            rows = {}
            if statuses:
                rows = {
                    identity: f.other(
                        statuses[i % len(statuses)],
                        "synthetic private reason",
                        prepared=True,
                        prediction=True,
                    )
                    for i, identity in enumerate(f.RECORDS)
                }
            native = f.output(f.MODELS[profile], rows)
            native["execution"] = copy.deepcopy(self.candidate["execution"])
            for row in native["results"]:
                if row["prediction"] is not None:
                    row["prediction"]["backend"] = copy.deepcopy(
                        native["execution"]["backend"]
                    )
            self.outputs[profile] = native
            (self.root / f"{profile}.json").write_bytes(canonical_bytes(native))
        codes = codes or {
            p: int(bool(statuses and set(statuses) & {"failed", "invalid_input"}))
            for p in c.PROFILES
        }
        body = (
            script
            or f"""
import json, os, sys
from pathlib import Path
assert "PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ
assert os.environ["PYTHONNOUSERSITE"] == "1"
assert all(os.environ[k] == "1" for k in {list(c.THREAD_ENV)!r})
assert os.environ["REGSITE_RNASTRUCTURE"] == {str(self.backend)!r}
assert sys.stdin.read() == ""
profile = sys.argv[sys.argv.index("--profile") + 1]
assert Path(sys.argv[1]).read_bytes() == {f.PANEL_RAW!r}
sys.stdout.buffer.write(Path({str(self.root)!r}, profile + ".json").read_bytes())
sys.stderr.write("synthetic private diagnostic")
sys.exit({codes!r}[profile])
"""
        )
        self.executable.write_text(f"#!{sys.executable}\n" + body)
        self.executable.chmod(0o700)

    def plan(self, **overrides):
        args = dict(
            panel_path=self.panel,
            panel_sha256=f.sha(self.panel.read_bytes()),
            candidate_path=self.candidate_path,
            candidate_sha256=f.sha(self.candidate_path.read_bytes()),
            executable=self.executable,
            executable_sha256=f.sha(self.executable.read_bytes()),
            admission_path=self.admission,
            admission_sha256=f.sha(self.admission.read_bytes()),
            backend_root=self.backend,
            backend_artifacts=self.artifacts,
            acknowledgement="root synthetic acknowledgement",
            output=self.output,
        )
        args.update(overrides)
        return c.make_plan(**args)

    def bindings(self, plan):
        return dict(
            expected_plan_sha256=document_sha256(plan),
            expected_candidate_sha256=plan["candidate"]["sha256"],
            expected_admission_sha256=plan["admission"]["sha256"],
            acknowledgement=plan["acknowledgement"],
        )

    def collect(self, plan=None):
        self.current_plan = plan or self.plan()
        return c.collect(
            self.current_plan, self.output, **self.bindings(self.current_plan)
        )

    def recover(self, plan=None):
        return c.recover(
            self.output, expected_plan_sha256=document_sha256(plan or self.current_plan)
        )

    def events(self):
        return [
            strict_json(line)
            for line in (self.output / "journal.jsonl").read_bytes().splitlines()
        ]

    def write_events(self, events, tail=b""):
        (self.output / "journal.jsonl").write_bytes(
            b"".join(canonical_bytes(e) for e in events) + tail
        )

    def test_complete_exact_output_permissions_and_metrics(self):
        with patch.dict(os.environ, PYTHONPATH="poison", PYTHONHOME="poison"):
            receipt = self.collect()
        state = self.recover()
        self.assertTrue(state["ready"], state)
        self.assertEqual(len(receipt["jobs"]), 2)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for path in self.output.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        raw = (self.output / "collection.json").read_bytes()
        collection, _ = c.metrics.load_collection(
            raw, f.sha(raw), f.PANEL, f.PANEL_SHA, f.COMMIT, f.MODELS
        )
        for p in c.PROFILES:
            self.assertEqual(collection["runs"][p]["output"], self.outputs[p])
            self.assertEqual(
                self.current_plan["jobs"][0]["record_ids"],
                [r["id"] for r in f.PANEL["records"]],
            )
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with patch.object(
            c.subprocess, "Popen", side_effect=AssertionError("read only")
        ):
            self.assertTrue(self.recover()["ready"])
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.output.iterdir()}
        )

    def test_valid_record_failures_and_unsupported_are_retained(self):
        for statuses in (
            ["failed", "unsupported", "invalid_input", "no_candidate"],
            ["unsupported", "no_candidate"],
        ):
            with self.subTest(statuses=statuses):
                self.configure(statuses=statuses)
                self.output = self.root / str(len(statuses))
                self.collect()
                self.assertTrue(self.recover()["ready"])
                self.assertEqual(
                    self.events()[2]["actual_exit_code"], int("failed" in statuses)
                )

    def test_process_exits_and_status_disagreement_stop(self):
        for code in (1, 2, 7, -signal.SIGTERM):
            with self.subTest(code=code):
                self.configure(codes=dict.fromkeys(c.PROFILES, code))
                if code < 0:
                    self.configure(
                        script=(
                            "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n"
                        )
                    )
                self.output = self.root / str(code)
                receipt = self.collect()
                self.assertEqual(len(receipt["jobs"]), 1)
                self.assertEqual(
                    receipt["jobs"][0]["observation"]["actual_exit_code"], code
                )
                self.assertFalse(self.recover()["ready"])
                collection = strict_json((self.output / "collection.json").read_bytes())
                self.assertEqual(collection["runs"]["historical"]["status"], "failed")
                self.assertIsNone(collection["runs"]["historical"]["output"])
                self.assertEqual(collection["runs"]["context2017"]["status"], "not_run")

    def test_failed_records_need_actual_exit_one(self):
        self.configure(statuses=["failed"], codes=dict.fromkeys(c.PROFILES, 0))
        receipt = self.collect()
        self.assertEqual(receipt["jobs"][0]["reason"], "invalid_native_output")

    def test_invalid_native_and_complete_model_identity(self):
        mutations = [
            lambda n: n.update(unexpected=True),
            lambda n: n["results"].pop(),
            lambda n: n["results"].append(n["results"][0]),
            lambda n: n["results"][0]["prediction"]["model"].update(
                parameters={"changed": 1}
            ),
            lambda n: n["results"][0]["prediction"].update(backend={}),
            lambda n: n["results"][0]["evidence"].update(extra=True),
            lambda n: n.update(execution={}),
        ]
        for i, mutate in enumerate(mutations):
            with self.subTest(i=i):
                self.configure()
                mutate(self.outputs["historical"])
                (self.root / "historical.json").write_bytes(
                    canonical_bytes(self.outputs["historical"])
                )
                self.output = self.root / f"invalid-{i}"
                receipt = self.collect()
                self.assertEqual(receipt["jobs"][0]["reason"], "invalid_native_output")
                self.assertFalse(self.recover()["ready"])
        for i, raw in enumerate((b"{", b"{}{}", b'{"x":1,"x":2}', b"\xff", b"NaN")):
            self.configure()
            (self.root / "historical.json").write_bytes(raw)
            self.output = self.root / f"json-{i}"
            self.assertEqual(
                self.collect()["jobs"][0]["reason"], "invalid_native_output"
            )

    def test_all_receipt_and_plan_bindings_required(self):
        plan = self.plan()
        for key, value in (
            ("expected_plan_sha256", "0" * 64),
            ("expected_candidate_sha256", "0" * 64),
            ("expected_admission_sha256", "0" * 64),
            ("acknowledgement", "different"),
        ):
            args = self.bindings(plan)
            args[key] = value
            with (
                self.subTest(key=key),
                self.assertRaises(ValueError),
                patch.object(c.subprocess, "Popen") as launch,
            ):
                c.collect(plan, self.output, **args)
            launch.assert_not_called()
            self.assertFalse(self.output.exists())
        changed = copy.deepcopy(plan)
        changed["jobs"][0]["record_ids"].pop()
        with self.assertRaises(ValueError):
            c.preflight(changed, **self.bindings(changed))

    def test_changed_files_rejected_before_process(self):
        for key in (
            "panel",
            "candidate",
            "admission",
            "executable",
            "table",
            "binary",
            "build",
        ):
            with self.subTest(key=key):
                plan = self.plan()
                specs = dict(
                    panel=plan["panel"],
                    candidate=plan["candidate"],
                    admission=plan["admission"],
                    executable=plan["executable"],
                    table=self.artifacts["tables"]["rna.dat"],
                    binary=self.artifacts["binaries"]["Fold"],
                    build=self.artifacts["build_receipt"],
                )
                path = Path(specs[key]["path"])
                old = path.read_bytes()
                path.write_bytes(old + b"changed")
                try:
                    with (
                        self.assertRaises(ValueError),
                        patch.object(c.subprocess, "Popen") as launch,
                    ):
                        self.collect(plan)
                    launch.assert_not_called()
                finally:
                    path.write_bytes(old)

    def test_plan_inputs_budget_and_artifact_boundaries(self):
        for key, value in (
            ("acknowledgement", ""),
            ("seconds_per_record", True),
            ("seconds_per_record", 61),
            ("stage_seconds", float("inf")),
            ("stage_seconds", float("nan")),
            ("stage_seconds", 0),
            ("grace_seconds", -1),
            ("grace_seconds", 31),
            ("stream_bytes", True),
            ("stream_bytes", 0),
            ("stream_bytes", c.MAX_STREAM + 1),
            ("seconds_per_batch", 10),
            ("executable_sha256", "bad"),
            ("backend_root", self.root / "absent"),
        ):
            with (
                self.subTest(key=key, value=value),
                self.assertRaises((ValueError, FileNotFoundError)),
            ):
                self.plan(**{key: value})
        for kind in (
            "commit",
            "models",
            "version",
            "minimal_model",
            "tables",
            "binary",
            "build",
            "table_hash",
        ):
            candidate, artifacts = (
                copy.deepcopy(self.candidate),
                copy.deepcopy(self.artifacts),
            )
            if kind == "commit":
                candidate["candidate_commit"] = "short"
            elif kind == "models":
                candidate["complete_models"].pop("context2017")
            elif kind == "version":
                candidate["complete_models"]["historical"]["implementation_version"] = (
                    "changed"
                )
            elif kind == "minimal_model":
                candidate["complete_models"]["historical"] = {"id": "x"}
            elif kind == "tables":
                artifacts["tables"] = {}
            else:
                backend = candidate["execution"]["backend"]
                if kind == "binary":
                    backend["binary_sha256"]["Fold"] = "a" * 64
                elif kind == "build":
                    backend["build_receipt_sha256"] = "a" * 64
                else:
                    backend["table_manifest_sha256"] = "invalid"
            self.candidate_path.write_bytes(canonical_bytes(candidate))
            self.admission.write_bytes(
                canonical_bytes(
                    dict(
                        candidate_commit=candidate["candidate_commit"],
                        bound_receipts={
                            "rbs-context-preparation/candidate.json": f.sha(
                                self.candidate_path.read_bytes()
                            )
                        },
                    )
                )
            )
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.plan(backend_artifacts=artifacts)
        self.configure()
        self.executable.chmod(0o600)
        with self.assertRaises(ValueError):
            self.plan()

    def test_transport_admission_and_limits(self):
        for raw in (
            f.PANEL_RAW.replace(b"\n", b"\r\n"),
            b"\xff",
            b'{"x":1,"x":1}',
            b"{}",
        ):
            self.panel.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.plan()
        self.panel.write_bytes(f.PANEL_RAW)
        for raw in (b"{}", b"[]", b"null"):
            self.admission.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.plan()
        self.configure()
        with (
            patch.object(c, "MAX_PANEL", len(f.PANEL_RAW) - 1),
            self.assertRaises(ValueError),
        ):
            self.plan()
        plan = self.plan()
        with patch.object(c, "MAX_PANEL", len(f.PANEL_RAW)):
            c.preflight(plan, **self.bindings(plan))

    def test_regular_files_symlinks_and_exclusive_output(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        for function in (c._read, lambda p, cap: c._hash_file(p)):
            with self.assertRaises(ValueError):
                function(fifo, 10)
            with self.assertRaises(ValueError):
                function(self.root, 10)
        link = self.root / "link"
        link.symlink_to(self.panel)
        with self.assertRaises(OSError):
            c._read(link, c.MAX_PANEL)
        with self.assertRaises(ValueError):
            c._spec(dict(path="relative", sha256="a" * 64))
        self.output.mkdir()
        with (
            self.assertRaises(FileExistsError),
            patch.object(c.subprocess, "Popen") as launch,
        ):
            self.collect()
        launch.assert_not_called()
        path = self.output / "existing"
        path.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            c._save(path, b"replace")
        self.assertEqual(path.read_bytes(), b"preserve")

    def test_launch_error_has_no_invented_exit(self):
        with patch.object(
            c.subprocess, "Popen", side_effect=OSError("private failure")
        ) as launch:
            receipt = self.collect()
        self.assertEqual(launch.call_count, 1)
        observation = receipt["jobs"][0]["observation"]
        self.assertIsNone(observation["actual_exit_code"])
        self.assertEqual(observation["reason"], "launch_error")
        self.assertFalse(self.recover()["ready"])

    def test_fresh_deadline_after_durable_intent(self):
        now = [0.0]
        append = c._event

        def delayed(journal, **event):
            append(journal, **event)
            if event["event"] == "intent":
                now[0] = 7201.0

        with (
            patch.object(c.time, "monotonic", side_effect=lambda: now[0]),
            patch.object(c, "_event", side_effect=delayed),
            patch.object(c.subprocess, "Popen") as launch,
        ):
            self.collect()
        launch.assert_not_called()
        state = self.recover()
        self.assertEqual(state["jobs"]["historical"]["state"], "cancelled_not_launched")
        self.assertFalse(state["ready"])
        self.assertNotIn("observed", [e["event"] for e in self.events()])

    def test_expired_before_intent_and_positive_synthetic_budgets(self):
        self.candidate["execution"].update(
            seconds_per_record=0.1, seconds_per_batch=0.2
        )
        self.configure()
        plan = self.plan(
            seconds_per_record=0.1,
            seconds_per_batch=0.2,
            stage_seconds=0.3,
            grace_seconds=0.1,
        )
        with (
            patch.object(c.time, "monotonic", side_effect=[0.0, 1.0]),
            patch.object(c.subprocess, "Popen") as launch,
        ):
            self.collect(plan)
        launch.assert_not_called()
        self.assertEqual(
            self.recover()["jobs"]["historical"]["state"], "cancelled_not_launched"
        )

    def test_observed_before_output_read_and_persistence_failure_stops(self):
        original = c._event

        def fail_observed(journal, **event):
            if event["event"] == "observed":
                raise OSError("fsync failed")
            original(journal, **event)

        with (
            patch.object(c, "_event", side_effect=fail_observed),
            self.assertRaises(OSError),
        ):
            self.collect()
        state = self.recover()
        self.assertEqual(state["jobs"]["historical"]["state"], "interrupted_unknown")
        self.assertEqual(state["jobs"]["context2017"]["state"], "not_run")

    def test_finish_and_output_persistence_failure_stops(self):
        for stage in ("finished", "save", "sync"):
            with self.subTest(stage=stage):
                self.check_persistence_failure(stage)

    def check_persistence_failure(self, stage):
        self.output = self.root / stage
        original_event, original_save, original_sync = c._event, c._save, c._sync
        observed = [False]

        def event(journal, **kw):
            if stage == "finished" and kw["event"] == "finished":
                raise OSError("durability")
            original_event(journal, **kw)
            observed[0] |= kw["event"] == "observed"

        def save(path, raw):
            if stage == "save" and path.name == "collection.json":
                raise OSError("durability")
            original_save(path, raw)

        def sync(stream):
            if stage == "sync" and observed[0]:
                raise OSError("durability")
            original_sync(stream)

        with (
            patch.object(c, "_event", side_effect=event),
            patch.object(c, "_save", side_effect=save),
            patch.object(c, "_sync", side_effect=sync),
            self.assertRaises(OSError),
        ):
            self.collect()
        self.assertFalse(self.recover()["ready"])

    def test_rlimit_and_stream_caps(self):
        self.configure(script="import os\nwhile True: os.write(1, b'x' * 8192)\n")
        receipt = self.collect(self.plan(stream_bytes=1024))
        self.assertLessEqual((self.output / "historical.stdout").stat().st_size, 1024)
        self.assertIsNone(receipt["jobs"][0]["observation"]["reason"])
        self.assertFalse(self.recover()["ready"])
        self.assertEqual(receipt["jobs"][0]["status"], "failed")
        for hard, expected in ((resource.RLIM_INFINITY, 1024), (100, 100)):
            with (
                patch.object(c.resource, "getrlimit", return_value=(10, hard)),
                patch.object(c.resource, "setrlimit") as setlimit,
            ):
                c._limit(1024)
                setlimit.assert_called_once_with(
                    resource.RLIMIT_FSIZE, (expected, hard)
                )

    def test_oversized_injected_stream_and_collection_cap(self):
        def too_large(argv, timeout, stdout, stderr, env, cap):
            stdout.write(b"x" * 101)
            return dict(actual_exit_code=0, reason=None, cleanup_confirmed=True)

        with patch.object(c, "_attempt", side_effect=too_large):
            receipt = self.collect(self.plan(stream_bytes=100))
        self.assertEqual(receipt["jobs"][0]["reason"], "output_cap")
        self.assertFalse(self.recover()["ready"])
        self.output = self.root / "collection-cap"
        with patch.object(c, "MAX_COLLECTION", 1), self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.recover()["ready"])

    def test_timeout_and_signal_cleanup_real_child_grandchild(self):
        for mode in ("timeout", "signal"):
            with self.subTest(mode=mode):
                self.check_real_cleanup(mode)

    def check_real_cleanup(self, mode):
        # Both descendants stay in the CLI session; no scientific processes.
        pidfile = self.root / "pids.json"
        script = f"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
grand_script = "import time; time.sleep(20)"
child_script = ("import subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c'," + repr(grand_script) + "]); "
                "print(p.pid,flush=True); time.sleep(20)")
child = subprocess.Popen([sys.executable, "-c", child_script],
                         stdout=subprocess.PIPE, text=True)
grandchild = int(child.stdout.readline())
Path({str(pidfile)!r}).write_text(json.dumps([os.getpid(), child.pid, grandchild]))
if {mode!r} == "signal":
    os.kill(os.getppid(), signal.SIGTERM)
time.sleep(20)
"""
        self.configure(script=script)
        self.output = self.root / mode
        self.collect(self.plan(stage_seconds=0.6 if mode == "timeout" else 5.0))
        detail = self.events()[2]
        self.assertEqual(
            detail["reason"], "timeout" if mode == "timeout" else "cancelled"
        )
        pids = json.loads(pidfile.read_text())
        self.assertEqual(detail["actual_exit_code"], -signal.SIGKILL)
        for pid in pids:
            result = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertTrue(
                result.returncode != 0 or result.stdout.strip().startswith("Z"),
                result.stdout,
            )
        self.assertFalse(self.recover()["ready"])

    def test_attempt_cancellation_survivors_and_unexpected_wait_error(self):
        process = Mock(pid=999999, returncode=-9)
        for error, reason in (
            (KeyboardInterrupt(), "cancelled"),
            (subprocess.TimeoutExpired("fake", 1), "timeout"),
        ):
            process.wait.side_effect = [error, None]
            with (
                patch.object(c.subprocess, "Popen", return_value=process),
                patch.object(c.os, "killpg") as kill,
            ):
                result = c._attempt([], 1, None, None, {}, 100)
            self.assertEqual(result["reason"], reason)
            self.assertFalse(result["cleanup_confirmed"])
            kill.assert_any_call(process.pid, signal.SIGKILL)
        process.wait.side_effect = [OSError("unexpected"), None]
        with (
            patch.object(c.subprocess, "Popen", return_value=process),
            patch.object(c.os, "killpg", side_effect=ProcessLookupError),
            self.assertRaises(OSError),
        ):
            c._attempt([], 1, None, None, {}, 100)
        process.wait.side_effect = None
        with (
            patch.object(c.subprocess, "Popen", return_value=process),
            patch.object(c.os, "killpg", side_effect=[None, None, ProcessLookupError]),
        ):
            result = c._attempt([], 1, None, None, {}, 100)
        self.assertEqual(result["reason"], "descendants_remaining")
        self.assertTrue(result["cleanup_confirmed"])

    def test_signal_during_real_preexec_startup_and_creation_failure(self):
        # Signal arrives while the constructor waits for the preexec error pipe.
        # Each child has its own session and is harmless; exec never does science.
        for pending in (False, True):
            for fail in (False, True):
                with self.subTest(pending=pending, fail=fail):
                    self.check_startup_window(pending, fail)

    def check_startup_window(self, pending, fail):
        pidfile = self.root / "startup.pid"
        parent = os.getpid()
        previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        original_limit = c._limit

        def startup(cap):
            original_limit(cap)
            pidfile.write_text(str(os.getpid()))
            if pending:
                os.kill(parent, signal.SIGTERM)
            # Keep Popen in its constructor after the signal has been sent.
            c.time.sleep(0.15)
            if fail:
                raise ValueError("synthetic preexec failure")

        body = "import time; time.sleep(5)" if pending else "pass"
        try:
            with c._signals(), patch.object(c, "_limit", side_effect=startup):
                observation = c._attempt(
                    [sys.executable, "-c", body],
                    2.0,
                    subprocess.DEVNULL,
                    subprocess.DEVNULL,
                    dict(os.environ),
                    1024,
                )
            pid = int(pidfile.read_text())
            self.assertEqual(
                observation["reason"],
                "launch_error" if fail else "cancelled" if pending else None,
            )
            self.assertEqual(
                observation["actual_exit_code"],
                None if fail else -signal.SIGKILL if pending else 0,
            )
            # Popen creation failure or the owned cleanup must reap the child.
            with self.assertRaises(ChildProcessError):
                os.waitpid(pid, os.WNOHANG)
        finally:
            # Also contain a regression of the startup leak if the test fails.
            if pidfile.exists():
                pid = int(pidfile.read_text())
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                deadline = c.time.monotonic() + 2.0
                while True:
                    try:
                        reaped, _ = os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        break
                    if reaped == pid:
                        break
                    if c.time.monotonic() >= deadline:
                        self.fail("Synthetic startup child was not reaped")
                    c.time.sleep(0.01)
        self.assertEqual(previous, {s: signal.getsignal(s) for s in previous})

    def test_pending_startup_signals_acquire_handle_before_cleanup(self):
        process = Mock(pid=999999, returncode=-signal.SIGKILL)
        for sig in (signal.SIGINT, signal.SIGTERM):
            for fail in (
                None,
                OSError("creation"),
                subprocess.SubprocessError("creation"),
            ):

                def launch(*args, sig=sig, fail=fail, **kwargs):
                    signal.raise_signal(sig)
                    if fail is not None:
                        raise fail
                    return process

                with (
                    self.subTest(sig=sig, fail=fail),
                    patch.object(c.subprocess, "Popen", side_effect=launch),
                    patch.object(c, "_kill_wait", return_value=True) as cleanup,
                ):
                    observation = c._attempt([], 1.0, None, None, {}, 1024)
                    if fail is None:
                        cleanup.assert_called_once_with(process)
                        self.assertEqual(observation["reason"], "cancelled")
                    else:
                        cleanup.assert_not_called()
                        self.assertEqual(observation["reason"], "launch_error")
                        self.assertIsNone(observation["actual_exit_code"])

    def test_constructor_exceptions_without_a_handle_propagate(self):
        for error in (KeyboardInterrupt(), RuntimeError("creation")):
            with (
                self.subTest(error=error),
                patch.object(c.subprocess, "Popen", side_effect=error),
                patch.object(c, "_kill_wait") as cleanup,
                self.assertRaises(type(error)),
            ):
                c._attempt([], 1.0, None, None, {}, 1024)
            cleanup.assert_not_called()

    def test_signal_handler_restores_previous_handlers(self):
        previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        with c._signals(), self.assertRaises(KeyboardInterrupt):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        self.assertEqual(previous, {s: signal.getsignal(s) for s in previous})

    def test_every_journal_prefix_unknown_and_truncated(self):
        self.collect()
        events = self.events()
        for n in range(1, len(events) + 1):
            with self.subTest(n=n):
                self.write_events(events[:n])
                state = self.recover()
                self.assertEqual(set(state["jobs"]), set(c.PROFILES))
                self.assertEqual(state["ready"], n == len(events))
                if n == 2:
                    self.assertEqual(
                        state["jobs"]["historical"]["state"], "interrupted_unknown"
                    )
                    self.assertFalse(state["jobs"]["historical"]["observed"])
                if n == 3:
                    self.assertEqual(
                        state["jobs"]["historical"]["state"], "observed_unvalidated"
                    )
        self.write_events(events[:-1], b'{"event":')
        state = self.recover()
        self.assertTrue(state["truncated"])
        self.assertFalse(state["ready"])
        self.write_events(events)
        with self.assertRaises(ValueError):
            c.recover(self.output, expected_plan_sha256="a" * 64)
        self.write_events([])
        with self.assertRaises(ValueError):
            self.recover()

    def test_recovery_event_corruption(self):
        self.collect()
        baseline = self.events()

        def change(index, **kwargs):
            events = copy.deepcopy(baseline)
            events[index].update(kwargs)
            return events

        cases = [
            baseline + [baseline[-1]],
            [baseline[0], baseline[2]],
            [baseline[0], baseline[-1], baseline[1]],
            change(1, profile="context2017"),
            change(1, argv=[]),
            change(2, actual_exit_code=None),
            change(2, cleanup_confirmed=False),
            change(2, reason="invented"),
            change(2, actual_exit_code=True),
            change(2, timeout_seconds=8000),
            change(3, timeout_seconds=1),
            change(3, status="not_run"),
            change(3, status="failed"),
            baseline[:2] + [baseline[-1]],
            baseline[:3] + [baseline[-1]],
            baseline[:1]
            + [dict(event="cancelled", profile="historical", launched=True)],
            baseline[:1]
            + [
                dict(event="cancelled", profile="historical", launched=False),
                baseline[1],
            ],
        ]
        for i, events in enumerate(cases):
            with self.subTest(i=i), self.assertRaises(ValueError):
                self.write_events(events)
                self.recover()

    def refresh_receipt(self, receipt, events):
        raw = canonical_bytes(receipt)
        (self.output / "receipt.json").write_bytes(raw)
        events[-1]["receipt_sha256"] = f.sha(raw)
        self.write_events(events)

    def test_recovery_rejects_changed_finished_and_receipt_exit_types(self):
        self.collect()
        baseline = self.events()
        receipt = strict_json((self.output / "receipt.json").read_bytes())
        self.assertTrue(self.recover()["ready"])
        for value in (False, True, 0.0, 1.0, 1):
            events, changed = copy.deepcopy(baseline), copy.deepcopy(receipt)
            events[3]["observation"]["actual_exit_code"] = value
            changed["jobs"][0]["observation"]["actual_exit_code"] = value
            self.refresh_receipt(changed, events)
            with (
                self.subTest(value=value, type=type(value)),
                self.assertRaises(ValueError),
            ):
                self.recover()
        self.refresh_receipt(receipt, baseline)
        self.assertTrue(self.recover()["ready"])

    def test_recovery_validates_observation_shapes_and_exit_types(self):
        self.collect()
        baseline = self.events()
        values = (False, True, 0.0, -9.0, "0", [], {}, None)
        for value in values:
            events = copy.deepcopy(baseline)
            events[2]["actual_exit_code"] = value
            self.write_events(events)
            with (
                self.subTest(value=value, type=type(value)),
                self.assertRaises(ValueError),
            ):
                self.recover()
        malformed = (
            None,
            [],
            {},
            {"actual_exit_code": 0},
            dict(actual_exit_code=0, reason=None, cleanup_confirmed=1),
            dict(actual_exit_code=0, reason="launch_error", cleanup_confirmed=True),
            dict(actual_exit_code=None, reason="cancelled", cleanup_confirmed=True),
            dict(actual_exit_code=0, reason=None, cleanup_confirmed=True, extra=0),
        )
        for value in malformed:
            events = copy.deepcopy(baseline)
            events[3]["observation"] = value
            self.write_events(events)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.recover()
        events = copy.deepcopy(baseline)
        events[3]["timeout_seconds"] = int(events[3]["timeout_seconds"])
        self.write_events(events)
        with self.assertRaises(ValueError):
            self.recover()
        events = baseline[:1] + [
            dict(event="cancelled", profile="historical", launched=0)
        ]
        self.write_events(events)
        with self.assertRaises(ValueError):
            self.recover()

    def test_recovery_type_sensitive_nested_artifact_reconciliation(self):
        self.collect()
        baseline = self.events()
        receipt = strict_json((self.output / "receipt.json").read_bytes())
        collection = strict_json((self.output / "collection.json").read_bytes())
        for kind in ("exit_bool", "exit_float", "cleanup", "stream_bytes", "timeout"):
            events, changed = copy.deepcopy(baseline), copy.deepcopy(receipt)
            job = changed["jobs"][0]
            if kind == "exit_bool":
                job["observation"]["actual_exit_code"] = False
            elif kind == "exit_float":
                job["observation"]["actual_exit_code"] = 0.0
            elif kind == "cleanup":
                job["observation"]["cleanup_confirmed"] = 1
            elif kind == "stream_bytes":
                job["streams"]["stdout"]["bytes"] = float(
                    job["streams"]["stdout"]["bytes"]
                )
            else:
                job["timeout_seconds"] = int(job["timeout_seconds"])
            self.refresh_receipt(changed, events)
            with self.subTest(kind=kind):
                self.assertFalse(self.recover()["ready"])
        for value in (False, 0):
            events, changed = copy.deepcopy(baseline), copy.deepcopy(collection)
            prediction = changed["runs"]["historical"]["output"]["results"][0][
                "prediction"
            ]
            self.assertIs(type(prediction["sites"][0]["log_tir"]), float)
            prediction["sites"][0]["log_tir"] = value
            raw = canonical_bytes(changed)
            (self.output / "collection.json").write_bytes(raw)
            events[-1]["collection_sha256"] = f.sha(raw)
            changed_receipt = copy.deepcopy(receipt)
            changed_receipt["collection_sha256"] = f.sha(raw)
            self.refresh_receipt(changed_receipt, events)
            with self.subTest(value=value):
                self.assertFalse(self.recover()["ready"])
        (self.output / "collection.json").write_bytes(canonical_bytes(collection))
        self.refresh_receipt(receipt, baseline)
        changed_plan = copy.deepcopy(self.current_plan)
        changed_plan["stage_seconds"] = int(changed_plan["stage_seconds"])
        (self.output / "plan.json").write_bytes(canonical_bytes(changed_plan))
        self.assertFalse(self.recover()["ready"])

    def test_recovery_missing_and_mismatched_artifacts(self):
        self.collect()
        for name in (
            "plan.json",
            "candidate.json",
            "admission.json",
            "panel.json",
            "historical.stdout",
            "historical.stderr",
            "collection.json",
            "receipt.json",
        ):
            path = self.output / name
            original = path.read_bytes()
            for replacement in (None, b"{}\n"):
                with self.subTest(name=name, replacement=replacement):
                    if replacement is None:
                        path.unlink()
                    else:
                        path.write_bytes(replacement)
                    state = self.recover()
                    self.assertFalse(state["ready"])
                    self.assertEqual(state["artifact_error"], "unreconciled_artifacts")
                    path.write_bytes(original)
        # Coherent hash changes still cannot change a validated output or receipt.
        for filename, field in (
            ("collection.json", "collection_sha256"),
            ("receipt.json", "receipt_sha256"),
        ):
            original = (self.output / filename).read_bytes()
            events = self.events()
            (self.output / filename).write_bytes(b"{}\n")
            events[-1][field] = f.sha(b"{}\n")
            self.write_events(events)
            self.assertFalse(self.recover()["ready"])
            (self.output / filename).write_bytes(original)
            events[-1][field] = f.sha(original)
            self.write_events(events)

    def test_additional_input_and_recovery_boundaries(self):
        plan = self.plan()
        with self.assertRaises(ValueError):
            c.collect(plan, self.root / "different-output", **self.bindings(plan))
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["table_manifest"]["sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.plan(backend_artifacts=artifacts)
        artifacts = copy.deepcopy(self.artifacts)
        artifacts["tables"]["rna.dat"]["sha256"] = "a" * 64
        with self.assertRaises(ValueError):
            self.plan(backend_artifacts=artifacts)
        old = self.candidate["execution"]["backend"]["table_manifest_sha256"]
        self.candidate["execution"]["backend"]["table_manifest_sha256"] = "a" * 64
        self.configure()
        with self.assertRaises(ValueError):
            self.plan()
        self.candidate["execution"]["backend"]["table_manifest_sha256"] = old
        self.candidate["complete_models"]["historical"]["parameters"] = None
        self.configure()
        with self.assertRaises(ValueError):
            self.plan()
        self.candidate["complete_models"]["historical"]["parameters"] = {}
        self.configure()
        self.collect()
        baseline = self.events()
        self.write_events([baseline[0], []])
        with self.assertRaises(ValueError):
            self.recover()
        for kind in (
            "candidate",
            "roster",
            "bytes",
            "stream_size",
            "observation",
            "native",
        ):
            events = copy.deepcopy(baseline)
            plan = events[0]["plan"]
            if kind == "candidate":
                plan["candidate"]["receipt"]["extra"] = True
            elif kind == "roster":
                plan["jobs"][0]["record_ids"].pop()
            elif kind == "bytes":
                plan["panel"]["bytes"] += 1
            elif kind == "stream_size":
                events[3]["streams"]["stdout"]["bytes"] += 1
            elif kind == "observation":
                events[2]["reason"] = "timeout"
                events[3]["observation"]["reason"] = "timeout"
            else:
                # Both stream and final hashes can be changed coherently, but
                # complete native schema/model validation must still reject it.
                path = self.output / "historical.stdout"
                original_native = path.read_bytes()
                path.write_bytes(b"{}\n")
                events[3]["streams"]["stdout"] = dict(sha256=f.sha(b"{}\n"), bytes=3)
            self.write_events(events)
            (self.output / "plan.json").write_bytes(canonical_bytes(plan))
            with self.subTest(kind=kind):
                self.assertFalse(self.recover(plan)["ready"])
            if kind == "native":
                path.write_bytes(original_native)
        self.write_events(baseline)

    def test_cleanup_wait_is_bounded_and_path_rosters(self):
        process = Mock(pid=999999, returncode=None)
        process.wait.side_effect = subprocess.TimeoutExpired("fake", 5)
        with patch.object(c.os, "killpg"):
            self.assertFalse(c._kill_wait(process))
        process.wait.assert_called_once_with(timeout=5.0)
        for kind in ("binary", "table"):
            artifacts = copy.deepcopy(self.artifacts)
            if kind == "binary":
                artifacts["binaries"]["Fold"]["path"] = str(self.backend / "wrong")
            else:
                artifacts["tables"]["rna.dat"]["path"] = str(self.backend / "wrong")
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.plan(backend_artifacts=artifacts)

    def test_inaccessible_group_is_not_released_and_changed_request_stops(self):
        with patch.object(c.os, "killpg", side_effect=PermissionError):
            self.assertTrue(c._group_exists(999999))
            process = Mock(pid=999999)
            self.assertFalse(c._kill_wait(process))
        original = c._event

        def corrupt(journal, **event):
            original(journal, **event)
            if event["event"] == "intent":
                (self.output / "panel.json").write_bytes(b"{}\n")

        with (
            patch.object(c, "_event", side_effect=corrupt),
            patch.object(c.subprocess, "Popen") as launch,
            self.assertRaises(ValueError),
        ):
            self.collect()
        launch.assert_not_called()
        self.assertEqual(
            self.recover()["jobs"]["historical"]["state"], "interrupted_unknown"
        )

    def test_journal_cap(self):
        with patch.object(c, "MAX_JOURNAL", 1), self.assertRaises(ValueError):
            c._event(io.BytesIO(), event="too_large")


if __name__ == "__main__":
    unittest.main()
