"""Artificial executable/result bytes only; no scientific calls or outcomes."""

import copy
import json
import stat
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from benchmarks.recoding import collect as c
from tests.benchmarks import test_recoding_runtime_check as f


@lru_cache(maxsize=80)
def wire(request_raw, limits_raw, failed=False):
    request, limits = json.loads(request_raw), json.loads(limits_raw)
    predictions = {s: f.native(request, s) for s in f.checker.SIDES}
    if failed:
        record = f.record(predictions["current"], request["calculator"])
        record.update(status="failed", sites=[])
    result = f.artificial_result(request, predictions, limits)
    return c.checker.canonical_bytes(result)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    class Setup:
        def save(self, name, value):
            path = tmp_path / name
            path.write_bytes(c.checker.canonical_bytes(value))
            return path

        def repin(self):
            self.save("backend.json", self.backend_candidate)
            self.save("candidate.json", self.candidate)
            self.admission["bound_receipts"].update(
                {
                    "candidate.json": c.digest(self.candidate_path.read_bytes()),
                    "rbs-context-preparation/candidate.json": c.digest(
                        self.backend_path.read_bytes()
                    ),
                }
            )
            self.save("admission.json", self.admission)
            self.preparation.update(
                candidate_receipt_sha256=c.digest(self.candidate_path.read_bytes()),
                ci_admission_sha256=c.digest(self.admission_path.read_bytes()),
            )
            self.save("preparation.json", self.preparation)
            monkeypatch.setattr(
                c, "PREPARATION_SHA256", c.digest(self.preparation_path.read_bytes())
            )

        def plan(self, **overrides):
            args = dict(
                executable=self.executable,
                executable_sha256=c.digest(self.executable.read_bytes()),
                backend_root=self.backend,
                backend_artifacts=self.artifacts,
                acknowledgement="root synthetic slot acknowledgement",
                output=tmp_path / "attempt",
                preparation_path=self.preparation_path,
                candidate_path=self.candidate_path,
                admission_path=self.admission_path,
                backend_candidate_path=self.backend_path,
            )
            args.update(overrides)
            return c.make_plan(**args)

        def kwargs(self, plan):
            return dict(
                expected_plan_sha256=c.plan_sha256(plan),
                expected_admission_sha256=plan["inputs"]["admission"]["sha256"],
                acknowledgement=plan["acknowledgement"],
            )

        def collect(self, plan=None):
            plan = self.plan() if plan is None else plan
            self.plan_value = plan
            return c.collect(plan, **self.kwargs(plan))

        def recover(self):
            return c.recover(
                tmp_path / "attempt",
                expected_plan_sha256=c.plan_sha256(self.plan_value),
            )

        def events(self):
            return [
                json.loads(line)
                for line in (tmp_path / "attempt/journal.jsonl")
                .read_bytes()
                .splitlines()
            ]

        def journal(self, events, tail=b""):
            (tmp_path / "attempt/journal.jsonl").write_bytes(
                b"".join(c.io.canonical_bytes(e) for e in events) + tail
            )

        def runner(self, raw=None, code=0, reason=None, clean=True, fail_first=False):
            calls = []

            def run(argv, timeout, stdout, stderr, env, cap):
                index = len(calls)
                calls.append((argv, timeout))
                request = Path(argv[1]).read_bytes()
                assert argv[-2:] == ["--format", "json"]
                assert not request.endswith(b"\n")
                assert request == c.checker.canonical_bytes(
                    self.plan_value["jobs"][index]["request"]
                )
                assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
                assert env["PYTHONNOUSERSITE"] == "1"
                assert all(env[k] == "1" for k in c.io.THREAD_ENV)
                assert env["REGSITE_RNASTRUCTURE"] == str(self.backend)
                output = (
                    raw
                    if raw is not None
                    else wire(
                        request,
                        c.checker.canonical_bytes(self.candidate["limits"]),
                        fail_first and index == 0,
                    )
                )
                stdout.write(output)
                stderr.write(b"private synthetic diagnostic")
                return dict(
                    actual_exit_code=1 if fail_first and index == 0 else code,
                    reason=reason,
                    cleanup_confirmed=clean,
                )

            monkeypatch.setattr(c.io, "_attempt", run)
            return calls

    s = Setup()
    s.root = tmp_path
    s.backend = tmp_path / "backend"
    s.backend.mkdir()
    s.artifacts = dict(binaries={}, tables={})
    for name in ("Fold", "bifold", "efn2", "rna.dat", "build.json"):
        folder = s.backend / (
            "exe"
            if name in ("Fold", "bifold", "efn2")
            else "data_tables"
            if name == "rna.dat"
            else "."
        )
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_bytes(b"artificial artifact")
        spec = dict(path=str(path), sha256=c.digest(path.read_bytes()))
        if name == "rna.dat":
            s.artifacts["tables"][name] = spec
        elif name == "build.json":
            s.artifacts["build_receipt"] = spec
        else:
            s.artifacts["binaries"][name] = spec
    manifest = s.save(
        "table-manifest.json",
        {k: v["sha256"] for k, v in s.artifacts["tables"].items()},
    )
    s.artifacts["table_manifest"] = dict(
        path=str(manifest), sha256=c.digest(manifest.read_bytes())
    )
    s.candidate = json.loads((c.MODEL / "candidate.json").read_bytes())
    s.backend_candidate = json.loads(
        (c.MODEL / "rbs-context-preparation/candidate.json").read_bytes()
    )
    s.backend_candidate["execution"]["backend"].update(
        binary_sha256={k: v["sha256"] for k, v in s.artifacts["binaries"].items()},
        build_receipt_sha256=s.artifacts["build_receipt"]["sha256"],
        table_manifest_sha256=s.artifacts["table_manifest"]["sha256"],
    )
    s.admission = dict(
        candidate_commit=s.candidate["candidate_commit"], bound_receipts={}
    )
    s.preparation = json.loads(c.PREPARATION.read_bytes())
    s.candidate_path = tmp_path / "candidate.json"
    s.backend_path = tmp_path / "backend.json"
    s.admission_path = tmp_path / "admission.json"
    s.preparation_path = tmp_path / "preparation.json"
    s.repin()
    s.executable = tmp_path / "artificial-executable"
    s.executable.write_text(f"#!{sys.executable}\nraise SystemExit(2)\n")
    s.executable.chmod(0o700)
    return s


