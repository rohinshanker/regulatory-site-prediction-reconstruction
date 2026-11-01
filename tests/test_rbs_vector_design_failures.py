"""Full-roster missingness, native integrity, budgets and fresh confirmation."""

import hashlib
import json
import math

import pytest
from test_rbs_vector_design import REAL_PREDICT, Backend, digest, example, site
from test_rbs_vector_design import fake as fake

from regsite import design_io as wire
from regsite import rbs
from regsite import rbs_vector_design as module
from regsite.structures import BackendError


@pytest.mark.parametrize("status", ["failed", "unsupported", "no_candidate"])
@pytest.mark.parametrize("some_success", [False, True])
def test_valid_mixed_native_sites_are_kept_not_ranked(
    monkeypatch, fake, status, some_success
):
    def score(request, start, folding, profile):
        result = site(request, start, folding, profile)
        if start == 65 and (not some_success or request.sequence[55] == "G"):
            result.update(
                status=status,
                reason="artificial_site_failure",
                tir=None,
                log_tir=None,
                energies=None,
            )
        return result

    monkeypatch.setattr(rbs, "_score_site", score)
    result = module.design(example(), Backend())
    assert result["status"] == ("partial" if some_success else "no_candidate")
    assert result["coverage"]["attempted"] == 4 and result["coverage"]["not_run"] == 0
    assert result["coverage"]["stop_reason"] is None
    failed = result["candidates"][0]
    assert failed["native_admitted"] and failed["objective"] is None
    assert (
        failed["targets"][0]["status"] == "ok"
        and failed["targets"][0]["absolute_log_error"] is not None
    )
    assert (
        failed["targets"][1]["status"] == status and failed["targets"][1]["tir"] is None
    )
    assert len(fake) == (5 if some_success else 4)
    if some_success:
        assert (
            result["selected"] is not None and result["reason"] == "candidate_failures"
        )


def test_native_record_setup_failure_without_sites_keeps_roster(fake):
    class Unavailable(Backend):
        def session(self, *args):
            raise BackendError("synthetic session unavailable")

    result = module.design(example(), Unavailable())
    assert result["status"] == "no_candidate" and result["confirmation"] is None
    assert result["coverage"]["failed"] == 4 and len(fake) == 4
    for row in result["candidates"]:
        assert row["native"]["sites"] == [] and row["native_admitted"]
        assert [t["id"] for t in row["targets"]] == ["first", "second"]
        assert all(
            t["status"] == "not_evaluated"
            and t["reason"] == "synthetic session unavailable"
            for t in row["targets"]
        )


@pytest.mark.parametrize(
    "exception", [BackendError("x"), OSError("x"), UnicodeError("x")]
)
def test_thrown_execution_error_keeps_remaining_candidates(
    monkeypatch, fake, exception
):
    score = rbs.predict
    calls = []

    def once(value, backend, **kwargs):
        calls.append(value)
        if len(calls) == 1:
            raise exception
        return score(value, backend, **kwargs)

    monkeypatch.setattr(rbs, "predict", once)
    result = module.design(example(), Backend())
    assert result["status"] == "partial" and result["selected"] is not None
    assert result["coverage"]["prediction_calls"] == len(calls) == 5
    assert result["candidates"][0]["reason"] == "prediction_execution_failed"
    assert result["candidates"][0]["native"] is None


def test_coherent_native_subnormal_rounding_is_preserved(monkeypatch, fake):
    # Independent literal equations used by the historical native scorer. Its
    # intermediate exponential is subnormal, so log(rounded TIR) is different.
    total = 1655.0
    rate = 2500.0 * math.exp(-total / 2.222)
    log_rate = math.log(2500) - total / 2.222
    assert 0 < rate < 2.2250738585072014e-308
    assert not math.isclose(math.log(rate), log_rate, rel_tol=1e-12, abs_tol=1e-12)

    def score(request, start, folding, profile):
        row = site(request, start, folding, profile)
        row.update(tir=rate, log_tir=log_rate, energies={"dG_total": total})
        return row

    monkeypatch.setattr(rbs, "_score_site", score)
    result = module.design(example(), Backend())
    assert result["status"] == "complete" and len(fake) == 5
    assert result["selected"]["index"] == 0
    assert all(
        row["native_admitted"]
        and all(t["tir"] == rate and t["log_tir"] == log_rate for t in row["targets"])
        for row in result["candidates"]
    )
    assert result["confirmation"]["status"] == "verified"


