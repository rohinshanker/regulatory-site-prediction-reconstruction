"""Independent search invariants and artificial scorer/failure controls."""

import copy
import hashlib
import itertools
import json
import math
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import design as module
from regsite import design_io as wire
from regsite.contracts import RbsRequest
from regsite.profiles import get_profile
from regsite.sequence import input_interval, reverse_complement
from regsite.structures import BackendError


def example():
    return json.loads(Path("examples/rbs-design-single.json").read_text())


def backend():
    return SimpleNamespace(identity={"name": "artificial-test", "version": "1"})


def native(value, engine, *, seconds, profile, execution_seconds):
    """Artificial response with real public request/prediction identities."""
    request = RbsRequest.from_dict(value)
    spec = get_profile(profile)
    start = request.start_positions[0]
    begin = max(0, start - spec.upstream_nt)
    end = min(len(request.sequence), start + spec.downstream_nt)
    model = {"id": spec.model_id, "parameters": {"artificial_control": True}}
    stable = {
        "input": asdict(request),
        "model": model,
        "backend": copy.deepcopy(engine.identity),
        "budget_seconds": float(seconds),
    }
    return {
        "model": model,
        "backend": stable["backend"],
        "input": stable["input"],
        "prediction_id": hashlib.sha256(
            json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "status": "ok",
        "reason": None,
        "sites": [
            {
                "status": "ok",
                "reason": None,
                "oriented_start": start,
                "start_codon": asdict(
                    input_interval(
                        start, start + 3, len(request.sequence), request.strand
                    )
                ),
                "codon": request.oriented_sequence[start : start + 3],
                "window": {
                    "oriented_start": begin,
                    "oriented_end": end,
                    "input_interval": asdict(
                        input_interval(
                            begin, end, len(request.sequence), request.strand
                        )
                    ),
                },
                "tir": 1000.0,
                "log_tir": math.log(1000.0),
            }
        ],
    }


@pytest.fixture
def fake(monkeypatch):
    calls = []

    def score(value, engine, **kwargs):
        calls.append((copy.deepcopy(value), kwargs))
        return native(value, engine, **kwargs)

    monkeypatch.setattr(module, "predict", score)
    return calls


def verify_hash(result):
    content = {k: v for k, v in result.items() if k != "result_sha256"}
    assert (
        result["result_sha256"]
        == hashlib.sha256(
            json.dumps(
                content, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("changes", [0, 1, 2])
def test_exhaustive_roster_independent_cartesian_oracle(strand, changes, fake):
    value = example()
    value["rbs"]["strand"] = strand
    if strand == "-":
        value["rbs"]["sequence"] = reverse_complement(
            value["rbs"]["sequence"].replace("T", "U")
        ).replace("U", "T")
    length = len(value["rbs"]["sequence"])
    positions = [2, 4, 5] if strand == "+" else [length - 3, length - 5, length - 6]
    value.update(editable_positions=positions, max_changes=changes)
    value["limits"]["max_candidates"] = 64
    seed = value["rbs"]["sequence"]
    expected = set()
    for replacements in itertools.product("ACGT", repeat=3):
        seq = list(seed)
        for position, base in zip(positions, replacements, strict=True):
            seq[position] = base
        if sum(a != b for a, b in zip(seed, seq, strict=True)) <= changes:
            expected.add("".join(seq))
    result = module.design(value, backend())
    assert result["status"] == "complete"
    assert {r["sequence"] for r in result["candidates"]} == expected
    assert len(result["candidates"]) == len(expected) == result["coverage"]["planned"]
    assert [len(r["edits"]) for r in result["candidates"]] == sorted(
        len(r["edits"]) for r in result["candidates"]
    )
    assert (
        result["selected"]["sequence"] == seed
    )  # Equal objectives prefer fewer edits.
    assert len(fake) == len(expected) + 1
    assert fake[-1][0]["sequence"] == seed
    for row in result["candidates"]:
        for edit in row["edits"]:
            i = edit["input_position"]
            assert edit["oriented_position"] == (i if strand == "+" else length - 1 - i)
            assert edit["from"] == seed[i] and edit["to"] == row["sequence"][i]
        assert row["native_sha256"] == wire.digest(row["native"])
    verify_hash(result)
    assert value["editable_positions"] == positions  # No caller mutation.


def test_best_target_then_lexical_order(monkeypatch):
    def scorer(value, engine, **kwargs):
        result = native(value, engine, **kwargs)
        tir = 2.0 if value["sequence"][4] == "G" else 100.0
        result["sites"][0].update(tir=tir, log_tir=math.log(tir))
        return result

    monkeypatch.setattr(module, "predict", scorer)
    value = example()
    value["target_tir"] = 100.0
    result = module.design(value, backend())
    assert result["selected"]["sequence"][4] == "A"
    assert result["selected"]["score"]["absolute_log_error"] == 0
    assert result["confirmation"]["status"] == "verified"


@pytest.mark.parametrize(
    "path,bad",
    [
        ([], []),
        ([], None),
        (["schema_version"], "wrong"),
        (["rbs"], None),
        (["rbs", "sequence"], "AAAGGAGGAAAAAAaugAAA"),
        (["rbs", "sequence"], "AAAGGAGGAAAAAA ATGAAA"),
        (["rbs", "sequence"], "A" * 1001),
        (["rbs", "sequence"], "A" * 1001 + "ATG"),
        (["rbs", "start_positions"], None),
        (["rbs", "start_positions"], []),
        (["rbs", "start_positions"], [0]),
        (["rbs", "start_positions"], [13, 14]),
        (["rbs", "start_positions"], [15]),
        (["rbs", "start_positions"], [True]),
        (["profile"], "invalid"),
        (["profile"], []),
        (["target_tir"], True),
        (["target_tir"], 0),
        (["target_tir"], -1),
        (["target_tir"], float("nan")),
        (["target_tir"], float("inf")),
        (["target_tir"], 10**400),
        (["target_tir"], "1"),
        (["editable_positions"], None),
        (["editable_positions"], [True]),
        (["editable_positions"], [1.0]),
        (["editable_positions"], [1, 1]),
        (["editable_positions"], [-1]),
        (["editable_positions"], [14]),
        (["editable_positions"], [51]),
        (["max_changes"], True),
        (["max_changes"], -1),
        (["max_changes"], 2),
        (["limits"], {}),
        (["limits"], None),
        (["limits", "max_candidates"], 3),
        (["limits", "max_candidates"], 0),
        (["limits", "max_candidates"], 257),
        (["limits", "max_candidates"], True),
        (["limits", "max_candidates"], 4.0),
        (["limits", "seconds_per_score"], 0),
        (["limits", "seconds_per_score"], 120.1),
        (["limits", "seconds_per_score"], False),
        (["limits", "seconds_per_score"], "1"),
        (["limits", "seconds_total"], 0),
        (["limits", "seconds_total"], 3600.1),
        (["limits", "seconds_total"], True),
    ],
)
def test_invalid_requests_refuse_before_prediction(path, bad, fake):
    value = example()
    if path:
        target = value
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = bad
    else:
        value = bad
    result = module.design(value, backend())
    assert result["status"] == "invalid_input"
    assert result["selected"] is None and result["candidates"] == []
    assert result["coverage"] is None and result["request"] is None
    assert not fake
    verify_hash(result)


@pytest.mark.parametrize("section", [None, "limits", "rbs"])
def test_unknown_fields(section, fake):
    value = example()
    (value if section is None else value[section])["unknown"] = 1
    assert module.design(value, backend())["status"] == "invalid_input"
    assert not fake


def test_transport_size_and_circular_requests(fake, monkeypatch):
    value = example()
    value["rbs"]["host"] = "a" * wire.INPUT_LIMIT
    assert module.design(value, backend())["status"] == "invalid_input"
    value = example()
    value["rbs"]["host"] = value
    assert module.design(value, backend())["status"] == "invalid_input"
    assert not fake


@pytest.mark.parametrize("profile", [p.name for p in module.PROFILES])
def test_window_boundaries_and_model_profiles(profile, fake):
    value = example()
    value["profile"] = profile
    value["rbs"].update(sequence="A" * 100 + "ATG" + "A" * 897, start_positions=[100])
    begin = 100 - get_profile(profile).upstream_nt
    value["editable_positions"] = [max(0, begin)]
    value["limits"].update(
        seconds_per_score=120, seconds_total=3600, max_candidates=256
    )
    result = module.design(value, backend())
    assert result["status"] == "complete"
    assert result["model"]["id"] == get_profile(profile).model_id
    if begin > 0:
        value["editable_positions"] = [begin - 1]
        assert (
            module.design(value, backend())["reason"]
            == "editable_position_outside_leader_window"
        )


@pytest.mark.parametrize("codon", ["ATG", "GTG", "TTG"])
def test_start_codons_and_zero_edits(codon, fake):
    value = example()
    value["rbs"].update(sequence="A" + codon, start_positions=[1])
    value.update(editable_positions=[], max_changes=0)
    value["limits"]["max_candidates"] = 1
    assert module.design(value, backend())["status"] == "complete"
    assert len(fake) == 2


@pytest.mark.parametrize(
    "change,reason",
    [
        (lambda s: s[:-1], "candidate_sequence_constraint"),
        (lambda s: "N" + s[1:], "candidate_sequence_constraint"),
        (lambda s: "C" + s[1:], "immutable_position_changed"),
        (lambda s: s[:4] + "C" + s[5:], "edit_count_constraint"),
    ],
)
def test_independent_candidate_constraint_guard(change, reason):
    value = example()
    value["max_changes"] = 0
    request = module.parse_request(value)
    with pytest.raises(wire.DesignError, match=reason):
        module.checked_edits(change(value["rbs"]["sequence"]), request)


@pytest.mark.parametrize("status", ["failed", "unsupported", "no_candidate"])
@pytest.mark.parametrize("empty", [False, True])
def test_native_failures_are_null_not_zero(monkeypatch, status, empty):
    def scorer(value, engine, **kwargs):
        response = native(value, engine, **kwargs)
        if value["sequence"][4] == "G":
            response["status"] = status
            if empty:
                response.update(sites=[], reason="test_failure")
            else:
                response["sites"][0].update(
                    status=status, reason="test_failure", tir=None, log_tir=None
                )
        return response

    monkeypatch.setattr(module, "predict", scorer)
    result = module.design(example(), backend())
    assert result["status"] == "partial" and result["reason"] == "candidate_failures"
    assert result["coverage"]["failed"] == 1
    assert result["candidates"][0]["score"] is None
    assert result["candidates"][0]["reason"] == "test_failure"
    assert result["selected"]["sequence"][4] == "A"


@pytest.mark.parametrize(
    "exception", [BackendError("failed"), OSError("failed"), UnicodeError("failed")]
)
def test_execution_failure_keeps_every_candidate(monkeypatch, exception):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(module, "predict", fail)
    result = module.design(example(), backend())
    assert result["status"] == "no_candidate"
    assert result["coverage"]["attempted"] == 4
    assert result["confirmation"]["reason"] == "no_successful_candidate"
    assert all(
        r["reason"] == "prediction_execution_failed" and r["score"] is None
        for r in result["candidates"]
    )


@pytest.mark.parametrize(
    "path,bad",
    [
        (["backend"], {}),
        (["input"], {}),
        (["model", "id"], "wrong"),
        (["prediction_id"], "0" * 64),
        (["status"], "invalid_input"),
        (["status"], []),
        (["sites"], {}),
        (["sites"], []),
        (["sites", 0, "oriented_start"], 15),
        (["sites", 0, "status"], "failed"),
        (["sites", 0, "reason"], "wrong"),
        (["reason"], "wrong"),
        (["sites", 0, "window", "oriented_end"], 20),
        (["sites", 0, "start_codon", "start"], 15),
        (["sites", 0, "codon"], "AAA"),
        (["sites", 0, "tir"], 0),
        (["sites", 0, "tir"], True),
        (["sites", 0, "log_tir"], float("inf")),
        (["sites", 0, "log_tir"], True),
        (["sites", 0, "log_tir"], 0),
    ],
)
def test_bad_native_identity_or_score_stops_without_selection(monkeypatch, path, bad):
    def scorer(value, engine, **kwargs):
        result = native(value, engine, **kwargs)
        cursor = result
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = bad
        return result

    monkeypatch.setattr(module, "predict", scorer)
    result = module.design(example(), backend())
    assert result["selected"] is None
    assert result["coverage"]["attempted"] == 1
    assert result["coverage"]["not_run"] == 3
    assert result["candidates"][0]["status"] == "failed"
    verify_hash(result)


@pytest.mark.parametrize(
    "malformation",
    ["missing", "recursive", "extra_site", "null_failure", "scored_failure"],
)
def test_native_malformed_shapes(monkeypatch, malformation):
    def scorer(value, engine, **kwargs):
        result = native(value, engine, **kwargs)
        if malformation == "missing":
            del result["input"]
        elif malformation == "recursive":
            result["loop"] = result
        elif malformation == "extra_site":
            result["sites"] *= 2
        else:
            result["status"] = result["sites"][0]["status"] = "failed"
            result["sites"][0]["reason"] = (
                None if malformation == "null_failure" else "fail"
            )
        return result

    monkeypatch.setattr(module, "predict", scorer)
    result = module.design(example(), backend())
    assert result["coverage"]["attempted"] == 1
    assert result["selected"] is None
    # Non-serializable payloads never leak into the result envelope.
    wire.result_bytes(result)


def test_model_change_and_backend_change_are_fatal(monkeypatch):
    for mode in ("model", "backend"):
        engine = backend()
        calls = []

        def scorer(value, engine, _calls=calls, _mode=mode, **kwargs):
            result = native(value, engine, **kwargs)
            _calls.append(value)
            if len(_calls) == 2:
                if _mode == "model":
                    result["model"]["parameters"]["another"] = 1
                else:
                    engine.identity["version"] = "2"
            return result

        monkeypatch.setattr(module, "predict", scorer)
        result = module.design(example(), engine)
        assert result["status"] == "partial" and result["selected"] is None
        assert result["coverage"]["attempted"] == 2
        assert result["reason"] == "native_identity_mismatch"


def test_backend_changed_before_invocation(monkeypatch):
    request = module.parse_request(example())
    row, model, fatal = module._native_result(
        request.raw["rbs"]["sequence"], request, backend(), {}, None, 10
    )
    assert fatal and model is None and row["reason"] == "native_identity_mismatch"


def test_embedded_native_output_cap(monkeypatch):
    value = example()
    value.update(editable_positions=[], max_changes=0)
    request = module.parse_request(value)
    response = native(
        value["rbs"],
        backend(),
        seconds=request.seconds,
        profile=request.profile.name,
        execution_seconds=1,
    )
    size = len(wire.pretty(response)) + 6 * len(wire.pretty(response).splitlines())
    monkeypatch.setattr(
        module, "predict", lambda *args, **kwargs: copy.deepcopy(response)
    )
    monkeypatch.setattr(wire, "NATIVE_LIMIT", size)
    assert module.design(value, backend())["status"] == "complete"
    monkeypatch.setattr(wire, "NATIVE_LIMIT", size - 1)
    result = module.design(value, backend())
    assert result["reason"] == "native_result_limit"
    assert result["candidates"][0]["native"] is None
    assert result["candidates"][0]["native_sha256"] == wire.digest(response)


@pytest.mark.parametrize("mode", ["failure", "changed"])
def test_fresh_confirmation_failure_never_selects_runner_up(monkeypatch, mode):
    calls = []

    def scorer(value, engine, **kwargs):
        calls.append(value)
        response = native(value, engine, **kwargs)
        if len(calls) == 5:
            if mode == "failure":
                response.update(status="failed", sites=[], reason="confirmation_failed")
            else:
                response["warning"] = "different native evidence"
        return response

    monkeypatch.setattr(module, "predict", scorer)
    result = module.design(example(), backend())
    assert result["status"] == "partial" and result["selected"] is None
    assert result["confirmation"]["reason"] == (
        "confirmation_failed" if mode == "failure" else "confirmation_mismatch"
    )
    assert len(calls) == 5


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.mark.parametrize(
    "where",
    ["enumeration", "score", "before_confirmation", "confirmation", "exact_deadline"],
)
def test_deadline_retains_roster_and_never_selects_late(monkeypatch, where):
    clock = Clock()
    calls = []
    monkeypatch.setattr(module.time, "monotonic", clock)
    original_candidates = module.candidates

    def enumerate_sequences(request):
        if where == "enumeration":
            clock.now = 10.0
        return original_candidates(request)

    def scorer(value, engine, **kwargs):
        calls.append(kwargs)
        if where == "score" or where == "confirmation" and len(calls) == 5:
            clock.now = 11.0
        elif where in {"before_confirmation", "exact_deadline"} and len(calls) == 4:
            clock.now = 10.0
        else:
            clock.now += 1
        return native(value, engine, **kwargs)

    monkeypatch.setattr(module, "candidates", enumerate_sequences)
    monkeypatch.setattr(module, "predict", scorer)
    value = example()
    value["limits"]["seconds_total"] = 10
    result = module.design(value, backend())
    assert result["selected"] is None
    assert len(result["candidates"]) == 4
    expected = {
        "enumeration": 0,
        "score": 1,
        "before_confirmation": 4,
        "confirmation": 5,
        "exact_deadline": 4,
    }[where]
    assert len(calls) == expected
    assert result["coverage"]["prediction_calls"] == expected
    assert all(c["seconds"] == 20.0 and 0 < c["execution_seconds"] <= 10 for c in calls)
    if where == "confirmation":
        assert result["confirmation"]["reason"] == "deadline"
    elif where == "enumeration":
        assert all(
            r["reason"] == "deadline" and not r["attempted"]
            for r in result["candidates"]
        )


def test_fractional_remaining_budget_and_success_at_exact_confirmation_deadline(
    monkeypatch,
):
    clock = Clock()
    monkeypatch.setattr(module.time, "monotonic", clock)
    calls = []

    def scorer(value, engine, **kwargs):
        calls.append(kwargs)
        clock.now += 0.5
        return native(value, engine, **kwargs)

    monkeypatch.setattr(module, "predict", scorer)
    value = example()
    value.update(editable_positions=[], max_changes=0)
    value["limits"].update(seconds_total=1, seconds_per_score=120)
    result = module.design(value, backend())
    assert result["status"] == "complete"
    assert [c["execution_seconds"] for c in calls] == [1.0, 0.5]
    assert result["coverage"]["elapsed_seconds"] == 1.0