def test_frozen_identity(setup):
    s = setup
    plan = s.plan()
    requests, manifest = c.checker.build_requests()
    assert (
        c.digest(c.PREPARATION.read_bytes())
        == "e79fa42cb04a0f2c5e31cdd1b10c3e469a5626fdb37b15bedf8a558a3b918b08"
    )
    assert (
        c.checker.sha256(requests)
        == "035ff8875ef9bca9c158a7b6ad7c72db15ef52fb242ce3247c7d7b8aa412ed8d"
    )
    assert len(plan["jobs"]) == 36
    assert [j["request"] for j in plan["jobs"]] == requests
    assert manifest == s.preparation["request_manifest"]
    assert manifest["counts"] == {
        "promoter": {"jobs": 18, "positions": 4108},
        "rbs": {"jobs": 18, "positions": 17},
    }
    assert any(
        j["manifest"]["positions"] == {"current": 0, "recoded": 0} for j in plan["jobs"]
    )
    assert not (s.root / "attempt").exists()
    c.preflight(plan, **s.kwargs(plan))
    plan["backend_artifacts"]["binaries"].clear()
    assert s.artifacts["binaries"]


def test_serial_real_artificial_executable(setup):
    s = setup
    requests, _ = c.checker.build_requests()
    for index, req in enumerate(requests):
        (s.root / f"wire{index:02d}").write_bytes(
            wire(
                c.checker.canonical_bytes(req),
                c.checker.canonical_bytes(s.candidate["limits"]),
            )
        )
    s.executable.write_text(f"""#!{sys.executable}
import os, sys
from pathlib import Path
assert sys.argv[2:] == ["--format", "json"]
assert sys.stdin.read() == ""
assert "PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ
assert os.environ["PYTHONNOUSERSITE"] == "1"
assert all(os.environ[k] == "1" for k in {list(c.io.THREAD_ENV)!r})
assert os.environ["REGSITE_RNASTRUCTURE"] == {str(s.backend)!r}
path = Path(sys.argv[1])
assert not path.read_bytes().endswith(b"\\n")
sys.stdout.buffer.write(Path({str(s.root)!r}, "wire" + path.name[:2]).read_bytes())
sys.stderr.buffer.write(b"private diagnostic")
""")
    receipt = s.collect()
    assert len(receipt["jobs"]) == 36
    assert all(
        j["state"] == "validated" and j["observation"]["actual_exit_code"] == 0
        for j in receipt["jobs"]
    )
    assert s.recover()["ready"]
    assert not s.recover()["native_prediction_admitted"]
    assert stat.S_IMODE((s.root / "attempt").stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(p.stat().st_mode) == 0o600 for p in (s.root / "attempt").iterdir()
    )
    with pytest.raises(FileExistsError):
        s.collect(s.plan_value)
    assert [e["event"] for e in s.events()] == ["initialized"] + [
        kind for _ in range(36) for kind in ("intent", "observed", "finished")
    ] + ["finalized"]