MUTATIONS = [
    (("model", "id"), "wrong"),
    (("model", "source_commit"), "wrong"),
    (("model", "implementation_version"), "wrong"),
    (("model", "parameters", "RT"), 2),
    (("model", "parameters", "optimal_aligned_spacing"), 5.0),
    (("backend",), {"other": True}),
    (("input", "host"), "substitution"),
    (("input", "start_positions", 0), 30.0),
    (("id",), "wrong"),
    (("schema_version",), "wrong"),
    (("prediction_id",), "0" * 64),
    (("status",), "invalid_input"),
    (("reason",), "record_has_sites"),
    (("warnings",), {}),
    (("warnings",), [None]),
    (("sites",), {}),
    (("sites",), []),
    (("sites", 0), None),
    (("sites", 0, "oriented_start"), 31),
    (("sites", 0, "oriented_start"), 30.0),
    (("sites", 0, "start_codon", "start"), 30.0),
    (("sites", 0, "start_codon", "strand"), "-"),
    (("sites", 0, "codon"), "GUG"),
    (("sites", 0, "window", "oriented_start"), 1),
    (("sites", 0, "window", "oriented_start"), False),
    (("sites", 0, "window", "input_interval", "end"), 64),
    (("sites", 0, "status"), "invalid_input"),
    (("sites", 0, "reason"), "wrong"),
    (("sites", 0, "tir"), True),
    (("sites", 0, "tir"), 0),
    (("sites", 0, "tir"), -1),
    (("sites", 0, "log_tir"), True),
    (("sites", 0, "log_tir"), 100),
    (("sites", 0, "log_tir"), None),
    (("sites", 0, "tir"), float("nan")),
    (("sites", 0, "energies"), None),
    (("sites", 0, "energies"), {}),
    (("sites", 0, "energies", "dG_total"), True),
    (("sites", 0, "energies", "dG_total"), "1"),
    (("sites", 0, "energies", "dG_total"), float("nan")),
    (("sites", 0, "energies", "dG_total"), 10**400),
    (("sites", 0, "energies", "dG_total"), 1e308),
    (("sites", 0, "energies", "dG_total"), -1e308),
    (("sites", 0, "energies", "dG_total"), 10),
    (("sites", 0, "tir"), 1.0),
    (("extra",), 1),
]


@pytest.mark.parametrize("path,bad", MUTATIONS, ids=lambda value: str(value)[:70])
def test_native_contradiction_stops_admission(monkeypatch, fake, path, bad):
    score = rbs.predict

    def corrupt(value, backend, **kwargs):
        result = score(value, backend, **kwargs)
        target = result
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
        return result

    monkeypatch.setattr(rbs, "predict", corrupt)
    result = module.design(example(), Backend())
    assert result["status"] == "no_candidate" and result["coverage"]["not_run"] == 3
    assert result["coverage"]["prediction_calls"] == len(fake) == 1
    assert result["coverage"]["stop_reason"]
    assert all(not row["native_admitted"] for row in result["candidates"])
    assert all(t["tir"] is None for row in result["candidates"] for t in row["targets"])


@pytest.mark.parametrize("payload", [None, False, [], "wrong", {"missing": 1}])
def test_nonobject_or_missing_native_shape(monkeypatch, payload):
    monkeypatch.setattr(rbs, "predict", lambda *a, payload=payload, **kw: payload)
    result = module.design(example(), Backend())
    row = result["candidates"][0]
    assert (
        row["reason"] == "invalid_native_result" and result["coverage"]["not_run"] == 3
    )
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    assert row["native_json_sha256"] == hashlib.sha256(raw).hexdigest()
    assert row["native"] == (payload if type(payload) is dict else None)


def test_invalid_serialization_and_wrong_budget(monkeypatch, fake):
    score = rbs.predict

    def wrong_budget(value, backend, **kwargs):
        native = score(value, backend, **kwargs)
        native["prediction_id"] = digest(
            {
                "input": native["input"],
                "backend": native["backend"],
                "model": native["model"],
                "budget_seconds": kwargs["seconds"] + 1,
            }
        )
        return native

    monkeypatch.setattr(rbs, "predict", wrong_budget)
    assert (
        module.design(example(), Backend())["coverage"]["stop_reason"]
        == "native_identity_mismatch"
    )
    recursive = {}
    recursive["self"] = recursive
    for payload in (recursive, {"bad": object()}):
        monkeypatch.setattr(rbs, "predict", lambda *a, payload=payload, **kw: payload)
        result = module.design(example(), Backend())
        assert result["coverage"]["stop_reason"] == "invalid_native_result"
        assert result["candidates"][0]["native_json_sha256"] is None


