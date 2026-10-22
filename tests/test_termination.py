"""Public termination contracts; native execution is verified separately."""

import copy
import hashlib
from types import SimpleNamespace

import pytest

from regsite import termination as subject
from regsite.termination_backend import TerminationBackendError
from regsite.termination_io import canonical_bytes, canonical_hash

SEQUENCE = "AC" * 40


def request(*records, **settings):
    return {
        "schema_version": "termination-request-1",
        "records": list(records) or [{"id": "fragment", "sequence": SEQUENCE}],
        "settings": {"max_seconds": 30, "per_record_seconds": 5, **settings},
    }


def diagnostics():
    return {
        "stdout_sha256": hashlib.sha256(b"fixture").hexdigest(),
        "stdout_bytes": 7,
        "stdout_complete": True,
        "stderr_sha256": hashlib.sha256(b"").hexdigest(),
        "stderr_bytes": 0,
        "stderr_complete": True,
        "returncode": 0,
    }


class FakeBackend:
    """A scheduling test double, never used as native scientific evidence."""

    identity = {"test_identity": "unit-only"}

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def run(self, sequence, *, timeout_seconds):
        self.calls.append((sequence, timeout_seconds))
        if self.error:
            raise self.error
        return SimpleNamespace(stdout=b"fixture", diagnostics=diagnostics())


@pytest.fixture
def parsed(monkeypatch):
    monkeypatch.setattr(subject, "parse_output", lambda raw, sequence: [])


def assert_identity(result):
    complete = {key: value for key, value in result.items() if key != "result_sha256"}
    assert result["result_sha256"] == canonical_hash(complete)
    prediction = {
        key: value for key, value in complete.items() if key != "prediction_sha256"
    }
    prediction["records"] = [
        {key: value for key, value in record.items() if key != "execution"}
        for record in prediction["records"]
    ]
    assert result["prediction_sha256"] == canonical_hash(prediction)


@pytest.mark.parametrize("value", [None, [], {}, 1, {"schema_version": "wrong"}])
def test_invalid_envelope_has_no_accepted_roster(value):
    result = subject.predict_termination(value)
    assert result["status"] == "invalid_input"
    assert result["records"] == []
    assert result["coverage"] is None
    assert_identity(result)


@pytest.mark.parametrize("records", [[], [None] * 21, None, "records"])
def test_roster_type_and_count_limits(records):
    value = request()
    value["records"] = records
    assert subject.predict_termination(value)["reason"] == "invalid_envelope"


def test_schema_version_and_unknown_envelope_fields():
    value = request()
    value["schema_version"] = "other"
    assert subject.predict_termination(value)["reason"] == "invalid_envelope"
    value = request()
    value["extra"] = 1
    assert subject.predict_termination(value)["reason"] == "invalid_envelope"


@pytest.mark.parametrize(
    "settings",
    [
        None,
        [],
        {},
        {"max_seconds": 1},
        {"max_seconds": 1, "per_record_seconds": 1, "x": 0},
    ],
)
def test_settings_shape(settings):
    value = request()
    value["settings"] = settings
    assert subject.predict_termination(value)["reason"] == "invalid_settings"


@pytest.mark.parametrize("key", ["max_seconds", "per_record_seconds"])
@pytest.mark.parametrize("value", [False, True, "1", None, 0, -1, 0.0009, 301])
def test_budget_type_and_bounds(key, value):
    assert (
        subject.predict_termination(request(**{key: value}))["reason"]
        == "invalid_settings"
    )


def test_per_record_upper_bound():
    assert (
        subject.predict_termination(request(per_record_seconds=60.001))["reason"]
        == "invalid_settings"
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {1, 2}])
def test_non_json_values_do_not_acquire_request_identity(bad):
    result = subject.predict_termination(bad)
    assert result["reason"] == "request_is_not_bounded_finite_json"
    assert result["request_sha256"] is None


def test_api_depth_limit():
    value = []
    for _ in range(32):
        value = [value]
    assert (
        subject.predict_termination(value)["reason"]
        == "request_is_not_bounded_finite_json"
    )


def test_object_cap_is_independent_from_transport(monkeypatch):
    value = request()
    size = len(canonical_bytes(value))
    monkeypatch.setattr(subject, "OBJECT_LIMIT", size)
    assert subject.predict_termination(value)["status"] == "partial"
    monkeypatch.setattr(subject, "OBJECT_LIMIT", size - 1)
    result = subject.predict_termination(value)
    assert result["reason"] == "api_object_byte_limit"
    assert result["request_sha256"] == canonical_hash(value)


