"""Runtime comparisons with Session B's independently prepared source fixtures."""

import json
from pathlib import Path

import pytest

from regsite.standby import ZERO_AREA, distortion, modules, optimize
from regsite.structures import Structure

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "benchmarks/rbs/standby-analytic-fixtures.json"
    ).read_text()
)


def structure(dot):
    """Translate a hand-drawn topology; these tests do not call a folding engine."""
    pairs, stack = [-1] * len(dot), []
    for index, symbol in enumerate(dot):
        if symbol == "(":
            stack.append(index)
        elif symbol == ")":
            left = stack.pop()
            pairs[left], pairs[index] = index, left
    assert not stack
    return Structure("A" * len(dot), tuple(pairs), -20)


@pytest.mark.parametrize("row", REFERENCE["raw_polynomial"])
def test_independent_polynomial_and_declared_continuation(row):
    area = float(row["surface_area"])
    # B retains the raw printed polynomial, including negative/upturn values.
    # The runtime's explicit monotone continuation differs above its first root.
    expected = float(row["energy"]) if area < ZERO_AREA else 0
    assert distortion(area) == pytest.approx(expected)


def test_independent_single_capped_and_branched_geometry():
    simple, capped, branched = REFERENCE["geometry"]
    hairpin = modules(structure("..(((...)))..."))[0]
    assert hairpin.height == float(simple["height"])
    assert hairpin.area == float(simple["surface_area"])
    hairpin = modules(structure(".." + "(" * 16 + "...." + ")" * 16 + "..."))[0]
    assert hairpin.height == float(capped["raw_height"])
    assert hairpin.area == float(capped["surface_area"])
    # Physical branch orientations have heights 12, 6 and 15 in Figure S3's
    # convention; this particular pair tree realizes those three orientations.
    tree = "(...." + "(" * 5 + "..." + ")" * 5
    tree += "...." + "(" * 8 + "..." + ")" * 8 + ")"
    assert modules(structure(tree))[0].height == float(branched["expected_mean_height"])


@pytest.mark.parametrize("row", REFERENCE["sliding"])
def test_independent_sliding_costs_are_not_height_capped(row):
    dot = "." * 10 + "(...)"
    for height in row["downstream_heights"]:
        stem = int(height) - 2
        dot += "(" * stem + "...." + ")" * stem
    result = optimize(structure(dot), -20, lambda pairs: 1000)
    assert result.selected.original_hairpin == (10, 15)
    assert result.selected.sliding == pytest.approx(float(row["expected_energy"]))


def test_independent_joint_unfolding_landscape():
    landscape = REFERENCE["synthetic_unfolding_landscape"]
    costs = {
        row["opened_pairs"]: float(row["unfolding_cost"])
        for row in landscape["candidates"]
    }
    prefix = structure("." + "(" * 9 + "......" + ")" * 9 + ".")
    seen = []

    def evaluate(pairs):
        opened = 9 - sum(right > left for left, right in enumerate(pairs))
        seen.append(opened)
        return -20 + costs.get(opened, 100)

    result = optimize(prefix, -20, evaluate)
    expected = next(
        row
        for row in landscape["candidates"]
        if row["opened_pairs"] == landscape["expected_selected_opened_pairs"]
    )
    assert sorted(seen) == list(range(1, 10))
    assert len(result.selected.opened_pairs) == expected["opened_pairs"]
    assert result.selected.module.area == float(expected["surface_area"])
    assert result.selected.distortion == pytest.approx(float(expected["distortion"]))
    assert result.selected.unfolding == pytest.approx(float(expected["unfolding_cost"]))
    assert result.selected.total == pytest.approx(float(expected["total"]))
