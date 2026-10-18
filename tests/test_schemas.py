"""Validate the versioned public contract across successful and missing results."""

import json
from pathlib import Path

import jsonschema
import pytest
from test_rbs import AlgebraBackend, request

from regsite.rbs import predict


@pytest.mark.parametrize("name", ["rbs-single", "rbs-batch"])
def test_shipped_requests(name):
    schema = json.loads(Path("schemas/rbs-request-1.0.schema.json").read_text())
    value = json.loads(Path(f"examples/{name}.json").read_text())
    for record in value if isinstance(value, list) else [value]:
        jsonschema.validate(record, schema)


def test_all_result_statuses():
    schema = json.loads(Path("schemas/rbs-result-1.0.schema.json").read_text())
    results = [
        predict(request(), AlgebraBackend()),
        predict(request(), AlgebraBackend(paired=None)),
        predict(request(start_positions=[0]), AlgebraBackend()),
        predict(None, AlgebraBackend()),
        predict(request(), AlgebraBackend(fail=True)),
    ]
    jsonschema.validate({"schema_version": "1.0", "results": results}, schema)
    assert {r["status"] for r in results} == {
        "ok",
        "no_candidate",
        "unsupported",
        "invalid_input",
        "failed",
    }
    results[-1]["sites"][0]["tir"] = 0
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema_version": "1.0", "results": results}, schema)
