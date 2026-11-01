"""Independent enumeration, vector arithmetic and coding/strand invariants."""

import copy
import hashlib
import itertools
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from regsite import design_io as wire
from regsite import rbs
from regsite import rbs_vector_design as module
from regsite.profiles import PROFILES
from regsite.sequence import reverse_complement

REAL_PREDICT = rbs.predict


def example():
    return json.loads(Path("examples/rbs-vector-design.json").read_text())


class Backend:
    """No executable or native table is used by these artificial controls."""

    def __init__(self):
        self.identity = {"name": "artificial-vector-control"}
        self.sessions = []

    def session(self, temperature, seconds):
        self.sessions.append((temperature, seconds))
        return object()


def site(request, start, folding, profile):
    """Independent simple sequence score, retaining real native invocation metadata."""
    length = len(request.sequence)
    begin = max(0, start - profile.upstream_nt)
    end = min(length, start + profile.downstream_nt)

    def interval(a, b):
        if request.strand == "-":
            a, b = length - b, length - a
        return {"start": a, "end": b, "strand": request.strand}

    sequence = request.oriented_sequence[begin:end]
    log_score = (
        math.log(1000) + (sequence.count("G") - sequence.count("C")) / 10 + start / 1000
    )
    return {
        "status": "ok",
        "reason": None,
        "oriented_start": start,
        "start_codon": interval(start, start + 3),
        "codon": request.oriented_sequence[start : start + 3],
        "window": {
            "oriented_start": begin,
            "oriented_end": end,
            "input_interval": interval(begin, end),
        },
        "tir": math.exp(log_score),
        "log_tir": log_score,
        "energies": {"dG_total": (math.log(2500) - log_score) * 2.222},
    }


