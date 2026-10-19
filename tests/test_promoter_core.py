"""Independent arithmetic, inputs, selection and serialization checks."""

import builtins
import itertools
import json
import math
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal, localcontext
from unittest.mock import patch

import pytest

from regsite import promoter as p


@pytest.fixture
def params():
    return p.load_parameters()


@pytest.fixture
def cal():
    return p.resolve_calibration("ecoli_mg1655")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ACGT", "ACGT"),
        (" \ta\nc\rg\vt\f ", "ACGT"),
        (" acgu ", "ACGT"),
    ],
)
def test_normalization(text, expected):
    assert p.normalize_dna(text, max_length=4) == expected


@pytest.mark.parametrize(
    "text,limit,code,index,char",
    [
        (None, 4, "invalid_sequence", None, None),
        (" \n\t", 4, "empty_sequence", None, None),
        ("", 4, "empty_sequence", None, None),
        ("AAA", 2, "limit_exceeded", None, None),
        ("t u", 3, "mixed_dna_rna", 2, "u"),
        ("ut", 3, "mixed_dna_rna", 1, "t"),
        ("a n", 3, "ambiguous_base", 2, "n"),
        ("AC>G", 4, "invalid_character", 2, ">"),
        ("A\u00a0T", 3, "invalid_character", 1, "\u00a0"),
        ("AßT", 3, "invalid_character", 1, "ß"),
        ("A1", 3, "invalid_character", 1, "1"),
    ],
)
def test_normalization_errors(text, limit, code, index, char):
    with pytest.raises(p.InputError) as exc:
        p.normalize_dna(text, max_length=limit)
    assert (exc.value.code, exc.value.field, exc.value.index, exc.value.character) == (
        code,
        "sequence",
        index,
        char,
    )
    assert str(exc.value) == f"{code}: sequence"


@pytest.mark.parametrize("value", [None, True, "2", math.inf, math.nan, -1, 0.5])
def test_integer_errors(value):
    with pytest.raises(p.InputError, match="invalid_integer"):
        p.normalize_dna("A", max_length=value)


def test_orientation_and_bad_direct_inputs():
    assert p.orient("ACGTT", "+") == "ACGTT"
    assert p.orient("ACGTT", "-") == "AACGT"
    for text in (None, "", "acgt", "ANGT"):
        with pytest.raises(p.InputError, match="invalid_sequence"):
            p.orient(text, "+")
    with pytest.raises(p.InputError, match="invalid_strand"):
        p.orient("A", "?")
    for d, s in ((5, 17), (11, 17), (6, 14), (6, 21)):
        with pytest.raises(p.InputError, match="invalid_state"):
            p.state_windows(100, d, s)
    with pytest.raises(p.InputError, match="insufficient_context"):
        p.score_state("A" * 77, 57, 6, 15, p.load_parameters())
    with pytest.raises(p.InputError, match="insufficient_context"):
        p.score_state("A" * 200, 181, 6, 15, p.load_parameters())


@pytest.mark.parametrize(
    "profile,host,status,beta,warning",
    [
        ("ecoli_mg1655", None, "unspecified", 1.636217004872062, "host_unspecified"),
        (
            "ecoli_mg1655",
            {"name": p.NATIVE_HOST},
            "calibration_native",
            1.636217004872062,
            None,
        ),
        ("in_vitro", None, "in_vitro_reference", 0.81632623, None),
        ("in_vitro", {"name": "in vitro"}, "in_vitro_reference", 0.81632623, None),
        (
            "in_vitro",
            {"name": p.NATIVE_HOST},
            "extrapolated",
            0.81632623,
            "host_extrapolation",
        ),
        (
            "ecoli_mg1655",
            {"name": "cyanobacteria", "taxon_id": 123.0},
            "extrapolated",
            1.636217004872062,
            "host_extrapolation",
        ),
        (
            "in_vitro",
            {"name": "e\u0301"},
            "extrapolated",
            0.81632623,
            "host_extrapolation",
        ),
    ],
)
def test_calibration(profile, host, status, beta, warning):
    result = p.resolve_calibration(profile, host)
    data = result.to_dict()
    assert data["K"] == 42 and type(data["K"]) is int
    assert data["beta"] == beta and data["host_status"] == status
    assert data["native_host"] == (p.NATIVE_HOST if profile == "ecoli_mg1655" else None)
    assert [w["code"] for w in result.warnings] == (
        [] if warning is None else [warning]
    )
    if host is None:
        assert data["host"] is None
    else:
        assert set(data["host"]) == {"name", "taxon_id"}
    if host and "taxon_id" in host:
        assert type(data["host"]["taxon_id"]) is int
    if host and host["name"] == "e\u0301":
        assert data["host"]["name"] == "é"


