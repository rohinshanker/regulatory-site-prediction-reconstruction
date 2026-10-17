"""Scientific cache identity, consistency and finite canonical hashing."""

from copy import deepcopy

import pytest
from test_rbs import AlgebraBackend, request

from regsite.provenance import (
    canonical_hash,
    consistent_energy_signature,
    energy_signature,
)
from regsite.rbs import predict


def prediction():
    return predict(request(), AlgebraBackend(), profile="context2017")


def test_canonical_identity_and_mixed_backend_rejection():
    assert canonical_hash({"x": 1, "y": 2}) == canonical_hash({"y": 2, "x": 1})
    with pytest.raises(ValueError):
        canonical_hash(float("nan"))
    value = prediction()
    assert consistent_energy_signature([value, deepcopy(value)]) == energy_signature(
        value
    )
    changed = deepcopy(value)
    changed["backend"]["changed"] = "different build"
    with pytest.raises(ValueError, match="mixes"):
        consistent_energy_signature([value, changed])
    with pytest.raises(ValueError, match="no predictions"):
        consistent_energy_signature([])


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", None),
        ("backend", None),
        ("backend", {}),
        ("id", "other"),
        ("source_commit", "wrong"),
        ("implementation_version", "old"),
        ("parameters", None),
    ],
)
def test_incompatible_model_provenance(field, value):
    item = prediction()
    (item if field in ("model", "backend") else item["model"])[field] = value
    with pytest.raises(ValueError, match="incompatible"):
        energy_signature(item)
