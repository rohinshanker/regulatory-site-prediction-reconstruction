"""Independent structural and arithmetic cases, without assay-derived fitting."""

import math

import pytest

from regsite.standby import ZERO_AREA, distortion, modules, optimize
from regsite.structures import BackendError, Structure


def structure(dot: str) -> Structure:
    pairs = [-1] * len(dot)
    stack = []
    for i, symbol in enumerate(dot):
        if symbol == "(":
            stack.append(i)
        elif symbol == ")":
            left = stack.pop()
            pairs[left], pairs[i] = i, left
    assert not stack
    return Structure("A" * len(dot), tuple(pairs), -20)


@pytest.mark.parametrize(
    "dot,height",
    [
        ("(...)", 2.5),
        ("((...))", 3.5),
        ("(..(...)...)", 6),
        ("((...)(...))", 10 / 3),
        ("(((...)(...)))", 13 / 3),
        ("((...)(...)(...))", 4),
        ("((...)..(...))", 13 / 3),
        # Independent specification-review fixtures, derived before code review.
        ("(((....)))", 5),
        ("(.(....))", 4.5),
        ("(..(....)...)", 6.5),
        ("(.(....).(......).)", 5.5),
        ("((....)(....)(....))", 4.375),
        ("(.(.(....).(......).).(....).)", 6),
    ],
)
def test_height_by_hand_counting_and_s3_orientations(dot, height):
    # Two branches: Hbase=2, Hleft=Hright=4 -> mean 10/3.
    # Three branches: Hbase=2.5, each extended=4.5 -> mean 4.
    module = modules(structure(".." + dot + "..."))[0]
    assert module.height == pytest.approx(height)
    assert module.distal == (0, 2)
    assert module.proximal == (2 + len(dot), 5 + len(dot))
    assert module.area == pytest.approx(20 - height)


def test_shared_gaps_uncapped_sliding_and_capped_accessibility():
    dot = ".(...).." + "(" * 20 + "...." + ")" * 20 + "..."
    left, right = modules(structure(dot))
    assert left.proximal == right.distal == (6, 8)
    assert left.downstream_height == 22
    assert right.height == 22
    assert right.area == 5  # 15 + D2 + P3 - capped H15.
    assert right.downstream_height == 0
    result = optimize(structure(dot), -20, lambda pairs: 1000)
    assert result.selected.module == left
    assert result.selected.sliding == pytest.approx(4.4)


@pytest.mark.parametrize("length", [0, 1, 5, 6, 100])
def test_unstructured_prefix_and_empty_boundary(length):
    prefix = structure("." * length)
    called = []
    result = optimize(prefix, -20, lambda pairs: called.append(pairs))
    assert called == []
    assert result.evaluated_states == result.original_modules == 1
    assert result.selected.module.hairpin is None
    assert result.selected.module.distal == (0, 0)
    assert result.selected.module.proximal == (0, length)
    assert result.selected.total == distortion(15 + length)
    assert result.ablations["no_sliding"] == result.selected.total
    assert result.ablations["no_distortion"] == 0


def test_polynomial_and_monotone_zero_continuation():
    assert distortion(0) == 17.359
    assert distortion(4) == pytest.approx(11.451)
    assert distortion(7) == pytest.approx(7.818)
    assert distortion(13) == pytest.approx(2.604)
    assert distortion(ZERO_AREA) == distortion(21) == distortion(10000) == 0
    values = [distortion(i / 10) for i in range(1001)]
    assert all(a >= b >= 0 for a, b in zip(values[:-1], values[1:], strict=True))
    for bad in (-1, math.inf, math.nan):
        with pytest.raises(BackendError, match="surface area"):
            distortion(bad)


def test_partial_unfolding_tradeoff_with_independent_energy_oracle():
    # Paper Figure 3's D=P2,H15 geometry, but an explicitly synthetic oracle:
    # first three closing pairs cost .9 each; the remaining pairs cost 4 each.
    prefix = structure(".." + "(" * 12 + "......" + ")" * 12 + "..")
    seen = []

    def evaluate(pairs):
        removed = 12 - sum(j > i for i, j in enumerate(pairs))
        seen.append(removed)
        return -20 + 0.9 * min(3, removed) + 4 * max(0, removed - 3)

    result = optimize(prefix, -20, evaluate)
    assert sorted(seen) == list(range(1, 13))
    selected = result.selected
    assert selected.opened_pairs == ((2, 31), (3, 30), (4, 29))
    assert selected.module.height == 12
    assert selected.module.area == 13
    assert selected.unfolding == pytest.approx(2.7)
    assert selected.distortion == pytest.approx(2.604)
    assert selected.total == pytest.approx(5.304)
    assert result.ablations["no_opening"] == pytest.approx(11.451)
    assert result.ablations["no_sliding"] == selected.total
    assert result.evaluated_states == 13
    assert not result.negative_unfolding_seen