@pytest.mark.parametrize("failed", [False, True])
def test_valid_wrapper_and_component_failure(setup, failed):
    s = setup
    calls = s.runner(fail_first=failed)
    receipt = s.collect()
    assert len(calls) == 36 and s.recover()["ready"]
    assert receipt["jobs"][0]["audit"]["status"] == (
        "unavailable" if failed else "complete"
    )
    assert receipt["jobs"][0]["observation"]["actual_exit_code"] == int(failed)
    assert receipt["jobs"][0]["audit"]["native_prediction_admitted"] is False
    assert all(
        0 < timeout <= (90 if i % 4 < 2 else 150)
        for i, (_, timeout) in enumerate(calls)
    )


@pytest.mark.parametrize(
    "raw,code,reason,clean,wanted",
    [
        (b"{broken", 0, None, True, "invalid_paired_output"),
        (b"{}", 0, None, True, "invalid_paired_output"),
        (None, 1, None, True, "invalid_paired_output"),
        (b"private", 2, None, True, "process_exit"),
        (b"", -9, "timeout", True, "timeout"),
        (b"", -9, "cancelled", True, "cancelled"),
        (b"", None, "launch_error", True, "launch_error"),
        (b"", None, "timeout", False, "timeout"),
        (b"", 0, "descendants_remaining", False, "descendants_remaining"),
    ],
)
def test_failures_stop_preserve_actual_observation(
    setup, raw, code, reason, clean, wanted
):
    s = setup
    calls = s.runner(raw, code, reason, clean)
    receipt = s.collect()
    assert len(calls) == 1
    assert receipt["jobs"][0]["reason"] == wanted
    assert receipt["jobs"][0]["observation"] == dict(
        actual_exit_code=code, reason=reason, cleanup_confirmed=clean
    )
    assert all(j["state"] == "not_run" for j in receipt["jobs"][1:])
    assert not s.recover()["ready"] and s.recover()["artifact_error"] is None


@pytest.mark.parametrize("stage", ["before_intent", "after_intent", "cancel_intent"])
def test_fresh_deadline_after_sync_and_cancelled_intent(setup, monkeypatch, stage):
    s = setup
    calls = s.runner()
    clock = [0.0]
    original = c.io._sync_dir

    def sync(path):
        original(path)
        directory = s.root / "attempt"
        if (directory / "35.request.json").exists() and (
            stage == "before_intent" or (directory / "00.stdout").exists()
        ):
            if stage == "cancel_intent":
                raise KeyboardInterrupt
            clock[0] = 3601.0

    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(c.io, "_sync_dir", sync)
    if stage == "cancel_intent":
        # Only one cancellation: final receipt must still sync normally.
        fired = [False]

        def once(path):
            if not fired[0] and (s.root / "attempt/00.stdout").exists():
                fired[0] = True
                raise KeyboardInterrupt
            original(path)

        monkeypatch.setattr(c.io, "_sync_dir", once)
    receipt = s.collect()
    assert not calls and receipt["jobs"][0]["state"] == "cancelled_not_launched"
    assert not s.recover()["ready"] and s.recover()["artifact_error"] is None
    assert not any(e["event"] == "observed" for e in s.events())
    assert any(e["event"] == "intent" for e in s.events()) == (stage != "before_intent")


