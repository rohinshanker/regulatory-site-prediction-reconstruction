"""Direct input contracts and equivalence of site and individual state scoring."""

from unittest.mock import patch

import pytest

from regsite import promoter as p


@pytest.fixture(scope="module")
def params():
    return p.load_parameters()


@pytest.fixture(scope="module")
def calibration():
    return p.resolve_calibration("in_vitro")


def assert_error(error, code, field):
    assert (error.code, error.field, error.index, error.character) == (
        code,
        field,
        None,
        None,
    )
    assert str(error) == f"{code}: {field}"


@pytest.mark.parametrize("dna", [None, 1, b"ACGT", "", "acgt", "ANGT", "ACGU", " A"])
def test_invalid_public_state_dna_precedes_state_validation(dna, params):
    # Invalid coordinates and params must not mask the original sequence error.
    with patch.object(p, "_score_validated_state") as unchecked:
        for t, d, s in ((100, 6, 17), (None, 5, 21)):
            with pytest.raises(p.InputError) as exc:
                p.score_state(dna, t, d, s, None)
            assert_error(exc.value, "invalid_sequence", "sequence")
        unchecked.assert_not_called()


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("dna", [None, 1, b"ACGT", "", "acgt", "ANGT", "ACGU", " A"])
def test_invalid_site_dna_cannot_reach_scoring(dna, strand, params, calibration):
    with patch.object(p, "_score_validated_state") as unchecked:
        with pytest.raises(p.InputError) as exc:
            p.score_site(dna, strand, None, params, calibration, keep_states=True)
        assert_error(exc.value, "invalid_sequence", "sequence")
        unchecked.assert_not_called()


def test_site_validation_precedence(params, calibration):
    for dna, strand, base, code, field in (
        (None, "?", None, "invalid_strand", "strand"),
        ("A" * 200, "+", None, "invalid_integer", "tss"),
        ("A" * 200, "-", 200, "position_out_of_range", "tss"),
    ):
        with patch.object(p, "_score_validated_state") as unchecked:
            with pytest.raises(p.InputError) as exc:
                p.score_site(dna, strand, base, params, calibration, keep_states=True)
            assert_error(exc.value, code, field)
            unchecked.assert_not_called()


@pytest.mark.parametrize(
    "length,t,d,s,code,field",
    [
        (200, None, None, None, "invalid_integer", "t"),
        (200, -1, 6, 17, "invalid_integer", "t"),
        (200, 100, True, None, "invalid_integer", "d"),
        (200, 100, 5, None, "invalid_integer", "s"),
        (200, 100, 5, 17, "invalid_state", "state"),
        (200, 100, 11, 17, "invalid_state", "state"),
        (200, 100, 6, 14, "invalid_state", "state"),
        (200, 100, 6, 21, "invalid_state", "state"),
        (200, 0, 5, 17, "invalid_state", "state"),
        (77, 57, 6, 15, "insufficient_context", "state"),
        (200, 181, 6, 15, "insufficient_context", "state"),
    ],
)
def test_public_state_keeps_state_and_context_errors(
    length, t, d, s, code, field, params
):
    with pytest.raises(p.InputError) as exc:
        p.score_state("A" * length, t, d, s, params)
    assert_error(exc.value, code, field)


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("keep_states", [False, True])
@pytest.mark.parametrize("t,count", [(57, 0), (58, 1), (63, 20), (67, 30), (181, 0)])
def test_site_validates_dna_once_regardless_of_state_count(
    strand, keep_states, t, count, params, calibration
):
    dna = "ACGTTGCA" * 25
    local_base = t if strand == "+" else len(dna) - 1 - t
    with patch.object(p, "_dna", wraps=p._dna) as validate:
        site = p.score_site(
            dna, strand, local_base, params, calibration, keep_states=keep_states
        )
    validate.assert_called_once_with(dna)
    assert site.state_count == count
    assert site.states is None if not keep_states else len(site.states) == count


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("motif", ["A", "ACGTTGCAGATCCGTA"])
@pytest.mark.parametrize(
    "length,t", [(77, 57), (78, 58), (87, 67), (200, 59), (200, 180), (200, 181)]
)
def test_site_matches_separately_requested_states(
    strand, motif, length, t, params, calibration
):
    dna = (motif * length)[:length]
    oriented = (
        dna if strand == "+" else dna.translate(str.maketrans("ACGT", "TGCA"))[::-1]
    )
    local_base = t if strand == "+" else length - 1 - t
    # Derive completeness from the declared extents, independently of eligible_states.
    expected = tuple(
        p.score_state(oriented, t, d, s, params)
        for d in range(6, 11)
        for s in range(15, 21)
        if t - d - s - 37 >= 0 and t + 20 <= length
    )
    site = p.score_site(dna, strand, local_base, params, calibration, keep_states=True)
    assert site.states == expected
    assert (site.local_base, site.oriented_base, site.length) == (local_base, t, length)
    assert site.state_count == len(expected)
    winner = min(expected, key=lambda state: state.terms["total"], default=None)
    assert site.selected == winner
    assert site.tie_count == (
        sum(state.terms["total"] == winner.terms["total"] for state in expected)
        if winner is not None
        else None
    )
    assert (site.status, site.reason) == (
        ("ok", None) if expected else ("no_candidate", "insufficient_context")
    )
    compact = p.score_site(
        dna, strand, local_base, params, calibration, keep_states=False
    )
    assert compact.selected == winner and compact.tie_count == site.tie_count
    data = site.to_dict()
    assert data["selected"] == (
        None if winner is None else winner.to_dict(length, strand, calibration)
    )
    assert data["states"] == [
        dict(
            state.to_dict(length, strand, calibration, elements=False),
            selected=state is winner,
        )
        for state in expected
    ]
