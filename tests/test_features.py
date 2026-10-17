"""Frozen feature contracts using public synthetic sequences and energy terms."""

import itertools
import json
import math
from copy import deepcopy
from dataclasses import asdict

import pytest
from test_rbs import AlgebraBackend

from regsite.contracts import RbsRequest
from regsite.features import FeatureError, extract_features, feature_names
from regsite.rbs import predict
from regsite.sequence import reverse_complement

SEQUENCE = "sequence-v1"
ENERGY = "context-energy-sequence-v1"
ENERGY_NAMES = (
    "dG_total",
    "dG_mRNA",
    "dG_spacing",
    "dG_standby_signed",
    "dG_post_footprint",
)


def request(leader="AAAGGAGGAAAAAA", coding="AUG" + "A" * 40, **changes):
    return RbsRequest.from_dict(
        {
            "sequence": leader + coding,
            "anti_sd": "ACCUCCUUA",
            "start_positions": [len(leader)],
            **changes,
        }
    )


def prediction_for(value):
    """A minimal synthetic successful result, never experimental evidence."""
    return {
        "status": "ok",
        "model": {"id": "context2017-rnastructure-6.6-reconstruction-1"},
        "input": asdict(value),
        "sites": [
            {
                "status": "ok",
                "oriented_start": value.start_positions[0],
                "codon": value.oriented_sequence[
                    value.start_positions[0] : value.start_positions[0] + 3
                ],
                "energies": dict(
                    zip(ENERGY_NAMES, (-8.25, -4, 0.5, -2, -1.2), strict=True)
                ),
            }
        ],
    }


def test_frozen_names_and_orders():
    expected = (
        "clipped_leader_length",
        "clipped_downstream_length",
        "up35_A_proportion",
        "up35_C_proportion",
        "up35_G_proportion",
        "up100_A_proportion",
        "up100_C_proportion",
        "up100_G_proportion",
        "coding13_A_proportion",
        "coding13_C_proportion",
        "coding13_G_proportion",
        "post13to35_A_proportion",
        "post13to35_C_proportion",
        "post13to35_G_proportion",
        "start_GUG",
        "start_UUG",
        "start_CUG",
        "sd_longest_exact_run",
        "sd_gap_of_best_run",
    )
    assert feature_names(SEQUENCE) == expected
    assert feature_names(ENERGY) == expected + ENERGY_NAMES
    assert len(expected) == len(set(expected)) == 19
    assert len(feature_names(ENERGY)) == 24
    assert issubclass(FeatureError, ValueError)


@pytest.mark.parametrize(
    "kind", ["", "sequence", "SEQUENCE-V1", "context2017", None, []]
)
def test_unknown_kinds_raise_feature_error(kind):
    with pytest.raises(FeatureError, match="unsupported feature kind"):
        feature_names(kind)
    with pytest.raises(FeatureError, match="unsupported feature kind"):
        extract_features(request(), kind=kind)


def test_independent_complete_vector():
    value = request(
        leader="U" * 65 + "C" * 25 + "G" * 10,
        coding="AUG" + "A" * 10 + "C" * 11 + "G" * 11 + "A" * 65,
        anti_sd="GGGGGGGGG",
    )
    actual = extract_features(value, kind=SEQUENCE)
    assert actual == pytest.approx(
        (
            100,
            100,
            0,
            25 / 35,
            10 / 35,
            0,
            0.25,
            0.1,
            11 / 13,
            0,
            1 / 13,
            0,
            0.5,
            0.5,
            0,
            0,
            0,
            9,
            10,
        )
    )
    assert isinstance(actual, tuple)
    assert all(type(item) is float and math.isfinite(item) for item in actual)


@pytest.mark.parametrize("leader_length", [1, 34, 35, 36, 99, 100, 101])
@pytest.mark.parametrize("coding_length", [3, 12, 13, 14, 34, 35, 36, 99, 100, 101])
def test_context_boundaries_and_empty_post_region(leader_length, coding_length):
    value = request(
        leader="C" * leader_length, coding="AUG" + "U" * (coding_length - 3)
    )
    vector = extract_features(value, kind=SEQUENCE)
    assert vector[:2] == (
        float(min(leader_length, 100)),
        float(min(coding_length, 100)),
    )
    assert vector[2:8] == (0, 1, 0, 0, 1, 0)
    denominator = min(coding_length, 13)
    assert vector[8:11] == pytest.approx((1 / denominator, 0, 1 / denominator))
    assert vector[11:14] == (0, 0, 0)