@pytest.mark.parametrize(
    "target",
    [
        "plan",
        "admission",
        "ack",
        "unknown",
        "schema",
        "request",
        "helper",
        "executable",
        "fixture",
        "input",
    ],
)
def test_preflight_rejects_changes_before_mkdir(setup, monkeypatch, target):
    s = setup
    plan = s.plan()
    kwargs = s.kwargs(plan)
    if target in ("plan", "admission", "ack"):
        kwargs[
            {
                "plan": "expected_plan_sha256",
                "admission": "expected_admission_sha256",
                "ack": "acknowledgement",
            }[target]
        ] = "wrong" if target == "ack" else "0" * 64
    elif target in ("schema", "request", "unknown", "helper"):
        if target == "schema":
            plan["schema_version"] = "wrong"
        elif target == "request":
            plan["jobs"][0]["request"]["settings"]["seconds_per_side"] = 30
        elif target == "helper":
            plan["sources"]["benchmarks/rbs/context_collect.py"]["sha256"] = "0" * 64
        else:
            plan["extra"] = 1
        kwargs["expected_plan_sha256"] = c.plan_sha256(plan)
    elif target == "executable":
        s.executable.write_bytes(b"changed")
    elif target == "input":
        s.candidate_path.write_bytes(b"changed")
    else:
        original = c.checker.build_requests
        monkeypatch.setattr(c.checker, "build_requests", lambda: original(b"changed"))
    with pytest.raises(ValueError):
        c.collect(plan, **kwargs)
    assert not (s.root / "attempt").exists()


@pytest.mark.parametrize("ack", [None, "", "  ", "x" * 4097])
def test_ack_required(setup, ack):
    with pytest.raises(ValueError, match="acknowledgement"):
        setup.plan(acknowledgement=ack)


@pytest.mark.parametrize(
    "mutation",
    [
        "prep_schema",
        "candidate_schema",
        "candidate_commit",
        "admission_commit",
        "backend_commit",
        "admission_candidate",
        "limits",
        "predictors",
        "roster",
        "count",
        "bytes",
        "not_executable",
        "not_backend",
    ],
)
def test_plan_invalid_pinned_inputs(setup, monkeypatch, mutation):
    s = setup
    if mutation == "prep_schema":
        s.preparation["schema_version"] = "bad"
    elif mutation == "candidate_schema":
        s.candidate["schema_version"] = "bad"
    elif mutation == "candidate_commit":
        s.candidate["candidate_commit"] = "f" * 40
    elif mutation == "admission_commit":
        s.admission["candidate_commit"] = "f" * 40
    elif mutation == "backend_commit":
        s.backend_candidate["candidate_commit"] = "f" * 40
    elif mutation == "admission_candidate":
        s.repin()
        s.admission["bound_receipts"]["candidate.json"] = "0" * 64
        s.save("admission.json", s.admission)
        s.preparation["ci_admission_sha256"] = c.digest(s.admission_path.read_bytes())
        s.save("preparation.json", s.preparation)
        monkeypatch.setattr(
            c, "PREPARATION_SHA256", c.digest(s.preparation_path.read_bytes())
        )
    elif mutation == "limits":
        s.candidate["limits"]["max_json_nodes"] = True
    elif mutation == "predictors":
        s.candidate["limits"]["predictors"] = {}
    elif mutation == "roster":
        s.preparation["request_manifest"]["jobs"].reverse()
    elif mutation == "count":
        original = c.checker.build_requests
        monkeypatch.setattr(
            c.checker, "build_requests", lambda: (original()[0][:-1], original()[1])
        )
    elif mutation == "bytes":
        s.candidate["limits"]["max_input_json_bytes"] = 1
    elif mutation == "not_executable":
        s.executable.chmod(0o600)
    if mutation != "admission_candidate":
        s.repin()
    with pytest.raises(ValueError):
        s.plan(
            **(
                {"backend_root": s.root / "missing"}
                if mutation == "not_backend"
                else {}
            )
        )


