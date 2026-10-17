"""Bridge B's independent finite-energy and coordinate fixtures to runtime APIs.

The abstract fixture supplies states/costs, not physically realizable RNA geometry.
This bridge tests the runtime's candidate objective and ties; geometric enumeration
and complete folding execution are tested in test_joint_runtime/test_standby.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from regsite import rbs
from regsite.contracts import RbsRequest
from regsite.genome import GenomicPath
from regsite.profiles import get_profile
from regsite.sequence import input_interval
from regsite.standby import Choice, Module, StandbyResult
from regsite.structures import Structure

FIXTURE = json.loads(Path("benchmarks/rbs/joint-selection-fixtures.json").read_text())


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["id"])
def test_independent_complete_energy_selection(case, monkeypatch):
    by_index = {c["index"]: c for c in case["candidates"]}
    request = RbsRequest.from_dict(
        {
            "sequence": "A" * 14 + "AUGAAA",
            "anti_sd": "ACCUCCUUA",
            "start_positions": [14],
        }
    )
    window, leader = request.sequence, request.sequence[:14]
    states = {}

    def assembled(window, leader, anti_sd, binding, folding, profile, evaluate):
        # Synthetic state energies and penalties are inputs to this isolated
        # selector check. No expected winning candidate is used to build them.
        index = binding[0][0]
        candidate = by_index[index]
        before_energy = Decimal(candidate["before"])
        choices = []
        for state_index, state in enumerate(candidate["states"]):
            penalty = (
                max(Decimal(0), Decimal(state["after"]) - before_energy)
                + Decimal(state["distortion"])
                + Decimal(state["sliding"])
            )
            choices.append(
                (penalty, state["opened"], state["module"], state["core"], state_index)
            )
        chosen = min(choices)
        state = candidate["states"][chosen[-1]]
        states[index] = chosen[-1]
        before = Structure(window, (-1,) * len(window), float(before_energy))
        after = Structure(window, before.pairs, float(state["after"]))
        unfolding = Decimal(state["after"]) - before_energy
        choice = Choice(
            Module((0, 0), None, (0, 0), 0, ()),
            None,
            (),
            (),
            float(unfolding),
            float(max(Decimal(0), unfolding)),
            float(state["distortion"]),
            float(state["sliding"]),
        )
        standby = StandbyResult(choice, len(choices), 1, {}, unfolding < 0)
        return rbs._BoundState(
            index, index, before, after, None, 14, standby, -choice.total
        )

    monkeypatch.setattr(rbs, "_bound_state", assembled)
    candidates = tuple(
        Structure(f"candidate-{i}", (), -1) for i in range(max(by_index) + 1)
    )
    options = [
        (
            float(Decimal(c["cofold"]) + Decimal(c["spacing"])),
            c["index"],
            5,
            float(c["spacing"]),
            [(c["index"], 0)],
        )
        for c in case["candidates"]
    ]
    search = rbs._empty_joint_search(len(candidates))
    option, bound = rbs._joint_selection(
        options,
        candidates,
        window,
        leader,
        request,
        "AUG",
        Structure(window, (-1,) * len(window), float(case["unbound"])),
        None,
        get_profile("joint_standby"),
        search,
    )
    expected = case["expected"]
    assert option[1] == search["selected_index"] == expected["winner"]
    assert search["greedy_index"] == expected["greedy"]
    assert states[option[1]] == expected["state"]
    assert search["complete"]
    assert search["evaluated"] == len(case["candidates"])
    assert [c["total_energy"] for c in search["candidates"]] == pytest.approx(
        [float(x) for x in expected["candidate_totals"]], abs=1e-12
    )
    assert search["greedy_total_energy"] == pytest.approx(
        float(expected["greedy_total"]), abs=1e-12
    )
    total = (
        bound.before.energy
        + option[3]
        + float(case["start"])
        - float(case["unbound"])
        - bound.standby_signed
    )
    assert total == pytest.approx(float(expected["total"]), abs=1e-12)


def test_independent_forward_reverse_start_and_circular_coordinates():
    for case in FIXTURE["coordinates"]:
        interval = input_interval(
            *(x + case["window_start"] for x in case["window_interval"]),
            case["length"],
            case["strand"],
        )
        assert [interval.start, interval.end] == case["expected_interval"]
    case = FIXTURE["start_mapping"]
    interval = input_interval(
        case["oriented_start"], case["oriented_start"] + 3, case["length"], "-"
    )
    assert [interval.start, interval.end] == case["reverse_start_codon_interval"]
    assert interval.end - 1 == case["reverse_forward_base"]
    for case in FIXTURE["circular"]:
        path = GenomicPath(
            case["genome_length"],
            case["oriented_first_base"],
            case["genome_length"],
            "+" if case["step"] == 1 else "-",
            True,
        )
        segments = path.project(*case["interval"])
        assert [[s.start, s.end] for s in segments] == case["expected_segments"]
