"""Source parity against the independently frozen pre-runtime synthetic states."""

import json
import math
from pathlib import Path

import pytest

from regsite import promoter as p

FIXTURES = json.loads(
    (
        Path(__file__).parents[1] / "benchmarks/promoter/reference-fixtures.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize("case", FIXTURES, ids=lambda c: c["id"])
def test_all_212_source_states(case):
    params = p.load_parameters()
    calibration = p.resolve_calibration(
        "in_vitro" if case["organism"] == "in vitro" else "ecoli_mg1655",
        {"name": case["organism"]},
    )
    result = p.score_site(
        case["sequence"], "+", case["tss"], params, calibration, keep_states=True
    )
    expected = case["expected_states"]
    assert result.state_count == len(expected)
    assert len(result.states) == len(expected)
    for actual, source in zip(result.states, expected, strict=True):
        assert (actual.discriminator_length, actual.spacer_length) == (
            source["discriminator"],
            source["spacer"],
        )
        for runtime_name, source_name in p.TERM_SOURCE_NAMES.items():
            if runtime_name != "intercept":
                assert math.isclose(
                    actual.terms[runtime_name],
                    source["terms"][source_name],
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ), (case["id"], runtime_name, actual.terms, source)
        serialized = actual.to_dict(len(case["sequence"]), "+", calibration)
        assert math.isclose(
            serialized["relative_transcription_score"],
            source["Tx_rate"],
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    if expected:
        winner = min(expected, key=lambda state: state["terms"]["dG_total"])
        assert (
            result.selected.discriminator_length,
            result.selected.spacer_length,
        ) == (winner["discriminator"], winner["spacer"])
        assert result.tie_count == sum(
            x["terms"]["dG_total"] == winner["terms"]["dG_total"] for x in expected
        )
        assert result.status == "ok"
    else:
        assert result.status == "no_candidate"
        assert result.selected is None and result.tie_count is None


def test_fixture_count_is_frozen():
    assert [len(c["expected_states"]) for c in FIXTURES] == [
        30,
        30,
        0,
        1,
        30,
        1,
        30,
        0,
        30,
        30,
        30,
    ]
    assert sum(len(c["expected_states"]) for c in FIXTURES) == 212