def test_caps_raw_and_pretty(setup, monkeypatch):
    s = setup
    monkeypatch.setattr(c, "MAX_STREAM", 32)
    s.runner(raw=b"x" * 33)
    result = s.collect()
    assert result["jobs"][0]["reason"] == "output_cap"
    assert s.recover()["artifact_error"] is None and not s.recover()["ready"]
    # The reviewed checker rejects independently both transport and pretty sizes.
    request = f.request()
    limits = f.limits()
    raw = c.checker.canonical_bytes(f.artificial_result(request))
    limits["max_result_json_bytes"] = len(raw) - 1
    with pytest.raises(ValueError):
        c._validate({"jobs": [{"request": request}], "limits": limits}, 0, raw, 0)
    limits["max_result_json_bytes"] = len(raw)
    with pytest.raises(ValueError):
        c._validate({"jobs": [{"request": request}], "limits": limits}, 0, raw, 0)


@pytest.mark.parametrize(
    "failure",
    [
        "save_plan",
        "observation",
        "raw_sync",
        "audit",
        "finish",
        "finish_sync",
        "receipt",
        "finalized",
        "runner",
    ],
)
def test_persistence_and_unknown_failures_no_next_launch(setup, monkeypatch, failure):
    s = setup
    calls = s.runner(raw=b"bad")
    save, event, sync, sync_dir, attempt = (
        c.io._save,
        c.io._event,
        c.io._sync,
        c.io._sync_dir,
        c.io._attempt,
    )

    def saving(path, raw):
        if (
            (failure == "save_plan" and path.name == "plan.json")
            or (failure == "audit" and path.name.endswith("audit.json"))
            or (failure == "receipt" and path.name == "receipt.json")
        ):
            raise OSError("synthetic persistence failure")
        save(path, raw)

    def emitting(journal, **entry):
        if entry["event"] == {
            "observation": "observed",
            "finish": "finished",
            "finalized": "finalized",
        }.get(failure):
            raise OSError("synthetic event failure")
        event(journal, **entry)

    def directory(path):
        if failure == "finish_sync" and (s.root / "attempt/00.audit.json").exists():
            raise OSError("synthetic directory sync failure")
        sync_dir(path)

    def running(*args):
        attempt(*args)
        raise RuntimeError("unknown process interruption")

    monkeypatch.setattr(c.io, "_save", saving)
    monkeypatch.setattr(c.io, "_event", emitting)
    monkeypatch.setattr(c.io, "_sync_dir", directory)
    if failure == "raw_sync":
        # Fail only on stdout sync after the observation has already synced.
        def raw_sync(stream):
            if calls and stream.name != (s.root / "attempt/journal.jsonl").name:
                events = s.events()
                if events[-1]["event"] == "observed" and stream.tell() == 3:
                    raise OSError("synthetic stream sync failure")
            sync(stream)

        monkeypatch.setattr(c.io, "_sync", raw_sync)
    if failure == "runner":
        monkeypatch.setattr(c.io, "_attempt", running)
    with pytest.raises((OSError, RuntimeError)):
        s.collect()
    assert len(calls) <= 1
    assert not s.recover()["ready"]
    if failure in ("observation", "runner"):
        assert s.recover()["jobs"][0]["state"] == "interrupted_unknown"


