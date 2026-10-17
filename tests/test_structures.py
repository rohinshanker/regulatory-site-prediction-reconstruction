"""Independent hand-constructed CT interchange/structure fixtures."""

import pytest

from regsite.structures import BackendError, Structure, parse_ct

CT = """4 ENERGY = -2.50 example
1 A 0 2 4 1
2 C 1 3 3 2
3 G 2 4 2 3
4 U 3 0 1 4
"""


def test_ct_multiple_structures_and_dot_bracket():
    structures = parse_ct("\n" + CT + "\n" + CT, "ACGU")
    assert len(structures) == 2
    assert structures[0].pairs == (3, 2, 1, 0)
    assert structures[0].energy == -2.5
    assert structures[0].dot_bracket() == "(())"
    assert Structure("AAA", (-1, -1, -1), 0).dot_bracket() == "..."


@pytest.mark.parametrize(
    "text,sequence",
    [
        ("", "ACGU"),
        (" " * 2_000_001, "ACGU"),
        (CT.replace("4 ENERGY", "x ENERGY"), "ACGU"),
        (CT.replace("-2.50", "bad"), "ACGU"),
        (CT.replace("-2.50", "nan"), "ACGU"),
        (CT, "ACG"),
        ("\n".join(CT.splitlines()[:-1]), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 A 0 2 4"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 A q 2 4 1"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "2 A 0 2 4 1"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 A 0 2 5 1"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 A 0 2 1 1"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 U 0 2 4 1"), "ACGU"),
        (CT.replace("1 A 0 2 4 1", "1 A 0 2 0 1"), "ACGU"),
        (CT * 101, "ACGU"),
    ],
)
def test_ct_errors_are_not_no_binding_results(text, sequence):
    with pytest.raises(BackendError):
        parse_ct(text, sequence)


@pytest.mark.parametrize("pairs", [(2, 3, 0, 1), (1, -1), (0,)])
def test_impossible_plain_dot_bracket_rejected(pairs):
    with pytest.raises(BackendError):
        Structure("A" * len(pairs), pairs, 0).dot_bracket()


def test_missing_energy_remains_missing_and_ct_roundtrip():
    from regsite.structures import to_ct

    structure = parse_ct(CT.replace(" ENERGY = -2.50", ""), "ACGU")[0]
    assert structure.energy is None
    assert parse_ct(to_ct("ACGU", structure.pairs), "ACGU")[0] == structure
    with pytest.raises(BackendError, match="lengths differ"):
        to_ct("AAAA", ())
    with pytest.raises(BackendError, match="linker bases cannot pair"):
        parse_ct(CT.replace("1 A", "1 I"), "ICGU")


def test_corrupt_candidate_rejects_whole_search_without_silent_discard():
    with pytest.raises(BackendError, match="not reciprocal"):
        parse_ct(CT + CT.replace("1 A 0 2 4 1", "1 A 0 2 0 1"), "ACGU")
