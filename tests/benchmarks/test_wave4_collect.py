"""Real subprocess, private receipt, integrity and collection-deadline tests."""

import copy
import io
import json
import runpy
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.rbs import wave4_collect as c
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.new_data import public_split


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = self.root / "predict.py"
        self.script.write_text(
            "import sys,json,hashlib\nraw=sys.stdin.buffer.read();r=json.loads(raw)\n"
            "print(json.dumps(dict(id=r['id'],"
            "input_sha256=hashlib.sha256(raw).hexdigest(),"
            "status='ok',predicted=2.5,reason='')))\n"
        )
        records = [
            dict(
                id=str(i),
                study="Cambray2018" if i < 4 else "Kuo2020",
                group=str(i // 2),
                sequence="AAATGCCCCC",
                sequence_sha256=digest("AAATGCCCCC"),
                start=2,
                partition="synthetic",
            )
            for i in range(6)
        ]
        inputs = dict(
            schema_version="rbs-new-inputs-1",
            manifest_sha256="synthetic",
            selection_seed="synthetic",
            selection_uses_outcomes=False,
            cambray_universe={},
            partition_counts={},
            records=records,
        )
        self.inputs = inputs
        self.input_path = self.root / "inputs.json"
        self.input_path.write_bytes(c.encoded(inputs))
        self.split_path = self.root / "split.json"
        self.split_path.write_bytes(c.encoded(public_split(inputs)))
        self.protocol = json.loads(
            (
                Path(__file__).parents[2] / "benchmarks/rbs/wave4-protocol.json"
            ).read_text()
        )
        self.protocol.update(
            input_file_sha256=digest(self.input_path.read_bytes()),
            split_file_sha256=digest(self.split_path.read_bytes()),
        )
        self.protocol["collection"]["total_seconds"] = 10
        self.protocol_path = self.root / "protocol.json"
        self.protocol_path.write_bytes(c.encoded(self.protocol))
        candidate = self.root / "candidate.json"
        candidate.write_text("{}")
        config = dict(
            id="reference",
            kind="mechanistic",
            profile="standby2014",
            backend="rnastructure-6.6-traceback-2",
            command=[sys.executable, str(self.script)],
            artifacts=[self.pin(self.script)],
            environment={},
            cwd=str(self.root),
        )
        self.receipt = dict(
            schema_version="rbs-wave4-receipt-1",
            evaluation_authorized=True,
            acknowledgements={
                "A_protocol": "synthetic-A",
                "B_candidate": "synthetic-B",
            },
            collector_sha256=digest(Path(c.__file__).read_bytes()),
            candidate_receipt=self.pin(candidate),
            protocol=self.pin(self.protocol_path),
            inputs=self.pin(self.input_path),
            split=self.pin(self.split_path),
            configurations=[
                config,
                {**config, "id": "contender", "profile": "joint_standby"},
            ],
            primary=dict(reference="reference", contender="contender", mode="joint"),
            new_backend=None,
        )
        self.receipt_path = self.root / "receipt.json"
        self.save()

    @staticmethod
    def pin(path):
        return dict(path=str(path), sha256=digest(path.read_bytes()))

    def save(self):
        self.protocol_path.write_bytes(c.encoded(self.protocol))
        self.receipt["protocol"] = self.pin(self.protocol_path)
        self.receipt_path.write_bytes(c.encoded(self.receipt))

    def test_verify_receipt_guards(self):
        protocol, rows, configs = c.verify(self.receipt)
        self.assertEqual(len(rows), 6)
        self.assertEqual(len(configs), 2)
        for key, value in [
            ("schema_version", "wrong"),
            ("evaluation_authorized", False),
            ("collector_sha256", "wrong"),
            ("configurations", []),
        ]:
            with self.assertRaises(ValueError):
                c.verify({**self.receipt, key: value})
        for ack in ("", None):
            bad = copy.deepcopy(self.receipt)
            bad["acknowledgements"]["A_protocol"] = ack
            with self.assertRaises(ValueError):
                c.verify(bad)
        bad = copy.deepcopy(self.receipt)
        bad["candidate_receipt"]["sha256"] = "wrong"
        with self.assertRaises(ValueError):
            c.verify(bad)
        for key, value in [
            ("kind", "unknown"),
            ("command", []),
            ("command", [""]),
            ("artifacts", []),
            ("environment", {"SECRET": "forbidden"}),
        ]:
            bad = copy.deepcopy(self.receipt)
            bad["configurations"][0][key] = value
            with self.assertRaises(ValueError):
                c.verify(bad)
        self.protocol["collection"]["roster_max_excluding_controls"] = 1
        self.save()
        with self.assertRaises(ValueError):
            c.verify(self.receipt)

    def test_primary_and_limit_guards(self):
        for change in (
            {"reference": "contender"},
            {"reference": "missing"},
            {"mode": "other"},
            {"mode": "fallback", "fallback_consumption_acknowledgement": ""},
        ):
            bad = copy.deepcopy(self.receipt)
            bad["primary"].update(change)
            with self.assertRaises(ValueError):
                c.verify(bad)
        bad = copy.deepcopy(self.receipt)
        bad["new_backend"] = {"id": "new", "accepted_before_freeze": False}
        with self.assertRaises(ValueError):
            c.verify(bad)
        bad["new_backend"]["accepted_before_freeze"] = True
        with self.assertRaises(ValueError):
            c.verify(bad)
        for config in bad["configurations"]:
            config["backend"] = "new"
        c.verify(bad)
        bad = copy.deepcopy(self.receipt)
        bad["primary"].update(
            mode="fallback",
            fallback_consumption_acknowledgement="synthetic explicit consumption",
        )
        bad["configurations"][0]["profile"] = "historical"
        bad["configurations"][1]["profile"] = "standby2014"
        c.verify(bad)
        for key, value in [
            ("max_processes", True),
            ("max_processes", 0),
            ("max_processes", 3),
            ("seconds_per_record", False),
            ("seconds_per_record", 0),
            ("total_seconds", 0),
        ]:
            original = self.protocol["collection"][key]
            self.protocol["collection"][key] = value
            self.save()
            with self.assertRaises(ValueError):
                c.verify(self.receipt)
            self.protocol["collection"][key] = original

    def test_input_split_integrity(self):
        self.protocol["input_file_sha256"] = "wrong"
        self.save()
        with self.assertRaises(ValueError):
            c.verify(self.receipt)
        self.protocol["input_file_sha256"] = digest(self.input_path.read_bytes())
        self.protocol["split_file_sha256"] = "wrong"
        self.save()
        with self.assertRaises(ValueError):
            c.verify(self.receipt)
        self.protocol["split_file_sha256"] = digest(self.split_path.read_bytes())
        self.save()
        changed = json.loads(self.split_path.read_text())
        changed["selection_seed"] = "wrong"
        self.split_path.write_bytes(c.encoded(changed))
        self.receipt["split"] = self.pin(self.split_path)
        self.protocol["split_file_sha256"] = self.receipt["split"]["sha256"]
        self.save()
        with self.assertRaises(ValueError):
            c.verify(self.receipt)
        for key, value in [("study", "unknown"), ("sequence", "changed")]:
            data = copy.deepcopy(self.inputs)
            data["records"][0][key] = value
            self.input_path.write_bytes(c.encoded(data))
            self.split_path.write_bytes(c.encoded(public_split(data)))
            self.receipt.update(
                inputs=self.pin(self.input_path), split=self.pin(self.split_path)
            )
            self.protocol.update(
                input_file_sha256=self.receipt["inputs"]["sha256"],
                split_file_sha256=self.receipt["split"]["sha256"],
            )
            self.save()
            with self.assertRaises(ValueError):
                c.verify(self.receipt)

    def test_scheduling_and_exact_normalization(self):
        jobs = c.schedule(self.inputs["records"], self.receipt["configurations"])
        self.assertEqual(
            [(r["id"], m["id"]) for r, m in jobs[:4]],
            [
                ("0", "contender"),
                ("0", "reference"),
                ("1", "reference"),
                ("1", "contender"),
            ],
        )
        packet = c.encoded(c.request(self.inputs["records"][0]))
        good = dict(
            id="0", input_sha256=digest(packet), status="ok", predicted=0, reason=""
        )
        self.assertEqual(c.normalized(c.encoded(good), packet)["predicted"], 0)
        for change in (
            {"id": "wrong"},
            {"input_sha256": "wrong"},
            {"status": "timeout"},
            {"predicted": True},
            {"status": "failed"},
            {"reason": None},
        ):
            with self.assertRaises(ValueError):
                c.normalized(c.encoded({**good, **change}), packet)
        failed = {**good, "status": "failed", "predicted": None, "reason": "known"}
        self.assertEqual(c.normalized(c.encoded(failed), packet)["status"], "failed")

    def test_real_collection_and_private_modes(self):
        self.receipt["configurations"].extend(
            [dict(id="constant", kind="constant"), dict(id="gc", kind="gc_content")]
        )
        self.save()
        output = self.root / "collection"
        result = c.collect(self.receipt_path, output)
        self.assertTrue(result["complete"])
        self.assertTrue(result["artifacts_unchanged"])
        self.assertEqual(
            {k: len(v) for k, v in result["records_by_configuration"].items()},
            {"reference": 6, "contender": 6, "constant": 6, "gc": 6},
        )
        self.assertEqual(result["records_by_configuration"]["gc"][0]["predicted"], 0.6)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(
            all(p.stat().st_mode & 0o777 == 0o600 for p in output.iterdir())
        )
        with self.assertRaises(FileExistsError):
            c.collect(self.receipt_path, output)

    def test_process_failures_and_timeouts(self):
        row = self.inputs["records"][0]
        config = self.receipt["configurations"][0]
        for index, (program, status, reason) in enumerate(
            [
                ("raise SystemExit(2)", "failed", "process_exit"),
                ('print("bad")', "failed", "invalid_output"),
                ("import time;time.sleep(1)", "timeout", "record_deadline"),
            ]
        ):
            self.script.write_text(program)
            limit = 0.05 if status == "timeout" else 2
            result = c.execute(
                row, config, limit, time.monotonic() + 3, self.root, index
            )
            self.assertEqual(
                (result["status"], result["reason"], result["predicted"]),
                (status, reason, None),
            )
        result = c.execute(
            row,
            {**config, "command": ["/nonexistent-wave4-test"]},
            1,
            time.monotonic() + 3,
            self.root,
            3,
        )
        self.assertEqual(result["reason"], "process_start")
        process = Mock(pid=123)
        with patch.object(c.os, "killpg", side_effect=ProcessLookupError):
            c.stop_process(process)
        self.script.write_text("import time;time.sleep(1)")
        self.receipt["configurations"][0]["artifacts"] = [self.pin(self.script)]
        self.receipt["configurations"][1]["artifacts"] = [self.pin(self.script)]
        self.protocol["collection"]["total_seconds"] = 0.05
        self.save()
        result = c.collect(self.receipt_path, self.root / "timed")
        self.assertFalse(result["complete"])
        records = [
            r for group in result["records_by_configuration"].values() for r in group
        ]
        self.assertEqual(len(records), 12)
        self.assertTrue(any(r["status"] == "not_run" for r in records))
        self.assertTrue(any(r["status"] == "timeout" for r in records))
        self.assertTrue(all(r["reason"] == "collection_deadline" for r in records))

    def test_global_cap_before_work_and_drift(self):
        self.protocol["collection"]["total_seconds"] = 1e-9
        self.save()
        result = c.collect(self.receipt_path, self.root / "capped")
        self.assertFalse(result["complete"])
        self.assertTrue(
            all(
                r["status"] == "not_run"
                for rows in result["records_by_configuration"].values()
                for r in rows
            )
        )
        self.protocol["collection"]["total_seconds"] = 10
        self.save()
        original = c.execute

        def drift(*args):
            result = original(*args)
            self.receipt_path.write_text("changed receipt")
            return result

        with patch.object(c, "execute", side_effect=drift):
            result = c.collect(self.receipt_path, self.root / "drift")
        self.assertFalse(result["artifacts_unchanged"])
        self.assertFalse(result["complete"])
        self.save()
        actual = c.verify
        with patch.object(
            c, "verify", side_effect=[actual(self.receipt), ValueError("changed")]
        ):
            result = c.collect(self.receipt_path, self.root / "changed")
        self.assertFalse(result["artifacts_unchanged"])

    def test_deadline_stops_descendant_work(self):
        marker = self.root / "descendant-finished"
        child = (
            "import time;from pathlib import Path;time.sleep(1);"
            f"Path({str(marker)!r}).touch()"
        )
        self.script.write_text(
            "import subprocess,sys,time\n"
            f"subprocess.Popen([sys.executable,'-c',{child!r}])\n"
            "print('descendant started',flush=True)\ntime.sleep(10)\n"
        )
        result = c.execute(
            self.inputs["records"][0],
            self.receipt["configurations"][0],
            0.5,
            time.monotonic() + 5,
            self.root,
            99,
        )
        self.assertEqual(result["reason"], "record_deadline")
        self.assertIn(
            b"descendant started", (self.root / "job-000099.stdout").read_bytes()
        )
        time.sleep(1)
        self.assertFalse(marker.exists())

    def test_parent_exit_cleans_silent_descendants(self):
        for exit_code in (0, 2):
            marker = self.root / f"silent-descendant-{exit_code}"
            child = (
                "import time;from pathlib import Path;time.sleep(1);"
                f"Path({str(marker)!r}).touch()"
            )
            self.script.write_text(
                "import subprocess,sys,json,hashlib\n"
                f"subprocess.Popen([sys.executable,'-c',{child!r}],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                "stderr=subprocess.DEVNULL)\n"
                "raw=sys.stdin.buffer.read();r=json.loads(raw)\n"
                "print(json.dumps(dict(id=r['id'],"
                "input_sha256=hashlib.sha256(raw).hexdigest(),"
                "status='ok',predicted=2.5,reason='')))\n"
                f"raise SystemExit({exit_code})\n"
            )
            result = c.execute(
                self.inputs["records"][0],
                self.receipt["configurations"][0],
                2,
                time.monotonic() + 5,
                self.root,
                100 + exit_code,
            )
            self.assertEqual(result["exit_code"], exit_code)
            self.assertEqual(
                result["execution"], "returned" if exit_code == 0 else "process_exit"
            )
            time.sleep(1.1)
            self.assertFalse(marker.exists())

    def test_numeric_overflow_preserves_full_failed_roster(self):
        self.script.write_text(
            self.script.read_text().replace("predicted=2.5", "predicted=10**400")
        )
        for config in self.receipt["configurations"]:
            config["artifacts"] = [self.pin(self.script)]
        self.save()
        directory = self.root / "overflow"
        result = c.collect(self.receipt_path, directory)
        self.assertTrue(result["complete"])
        rows = [
            r for group in result["records_by_configuration"].values() for r in group
        ]
        self.assertEqual(len(rows), 12)
        self.assertTrue(
            all(
                r["reason"] == "invalid_output" and r["predicted"] is None for r in rows
            )
        )
        self.assertEqual(len(list(directory.glob("job-*.json"))), 12)

    def test_timeout_can_have_successful_parent_with_open_descendant_pipe(self):
        from benchmarks.rbs.wave4_evaluate import audit_execution

        self.script.write_text(
            "import subprocess,sys,json,hashlib\n"
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])\n"
            "raw=sys.stdin.buffer.read();r=json.loads(raw)\n"
            "print(json.dumps(dict(id=r['id'],"
            "input_sha256=hashlib.sha256(raw).hexdigest(),"
            "status='ok',predicted=2.5,reason='')))\n"
        )
        row, config = self.inputs["records"][0], self.receipt["configurations"][0]
        result = c.execute(row, config, 1, time.monotonic() + 5, self.root, 103)
        self.assertEqual((result["status"], result["exit_code"]), ("timeout", 0))
        self.assertIsNone(result["predicted"])
        audit_execution(
            result,
            row,
            config,
            (self.root / "job-000103.stdout").read_bytes(),
            (self.root / "job-000103.stderr").read_bytes(),
        )

    def test_checked_bytes_returns_the_same_buffer_it_hashes(self):
        path = self.root / "replace.json"
        original = b'{"synthetic":1}'
        path.write_bytes(original)
        spec = self.pin(path)
        actual_read = Path.read_bytes

        def replace_after_read(selected):
            raw = actual_read(selected)
            selected.write_bytes(b'{"synthetic":2}')
            return raw

        with patch.object(
            Path, "read_bytes", autospec=True, side_effect=replace_after_read
        ) as read:
            self.assertEqual(c.checked_bytes(spec), original)
        self.assertEqual(read.call_count, 1)
        with self.assertRaises(ValueError):
            c.checked_bytes(spec)

    def test_cli_summary_only(self):
        self.protocol["collection"]["total_seconds"] = 1e-9
        self.save()
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            c.main([str(self.receipt_path), str(self.root / "cli")])
        self.assertEqual(
            set(json.loads(output.getvalue())), {"complete", "collection_sha256"}
        )
        with (
            patch.object(
                sys,
                "argv",
                ["wave4_collect", str(self.receipt_path), str(self.root / "module")],
            ),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            runpy.run_module("benchmarks.rbs.wave4_collect", run_name="__main__")


if __name__ == "__main__":
    unittest.main()