def test_every_journal_prefix_is_not_ready(setup):
    s = setup
    s.runner()
    s.collect()
    events = s.events()
    for end in range(1, len(events)):
        s.journal(events[:end])
        recovered = s.recover()
        assert len(recovered["jobs"]) == 36 and not recovered["ready"]
        assert recovered["jobs"][0]["state"] == (
            "not_run"
            if end == 1
            else "interrupted_unknown"
            if end == 2
            else "observed_unvalidated"
            if end == 3
            else "validated"
        )
    s.journal(events, b'{"event":')
    assert not s.recover()["ready"] and s.recover()["truncated"]
    s.journal(events)
    assert s.recover()["ready"]


@pytest.mark.parametrize(
    "artifact",
    [
        "plan.json",
        "candidate.input",
        "00.stdout",
        "00.stderr",
        "00.audit.json",
        "35.request.json",
        "receipt.json",
        "missing",
    ],
)
def test_recovery_artifact_tamper_read_only(setup, artifact):
    s = setup
    s.runner(raw=b"bad")
    s.collect()
    path = s.root / "attempt" / ("receipt.json" if artifact == "missing" else artifact)
    path.unlink() if artifact == "missing" else path.write_bytes(b"changed")
    before = {p.name: p.read_bytes() for p in (s.root / "attempt").iterdir()}
    result = s.recover()
    assert not result["ready"] and result["artifact_error"] == "unreconciled_artifacts"
    assert before == {p.name: p.read_bytes() for p in (s.root / "attempt").iterdir()}


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "list",
        "first_keys",
        "first_kind",
        "hash",
        "plan_schema",
        "plan_output",
        "plan_count",
        "after_final",
        "event_list",
        "early_final",
        "intent_final",
        "bad_index",
        "bool_index",
        "past_end",
        "after_stop",
        "argv",
        "intent_timeout",
        "cancel_launched",
        "cancel_zero",
        "cancel_phase",
        "observe_phase",
        "finish_phase",
        "repeat_intent",
        "finish_observation",
        "finish_timeout",
        "finish_state",
        "finish_reason",
        "unknown",
    ],
)
def test_recovery_rejects_invalid_journal(setup, mutation):
    s = setup
    s.runner(raw=b"bad")
    s.collect()
    events = s.events()
    initial, intent, observed, finished, final = events
    if mutation == "empty":
        events = []
    elif mutation == "list":
        events = [[]]
    elif mutation == "first_keys":
        initial["extra"] = 1
    elif mutation == "first_kind":
        initial["event"] = "intent"
    elif mutation == "hash":
        initial["plan"]["extra"] = 1
    elif mutation.startswith("plan_"):
        plan = initial["plan"]
        if mutation == "plan_schema":
            plan["schema_version"] = "bad"
        elif mutation == "plan_output":
            plan["output"] = "/wrong"
        else:
            plan["jobs"].pop()
        s.plan_value = plan
    elif mutation == "after_final":
        events.append(intent)
    elif mutation == "event_list":
        events = [initial, []]
    elif mutation == "early_final":
        events = [initial, final]
    elif mutation == "intent_final":
        events = [initial, intent, final]
    elif mutation == "bad_index":
        intent["index"] = 1
    elif mutation == "bool_index":
        intent["index"] = False
    elif mutation == "past_end":
        # Exercise order rejection after all 36 finishes, before finalization.
        events = [initial]
        for i in range(36):
            for original in (intent, observed, finished):
                e = copy.deepcopy(original)
                e["index"] = i
                if e["event"] == "intent":
                    e["argv"] = c._argv(s.plan_value, i)
                if e["event"] == "finished":
                    e.update(
                        state="validated",
                        reason=None,
                        audit={"native_prediction_admitted": False},
                    )
                events.append(e)
        events.append(dict(event="intent", index=36))
    elif mutation == "after_stop":
        events = [initial, dict(event="cancelled", index=0, launched=False), intent]
    elif mutation == "argv":
        intent["argv"].append("--other")
    elif mutation == "intent_timeout":
        intent["timeout_ceiling"] = 3601
    elif mutation in ("cancel_launched", "cancel_zero"):
        events = [
            initial,
            dict(
                event="cancelled",
                index=0,
                launched=True if mutation == "cancel_launched" else 0,
            ),
        ]
    elif mutation == "cancel_phase":
        events = [
            initial,
            intent,
            observed,
            dict(event="cancelled", index=0, launched=False),
        ]
    elif mutation == "observe_phase":
        events = [initial, observed]
    elif mutation == "finish_phase":
        events = [initial, finished]
    elif mutation == "repeat_intent":
        events = [initial, intent, intent]
    elif mutation == "finish_observation":
        finished["observation"]["actual_exit_code"] = -9
    elif mutation == "finish_timeout":
        finished["timeout_seconds"] = 1
    elif mutation == "finish_state":
        finished["state"] = "invented"
    elif mutation == "finish_reason":
        finished["reason"] = None
    else:
        events = [initial, dict(event="unknown", index=0)]
    s.journal(events)
    with pytest.raises(ValueError):
        s.recover()