def test_status_precedence_reason_roster_and_failed_scalars(monkeypatch, fake):
    score = rbs.predict

    def run(mutate):
        def corrupt(value, backend, **kwargs):
            native = score(value, backend, **kwargs)
            mutate(native)
            return native

        monkeypatch.setattr(rbs, "predict", corrupt)
        result = module.design(example(), Backend())
        assert result["coverage"]["not_run"] == 3 and result["selected"] is None
        return result["coverage"]["stop_reason"]

    assert run(lambda n: n.update(status="failed")) == "native_status_mismatch"
    assert run(lambda n: n["sites"].pop()) == "native_roster_mismatch"
    assert run(lambda n: n["sites"].reverse()) == "native_coordinate_mismatch"
    assert (
        run(lambda n: n.update(status="failed", sites=[], reason=None))
        == "invalid_native_result"
    )
    assert (
        run(lambda n: n["sites"][0].update(status="failed", reason="x"))
        == "invalid_native_score"
    )
    assert (
        run(
            lambda n: n["sites"][0].update(
                status="failed", reason="", tir=None, log_tir=None, energies=None
            )
        )
        == "invalid_native_score"
    )
    assert (
        run(
            lambda n: n["sites"][0].update(
                status="failed", reason="x", tir=None, log_tir=None
            )
        )
        == "invalid_native_score"
    )


def test_exact_native_cap_includes_nested_indentation(monkeypatch, fake):
    value = example()
    backend = Backend()
    request = module.parse_request(value)
    native = REAL_PREDICT(value["rbs"], backend, seconds=20, profile="historical")
    raw = wire.pretty(native)
    limit = len(raw) + 6 * len(raw.splitlines())
    monkeypatch.setattr(module, "NATIVE_LIMIT", limit)
    result = module.design(value, Backend())
    assert result["status"] == "complete"
    monkeypatch.setattr(module, "NATIVE_LIMIT", limit - 1)
    result = module.design(value, Backend())
    row = result["candidates"][0]
    assert row["reason"] == "native_result_limit" and row["native"] is None
    assert (
        row["native_bytes"] == len(raw)
        and row["native_json_sha256"] == hashlib.sha256(raw).hexdigest()
    )
    assert result["coverage"]["not_run"] == request.count - 1


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_preflight_deadline_leaves_complete_unstarted_roster(monkeypatch, fake):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    parse = module.parse_request

    def slow(value):
        result = parse(value)
        clock.now = 181
        return result

    monkeypatch.setattr(module, "parse_request", slow)
    result = module.design(example(), Backend())
    assert result["status"] == "no_candidate" and not fake
    assert (
        result["coverage"]["not_run"] == 4 and result["coverage"]["deadline_exceeded"]
    )
    assert all(row["reason"] == "deadline_exceeded" for row in result["candidates"])


def test_late_candidate_kept_and_no_fresh_confirmation(monkeypatch, fake):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    score = rbs.predict

    def slow(*args, **kwargs):
        native = score(*args, **kwargs)
        clock.now = 181
        return native

    monkeypatch.setattr(rbs, "predict", slow)
    result = module.design(example(), Backend())
    assert (
        result["status"] == "partial"
        and result["proposal"]
        and result["selected"] is None
    )
    assert (
        result["candidates"][0]["status"] == "ok" and result["coverage"]["not_run"] == 3
    )
    assert result["confirmation"]["status"] == "not_run" and len(fake) == 1


def test_constraint_check_consumes_remaining_confirmation_time(monkeypatch, fake):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    check = module.checked_edits
    calls = []

    def slow(*args):
        calls.append(1)
        result = check(*args)
        if len(calls) == 5:
            clock.now = 180
        return result

    monkeypatch.setattr(module, "checked_edits", slow)
    result = module.design(example(), Backend())
    assert (
        result["coverage"]["successful"] == 4
        and result["coverage"]["prediction_calls"] == 4
    )
    assert result["confirmation"]["status"] == "not_run" and result["selected"] is None
    assert result["coverage"]["deadline_exceeded"]


def test_fresh_constraint_failure_and_remaining_native_budget(monkeypatch, fake):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    check = module.checked_edits
    calls = []

    def fail(*args):
        calls.append(1)
        if len(calls) == 5:
            raise wire.DesignError("artificial_constraint_failure")
        return check(*args)

    monkeypatch.setattr(module, "checked_edits", fail)
    result = module.design(example(), Backend())
    assert (
        result["confirmation"]["status"] == "failed"
        and not result["confirmation"]["attempted"]
    )
    assert result["coverage"]["stop_reason"] == "artificial_constraint_failure"
    monkeypatch.setattr(module, "checked_edits", check)
    value = example()
    value["limits"]["seconds_total"] = 0.5
    result = module.design(value, Backend())
    assert result["status"] == "complete" and all(
        settings["seconds"] == 20 and settings["execution_seconds"] == 0.5
        for _, settings in fake[-5:]
    )