def test_duplicate_ids_reject_whole_envelope():
    value = request(
        {"id": "same", "sequence": SEQUENCE}, {"id": "same", "sequence": SEQUENCE}
    )
    result = subject.predict_termination(value)
    assert result["reason"] == "duplicate_record_id"
    assert result["records"] == []


@pytest.mark.parametrize(
    "record",
    [
        None,
        [],
        {},
        {"id": "x"},
        {"id": "x", "sequence": SEQUENCE, "x": 1},
        {"id": [], "sequence": SEQUENCE},
        {"id": "", "sequence": SEQUENCE},
        {"id": "é", "sequence": SEQUENCE},
        {"id": "x" * 129, "sequence": SEQUENCE},
        {"id": "x", "sequence": 1},
    ],
)
def test_invalid_records_are_retained(record):
    result = subject.predict_termination(request(record))
    assert len(result["records"]) == 1
    item = result["records"][0]
    assert item["index"] == 0
    assert item["status"] == "invalid_input"
    assert item["reason"] == "invalid_record"
    assert item["candidates"] is None
    assert result["coverage"]["failed_records"] == 1


@pytest.mark.parametrize(
    "sequence",
    [
        "",
        " \t\r\n",
        "ACGN",
        "ACGU",
        "ACGT\x00",
        ">seq\nACGT",
        "A-CG",
        "ＡＣＧＴ",
        "AC\u00a0GT",
    ],
)
def test_invalid_symbols_never_reach_backend(sequence):
    backend = FakeBackend()
    result = subject.predict_termination(
        request({"id": "x", "sequence": sequence}), backend=backend
    )
    assert result["records"][0]["reason"] == "invalid_sequence_alphabet"
    assert backend.calls == []


@pytest.mark.parametrize("sequence", ["AC" * 37, "AC" * 50001])
def test_length_domain_preserves_normalized_input_identity(sequence):
    item = subject.predict_termination(request({"id": "x", "sequence": sequence}))[
        "records"
    ][0]
    assert item["reason"] == "sequence_length_outside_domain"
    assert item["input"] == {
        "sequence_length": len(sequence),
        "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
    }
    assert item["coverage"] is None
    assert item["candidates"] is None


def test_length_75_does_not_turn_zero_coverage_into_a_negative():
    item = subject.predict_termination(
        request({"id": "x", "sequence": "AC" * 37 + "A"})
    )["records"][0]
    assert item["reason"] == "no_search_positions"
    assert item["coverage"]["total_anchor_positions"] == 0
    assert item["candidates"] is None
    assert item["attempted"] is False


@pytest.mark.parametrize(
    "sequence",
    [
        "AC" + "G" * 76 + "AC",
        "AC" + "A" * 76 + "AC",
        "GG" + "AC" * 38 + "GG",
        "AA" + "AC" * 38 + "AA",
    ],
)
def test_uniform_backgrounds_remain_unsupported(sequence):
    result = subject.predict_termination(request({"id": "x", "sequence": sequence}))
    assert result["records"][0]["reason"] == "uniform_background"
    assert result["coverage"]["domain_eligible_records"] == 0


def test_supported_boundaries_and_normalization(parsed):
    backend = FakeBackend()
    short = "ac" * 38
    long = "ac" * 50000
    value = request(
        {"id": "a" * 128, "sequence": "\t " + short + "\r\n\v\f"},
        {"id": "long", "sequence": long},
        max_seconds=300,
        per_record_seconds=60,
    )
    before = copy.deepcopy(value)
    result = subject.predict_termination(value, backend=backend, clock=lambda: 0)
    assert result["status"] == "complete"
    assert value == before
    assert backend.calls == [(short.upper(), 60), (long.upper(), 60)]
    assert result["records"][0]["coverage"] == {
        "forward_anchors": {"start": 59, "end": 60, "count": 1},
        "reverse_anchors": {"start": 16, "end": 17, "count": 1},
        "total_anchor_positions": 2,
    }
    assert result["records"][0]["candidates"] == []
    assert result["coverage"]["successful_records"] == 2
    assert_identity(result)


@pytest.mark.parametrize(
    "count,table,tie,clamped",
    [
        (27, 26, True, False),
        (55, 56, True, False),
        (26, 26, False, False),
        (1, 26, False, True),
        (99, 84, False, True),
    ],
)
def test_table_selection_preserves_binary64_and_exact_tie_distinction(
    count, table, tie, clamped
):
    actual = subject._background("A" * count + "C" * (100 - count))
    assert actual == {
        "at_count": count,
        "gc_count": 100 - count,
        "length": 100,
        "at_fraction": count / 100,
        "selected_at_percent": table,
        "exact_table_tie": tie,
        "endpoint_clamped": clamped,
    }