@pytest.mark.parametrize(
    "update",
    [
        {"cleanup_confirmed": 1},
        {"reason": "invented"},
        {"actual_exit_code": True},
        {"reason": "launch_error", "actual_exit_code": 0},
        {"actual_exit_code": None},
        {"actual_exit_code": None, "reason": "timeout", "cleanup_confirmed": True},
        {"actual_exit_code": 0, "reason": None, "cleanup_confirmed": False},
        {"timeout_seconds": 0},
    ],
)
def test_observation_rejects_invented_facts(setup, update):
    s = setup
    s.runner(raw=b"bad")
    s.collect()
    events = s.events()
    events[2].update(update)
    s.journal(events)
    with pytest.raises(ValueError):
        s.recover()


@pytest.mark.parametrize("tamper", ["roster", "receipt", "raw_same_size", "audit"])
def test_recovery_content_reconciliation(setup, tamper):
    s = setup
    s.runner(raw=b"bad")
    s.collect()
    events = s.events()
    output = s.root / "attempt"
    if tamper == "roster":
        plan = events[0]["plan"]
        plan["jobs"][0]["request"]["settings"]["seconds_per_side"] = 30
        s.plan_value = plan
        (output / "plan.json").write_bytes(c.checker.canonical_bytes(plan))
    elif tamper == "receipt":
        path = output / "receipt.json"
        receipt = json.loads(path.read_bytes())
        receipt["extra"] = True
        path.write_bytes(c.checker.canonical_bytes(receipt))
        events[-1]["receipt_sha256"] = c.digest(path.read_bytes())
    elif tamper == "audit":
        events[3]["audit"] = {"invented": 1}
    else:
        (output / "00.stdout").write_bytes(b"xxx")
    s.journal(events)
    if tamper == "audit":
        with pytest.raises(ValueError, match="cannot have a passing audit"):
            s.recover()
    else:
        assert s.recover()["artifact_error"] == "unreconciled_artifacts"


@pytest.mark.parametrize(
    "failure", ["exclusive_request", "linked_request", "launch_error", "real_exit"]
)
def test_shared_helper_interaction(setup, monkeypatch, failure):
    s = setup
    save, event = c.io._save, c.io._event
    calls = []

    def saving(path, raw):
        if path.name == "00.request.json" and failure in (
            "exclusive_request",
            "linked_request",
        ):
            if failure == "linked_request":
                path.symlink_to(s.executable)
            else:
                path.write_bytes(b"existing private file")
        save(path, raw)

    def emitting(journal, **entry):
        event(journal, **entry)
        if entry["event"] == "intent":
            calls.append(entry)
            if failure == "launch_error":
                s.executable.unlink()

    monkeypatch.setattr(c.io, "_save", saving)
    monkeypatch.setattr(c.io, "_event", emitting)
    if failure in ("exclusive_request", "linked_request"):
        with pytest.raises(FileExistsError):
            s.collect()
        assert not calls and not s.recover()["ready"]
    else:
        receipt = s.collect()
        observed = receipt["jobs"][0]["observation"]
        assert observed["actual_exit_code"] == (
            None if failure == "launch_error" else 2
        )
        assert observed["reason"] == (
            "launch_error" if failure == "launch_error" else None
        )
        assert len(calls) == 1 and not s.recover()["ready"]