@pytest.mark.parametrize("mode", ["late", "mismatch", "failure", "integrity"])
def test_unsuccessful_confirmation_never_chooses_alternative(monkeypatch, fake, mode):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    score = rbs.predict
    calls = []

    def changed(value, backend, **kwargs):
        calls.append(1)
        native = score(value, backend, **kwargs)
        if len(calls) == 5:
            if mode == "late":
                clock.now = 181
            elif mode == "mismatch":
                native["warnings"].append("artificial nondeterminism")
            elif mode == "failure":
                native.update(status="failed", reason="confirmation failed", sites=[])
            else:
                native["prediction_id"] = "0" * 64
        return native

    monkeypatch.setattr(rbs, "predict", changed)
    result = module.design(example(), Backend())
    assert (
        result["status"] == "partial"
        and result["proposal"]
        and result["selected"] is None
    )
    assert (
        result["confirmation"]["status"] == "failed"
        and result["confirmation"]["attempted"]
    )
    assert len(calls) == 5 and result["coverage"]["prediction_calls"] == 5
    assert result["confirmation"]["reason"]


@pytest.mark.parametrize("late", [False, True])
def test_confirmation_integrity_stop_precedes_later_deadline(monkeypatch, fake, late):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    score = rbs.predict

    def corrupt_confirmation(*args, **kwargs):
        native = score(*args, **kwargs)
        if len(fake) == 5:
            native["prediction_id"] = "0" * 64
            if late:
                clock.now = 181
        return native

    monkeypatch.setattr(rbs, "predict", corrupt_confirmation)
    result = module.design(example(), Backend())
    assert result["status"] == "partial" and result["selected"] is None
    assert result["proposal"] is not None
    assert result["reason"] == "native_identity_mismatch"
    assert result["confirmation"]["status"] == "failed"
    assert result["confirmation"]["reason"] == "native_identity_mismatch"
    assert result["confirmation"]["attempted"]
    assert not result["confirmation"]["native_admitted"]
    assert result["coverage"] == {
        "planned": 4,
        "attempted": 4,
        "successful": 4,
        "failed": 0,
        "not_run": 0,
        "prediction_calls": 5,
        "all_candidates_scored": True,
        "deadline_exceeded": late,
        "stop_reason": "native_identity_mismatch",
    }
    assert len(fake) == 5
    assert all(row["status"] == "ok" for row in result["candidates"])
    assert all(len(row["targets"]) == 2 for row in result["candidates"])


def test_integrity_failure_after_success_blocks_confirmation(monkeypatch, fake):
    score = rbs.predict
    calls = []

    def changed(*args, **kwargs):
        calls.append(1)
        native = score(*args, **kwargs)
        if len(calls) == 2:
            native["prediction_id"] = "0" * 64
        return native

    monkeypatch.setattr(rbs, "predict", changed)
    result = module.design(example(), Backend())
    assert result["status"] == "partial" and result["coverage"]["not_run"] == 2
    assert (
        result["confirmation"]["status"] == "not_run"
        and not result["confirmation"]["attempted"]
    )
    assert (
        result["confirmation"]["reason"] == "native_identity_mismatch"
        and len(fake) == 2
    )


@pytest.mark.parametrize("when", ["before", "after"])
def test_backend_identity_substitution_and_honest_invocation_count(
    monkeypatch, fake, when
):
    backend = Backend()
    score = rbs.predict
    reads = []

    def clock():
        reads.append(1)
        if when == "before" and len(reads) == 2:
            backend.identity = {"wrong": True}
        return 0.0

    monkeypatch.setattr(module.time, "monotonic", clock)

    def changed(*args, **kwargs):
        native = score(*args, **kwargs)
        backend.identity = {"wrong": True}
        return native

    if when == "after":
        monkeypatch.setattr(rbs, "predict", changed)
    result = module.design(example(), backend)
    assert result["coverage"]["attempted"] == 1 and result["coverage"]["not_run"] == 3
    assert (
        result["coverage"]["prediction_calls"]
        == len(fake)
        == (0 if when == "before" else 1)
    )
    assert result["coverage"]["stop_reason"] == "native_identity_mismatch"