def test_maximum_roster(parsed):
    value = request(*[{"id": str(i), "sequence": SEQUENCE} for i in range(20)])
    result = subject.predict_termination(value, backend=FakeBackend(), clock=lambda: 0)
    assert result["coverage"] == {
        "requested_records": 20,
        "domain_eligible_records": 20,
        "attempted_records": 20,
        "successful_records": 20,
        "not_evaluated_records": 0,
        "failed_records": 0,
        "retained_candidates": 0,
        "admitted_candidate_scores": 0,
    }


def test_missing_or_failed_backend_keeps_eligible_records():
    for backend, expected in [
        (None, "backend_unavailable"),
        (
            TerminationBackendError("bad config", code="backend_manifest"),
            "backend_manifest",
        ),
    ]:
        result = subject.predict_termination(request(), backend=backend)
        assert result["model"]["backend"] is None
        assert result["records"][0]["reason"] == expected
        assert result["records"][0]["attempted"] is False
        assert result["coverage"]["domain_eligible_records"] == 1


@pytest.mark.parametrize("capture", [None, diagnostics()])
def test_native_failures_preserve_capture_and_null_candidates(capture):
    error = TerminationBackendError(
        "native failed", code="native_exit", diagnostics=capture
    )
    result = subject.predict_termination(request(), backend=FakeBackend(error))
    item = result["records"][0]
    assert item["attempted"] is True
    assert item["status"] == "backend_failure"
    assert item["execution"] == capture
    assert item["candidates"] is None


def test_parser_failure_retains_successful_process_capture(monkeypatch):
    def invalid(*args):
        raise TerminationBackendError("invalid output", code="native_output_invalid")

    monkeypatch.setattr(subject, "parse_output", invalid)
    result = subject.predict_termination(request(), backend=FakeBackend())
    assert result["records"][0]["execution"] == diagnostics()
    assert result["records"][0]["reason"] == "native_output_invalid"


@pytest.mark.parametrize(
    "times,attempted,reason",
    [
        ([0, 1], False, "time_budget_exhausted"),
        ([0, 0, 1], False, "time_budget_exhausted"),
        ([0, 0, 0, 1], True, "batch_deadline_exceeded"),
    ],
)
def test_deadlines_keep_roster_and_never_export_late_success(
    parsed, times, attempted, reason
):
    clock = iter(times)
    backend = FakeBackend()
    result = subject.predict_termination(
        request(max_seconds=1), backend=backend, clock=lambda: next(clock)
    )
    item = result["records"][0]
    assert item["reason"] == reason
    assert item["attempted"] is attempted
    assert item["candidates"] is None
    assert len(result["records"]) == 1


def test_per_record_budget_is_capped_by_remaining_batch(parsed):
    backend = FakeBackend()
    subject.predict_termination(
        request(max_seconds=0.001, per_record_seconds=60),
        backend=backend,
        clock=lambda: 0,
    )
    assert backend.calls[0][1] == 0.001


def test_candidate_counts_include_withheld_confidence(monkeypatch):
    candidates = [{"confidence": 78}, {"confidence": None}]
    monkeypatch.setattr(subject, "parse_output", lambda *args: candidates)
    result = subject.predict_termination(
        request(), backend=FakeBackend(), clock=lambda: 0
    )
    assert result["records"][0]["candidates"] == candidates
    assert result["coverage"]["retained_candidates"] == 2
    assert result["coverage"]["admitted_candidate_scores"] == 1
    assert_identity(result)


def test_runtime_capture_variation_does_not_change_prediction_identity(parsed):
    first = subject.predict_termination(
        request(), backend=FakeBackend(), clock=lambda: 0
    )

    class DifferentTiming(FakeBackend):
        def run(self, sequence, *, timeout_seconds):
            native = super().run(sequence, timeout_seconds=timeout_seconds)
            native.diagnostics["stderr_sha256"] = "b" * 64
            native.diagnostics["stderr_bytes"] = 40
            return native

    second = subject.predict_termination(
        request(), backend=DifferentTiming(), clock=lambda: 0
    )
    assert first["prediction_sha256"] == second["prediction_sha256"]
    assert first["result_sha256"] != second["result_sha256"]
    assert_identity(first)
    assert_identity(second)
