"""Real offline artificial design checks using the required release backend."""

import json
import math
from pathlib import Path

import jsonschema
import pytest
from test_design import example, verify_hash

from regsite.design import design
from regsite.sequence import reverse_complement


def test_real_leader_search_and_strand_equivalence(real_backend):
    value = example()
    positive = design(value, real_backend)
    assert positive["status"] == "complete", positive["reason"]
    assert positive["coverage"]["prediction_calls"] == 5
    assert positive["confirmation"]["status"] == "verified"
    assert positive["selected"]["score"]["absolute_log_error"] == min(
        row["score"]["absolute_log_error"] for row in positive["candidates"]
    )
    seed = value["rbs"]["sequence"]
    assert positive["selected"]["sequence"][:4] == seed[:4]
    assert positive["selected"]["sequence"][5:] == seed[5:]
    value["rbs"]["sequence"] = reverse_complement(seed.replace("T", "U")).replace(
        "U", "T"
    )
    value["rbs"]["strand"] = "-"
    value["editable_positions"] = [len(seed) - 5]
    negative = design(value, real_backend)
    assert negative["status"] == "complete", negative["reason"]
    plus_scores = {
        row["sequence"][4]: row["score"]["tir"] for row in positive["candidates"]
    }
    for row in negative["candidates"]:
        plus_base = reverse_complement(row["sequence"].replace("T", "U"))[4].replace(
            "U", "T"
        )
        assert row["score"]["tir"] == pytest.approx(plus_scores[plus_base], rel=1e-12)
        assert math.isfinite(row["score"]["absolute_log_error"])
    schema = json.loads(Path("schemas/rbs-design-result-1.schema.json").read_text())
    for result in (positive, negative):
        verify_hash(result)
        jsonschema.Draft202012Validator(schema).validate(json.loads(json.dumps(result)))
        for candidate in result["candidates"]:
            assert candidate["native"]["backend"] == real_backend.identity
