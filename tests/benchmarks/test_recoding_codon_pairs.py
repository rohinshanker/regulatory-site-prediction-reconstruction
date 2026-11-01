"""Frozen literal results and independent token-based codon geometry checks."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.recoding.codon_pairs import MAX_CANDIDATES, match_rbs_candidates
from benchmarks.recoding.edit_maps import MAX_BASES, build_map

FIXTURE_PATH = Path("benchmarks/recoding/rbs-codon-correspondence-fixtures.json")
CASES = json.loads(FIXTURE_PATH.read_bytes())["cases"]


def candidate(name, base, strand="+"):
    return {"id": name, "base": base, "strand": strand}


def document(
    sequence="CCCCCC", start=None, end=None, replacement="", topology="linear"
):
    """Make a synthetic input with at most one explicitly supplied edit."""
    edits = []
    recoded = sequence
    if start is not None:
        edits = [{"id": "edit", "start": start, "end": end, "replacement": replacement}]
        recoded = sequence[:start] + replacement + sequence[end:]
    return {
        "schema_version": "paired-edit-input-1",
        "pair_id": "geometry",
        "topology": topology,
        "current": {"id": "before", "sequence": sequence},
        "recoded": {"id": "after", "sequence": recoded},
        "edits": edits,
    }


def all_geometry(length, side):
    """Supply every complete three-base window on both strands, without motifs."""
    return [
        candidate(f"{side}:{anchor}:{strand}", anchor, strand)
        for left in range(length - 2)
        for anchor, strand in ((left, "+"), (left + 2, "-"))
    ]


def window(row, labels):
    """Read a window by slicing an independent list of position identities."""
    anchor = row["base"]
    if row["strand"] == "+":
        return labels[anchor : anchor + 3]
    return labels[anchor - 2 : anchor + 1][::-1]


def assert_partition(result, current, recoded):
    assert result["matched_pairs"] == len(result["pairs"])
    for side, rows in (("current", current), ("recoded", recoded)):
        ids = [row["id"] for row in rows]
        paired = [pair[f"{side}_id"] for pair in result["pairs"]]
        unmatched = [row["id"] for row in result[f"unmatched_{side}"]]
        assert result[f"{side}_count"] == len(ids)
        assert sorted(paired + unmatched) == sorted(ids)
        assert len(set(paired + unmatched)) == len(ids)
        assert [path["id"] for path in result[f"{side}_paths"]] == ids
        assert unmatched == [name for name in ids if name not in set(paired)]
    assert result["biological_gain_loss_evaluated"] is False


def assert_token_accounting(result, current, recoded, before, after):
    """Compare both partitions to window identity, without using an edit map."""
    expected_pairs = []
    for side, rows, other_rows, source, target, missing_reason in (
        ("current", current, recoded, before, after, "deleted_coordinate"),
        ("recoded", recoded, current, after, before, "inserted_coordinate"),
    ):
        expected_unmatched = []
        expected_paths = []
        for row in rows:
            bases = window(row, list(range(len(source))))
            labels = window(row, source)
            expected_paths.append(
                {
                    "id": row["id"],
                    "bases": bases,
                    "mapped_bases": [
                        target.index(label) if label in target else None
                        for label in labels
                    ],
                }
            )
            counterparts = [
                other
                for other in other_rows
                if source[row["base"]] == target[other["base"]]
                and row["strand"] == other["strand"]
            ]
            if source[row["base"]] not in target:
                reason = missing_reason
            elif not counterparts:
                reason = "mapped_anchor_absent"
            elif labels != window(counterparts[0], target):
                reason = "interrupted_codon"
            else:
                if side == "current":
                    expected_pairs.append(
                        {"current_id": row["id"], "recoded_id": counterparts[0]["id"]}
                    )
                continue
            expected_unmatched.append({"id": row["id"], "reason": reason})
        assert result[f"unmatched_{side}"] == expected_unmatched
        assert result[f"{side}_paths"] == expected_paths
    assert result["pairs"] == expected_pairs
    assert_partition(result, current, recoded)


def test_fixture_identity_and_totals():
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == (
        "4dcd59ec3195178e93aa575524572ea94f012433701a615effb4fc7cb94283e6"
    )
    assert len(CASES) == 19
    assert sum(len(case["candidates"]["current"]) for case in CASES) == 19
    assert sum(len(case["candidates"]["recoded"]) for case in CASES) == 21
    assert sum(case["expected"]["matched_pairs"] for case in CASES) == 6
    assert (
        sum(
            row["reason"] == "interrupted_codon"
            for case in CASES
            for side in ("current", "recoded")
            for row in case["expected"][f"unmatched_{side}"]
        )
        == 16
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["input"]["pair_id"])
def test_literal_outputs_and_independent_complete_motif_rosters(case):
    doc = case["input"]
    current, recoded = (case["candidates"][side] for side in ("current", "recoded"))
    original = copy.deepcopy((doc, current, recoded))
    result = match_rbs_candidates(doc, current, recoded)
    assert result == case["expected"]
    assert (doc, current, recoded) == original
    assert_partition(result, current, recoded)
    # Enumerate forward windows and their reverse complements independently.
    for side in ("current", "recoded"):
        sequence = doc[side]["sequence"]
        expected = set()
        for left in range(len(sequence) - 2):
            triplet = sequence[left : left + 3]
            if triplet in {"ATG", "GTG", "TTG"}:
                expected.add((left, "+"))
            reverse = triplet.translate(str.maketrans("ACGT", "TGCA"))[::-1]
            if reverse in {"ATG", "GTG", "TTG"}:
                expected.add((left + 2, "-"))
        assert {(row["base"], row["strand"]) for row in case["candidates"][side]} == (
            expected
        )
    mapping = build_map(doc)
    assert mapping["current_to_recoded"] == case["current_to_recoded"]
    assert mapping["recoded_to_current"] == case["recoded_to_current"]


@pytest.mark.parametrize("side", ["current", "recoded"])
@pytest.mark.parametrize(
    "rows, message",
    [
        (None, "list"),
        ({}, "list"),
        ((), "list"),
        ([{}] * (MAX_CANDIDATES + 1), "at most"),
        ([None], "exactly"),
        ([[]], "exactly"),
        ([{}], "exactly"),
        ([{"id": "c", "base": 0}], "exactly"),
        ([dict(candidate("c", 0), score=0)], "exactly"),
        ([dict(candidate("c", 0), status="failed")], "exactly"),
        ([candidate("", 0)], "ID"),
        ([candidate("x" * 129, 0)], "ID"),
        ([candidate(None, 0)], "ID"),
        ([candidate([], 0)], "ID"),
        ([candidate(1, 0)], "ID"),
        ([candidate("c", True)], "integer"),
        ([candidate("c", False)], "integer"),
        ([candidate("c", 0.0)], "integer"),
        ([candidate("c", "0")], "integer"),
        ([candidate("c", None)], "integer"),
        ([candidate("c", [])], "integer"),
        ([candidate("c", -1)], "integer"),
        ([candidate("c", 6)], "integer"),
        ([candidate("c", 10**100)], "integer"),
        ([candidate("c", 0, "?")], "strand"),
        ([candidate("c", 0, None)], "strand"),
        ([candidate("c", 0, [])], "strand"),
        ([candidate("same", 0), candidate("same", 1)], "Duplicate"),
        ([candidate("same", 0), candidate("other", 0)], "Duplicate"),
        ([candidate("same", 2), candidate("same", 2, "-")], "Duplicate"),
        ([candidate("c", 0)] * MAX_CANDIDATES, "Duplicate"),
    ],
)
def test_strict_roster_validation(side, rows, message):
    rosters = {"current": [], "recoded": []}
    rosters[side] = rows
    with pytest.raises(ValueError, match=message):
        match_rbs_candidates(document(), **rosters)


@pytest.mark.parametrize("topology", ["linear", "circular"])
def test_all_path_boundaries_and_short_sequences(topology):
    for length in range(1, 7):
        doc = document("C" * length, topology=topology)
        for base in range(length):
            for strand in ("+", "-"):
                row = candidate("boundary", base, strand)
                fits = base <= length - 3 if strand == "+" else base >= 2
                for current, recoded in (([row], []), ([], [row])):
                    if fits:
                        result = match_rbs_candidates(doc, current, recoded)
                        assert_partition(result, current, recoded)
                    else:
                        with pytest.raises(ValueError, match="three codon bases"):
                            match_rbs_candidates(doc, current, recoded)


def test_revalidate_document_and_reject_serialized_map():
    doc = document()
    for invalid in (None, {}, build_map(doc), json.loads(json.dumps(build_map(doc)))):
        with pytest.raises(ValueError):
            match_rbs_candidates(invalid, [], [])
    for invalid in (
        dict(doc, current={"id": "c", "sequence": "cccccc"}),
        dict(doc, recoded={"id": "r", "sequence": "ACCCCC"}),
        dict(doc, schema_version="wrong"),
        dict(doc, edits=[{"id": "e", "start": True, "end": 1, "replacement": "C"}]),
        dict(doc, edits=[{"id": "e", "start": 1, "end": 2, "replacement": "A"}]),
    ):
        with pytest.raises(ValueError):
            match_rbs_candidates(invalid, [], [])


def test_empty_arbitrary_motifs_identity_boundaries_and_output_isolation():
    doc = document()
    empty = match_rbs_candidates(doc, [], [])
    assert empty == {
        "schema_version": "rbs-codon-correspondence-1",
        "pair_id": "geometry",
        "current_count": 0,
        "recoded_count": 0,
        "matched_pairs": 0,
        "pairs": [],
        "unmatched_current": [],
        "unmatched_recoded": [],
        "current_paths": [],
        "recoded_paths": [],
        "biological_gain_loss_evaluated": False,
    }
    rows = [candidate("x" * 128, 2), candidate(" ", 2, "-")]
    result = match_rbs_candidates(doc, rows, rows)
    assert result["pairs"] == [
        {"current_id": row["id"], "recoded_id": row["id"]} for row in rows
    ]
    assert_partition(result, rows, rows)
    result["current_paths"][0]["bases"][0] = -1
    result["current_paths"][0]["mapped_bases"][0] = -1
    assert result["recoded_paths"][0]["bases"][0] == 2
    assert match_rbs_candidates(doc, rows, rows)["current_paths"][0]["bases"][0] == 2
    assert rows[0]["base"] == 2


def test_largest_complete_geometry_rosters():
    rows = all_geometry(MAX_BASES, "same")
    assert len(rows) == 19996
    result = match_rbs_candidates(document("C" * MAX_BASES), rows, rows)
    assert result["matched_pairs"] == len(rows)
    assert result["unmatched_current"] == result["unmatched_recoded"] == []
    assert result["pairs"] == [
        {"current_id": row["id"], "recoded_id": row["id"]} for row in rows
    ]


def test_mixed_order_retention_and_absence_precedence():
    doc = document("C" * 10, 3, 3, "CC")
    current = [
        candidate("c7", 7),
        candidate("c2", 2),
        candidate("c5m", 5, "-"),
        candidate("c4m", 4, "-"),
        candidate("c0", 0),
        candidate("c3m", 3, "-"),
    ]
    recoded = [
        candidate("r6m", 6, "-"),
        candidate("r4m", 4, "-"),
        candidate("r9", 9),
        candidate("r2", 2),
        candidate("r7m", 7, "-"),
        candidate("r8", 8),
    ]
    result = match_rbs_candidates(doc, current, recoded)
    assert result["pairs"] == [
        {"current_id": "c7", "recoded_id": "r9"},
        {"current_id": "c5m", "recoded_id": "r7m"},
    ]
    assert result["unmatched_current"] == [
        {"id": "c2", "reason": "interrupted_codon"},
        {"id": "c4m", "reason": "interrupted_codon"},
        {"id": "c0", "reason": "mapped_anchor_absent"},
        {"id": "c3m", "reason": "mapped_anchor_absent"},
    ]
    assert result["unmatched_recoded"] == [
        {"id": "r6m", "reason": "interrupted_codon"},
        {"id": "r4m", "reason": "inserted_coordinate"},
        {"id": "r2", "reason": "interrupted_codon"},
        {"id": "r8", "reason": "mapped_anchor_absent"},
    ]
    assert_partition(result, current, recoded)


def test_exhaustive_small_single_edits_paths_sparse_rosters_and_symmetry():
    for length in range(1, 7):
        before = list(range(length))
        for start in range(length + 1):
            for end in range(start, length + 1):
                for count in range(4):
                    if (start == end and count == 0) or length - (
                        end - start
                    ) + count == 0:
                        continue
                    # Equal replacements retain identities; unequal blocks have
                    # fresh identities. Window equality is the independent oracle.
                    replacement = (
                        before[start:end]
                        if end - start == count
                        else [f"new:{i}" for i in range(count)]
                    )
                    after = before[:start] + replacement + before[end:]
                    doc = document("C" * length, start, end, "A" * count)
                    inverse = document(
                        doc["recoded"]["sequence"],
                        start,
                        start + count,
                        "C" * (end - start),
                    )
                    current = all_geometry(length, "c")[::-1]
                    recoded = all_geometry(len(after), "r")
                    for c_rows, r_rows in (
                        (current, recoded),
                        (current[::2], recoded[1::3]),
                        (current[1::3], recoded[::2]),
                    ):
                        original = copy.deepcopy((doc, c_rows, r_rows))
                        result = match_rbs_candidates(doc, c_rows, r_rows)
                        assert_token_accounting(result, c_rows, r_rows, before, after)
                        swapped = match_rbs_candidates(inverse, r_rows, c_rows)
                        assert_token_accounting(swapped, r_rows, c_rows, after, before)
                        assert (doc, c_rows, r_rows) == original
