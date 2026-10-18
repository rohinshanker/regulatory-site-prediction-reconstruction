"""Literal map expectations and exhaustive small-sequence path properties."""

import copy
import hashlib
import itertools
import json
from dataclasses import FrozenInstanceError

import pytest

from regsite.edits import EditError, build_edit_map


def pair(current="ACGT", recoded="ACGT", edits=None, **changes):
    return {
        "schema_version": "paired-edit-input-1",
        "pair_id": "pair",
        "topology": "linear",
        "current": {"id": "current", "sequence": current},
        "recoded": {"id": "recoded", "sequence": recoded},
        "edits": [] if edits is None else edits,
        **changes,
    }


def edit(start, end, replacement, identifier="e0"):
    return {"id": identifier, "start": start, "end": end, "replacement": replacement}


@pytest.mark.parametrize(
    "current,recoded,edits,forward,reverse",
    [
        ("ACGT", "ACGT", [], [0, 1, 2, 3], [0, 1, 2, 3]),
        ("ACGT", "ATGT", [edit(1, 2, "T")], [0, 1, 2, 3], [0, 1, 2, 3]),
        ("ACGT", "ACGT", [edit(1, 2, "C")], [0, 1, 2, 3], [0, 1, 2, 3]),
        ("ACGT", "ACCCGT", [edit(2, 2, "CC")], [0, 1, 4, 5], [0, 1, None, None, 2, 3]),
        ("ACGT", "AGT", [edit(1, 2, "")], [0, None, 1, 2], [0, 2, 3]),
        ("ACGT", "ATT", [edit(1, 3, "T")], [0, None, None, 2], [0, None, 3]),
        ("ACGT", "AACGT", [edit(0, 0, "A")], [1, 2, 3, 4], [None, 0, 1, 2, 3]),
        ("ACGT", "ACGTT", [edit(4, 4, "T")], [0, 1, 2, 3], [0, 1, 2, 3, None]),
        ("ACGT", "GT", [edit(0, 2, "")], [None, None, 0, 1], [2, 3]),
        ("ACGT", "GG", [edit(0, 4, "GG")], [None] * 4, [None] * 2),
        (
            "ACGT",
            "AGT",
            [edit(1, 2, "G"), edit(2, 3, "", "e1")],
            [0, 1, None, 2],
            [0, 1, 3],
        ),
    ],
)
def test_literal_correspondence(current, recoded, edits, forward, reverse):
    request = pair(current, recoded, edits)
    original = copy.deepcopy(request)
    mapping = build_edit_map(request)
    result = mapping.to_dict()
    assert request == original
    assert result["current_to_recoded"] == forward
    assert result["recoded_to_current"] == reverse
    assert result["current_sha256"] == hashlib.sha256(current.encode()).hexdigest()
    assert result["recoded_sha256"] == hashlib.sha256(recoded.encode()).hexdigest()
    assert (
        result["edits_sha256"]
        == hashlib.sha256(
            json.dumps(
                edits, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
        ).hexdigest()
    )
    expected_edited = [
        any(e["start"] <= i < e["end"] for e in edits) for i in range(len(current))
    ]
    assert result["current_declared_edited"] == expected_edited
    assert result["current_unmatched"] == [
        i for i, v in enumerate(forward) if v is None
    ]
    assert result["recoded_unmatched"] == [
        i for i, v in enumerate(reverse) if v is None
    ]
    for i, target in enumerate(forward):
        assert mapping.map_base("current", i) == target
        if target is not None:
            assert mapping.map_base("recoded", target) == i
            if not expected_edited[i]:
                assert current[i] == recoded[target]
    result["current_to_recoded"][0] = -999
    assert mapping.map_base("current", 0) == forward[0]
    with pytest.raises(FrozenInstanceError):
        mapping.pair_id = "changed"


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": "wrong"},
        {"pair_id": ""},
        {"pair_id": "a" * 129},
        {"pair_id": 1},
        {"topology": []},
        {"current": []},
        {"current": {"id": "a", "sequence": ""}},
        {"current": {"id": "a", "sequence": "N"}},
        {"current": {"id": "a", "sequence": "acgt"}},
        {"current": {"id": "a", "sequence": "A" * 10001}},
        {"recoded": {"id": None, "sequence": "A"}},
        {"edits": None},
        {"edits": [{}] * 10001},
        {"edits": [None]},
    ],
)
def test_malformed_document(changes):
    with pytest.raises(EditError):
        build_edit_map(pair() | changes)


def test_top_level_fields_and_sequence_types():
    for document in (
        None,
        pair() | {"extra": 1},
        {k: v for k, v in pair().items() if k != "pair_id"},
    ):
        with pytest.raises(EditError):
            build_edit_map(document)
    request = pair()
    request["current"]["sequence"] = None
    with pytest.raises(EditError):
        build_edit_map(request)