@pytest.mark.parametrize(
    "host",
    [
        [],
        {},
        {"name": ""},
        {"name": "x" * 201},
        {"name": 2},
        {"name": "x", "extra": 0},
        {"name": "x", "taxon_id": None},
        {"name": "x", "taxon_id": True},
        {"name": "x", "taxon_id": -1},
        {"name": "x", "taxon_id": 1.5},
    ],
)
def test_bad_host(host):
    with pytest.raises(p.InputError, match="invalid_host"):
        p.resolve_calibration("ecoli_mg1655", host)


@pytest.mark.parametrize("profile", [None, "", "unknown"])
def test_bad_calibration(profile):
    with pytest.raises(p.InputError, match="invalid_calibration"):
        p.resolve_calibration(profile)


def test_relative_score_bounds():
    for bound in (p.LOG_MIN, p.LOG_MAX):
        value, status = p.relative_score(bound)
        assert status == "ok" and value == math.exp(bound)
        assert sys.float_info.min <= value <= sys.float_info.max
    assert p.relative_score(math.nextafter(p.LOG_MIN, -math.inf)) == (None, "underflow")
    assert p.relative_score(math.nextafter(p.LOG_MAX, math.inf)) == (None, "overflow")
    for value in (
        0,
        math.nextafter(p.LOG_MIN, math.inf),
        math.nextafter(p.LOG_MAX, -math.inf),
    ):
        assert p.relative_score(value) == (math.exp(value), "ok")
    for value in (math.inf, -math.inf, math.nan):
        with pytest.raises(ArithmeticError, match="nonfinite_arithmetic"):
            p.relative_score(value)


def test_homopolymer_decimal_independent(params):
    """A separate 50-digit calculation uses declared table constants and weights."""
    with localcontext() as ctx:
        ctx.prec = 50

        def D(x):
            return Decimal(str(x))

        c = params.coefficients
        numeric = [
            D(30) / D(256) * D(c[339]),
            D(30) / D(255) * D(c[340]),
            D("-5.6") / D("4.300000000000002") * D(c[341]),
            D("25.2") / D("25.780434782608694") * D(c[342]),
        ]
        expected = {
            "hex10": D(c[0]) + D(c[64]),
            "hex35": D(c[128]) + D(c[192]),
            "discriminator": D(c[256]),
            "extended10": D(c[320]),
            "itr": numeric[2],
            "up": numeric[0] + numeric[1] + numeric[3],
            "spacer": D("0.1463") * 17**2 - D("4.9113") * 17 + D("41.119"),
            "intercept": D(params.intercept),
        }
        state = p.score_state("A" * 200, 100, 6, 17, params)
        for key, value in expected.items():
            assert state.terms[key] == pytest.approx(float(value), abs=2e-14)
        assert state.terms["total"] == pytest.approx(
            float(sum(expected.values())), abs=2e-14
        )
    assert p._dimer_sum("A" * 12, params.tables["groove_access"]) == 30
    assert p._dimer_sum("A" * 44, params.tables["persistence"]) / 44 == 25.2
    assert (
        p._dimer_sum("A" * 14, params.tables["DNA_DNA_hybrids"])
        - p._dimer_sum("A" * 14, params.tables["RNA_DNA_hybrids"])
    ) == pytest.approx(-5.6)


@pytest.mark.parametrize(
    "offset,k,interval,term",
    [
        (0, 3, (88, 91), "hex10"),
        (64, 3, (91, 94), "hex10"),
        (128, 3, (65, 68), "hex35"),
        (192, 3, (68, 71), "hex35"),
        (256, 3, (94, 97), "discriminator"),
        (320, 2, (85, 87), "extended10"),
    ],
)
def test_every_categorical_index(params, offset, k, interval, term):
    for index, letters in enumerate(itertools.product("ACGT", repeat=k)):
        c = [0.0] * 343
        c[offset + index] = 1.0
        sequence = list("A" * 200)
        sequence[interval[0] : interval[1]] = letters
        state = p.score_state(
            "".join(sequence), 100, 6, 17, replace(params, coefficients=tuple(c))
        )
        assert state.terms[term] == 1.0


def test_numeric_indices_and_unused_coefficients(params):
    base = p.score_state("A" * 200, 100, 6, 17, params)
    changed = list(params.coefficients)
    changed[336:339] = [math.nan, math.inf, -math.inf]
    assert (
        p.score_state(
            "A" * 200, 100, 6, 17, replace(params, coefficients=tuple(changed))
        )
        == base
    )
    for index, raw, term, normalizer in [
        (339, 30, "up", 0),
        (340, 30, "up", 1),
        (341, -5.6, "itr", 2),
        (342, 25.2, "up", 3),
    ]:
        c = [0.0] * 343
        c[index] = 1.0
        state = p.score_state(
            "A" * 200, 100, 6, 17, replace(params, coefficients=tuple(c))
        )
        assert state.terms[term] == pytest.approx(raw / params.normalizers[normalizer])


