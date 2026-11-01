"""Independent frozen codon geometry, separate from predictor accuracy."""

import hashlib
import json
from pathlib import Path

import pytest

from regsite import paired
from regsite.edits import build_edit_map

FIXTURE = Path("benchmarks/recoding/rbs-codon-correspondence-fixtures.json")
FIXTURE_SHA256 = "4dcd59ec3195178e93aa575524572ea94f012433701a615effb4fc7cb94283e6"
CASES = json.loads(FIXTURE.read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["input"]["pair_id"])
def test_comparison_matches_independent_literal_codon_rosters(case):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
    geometry = build_edit_map(case["input"])
    assert list(geometry.current_to_recoded) == case["current_to_recoded"]
    assert list(geometry.recoded_to_current) == case["recoded_to_current"]
    sides: dict[str, dict] = {}
    for side in paired.SIDES:
        candidates = []
        for item in case["candidates"][side]:
            step = 1 if item["strand"] == "+" else -1
            candidates.append(
                {
                    "id": item["id"],
                    "strand": item["strand"],
                    "anchor": item["base"],
                    "codon_bases": [item["base"] + step * i for i in range(3)],
                    "status": "ok",
                    "scalars": {},
                    "features": {},
                }
            )
        sides[side] = {
            "identities": dict.fromkeys(
                [
                    "model_sha256",
                    "settings_sha256",
                    "backend_sha256",
                    "calibration_sha256",
                ],
                "synthetic-geometry-only",
            ),
            "roster_status": "known",
            "candidates": candidates,
        }
    rows = paired._comparisons(sides, geometry)
    expected = case["expected"]
    assert [
        {
            "current_id": row["current_candidate_id"],
            "recoded_id": row["recoded_candidate_id"],
        }
        for row in rows
        if row["status"] == "paired"
    ] == expected["pairs"]
    translated = {
        "unmapped_current_anchor": "deleted_coordinate",
        "unmapped_recoded_anchor": "inserted_coordinate",
        "mapped_anchor_absent_from_current_roster": "mapped_anchor_absent",
        "mapped_anchor_absent_from_recoded_roster": "mapped_anchor_absent",
        "interrupted_codon": "interrupted_codon",
    }
    for side in paired.SIDES:
        assert [
            {"id": row[side + "_candidate_id"], "reason": translated[row["reason"]]}
            for row in rows
            if row["status"] == "unmatched" and row[side + "_candidate_id"] is not None
        ] == expected["unmatched_" + side]
        assert [
            {
                "id": c["id"],
                "bases": c["codon_bases"],
                "mapped_bases": [
                    geometry.map_base(side, base) for base in c["codon_bases"]
                ],
            }
            for c in sides[side]["candidates"]
        ] == expected[side + "_paths"]