@pytest.mark.parametrize(
    "edits",
    [
        [edit(0, 1, "A"), edit(1, 2, "C")],  # duplicate IDs
        [edit(True, 1, "A")],
        [edit(0.0, 1, "A")],
        [edit(-1, 1, "A")],
        [edit(0, 5, "A")],
        [edit(2, 1, "A")],
        [edit(0, 1, "a")],
        [edit(0, 0, "")],
        [edit(2, 2, "A"), edit(2, 3, "A", "e1")],
        [edit(0, 3, "A"), edit(2, 3, "A", "e1")],
        [edit(2, 3, "A"), edit(0, 1, "A", "e1")],
        [edit(0, 0, "A" * 10000), edit(1, 1, "A", "e1")],
        [edit(0, 4, "AAAA")],  # does not reconstruct supplied ACGT
    ],
)
def test_bad_edits_are_never_guessed(edits):
    with pytest.raises(EditError):
        build_edit_map(pair(edits=edits))


def test_missing_and_split_features_are_distinct():
    insertion = build_edit_map(pair("ACGT", "ACCCGT", [edit(2, 2, "CC")]))
    p = insertion.map_interval("current", 0, 4, "+")
    assert p == {
        "source_bases": [0, 1, 2, 3],
        "mapped_bases": [0, 1, 4, 5],
        "mapped_runs": [[0, 2], [4, 6]],
        "unmatched_bases": 0,
        "complete_base_mapping": True,
        "contiguous_target_path": False,
    }
    reverse = insertion.map_interval("current", 0, 4, "-")
    assert reverse["mapped_runs"] == [[4, 6], [0, 2]]
    p = insertion.map_interval("recoded", 0, 6, "+")
    assert p["mapped_bases"] == [0, 1, None, None, 2, 3]
    assert p["mapped_runs"] == [[0, 2], [2, 4]]
    assert not p["complete_base_mapping"] and not p["contiguous_target_path"]
    assert insertion.map_interval("recoded", 2, 4, "+")["mapped_runs"] == []
    empty = insertion.map_interval("current", 4, 4, "+")
    assert (
        empty["mapped_bases"] == []
        and empty["complete_base_mapping"]
        and empty["contiguous_target_path"]
    )


def test_circular_origin_is_split_but_contiguous():
    mapping = build_edit_map(pair(topology="circular"))
    plus = mapping.map_interval("current", 3, 7, "+")
    minus = mapping.map_interval("current", 3, 7, "-")
    assert plus["source_bases"] == [3, 0, 1, 2]
    assert plus["mapped_runs"] == [[3, 4], [0, 3]]
    assert minus["mapped_runs"] == [[0, 3], [3, 4]]
    assert plus["contiguous_target_path"] and minus["contiguous_target_path"]
    for bounds in ((4, 4), (0, 5), (-1, 1), (2, 1)):
        with pytest.raises(EditError):
            mapping.map_interval("current", *bounds, "+")


@pytest.mark.parametrize(
    "side,base",
    [("unknown", 0), ([], 0), ("current", 4), ("recoded", -1), ("current", True)],
)
def test_bad_points(side, base):
    with pytest.raises(EditError):
        build_edit_map(pair()).map_base(side, base)


def test_bad_interval():
    mapping = build_edit_map(pair())
    for args in (
        ("other", 0, 1, "+"),
        ("current", 0, 1, []),
        ("current", 0, 5, "+"),
        ("current", 0, 1.0, "+"),
    ):
        with pytest.raises(EditError):
            mapping.map_interval(*args)


def test_exhaustive_interval_paths_and_inverse_on_small_edits():
    """Literal splice geometry, expanded runs and base maps must agree everywhere."""
    for n in range(1, 7):
        current = ("ACGT" * 2)[:n]
        for start, end, replacement in itertools.product(
            range(n + 1), range(n + 1), ("", "A", "TG")
        ):
            if end < start or (start == end and not replacement):
                continue
            recoded = current[:start] + replacement + current[end:]
            if not recoded:
                continue
            for topology in ("linear", "circular"):
                mapping = build_edit_map(
                    pair(
                        current,
                        recoded,
                        [edit(start, end, replacement)],
                        topology=topology,
                    )
                )
                for side in ("current", "recoded"):
                    seq = current if side == "current" else recoded
                    target_size = len(recoded if side == "current" else current)
                    for a in range(len(seq) + int(topology == "linear")):
                        bound = a + len(seq) if topology == "circular" else len(seq)
                        for b in range(a, bound + 1):
                            for strand in ("+", "-"):
                                result = mapping.map_interval(side, a, b, strand)
                                points = [i % len(seq) for i in range(a, b)]
                                if strand == "-":
                                    points.reverse()
                                assert result["source_bases"] == points
                                mapped = [mapping.map_base(side, i) for i in points]
                                assert result["mapped_bases"] == mapped
                                expanded = [
                                    i
                                    for lo, hi in result["mapped_runs"]
                                    for i in (
                                        range(lo, hi)
                                        if strand == "+"
                                        else range(hi - 1, lo - 1, -1)
                                    )
                                ]
                                assert expanded == [i for i in mapped if i is not None]
                                step = 1 if strand == "+" else -1
                                adjacent = all(
                                    y == (x + step) % target_size
                                    if topology == "circular"
                                    else y == x + step
                                    for x, y in zip(mapped, mapped[1:], strict=False)
                                    if x is not None and y is not None
                                )
                                assert result["contiguous_target_path"] == (
                                    None not in mapped and adjacent
                                )