def test_each_region_has_its_own_bounds_and_denominator():
    # Changes before -100 and after +35 affect only the clipped length signals.
    value = request(
        leader="A" * 10 + "C" * 65 + "G" * 35,
        coding="AUG" + "A" * 10 + "C" * 22 + "G" * 100,
    )
    vector = extract_features(value, kind=SEQUENCE)
    assert vector[:8] == (100, 100, 0, 0, 1, 0, 0.65, 0.35)
    assert vector[8:14] == pytest.approx((11 / 13, 0, 1 / 13, 0, 1, 0))
    truncated = request(leader="C" * 65 + "G" * 35, coding="AUG" + "A" * 10 + "C" * 22)
    assert extract_features(truncated, kind=SEQUENCE)[2:] == vector[2:]


@pytest.mark.parametrize("post_length", [1, 21, 22, 23])
def test_truncated_post_region_uses_available_bases(post_length):
    value = request(coding="AUG" + "U" * 10 + "A" * post_length)
    vector = extract_features(value, kind=SEQUENCE)
    assert vector[8:11] == pytest.approx((1 / 13, 0, 1 / 13))
    assert vector[11:14] == (1, 0, 0)


@pytest.mark.parametrize(
    "codon,indicators",
    [
        ("AUG", (0, 0, 0)),
        ("GUG", (1, 0, 0)),
        ("UUG", (0, 1, 0)),
        ("CUG", (0, 0, 1)),
    ],
)
def test_explicit_supported_start_indicators(codon, indicators):
    vector = extract_features(request(coding=codon), kind=SEQUENCE)
    assert vector[14:17] == indicators


@pytest.mark.parametrize("kind", [SEQUENCE, ENERGY])
@pytest.mark.parametrize("starts", [None, [], [1, 2]])
def test_requires_one_explicit_start(kind, starts):
    with pytest.raises(FeatureError, match="exactly one explicit start"):
        extract_features(request(start_positions=starts), kind=kind)


@pytest.mark.parametrize(
    "codon",
    [
        "".join(x)
        for x in itertools.product("ACGU", repeat=3)
        if "".join(x) not in ("AUG", "GUG", "UUG", "CUG")
    ],
)
def test_all_unsupported_start_codons(codon):
    with pytest.raises(FeatureError, match="unsupported start codon"):
        extract_features(request(coding=codon), kind=SEQUENCE)


@pytest.mark.parametrize("kind", [SEQUENCE, ENERGY])
def test_leaderless_context_is_explicitly_unsupported(kind):
    with pytest.raises(FeatureError, match="leaderless"):
        extract_features(request(leader=""), kind=kind)


@pytest.mark.parametrize(
    "leader,target,expected",
    [
        ("U" * 35, "AAAAAAAAA", (0, 36)),
        ("A", "AAAAAAAAA", (1, 0)),
        ("A" + "U" * 34, "AAAAAAAAA", (1, 34)),
        ("A" + "U" * 35, "AAAAAAAAA", (0, 36)),
        ("AGGAGGAAA" + "U" * 5, "AGGAGGAAA", (9, 5)),
        ("UAAAAUUUUU", "AAAAAAAAA", (4, 5)),
        ("AAUUUAUUUUU", "AAAAAAAAA", (2, 9)),  # Length wins over optimal gap.
        ("UAUAUUUUU", "AAAAAAAAA", (1, 5)),  # Closest gap wins.
        ("UAUUUAUUU", "AAAAAAAAA", (1, 3)),  # Gaps 7/3 tie; smaller wins.
        ("CAAACCCCC", "GAAAGGGGG", (3, 5)),  # Shared internal target substring.
    ],
)
def test_exact_sd_match_and_ties(leader, target, expected):
    value = request(leader=leader, anti_sd=reverse_complement(target))
    assert extract_features(value, kind=SEQUENCE)[-2:] == expected


def test_sd_matches_exhaustive_short_leaders_against_shared_substring_definition():
    for target in ("AAAAAAAAA", "AGGAGGAAA", "CGUACGUAC"):
        shared = {
            target[begin:end]
            for begin in range(len(target))
            for end in range(begin + 1, len(target) + 1)
        }
        for length in range(1, 6):
            for bases in itertools.product("ACGU", repeat=length):
                leader = "".join(bases)
                # Enumerate all shared intervals, independently of length-first search.
                matches = [
                    (end - begin, length - end)
                    for begin in range(length)
                    for end in range(begin + 1, length + 1)
                    if leader[begin:end] in shared
                ]
                expected = (
                    min(matches, key=lambda pair: (-pair[0], abs(pair[1] - 5), pair[1]))
                    if matches
                    else (0, 36)
                )
                value = request(leader=leader, anti_sd=reverse_complement(target))
                assert extract_features(value, kind=SEQUENCE)[-2:] == expected