def test_linked_and_changed_preparation_rejected(setup):
    s = setup
    link = s.root / "linked-candidate.json"
    link.symlink_to(s.candidate_path)
    with pytest.raises(OSError):
        s.plan(candidate_path=link)
    s.preparation_path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA-256"):
        s.plan()


@pytest.mark.parametrize(
    "pin", ["checker", "fixture", "contract", "request_schema", "result_schema"]
)
def test_public_authority_pins_required(setup, pin):
    s = setup
    if pin == "checker":
        s.preparation["checker_sha256"] = "0" * 64
    elif pin == "fixture":
        s.preparation["request_manifest"]["fixture_sha256"] = "0" * 64
    else:
        s.candidate[
            {
                "contract": "runtime_contract_sha256",
                "request_schema": "request_schema_sha256",
                "result_schema": "result_schema_sha256",
            }[pin]
        ] = "0" * 64
    s.repin()
    with pytest.raises(ValueError, match="pin mismatch"):
        s.plan()


def test_detect_helper_changed_after_plan(setup, monkeypatch):
    s = setup
    plan = s.plan()
    snapshot = c._snapshot

    def changed(path, expected=None):
        spec, raw = snapshot(path, expected)
        if str(path).endswith("context_collect.py"):
            spec["sha256"] = "f" * 64
        return spec, raw

    monkeypatch.setattr(c, "_snapshot", changed)
    with pytest.raises(ValueError, match="differs from preflight"):
        s.collect(plan)
    assert not (s.root / "attempt").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("observation_exit", 0.0),
        ("observation_cleanup", 1),
        ("timeout", 1),
        ("stream_bytes", False),
        ("stream_bytes", 3.0),
        ("stream_hash", "not-a-hash"),
        ("streams", {}),
        ("failed_audit", {"native_prediction_admitted": False}),
        ("validated_audit", None),
        ("validated_admission", 0),
    ],
)
def test_recovery_prefix_evidence_is_type_sensitive(setup, field, value):
    s = setup
    s.runner(raw=b"bad")
    s.collect()
    events = s.events()[:4]
    finish = events[3]
    if field == "observation_exit":
        finish["observation"]["actual_exit_code"] = value
    elif field == "observation_cleanup":
        finish["observation"]["cleanup_confirmed"] = value
    elif field == "timeout":
        # Equal numerical values must retain their wire representation.
        events[2]["timeout_seconds"] = 1.0
        finish["timeout_seconds"] = 1
    elif field == "stream_bytes":
        finish["streams"]["stdout"]["bytes"] = value
    elif field == "stream_hash":
        finish["streams"]["stdout"]["sha256"] = value
    elif field == "streams":
        finish["streams"] = value
    elif field == "failed_audit":
        finish["audit"] = value
    else:
        finish.update(state="validated", reason=None)
        finish["audit"] = (
            None
            if field == "validated_audit"
            else {"native_prediction_admitted": value}
        )
    s.journal(events)
    with pytest.raises(ValueError):
        s.recover()


def test_fresh_remaining_timeout_is_lowered_after_intent_fsync(setup, monkeypatch):
    s = setup
    clock = [0.0]
    sync = c.io._sync_dir

    def delayed(path):
        sync(path)
        if (s.root / "attempt/00.stdout").exists():
            clock[0] = 3595.0

    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(c.io, "_sync_dir", delayed)
    calls = s.runner(raw=b"bad")
    s.collect()
    assert calls[0][1] == 5.0
    assert s.events()[1]["timeout_ceiling"] == 90.0
    assert s.events()[2]["timeout_seconds"] == 5.0
    assert not s.recover()["ready"] and s.recover()["artifact_error"] is None
