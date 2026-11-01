"""Public runtime correspondence to B's literal, outcome-free organization panel."""

import hashlib
import json
from pathlib import Path

import pytest
from test_transcript import annotation, document
from test_transcript import backend as backend

from regsite.transcript import predict_transcript
from regsite.transcript_geometry import feature

FIXTURE = (
    Path(__file__).parents[1] / "benchmarks/operon/organization-fixtures.json"
).read_bytes()
assert hashlib.sha256(FIXTURE).hexdigest() == (
    "cb9fd2eeb8a1927c5d8bba41bd8ed63fb9c5d44398e65571c8a350b3cbd14e10"
)
CASES = json.loads(FIXTURE)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_literal_geometry_through_public_predictors(case, backend):
    supplied, expected = case["input"], case["expected"]
    request = document()
    request["sequence"] = supplied["sequence"]
    request["transcript"] = annotation("rna", *supplied["transcript_range"])
    request["cds"] = [
        annotation(item["id"], *item["range"]) for item in supplied["cds"]
    ]
    request["promoter"]["scan"]["positions"] = []
    projection = supplied["projection"]
    if projection is not None:
        last = projection["origin"] + (len(supplied["sequence"]) - 1) * (
            1 if projection["sequence_strand"] == "+" else -1
        )
        request["projection"] = {
            "contig": projection["contig"],
            "contig_length": projection["length"],
            "origin": projection["origin"],
            "sequence_strand": projection["sequence_strand"],
            "topology": projection["topology"],
            "origin_crossing": not 0 <= last < projection["length"],
        }
    result = predict_transcript(request, backend)
    assert result["transcript"]["sequence"] == expected["transcript_sequence"]
    assert len(result["transcript"]["sequence"]) == expected["transcript_length"]
    assert result["components"]["rbs"]["roster"] == [
        position for position in expected["rbs_start_positions"] if position is not None
    ]
    assert [
        row["transcript_offset"] if row["eligible"] else None for row in result["cds"]
    ] == expected["rbs_start_positions"]
    assert [row["eligible"] for row in result["cds"]] == expected["eligible"]
    assert [row["transcript_offset"] for row in result["cds"]] == expected[
        "signed_start_offsets"
    ]
    # Fixtures mark annotation overhang even when the start is incompatible.
    # The runtime warns about truncated scoring context only for eligible starts.
    assert [
        row["annotation"]["range"][1] > supplied["transcript_range"][1]
        for row in result["cds"]
    ] == expected["downstream_annotation_clipped"]
    assert ["downstream_clipped" in row["warnings"] for row in result["cds"]] == [
        clipped and eligible
        for clipped, eligible in zip(
            expected["downstream_annotation_clipped"], expected["eligible"], strict=True
        )
    ]
    mapped = result["transcript"]["coordinates"]["genomic"]
    assert (None if mapped is None else mapped["runs"]) == expected[
        "transcript_genomic_segments"
    ]
    for index, row in enumerate(result["cds"]):
        if not row["eligible"]:
            assert row["reason"] == expected["reasons"][index]
        assert row["annotation"]["range"] == supplied["cds"][index]["range"]
        start = row["annotation"]["range"][0]
        # Annotation projection remains available even for an unsupported codon.
        projected = feature(
            [start, start + 3],
            length=len(request["sequence"]),
            offset=0,
            strand="+",
            projection=request["projection"],
        )["genomic"]
        points = None
        if projected is not None:
            points = [
                point
                for left, right in projected["runs"]
                for point in (
                    range(left, right)
                    if projected["strand"] == "+"
                    else range(right - 1, left - 1, -1)
                )
            ]
        assert points == expected["start_codon_genomic_points"][index]