@pytest.fixture
def fake(monkeypatch):
    calls = []
    monkeypatch.setattr(rbs, "_score_site", site)

    def score(value, backend, **kwargs):
        calls.append((copy.deepcopy(value), copy.deepcopy(kwargs)))
        return REAL_PREDICT(value, backend, **kwargs)

    monkeypatch.setattr(rbs, "predict", score)
    return calls


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def verify_hashes(result):
    assert result["result_sha256"] == digest(
        {k: v for k, v in result.items() if k != "result_sha256"}
    )
    assert result["request_sha256"] == digest(result["request"])
    assert result["design_id"] == digest(
        {
            k: result[k]
            for k in (
                "request_sha256",
                "algorithm",
                "backend",
                "model",
                "targets",
                "limits",
            )
        }
    )
    for row in result["candidates"]:
        assert (
            row["sequence_sha256"]
            == hashlib.sha256(row["sequence"].encode()).hexdigest()
        )
        assert row["candidate_id"] == digest(
            {
                "design_id": result["design_id"],
                "index": row["index"],
                "sequence_sha256": row["sequence_sha256"],
            }
        )
        assert row["native_request_sha256"] == digest(row["native_request"])
        if row["native"] is not None:
            raw = (
                json.dumps(
                    row["native"],
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
            assert row["native_json_sha256"] == hashlib.sha256(raw).hexdigest()
            assert row["native_bytes"] == len(raw)


def oriented(sequence, strand):
    return (
        sequence
        if strand == "+"
        else reverse_complement(sequence.replace("T", "U")).replace("U", "T")
    )


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("changes", [0, 1, 2])
@pytest.mark.parametrize("profile", [p.name for p in PROFILES])
def test_independent_cartesian_roster_and_vector_objective(
    strand, changes, profile, fake
):
    value = example()
    value["profile"] = profile
    seed = value["rbs"]["sequence"]
    value["rbs"].update(sequence=oriented(seed, strand), strand=strand)
    seed = value["rbs"]["sequence"]
    indices = [4, 55]
    positions = indices if strand == "+" else [len(seed) - 1 - i for i in indices]
    value.update(editable_positions=positions[::-1], max_changes=changes)
    value["limits"]["max_candidates"] = 64
    preserved = copy.deepcopy(value)
    expected = []
    for bases in itertools.product("ACGT", repeat=2):
        candidate = list(seed)
        for p, base in zip(positions, bases, strict=True):
            candidate[p] = base
        changed = tuple(
            i for i, (a, b) in enumerate(zip(seed, candidate, strict=True)) if a != b
        )
        if len(changed) <= changes:
            expected.append(
                (
                    len(changed),
                    changed,
                    tuple(candidate[p] for p in changed),
                    "".join(candidate),
                )
            )
    expected = [row[-1] for row in sorted(expected)]
    result = module.design(value, Backend())
    assert value == preserved
    assert result["status"] == "complete"
    assert [row["sequence"] for row in result["candidates"]] == expected
    assert len(fake) == len(expected) + 1
    for call, settings in fake:
        assert call["start_positions"] == [30, 65]
        assert settings["seconds"] == 20.0 and 0 < settings["execution_seconds"] <= 20
        assert settings["profile"] == profile
    for row in result["candidates"]:
        transcript = oriented(row["sequence"], strand)
        for cds in value["cds"]:
            assert (
                transcript[cds["start"] : cds["end"]]
                == oriented(seed, strand)[cds["start"] : cds["end"]]
            )
        errors = []
        for target, native in zip(row["targets"], row["native"]["sites"], strict=True):
            assert target["log_tir"] == native["log_tir"]
            errors.append(abs(native["log_tir"] - math.log(1000)))
        assert row["objective"] == math.fsum(errors) / 2
        for edit in row["edits"]:
            p = edit["input_position"]
            assert edit["oriented_position"] == (
                p if strand == "+" else len(seed) - 1 - p
            )
            assert edit["from"] == seed[p] and edit["to"] == row["sequence"][p]
    best = min(
        result["candidates"],
        key=lambda row: (row["objective"], len(row["edits"]), row["sequence"]),
    )
    assert (
        result["selected"] == result["proposal"]
        and result["selected"]["index"] == best["index"]
    )
    assert result["confirmation"]["native"] == best["native"]
    assert result["confirmation"]["status"] == "verified"
    assert result["coverage"] == {
        "planned": len(expected),
        "attempted": len(expected),
        "successful": len(expected),
        "failed": 0,
        "not_run": 0,
        "prediction_calls": len(expected) + 1,
        "all_candidates_scored": True,
        "deadline_exceeded": False,
        "stop_reason": None,
    }
    verify_hashes(result)


def test_targets_are_jointly_recomputed_for_shared_context(fake):
    result = module.design(example(), Backend())
    observed = [
        tuple(t["log_tir"] for t in row["targets"]) for row in result["candidates"]
    ]
    assert len({row[0] for row in observed}) > 1
    assert len({row[1] for row in observed}) > 1
    assert result["constraints"]["coding_intervals"] == [[30, 48], [65, 89]]


def test_maximum_roster_and_ten_targets(fake):
    value = example()
    sequence = list("A" * 1000)
    starts = list(range(30, 931, 100))
    for start in starts:
        sequence[start : start + 3] = "ATG"
    value["rbs"].update(sequence="".join(sequence), start_positions=starts)
    value["cds"] = [
        {"id": f"cds-{i}", "start": start, "end": start + 30}
        for i, start in enumerate(starts)
    ]
    value.update(target_tirs=[1000] * 10, editable_positions=list(range(21)))
    value["limits"]["max_candidates"] = 64
    result = module.design(value, Backend())
    assert result["status"] == "complete" and result["coverage"]["planned"] == 64
    assert len(fake) == 65 and all(
        len(row["targets"]) == 10 for row in result["candidates"]
    )
    verify_hashes(result)


@pytest.mark.parametrize("strand", ["+", "-"])
def test_overlapping_coding_spans_are_all_locked(strand, fake):
    value = example()
    value["cds"][0]["end"] = 78
    value["rbs"].update(
        sequence=oriented(value["rbs"]["sequence"], strand), strand=strand
    )
    length = len(value["rbs"]["sequence"])
    value["editable_positions"] = [4 if strand == "+" else length - 5]
    result = module.design(value, Backend())
    assert result["status"] == "complete" and result["constraints"][
        "coding_intervals"
    ] == [[30, 78], [65, 89]]
    value["editable_positions"] = [55 if strand == "+" else length - 56]
    assert (
        module.design(value, Backend())["reason"]
        == "editable_position_in_coding_region"
    )


def test_equal_objectives_prefer_seed_then_lexical_dna(monkeypatch, fake):
    def fixed(request, start, folding, profile):
        row = site(request, start, folding, profile)
        rate = 2000.0 if request.sequence[55] == "G" else 1000.0
        row.update(
            tir=rate,
            log_tir=math.log(rate),
            energies={"dG_total": (math.log(2500) - math.log(rate)) * 2.222},
        )
        return row

    monkeypatch.setattr(rbs, "_score_site", fixed)
    value = example()
    result = module.design(value, Backend())
    assert result["selected"]["sequence"][55] == "A"
    value["target_tirs"] = [2000, 2000]
    result = module.design(value, Backend())
    assert result["selected"]["index"] == 0


def test_seed_only_and_numeric_extremes_preserve_raw_request(fake):
    value = example()
    value.update(
        editable_positions=[],
        max_changes=0,
        target_tirs=[5e-324, 1.7976931348623157e308],
    )
    value["limits"].update(seconds_per_score=30, seconds_total=600, max_candidates=1)
    result = module.design(value, Backend())
    assert result["status"] == "complete" and result["selected"]["edits"] == []
    assert result["request"] == value and result["coverage"]["prediction_calls"] == 2
    assert math.isfinite(result["selected"]["objective"])


def test_start_cug_and_native_defaults(fake):
    value = example()
    sequence = value["rbs"]["sequence"]
    value["rbs"]["sequence"] = sequence[:30] + "CTG" + sequence[33:]
    for key in ("id", "host", "strand", "temperature_c", "schema_version"):
        value["rbs"].pop(key)
    result = module.design(value, Backend())
    assert result["status"] == "complete"
    assert result["candidates"][0]["native"]["sites"][0]["codon"] == "CUG"
    assert result["candidates"][0]["native"]["id"] == "sequence"


@pytest.mark.parametrize("bad", [None, "", "A", "N" * 98])
def test_independent_sequence_constraint(bad):
    with pytest.raises(wire.DesignError, match="candidate_sequence_constraint"):
        module.checked_edits(bad, module.parse_request(example()))


def test_independent_lock_and_edit_count_checks():
    request = module.parse_request(example())
    seed = request.raw["rbs"]["sequence"]
    with pytest.raises(wire.DesignError, match="immutable_position_changed"):
        module.checked_edits("C" + seed[1:], request)
    bad = seed[:30] + "C" + seed[31:]
    with pytest.raises(wire.DesignError, match="coding_region_changed"):
        module.checked_edits(bad, replace(request, positions=(30,)))
    changed = seed[:55] + "A" + seed[56:]
    with pytest.raises(wire.DesignError, match="edit_count_constraint"):
        module.checked_edits(changed, replace(request, changes=0))


def test_exact_canonical_byte_cap(monkeypatch):
    value = example()
    size = len(wire.canonical(value))
    monkeypatch.setattr(wire, "INPUT_LIMIT", size)
    assert module.parse_request(value).count == 4
    monkeypatch.setattr(wire, "INPUT_LIMIT", size - 1)
    assert module.design(value, Backend())["status"] == "invalid_input"


@pytest.mark.parametrize("identity", [{}, None, {"bad": set()}, {"n": float("nan")}])
def test_invalid_backend_identity(identity):
    backend = Backend()
    backend.identity = identity
    assert module.design(example(), backend)["reason"] == "invalid_backend_identity"


def test_missing_backend_identity_and_recursive_values():
    assert module.design(example(), None)["reason"] == "invalid_backend_identity"
    value = example()
    value["rbs"] = value
    assert module.design(value, Backend())["status"] == "invalid_input"
    backend = Backend()
    backend.identity["cycle"] = backend.identity
    assert module.design(example(), backend)["reason"] == "invalid_backend_identity"