def test_ties_serialization_and_no_implicit_complement(params, cal):
    with patch.object(p, "orient", wraps=p.orient) as spy:
        site = p.score_site("A" * 200, "+", 100, params, cal, keep_states=True)
    spy.assert_called_once_with("A" * 200, "+")
    assert site.tie_count == 5
    assert (site.selected.discriminator_length, site.selected.spacer_length) == (6, 17)
    data = site.to_dict()
    assert data["state_count"] == 30 and data["complete_state_set"]
    assert data["attempted"] and data["genomic"] is None
    assert len(data["states"]) == 30 and sum(s["selected"] for s in data["states"]) == 1
    assert "elements" in data["selected"] and all(
        "elements" not in s for s in data["states"]
    )
    assert "elements" not in site.to_dict(elements=False)["selected"]
    assert set(data["selected"]["elements"]) == {
        "UP",
        "hex35",
        "spacer",
        "hex10",
        "discriminator",
        "itr",
    }
    json.dumps(data, allow_nan=False)
    compact = p.score_site(
        "A" * 200, "+", 100, params, cal, keep_states=False
    ).to_dict()
    assert "states" not in compact
    no = p.score_site("A" * 77, "+", 57, params, cal, keep_states=True).to_dict()
    assert no["selected"] is None and no["states"] == [] and no["tie_count"] is None


def test_ulp_difference_is_not_a_tie(params, cal):
    # Inject two independently specified totals to exercise exact-float tie semantics.
    first = p.score_state("A" * 200, 59, 6, 15, params)
    later = replace(
        first,
        terms={**first.terms, "total": math.nextafter(first.terms["total"], -math.inf)},
    )
    with patch.object(p, "_score_validated_state", side_effect=[first, later, first]):
        result = p.score_site("A" * 200, "+", 59, params, cal, keep_states=True)
    assert result.selected is later and result.tie_count == 1


def test_nonfinite_sites_fail_without_partial_scores(params, cal):
    for replacement in (math.nan, math.inf, 1e308):
        bad = replace(params, intercept=replacement)
        if replacement == 1e308:
            bad = replace(bad, coefficients=(1e308,) * 343)
        site = p.score_site("A" * 200, "+", 100, bad, cal, keep_states=True)
        assert site.status == "failed" and site.reason == "nonfinite_arithmetic"
        assert site.state_count == 30 and site.selected is None and site.states == ()
        assert site.to_dict()["selected"] is None
    badcal = replace(cal, beta=math.inf)
    assert (
        p.score_site("A" * 200, "+", 100, params, badcal, keep_states=False).status
        == "failed"
    )
    assert (
        p.score_site(
            "A" * 200, "+", 100, params, replace(cal, beta=1e300), keep_states=False
        ).status
        == "ok"
    )


def test_runtime_has_no_external_execution(params, cal):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert name.split(".")[0] not in {
            "numpy",
            "scipy",
            "sklearn",
            "Bio",
            "benchmarks",
        }
        return original(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=guarded),
        patch("socket.socket", side_effect=AssertionError),
        patch.object(subprocess, "Popen", side_effect=AssertionError),
    ):
        assert p.load_parameters() == params
        assert (
            p.score_site("ACGT" * 50, "-", 100, params, cal, keep_states=True).status
            == "ok"
        )


@pytest.mark.parametrize(
    "intercept,expected_status", [(1000.0, "underflow"), (-1000.0, "overflow")]
)
def test_extreme_finite_scores_keep_logs_and_winners(
    params, cal, intercept, expected_status
):
    site = p.score_site(
        "A" * 200, "+", 100, replace(params, intercept=intercept), cal, keep_states=True
    )
    data = site.to_dict()
    assert site.status == "ok" and site.tie_count == 5
    assert (site.selected.discriminator_length, site.selected.spacer_length) == (6, 17)
    for state in [data["selected"], *data["states"]]:
        assert state["score_status"] == expected_status
        assert state["relative_transcription_score"] is None
        assert math.isfinite(state["log_relative_transcription_score"])
    json.dumps(data, allow_nan=False)


def test_direct_integral_float_arguments_resolve_integers(params):
    state = p.score_state("A" * 200, 100.0, 6.0, 17.0, params)
    assert type(state.discriminator_length) is int and type(state.spacer_length) is int