def test_branch_openings_are_complete_reciprocal_and_ancestor_closed():
    prefix = structure(".((...)(...)).")
    seen = []

    def evaluate(pairs):
        # Independent set characterization: an inner pair cannot disappear
        # while the outer pair (1,11) remains. Reciprocal state is mandatory.
        assert pairs[1] == -1
        assert all(j < 0 or pairs[j] == i for i, j in enumerate(pairs))
        removed = frozenset(
            i for i, j in enumerate(prefix.pairs) if j > i and pairs[i] == -1
        )
        seen.append(removed)
        return 100

    result = optimize(prefix, -20, evaluate)
    assert set(seen) == {
        frozenset((1,)),
        frozenset((1, 2)),
        frozenset((1, 7)),
        frozenset((1, 2, 7)),
    }
    assert result.evaluated_states == 5
    assert result.selected.opened_pairs == ()


def test_complete_opening_gap_and_unaffected_neighbors():
    prefix = structure("(...)..((...))..(...)")

    def evaluate(pairs):
        # Favor complete opening of middle module only. The state set must not
        # open more than one original connected module simultaneously.
        if pairs[7] == pairs[8] == -1:
            assert pairs[0] == 4 and pairs[16] == 20
            return -20
        return 100

    result = optimize(prefix, -20, evaluate)
    chosen = result.selected
    assert chosen.original_hairpin == (7, 14)
    assert chosen.module.hairpin is None
    assert chosen.module.proximal == (5, 16)
    assert chosen.module.distal == (5, 5)
    assert chosen.sliding == 0.5
    assert chosen.distortion == 0
    assert result.original_modules == 3
    assert result.evaluated_states == 5


def test_negative_energy_delta_is_visible_and_clamped_not_rewarded():
    result = optimize(structure("((...))"), -20, lambda pairs: -21)
    assert result.negative_unfolding_seen
    assert result.selected.unfolding_raw == -1
    assert result.selected.unfolding == 0
    assert result.selected.total >= 0


def test_no_opening_wins_exact_ties_and_5prime_module_breaks_remaining_tie():
    prefix = structure("." * 6 + "(...)" + "." * 6)
    result = optimize(prefix, -20, lambda pairs: -20)
    assert result.selected.opened_pairs == ()
    # No sliding/distortion ablations are reoptimized, not terms subtracted
    # from the full model's selected state.
    assert result.ablations["no_distortion"] == 0


def test_validation_energy_failures_and_no_partial_over_limit_search():
    with pytest.raises(BackendError, match="100 nucleotides"):
        modules(structure("." * 101))
    with pytest.raises(BackendError, match="reciprocal"):
        modules(Structure("AAA", (2, 2, 0), 0))
    with pytest.raises(BackendError, match="baseline"):
        optimize(structure("..."), math.nan, lambda pairs: 0)
    with pytest.raises(BackendError, match="state energy"):
        optimize(structure("(...)"), 0, lambda pairs: math.inf)
    # Nine independent branches beneath one pair give 1+2**9 states.
    with pytest.raises(BackendError, match="512 states"):
        optimize(structure("(" + "(...)" * 9 + ")"), 0, lambda pairs: pytest.fail())
    # Two original roots each have 257 states; union includes baseline once.
    with pytest.raises(BackendError, match="512 states"):
        optimize(
            structure(("(" + "(...)" * 8 + ")") * 2),
            0,
            lambda pairs: pytest.fail(),
        )


def test_exact_512_state_boundary_and_any_oracle_failure_aborts():
    # Independent count: roots with C=257 and C=256 have 1+256+255=512.
    # C=256 is 1+3*5*17, from a chain and two forks under another root.
    first = "(" + "(...)" * 8 + ")"
    second = "(" + "((...))" + "((...)(...))" + "(" + "(...)" * 4 + ")" + ")"
    seen = set()

    def evaluate(pairs):
        assert pairs not in seen
        seen.add(pairs)
        return 100

    result = optimize(structure(first + second), 0, evaluate)
    assert result.evaluated_states == 512
    assert len(seen) == 511
    for failure_call in (1, 2, 3):
        calls = []

        def fail(pairs, calls=calls, failure_call=failure_call):
            calls.append(pairs)
            if len(calls) == failure_call:
                raise BackendError("oracle failed")
            return 100

        with pytest.raises(BackendError, match="oracle failed"):
            optimize(structure("(((...)))"), 0, fail)
        assert len(calls) == failure_call
