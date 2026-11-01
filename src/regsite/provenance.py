"""Canonical scientific identity checks for explicitly admitted energy caches."""

import hashlib
import json

from regsite import __version__
from regsite.profiles import get_profile
from regsite.rbs import SOURCE_COMMIT


def canonical_hash(value: object) -> str:
    """Hash finite canonical JSON, excluding no fields implicitly."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def energy_signature(prediction: dict) -> dict[str, str]:
    """Identify model and backend; this is provenance, not proof of authenticity."""
    model, backend = prediction.get("model"), prediction.get("backend")
    if (
        not isinstance(model, dict)
        or not isinstance(backend, dict)
        or not backend
        or model.get("id") != get_profile("context2017").model_id
        or model.get("source_commit") != SOURCE_COMMIT
        or model.get("implementation_version") != __version__
        or not isinstance(model.get("parameters"), dict)
    ):
        raise ValueError("energy cache model/backend provenance is incompatible")
    return {
        "energy_backend_sha256": canonical_hash(backend),
        "energy_model_sha256": canonical_hash(model),
    }


def consistent_energy_signature(predictions: list[dict]) -> dict[str, str]:
    """Refuse a mixture of scientific model parameters or backend installations."""
    if not predictions:
        raise ValueError("energy cache contains no predictions")
    first = energy_signature(predictions[0])
    if any(energy_signature(p) != first for p in predictions[1:]):
        raise ValueError("energy cache mixes model or backend identities")
    return first
