"""Native contradictions, failure denominators, deadlines and confirmation."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from regsite import (
    promoter,
    promoter_io,
)
from regsite import (
    promoter_design as design,
)
from regsite import (
    promoter_design_io as io,
)


def request():
    value = json.loads(Path("examples/promoter-design-single.json").read_text())
    value["limits"]["seconds_total"] = 1.0
    return value


def mutate(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def fail_site(native, index=0):
    record = native["results"][0]
    record["sites"][index].update(
        status="failed", reason="nonfinite_arithmetic", selected=None, tie_count=None
    )
    promoter_io._summarize(record)
    native["batch"].update(
        status_counts={
            status: int(status == "failed") for status in promoter_io.STATUSES
        },
        complete=False,
    )
    return native


def unsupported(native):
    native["results"][0].update(
        status="unsupported",
        reasons=["model_unavailable"],
        prediction_id=None,
        coverage=None,
        sites=[],
        errors=[
            {
                "code": "model_unavailable",
                "field": "model",
                "message": "artificial refusal",
            }
        ],
    )
    native["batch"].update(
        status_counts={
            status: int(status == "unsupported") for status in promoter_io.STATUSES
        },
        complete=True,
    )
    return native


@pytest.mark.parametrize("failure", [fail_site, unsupported])
def test_ordinary_native_failure_keeps_all_rows_and_can_confirm_other_successes(
    failure, monkeypatch
):
    real = promoter_io.predict_batch
    count = 0

    def predict(*args, **kwargs):
        nonlocal count
        count += 1
        native = real(*args, **kwargs)
        return failure(native) if count == 1 else native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=lambda: 0.0)
    assert result["status"] == "partial" and result["selected"] is not None
    assert count == 5
    assert result["coverage"] == {
        "planned": 4,
        "attempted": 4,
        "successful": 3,
        "failed": 1,
        "not_run": 0,
        "prediction_calls": 5,
        "all_candidates_scored": False,
        "deadline_exceeded": False,
        "stop_reason": None,
    }
    failed = result["candidates"][0]
    assert failed["native_admitted"] and failed["objective"] is None
    assert (
        failed["observed_log_scores"] is None and failed["absolute_log_errors"] is None
    )
    assert result["confirmation"]["status"] == "matched"


def test_tied_neutral_mutants_use_dna_order_after_failed_seed(monkeypatch):
    value = request()
    value["promoter"]["sequence"] = "A" * 200
    value["promoter"]["scan"]["positions"] = [{"strand": "+", "tss": 100}]
    value.update(
        target_log_scores=[0],
        editable_positions=[117, 118],
        immutable_intervals=[[0, 117], [119, 200]],
    )
    value["limits"]["max_candidates"] = 7
    real = promoter_io.predict_batch
    calls = 0

    def predict(*args, **kwargs):
        nonlocal calls
        calls += 1
        native = real(*args, **kwargs)
        return fail_site(native) if calls == 1 else native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(value, clock=lambda: 0.0)
    rows = result["candidates"]
    assert result["status"] == "partial" and calls == 8
    assert len({row["objective"] for row in rows[1:]}) == 1
    expected = "A" * 118 + "C" + "A" * 81
    assert result["selected"]["sequence"] == expected
    assert result["selected"]["index"] == 4
    assert rows[1]["sequence"] > expected


def test_all_ordinary_failures_leave_no_proposal(monkeypatch):
    real = promoter_io.predict_batch
    monkeypatch.setattr(
        promoter_io, "predict_batch", lambda *a, **k: fail_site(real(*a, **k))
    )
    result = design.design(request(), clock=lambda: 0.0)
    assert result["status"] == "no_candidate"
    assert result["proposal"] is result["confirmation"] is result["selected"] is None
    assert result["coverage"]["failed"] == result["coverage"]["prediction_calls"] == 4


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("schema_version",), "bad"),
        (("model", "id"), "bad"),
        (("model", "implementation_version"), "other"),
        (("results",), []),
        (("results", 0), []),
        (("results", 0, "id"), "other"),
        (("results", 0, "prediction_id"), "0" * 64),
        (("results", 0, "input", "raw_sha256"), "0" * 64),
        (("results", 0, "calibration", "beta"), 1.0),
        (("results", 0, "metadata"), {}),
        (("results", 0, "warnings"), []),
        (("results", 0, "sites"), []),
        (("results", 0, "sites", 0), None),
        (("results", 0, "sites", 0, "status"), "unknown"),
        (("results", 0, "sites", 0, "state_count"), True),
        (("results", 0, "sites", 0, "state_count"), 29),
        (("results", 0, "sites", 0, "attempted"), 1),
        (("results", 0, "sites", 0, "attempted"), False),
        (("results", 0, "sites", 0, "selected"), None),
        (("results", 0, "sites", 0, "tie_count"), 0),
        (("results", 0, "sites", 0, "tss", "oriented_base"), 101),
        (("results", 0, "sites", 0, "selected", "discriminator_length"), 5),
        (("results", 0, "sites", 0, "selected", "spacer_length"), 21),
        (("results", 0, "sites", 0, "selected", "terms"), {}),
        (("results", 0, "sites", 0, "selected", "terms", "total"), True),
        (
            ("results", 0, "sites", 0, "selected", "log_relative_transcription_score"),
            0.0,
        ),
        (("results", 0, "sites", 0, "selected", "relative_transcription_score"), None),
        (("results", 0, "sites", 0, "selected", "score_status"), "underflow"),
        (("results", 0, "sites", 0, "selected", "elements", "itr"), "A" * 20),
        (("results", 0, "sites", 0, "selected", "intervals", "itr"), [100, 119]),
        (("results", 0, "coverage", "scored_sites"), 0),
        (("batch", "batch_id"), "0" * 64),
        (("batch", "seconds_per_record"), 1),
        (("batch", "record_count"), True),
        (("batch", "status_counts", "ok"), 2),
    ],
)
def test_native_contradictions_stop_refill_and_retain_opaque_evidence(
    path, replacement, monkeypatch
):
    real = promoter_io.predict_batch
    returned = []

    def predict(*args, **kwargs):
        native = real(*args, **kwargs)
        mutate(native, path, replacement)
        returned.append(copy.deepcopy(native))
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=lambda: 0.0)
    assert result["status"] == "no_candidate" and len(returned) == 1
    assert result["coverage"]["not_run"] == 3
    first = result["candidates"][0]
    assert first["reason"] == "native_contract" and not first["native_admitted"]
    assert first["native"] == returned[0] and first["objective"] is None
    assert all(
        row["reason"] == "native_contract" and not row["attempted"]
        for row in result["candidates"][1:]
    )


@pytest.mark.parametrize(
    "replacement,reason,has_hash",
    [
        ([], "native_shape", True),
        (None, "native_shape", True),
        ({"large": "x" * 131072}, "native_output_limit", True),
        ({"x": float("nan")}, "native_serialization", False),
        ({"x": (1, 2)}, "native_serialization", False),
    ],
)
def test_bounded_or_unserializable_native_payloads(
    replacement, reason, has_hash, monkeypatch
):
    monkeypatch.setattr(promoter_io, "predict_batch", lambda *a, **k: replacement)
    result = design.design(request(), clock=lambda: 0.0)
    first = result["candidates"][0]
    assert first["native"] is None and first["reason"] == reason
    assert (first["native_sha256"] is not None) == has_hash
    assert first["native_bytes"] is None if not has_hash else first["native_bytes"] > 0
    if has_hash:
        raw = (
            json.dumps(replacement, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode()
        assert first["native_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["coverage"]["not_run"] == 3


def test_predictor_exception_after_success_prevents_confirmation_and_new_admission(
    monkeypatch,
):
    real = promoter_io.predict_batch
    calls = 0

    def predict(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("private detail")
        return real(*args, **kwargs)

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=lambda: 0.0)
    assert calls == 2 and result["status"] == "partial"
    assert result["proposal"] is not None and result["selected"] is None
    assert result["confirmation"]["status"] == "not_run"
    assert result["coverage"]["not_run"] == 2
    assert "private detail" not in json.dumps(result)


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


@pytest.mark.parametrize(
    "when,attempted",
    [("preflight", 0), ("constraints", 0), ("first_call", 1), ("confirmation", 5)],
)
def test_cooperative_deadlines_preserve_late_outcomes(when, attempted, monkeypatch):
    clock = Clock()
    real_parse, real_constraints, real_predict = (
        design.parse_request,
        design._constraints,
        promoter_io.predict_batch,
    )
    calls = 0

    def parse(value):
        result = real_parse(value)
        if when == "preflight":
            clock.value = 1.0
        return result

    def constraints(*args):
        result = real_constraints(*args)
        if when == "constraints":
            clock.value = 1.0
        return result

    def predict(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = real_predict(*args, **kwargs)
        if when == "first_call" or (when == "confirmation" and calls == 5):
            clock.value = 1.0
        return result

    monkeypatch.setattr(design, "parse_request", parse)
    monkeypatch.setattr(design, "_constraints", constraints)
    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=clock)
    assert calls == attempted and result["coverage"]["prediction_calls"] == attempted
    assert result["coverage"]["deadline_exceeded"]
    assert result["reason"] == result["coverage"]["stop_reason"] == "total_deadline"
    if attempted == 0:
        assert result["status"] == "no_candidate" and result["coverage"]["not_run"] == 4
    else:
        assert (
            result["status"] == "partial" and result["candidates"][0]["status"] == "ok"
        )
        assert (result["selected"] is not None) == (when == "confirmation")


@pytest.mark.parametrize("fault", ["failed", "contract"])
def test_confirmation_never_falls_back_to_another_candidate(fault, monkeypatch):
    real = promoter_io.predict_batch
    calls = 0

    def predict(*args, **kwargs):
        nonlocal calls
        calls += 1
        native = real(*args, **kwargs)
        if calls == 5:
            if fault == "failed":
                return fail_site(native)
            if fault == "contract":
                native["model"]["id"] = "bad"
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=lambda: 0.0)
    assert calls == 5 and result["status"] == "partial"
    assert result["proposal"] is not None and result["selected"] is None
    assert result["confirmation"]["status"] == "failed"


def test_equal_score_but_different_complete_native_confirmation_is_rejected(
    monkeypatch,
):
    value = request()
    value["promoter"]["sequence"] = "A" * 200
    value["max_changes"] = 0
    real = promoter_io.predict_batch
    calls = 0

    def predict(native_request, params, **kwargs):
        nonlocal calls
        calls += 1
        native = real(native_request, params, **kwargs)
        if calls == 2:
            site = native["results"][0]["sites"][0]
            assert (
                site["selected"]["discriminator_length"] == 6 and site["tie_count"] == 5
            )
            alternate = promoter.score_state("A" * 200, 100, 7, 17, params)
            calibration = promoter.resolve_calibration(native_request["calibration"])
            selected = alternate.to_dict(200, "+", calibration)
            selected["state_id"] = site["site_id"] + ":d7s17"
            assert (
                selected["log_relative_transcription_score"]
                == site["selected"]["log_relative_transcription_score"]
            )
            site["selected"] = selected
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(value, clock=lambda: 0.0)
    assert calls == 2 and result["status"] == "partial"
    assert result["confirmation"]["native_admitted"]
    assert result["confirmation"]["status"] == "mismatch"
    assert result["selected"] is None and result["proposal"] is not None


def test_exact_native_byte_cap_and_one_byte_over(monkeypatch):
    value = request()
    value["max_changes"] = 0
    baseline = design.design(value, clock=lambda: 0.0)
    size = baseline["candidates"][0]["native_bytes"]
    monkeypatch.setattr(io, "NATIVE_LIMIT", size)
    assert design.design(value, clock=lambda: 0.0)["status"] == "complete"
    monkeypatch.setattr(io, "NATIVE_LIMIT", size - 1)
    result = design.design(value, clock=lambda: 0.0)
    assert result["candidates"][0]["reason"] == "native_output_limit"


@pytest.mark.parametrize(
    "total,score_status", [(500.0, "underflow"), (-500.0, "overflow")]
)
def test_finite_log_scores_rank_even_when_linear_scores_are_null(
    total, score_status, monkeypatch
):
    value = request()
    value["max_changes"] = 0
    real = promoter_io.predict_batch

    def predict(*args, **kwargs):
        native = real(*args, **kwargs)
        calibration = native["results"][0]["calibration"]
        for site in native["results"][0]["sites"]:
            state = site["selected"]
            state["terms"]["total"] = total
            state.update(
                log_relative_transcription_score=math.log(calibration["K"])
                - calibration["beta"] * total,
                relative_transcription_score=None,
                score_status=score_status,
            )
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(value, clock=lambda: 0.0)
    assert result["status"] == "complete" and result["selected"] is not None
    assert result["confirmation"]["status"] == "matched"
    assert all(math.isfinite(v) for v in result["selected"]["observed_log_scores"])
    assert result["selected"]["objective"] > 700


def test_unrepresentable_mean_is_failure_not_an_infinite_rank(monkeypatch):
    real = promoter_io.predict_batch

    def predict(*args, **kwargs):
        native = real(*args, **kwargs)
        beta = native["results"][0]["calibration"]["beta"]
        for site in native["results"][0]["sites"]:
            state = site["selected"]
            state["terms"].update(
                hex10=-1e308,
                total=-1e308,
                binding=-1e308,
                source_apparent=(-1e308 + 2.80271176) / 0.81632623,
            )
            state.update(
                log_relative_transcription_score=math.log(42) - beta * -1e308,
                relative_transcription_score=None,
                score_status="overflow",
            )
        return native

    monkeypatch.setattr(promoter_io, "predict_batch", predict)
    result = design.design(request(), clock=lambda: 0.0)
    assert (
        result["status"] == "no_candidate"
        and result["coverage"]["prediction_calls"] == 4
    )
    for row in result["candidates"]:
        assert row["native_admitted"] and row["reason"] == "objective_unrepresentable"
        assert row["objective"] is None and len(row["observed_log_scores"]) == 2
        assert all(math.isfinite(v) for v in row["absolute_log_errors"])


@pytest.mark.parametrize("when", [1, 5])
@pytest.mark.parametrize(
    "fault",
    [
        "outside_edit",
        "wrong_length",
        "wrong_edits",
        "changed_request",
        "changed_request_hash",
    ],
)
def test_constraints_are_rechecked_before_candidate_and_confirmation(
    when, fault, monkeypatch
):
    original = design._candidate
    built = 0

    def candidate(*args):
        nonlocal built
        built += 1
        row = original(*args)
        if built == when:
            if fault == "outside_edit":
                row["sequence"] = "T" + row["sequence"][1:]
            if fault == "wrong_length":
                row["sequence"] += "A"
            if fault == "wrong_edits":
                row["edits"] = [{"position": 1}]
            if fault == "changed_request":
                row["native_request"]["id"] = "unexpected"
            if fault == "changed_request_hash":
                row["native_request_sha256"] = "0" * 64
        return row

    monkeypatch.setattr(design, "_candidate", candidate)
    result = design.design(request(), clock=lambda: 0.0)
    assert result["reason"] == "candidate_constraints"
    assert result["selected"] is None
    if when == 1:
        assert result["coverage"]["prediction_calls"] == 0
        assert all(row["status"] == "not_run" for row in result["candidates"])
    else:
        assert result["coverage"]["prediction_calls"] == 4
        assert (
            result["proposal"] is not None
            and result["confirmation"]["status"] == "not_run"
        )


@pytest.mark.parametrize("phase", ["proposal", "confirmation_constraints"])
def test_expiry_while_preparing_confirmation_prevents_admission(phase, monkeypatch):
    clock = Clock()
    original_proposal, original_constraints = design._proposal, design._constraints
    validations = 0

    def proposal(row):
        result = original_proposal(row)
        if phase == "proposal":
            clock.value = 1.0
        return result

    def constraints(*args):
        nonlocal validations
        validations += 1
        result = original_constraints(*args)
        if phase == "confirmation_constraints" and validations == 5:
            clock.value = 1.0
        return result

    monkeypatch.setattr(design, "_proposal", proposal)
    monkeypatch.setattr(design, "_constraints", constraints)
    result = design.design(request(), clock=clock)
    assert result["status"] == "partial" and result["selected"] is None
    assert result["coverage"]["prediction_calls"] == 4
    assert result["confirmation"]["status"] == "not_run"
    assert result["confirmation"]["reason"] == "total_deadline"