@pytest.mark.parametrize("kind", [SEQUENCE, ENERGY])
@pytest.mark.parametrize("codon", ["AUG", "GUG", "UUG", "CUG"])
def test_reverse_complement_equivalence_and_no_mutation(kind, codon):
    forward = request(coding=codon + "ACGU" * 12)
    reverse = request(
        sequence=reverse_complement(forward.sequence),
        strand="-",
        coding=codon + "ACGU" * 12,
    )
    prediction = prediction_for(forward)
    reverse_prediction = prediction_for(reverse)
    before = deepcopy((forward, reverse, prediction, reverse_prediction))
    assert extract_features(
        forward, kind=kind, prediction=prediction
    ) == extract_features(reverse, kind=kind, prediction=reverse_prediction)
    assert (forward, reverse, prediction, reverse_prediction) == before


def test_normalization_is_owned_by_request_and_labels_are_unused():
    value = request(
        sequence=" aa agg agg aaaaaa atg " + "a" * 40,
        anti_sd=" acc tcc tta ",
        id="one",
        host="unfitted host",
    )
    equivalent = request(id="two", host="different metadata")
    assert value.input_sha256 != equivalent.input_sha256
    assert value.oriented_sha256 == equivalent.oriented_sha256
    assert extract_features(value, kind=SEQUENCE) == extract_features(
        equivalent, kind=SEQUENCE
    )
    assert extract_features(value, kind=ENERGY, prediction=prediction_for(equivalent))[
        -5:
    ] == (-8.25, -4, 0.5, -2, -1.2)
    assert extract_features(value, kind=SEQUENCE, prediction={"status": "failed"}) == (
        extract_features(value, kind=SEQUENCE)
    )


def test_energy_append_order_signed_value_json_and_actual_prediction_contract():
    value = request()
    synthetic = prediction_for(value)
    result = extract_features(value, kind=ENERGY, prediction=synthetic)
    assert result == extract_features(value, kind=SEQUENCE) + (-8.25, -4, 0.5, -2, -1.2)
    assert all(type(item) is float for item in result)
    assert (
        extract_features(
            value, kind=ENERGY, prediction=json.loads(json.dumps(synthetic))
        )
        == result
    )
    real_contract = predict(
        {
            "sequence": value.sequence,
            "anti_sd": value.anti_sd,
            "start_positions": list(value.start_positions),
        },
        AlgebraBackend(),
        profile="context2017",
    )
    assert real_contract["status"] == "ok"
    assert extract_features(value, kind=ENERGY, prediction=real_contract)[-5:] == tuple(
        real_contract["sites"][0]["energies"][name] for name in ENERGY_NAMES
    )


@pytest.mark.parametrize(
    "prediction",
    [
        None,
        [],
        {},
        {"status": "failed"},
        {"status": "no_candidate"},
        {"status": "unsupported"},
    ],
)
def test_energy_requires_explicit_successful_prediction(prediction):
    with pytest.raises(FeatureError, match="successful prediction"):
        extract_features(request(), kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize(
    "model",
    [
        None,
        [],
        {},
        {"id": "context2017"},
        {"id": "salis-v1-rnastructure-6.6-reconstruction-1"},
        {"id": "footprint2017-rnastructure-6.6-reconstruction-1"},
    ],
)
def test_energy_rejects_other_models(model):
    value = request()
    prediction = prediction_for(value)
    prediction["model"] = model
    with pytest.raises(FeatureError, match="require model"):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("context", [None, [], {}])
def test_energy_rejects_missing_context(context):
    value = request()
    prediction = prediction_for(value)
    prediction["input"] = context
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("sequence", "AUG"),
        ("normalized_sha256", "0" * 64),
        ("oriented_sequence", "AUG"),
        ("oriented_sha256", "0" * 64),
        ("anti_sd", "ACCUCCUUU"),
        ("strand", "-"),
        ("temperature_c", 36),
        ("temperature_c", True),
        ("temperature_c", float("nan")),
        ("temperature_c", "37"),
        ("start_positions", None),
        ("start_positions", []),
        ("start_positions", [14, 15]),
        ("start_positions", [13]),
        ("start_positions", [14.0]),
        ("start_positions", [True]),
    ],
)
def test_energy_rejects_each_context_mismatch(field, bad):
    value = request()
    prediction = prediction_for(value)
    prediction["input"][field] = bad
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize(
    "field",
    [
        "sequence",
        "normalized_sha256",
        "oriented_sequence",
        "oriented_sha256",
        "anti_sd",
        "strand",
        "temperature_c",
        "start_positions",
    ],
)
def test_energy_requires_each_context_field(field):
    value = request()
    prediction = prediction_for(value)
    del prediction["input"][field]
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


