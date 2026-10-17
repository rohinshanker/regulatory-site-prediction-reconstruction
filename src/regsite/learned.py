"""Explicit assay-response regression, separate from thermodynamic scoring."""

import hashlib
import json
from dataclasses import asdict
from typing import Any, cast

from regsite import __version__
from regsite.backend import RnaStructure
from regsite.contracts import RbsRequest
from regsite.features import FeatureError, extract_features, feature_names
from regsite.learning import RidgeModel
from regsite.provenance import energy_signature
from regsite.rbs import predict
from regsite.sequence import InputError, input_interval, normalize_rna

RESULT_VERSION = "rbs-learned-result-1"


def validate_model(model: RidgeModel) -> dict:
    """Require a named feature recipe, assay target and explicit training domain."""
    required = {"feature_kind", "target_name", "target_units", "training_domain"}
    if not required <= model.provenance.keys():
        raise ValueError(
            "RBS regression requires feature, target and domain provenance"
        )
    if model.feature_names != feature_names(model.provenance["feature_kind"]):
        raise ValueError(
            "artifact feature names disagree with the frozen feature recipe"
        )
    try:
        domain = json.loads(model.provenance["training_domain"])
    except ValueError as exc:
        raise ValueError("invalid training_domain JSON") from exc
    if (
        not isinstance(domain, dict)
        or domain.keys() != {"hosts", "anti_sd", "temperatures_c"}
        or any(
            not isinstance(v, list) or not 1 <= len(v) <= 100 for v in domain.values()
        )
        or any(not isinstance(h, str) or not h.strip() for h in domain["hosts"])
        or any(
            type(t) not in (int, float) or not 0 <= t <= 100
            for t in domain["temperatures_c"]
        )
    ):
        raise ValueError("invalid training_domain structure or values")
    for sequence in domain["anti_sd"]:
        if (
            normalize_rna(sequence, "training anti_sd", max_length=9) != sequence
            or len(sequence) != 9
        ):
            raise ValueError("training anti_sd must be normalized nine-base RNA")
    if (
        model.provenance["feature_kind"] == "context-energy-sequence-v1"
        and not {"energy_backend_sha256", "energy_model_sha256"}
        <= model.provenance.keys()
    ):
        raise ValueError(
            "energy artifact requires explicit training backend/model digests"
        )
    return domain


def predict_learned(
    value: object,
    model: RidgeModel,
    backend: RnaStructure | None = None,
    *,
    seconds: float = 60,
) -> dict:
    """Predict one supplied-start log2 assay response; retain explicit failures.

    Artifact/setup errors raise ValueError. Input/coverage/numeric errors become
    result records. Sequence-only inference needs no folding engine. Energy
    features require the exact context2017 mechanism; its independent energies
    remain inside mechanistic_reference and never become learned energy terms.
    """
    domain = validate_model(model)
    kind = model.provenance["feature_kind"]
    energy = kind == "context-energy-sequence-v1"
    if energy and backend is None:
        raise ValueError("energy regression requires the pinned folding backend")
    if type(seconds) not in (int, float) or not 0 < seconds <= 120:
        raise ValueError("learned record budget must be finite and within (0,120]")
    artifact_id = model.to_dict()["artifact_sha256"]
    result: dict[str, Any] = {
        "schema_version": RESULT_VERSION,
        "implementation_version": __version__,
        "model_id": f"{model.version}:{artifact_id}",
        "artifact_sha256": artifact_id,
        "feature_kind": kind,
        "score_scale": "log2_assay_response",
        "target": {
            "name": model.provenance["target_name"],
            "units": model.provenance["target_units"],
            "training_dataset": model.provenance["dataset_id"],
        },
        "id": None,
        "status": "invalid_input",
        "reason": None,
        "input": None,
        "prediction_id": None,
        "start_codon": None,
        "score_log2": None,
        "features": None,
        "unlearned_feature_changes": [],
        "mechanistic_reference": None,
        "warnings": [
            "learned_assay_response_not_energy_or_probability",
            "development_model_not_independently_promoted",
            "fluorescence_or_TE_proxy_does_not_measure_initiation_alone",
        ],
    }
    try:
        request = RbsRequest.from_dict(value)
        result.update(id=request.id, input=asdict(request))
        identity = {
            "implementation_version": __version__,
            "artifact_sha256": artifact_id,
            "input": asdict(request),
            "backend": cast(RnaStructure, backend).identity if energy else None,
            "seconds": float(seconds) if energy else None,
        }
        result["prediction_id"] = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if (
            request.host not in domain["hosts"]
            or request.anti_sd not in domain["anti_sd"]
            or request.temperature_c not in domain["temperatures_c"]
        ):
            result["warnings"].append("outside_declared_training_host_or_settings")
        # Validate supplied-start sequence eligibility before spending fold time.
        extract_features(request, kind="sequence-v1")
        assert request.start_positions is not None
        start = request.start_positions[0]
        result["start_codon"] = asdict(
            input_interval(start, start + 3, len(request.sequence), request.strand)
        )
        reference = (
            predict(
                value,
                cast(RnaStructure, backend),
                seconds=seconds,
                profile="context2017",
            )
            if energy
            else None
        )
        result["mechanistic_reference"] = reference
        if reference is not None and reference["status"] != "ok":
            result.update(
                status=reference["status"], reason="mechanistic_feature_unavailable"
            )
            return result
        if reference is not None:
            signature = energy_signature(reference)
            if any(
                model.provenance[key] != digest for key, digest in signature.items()
            ):
                result["warnings"].append(
                    "energy_backend_or_model_differs_from_training"
                )
        values = extract_features(request, kind=kind, prediction=reference)
        changed = [
            name
            for name, value, mean, scale in zip(
                model.feature_names, values, model.means, model.scales, strict=True
            )
            if scale == 0 and value != mean
        ]
        result["unlearned_feature_changes"] = changed
        if changed:
            result["warnings"].append(
                "changed_constant_training_features_have_no_learned_effect"
            )
        score = model.predict([values])[0]
        result.update(
            status="ok",
            score_log2=score,
            features={"names": list(model.feature_names), "values": list(values)},
        )
    except InputError as exc:
        result.update(status="invalid_input", reason=str(exc))
    except FeatureError as exc:
        result.update(status="unsupported", reason=str(exc))
    except ValueError as exc:
        result.update(status="failed", reason=str(exc))
    return result