def test_id_does_not_prove_sequence_or_orientation_match():
    value = request(id="same-id")
    other = request(id="same-id", coding="AUG" + "G" * 40)
    assert other.id == value.id
    with pytest.raises(FeatureError, match="mismatch"):
        extract_features(value, kind=ENERGY, prediction=prediction_for(other))
    reverse = request(
        sequence=reverse_complement(value.sequence), strand="-", id=value.id
    )
    assert reverse.oriented_sequence == value.oriented_sequence
    with pytest.raises(FeatureError, match="strand mismatch"):
        extract_features(value, kind=ENERGY, prediction=prediction_for(reverse))


def test_start_and_temperature_booleans_cannot_match_numeric_one():
    value = request(leader="A", temperature_c=1)
    for field, bad in (("start_positions", [True]), ("temperature_c", True)):
        prediction = prediction_for(value)
        prediction["input"][field] = bad
        with pytest.raises(FeatureError):
            extract_features(value, kind=ENERGY, prediction=prediction)
    prediction = prediction_for(value)
    prediction["sites"][0]["oriented_start"] = True
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("sites", [None, {}, [], [None], [{}], [{}, {}]])
def test_energy_requires_exactly_one_successful_site(sites):
    value = request()
    prediction = prediction_for(value)
    prediction["sites"] = sites
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("status", "failed"),
        ("status", "unsupported"),
        ("status", "no_candidate"),
        ("oriented_start", 13),
        ("oriented_start", 14.0),
        ("codon", "GUG"),
    ],
)
def test_energy_rejects_site_mismatch(field, bad):
    value = request()
    prediction = prediction_for(value)
    prediction["sites"][0][field] = bad
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("field", ["status", "oriented_start", "codon", "energies"])
def test_energy_requires_each_site_field(field):
    value = request()
    prediction = prediction_for(value)
    del prediction["sites"][0][field]
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("energies", [None, [], {}])
def test_energy_rejects_missing_terms(energies):
    value = request()
    prediction = prediction_for(value)
    prediction["sites"][0]["energies"] = energies
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("field", ENERGY_NAMES)
@pytest.mark.parametrize(
    "bad",
    [
        None,
        True,
        False,
        "0",
        [],
        {},
        float("nan"),
        float("inf"),
        float("-inf"),
        10**400,
    ],
)
def test_energy_rejects_nonfinite_boolean_and_nonnumeric_terms(field, bad):
    value = request()
    prediction = prediction_for(value)
    prediction["sites"][0]["energies"][field] = bad
    with pytest.raises(FeatureError, match="prediction energy"):
        extract_features(value, kind=ENERGY, prediction=prediction)


@pytest.mark.parametrize("field", ENERGY_NAMES)
def test_missing_term_is_never_replaced_with_zero(field):
    value = request()
    prediction = prediction_for(value)
    del prediction["sites"][0]["energies"][field]
    # The old unsigned key is not an alias for the frozen signed feature.
    prediction["sites"][0]["energies"]["dG_standby"] = 0
    with pytest.raises(FeatureError):
        extract_features(value, kind=ENERGY, prediction=prediction)


def test_explicit_zero_energy_is_valid():
    value = request()
    prediction = prediction_for(value)
    prediction["sites"][0]["energies"] = dict.fromkeys(ENERGY_NAMES, 0)
    assert extract_features(value, kind=ENERGY, prediction=prediction)[-5:] == (0,) * 5


@pytest.mark.parametrize("coding_length", [3, 12, 13])
def test_complete_coding_footprint_required_for_energy(coding_length):
    value = request(coding="AUG" + "A" * (coding_length - 3))
    if coding_length < 13:
        with pytest.raises(FeatureError, match="truncated"):
            extract_features(value, kind=ENERGY, prediction=prediction_for(value))
    else:
        assert (
            len(extract_features(value, kind=ENERGY, prediction=prediction_for(value)))
            == 24
        )
