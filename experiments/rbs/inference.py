"""Export frozen learned scores from pinned input-only files, without folding.

Pins admit exact file bytes; they do not establish authenticity. The code commit
is a caller assertion, as in the other recipes. No calibration is applied.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from regsite.contracts import RbsRequest
from regsite.features import FeatureError, extract_features
from regsite.learned import validate_model
from regsite.learning import RidgeModel
from regsite.provenance import canonical_hash, energy_signature

INPUT_VERSION = "rbs-learned-inference-input-1"
CACHE_VERSION = "rbs-learned-energy-cache-1"
OUTPUT_VERSION = "rbs-learned-inference-collection-1"
ENERGY_KIND = "context-energy-sequence-v1"
_BASE_WARNINGS = (
    "learned_assay_response_not_energy_or_probability",
    "development_model_not_independently_promoted",
    "fluorescence_or_TE_proxy_does_not_measure_initiation_alone",
)
_STATUSES = ("ok", "no_candidate", "unsupported", "invalid_input", "failed")
_CORE_FIELDS = {
    "schema_version",
    "id",
    "status",
    "reason",
    "sites",
    "warnings",
    "model",
    "backend",
    "input",
    "prediction_id",
}
_SITE_FIELDS = {
    "status",
    "reason",
    "codon",
    "start_codon",
    "oriented_start",
    "window",
    "energies",
    "tir",
    "log_tir",
    "aligned_spacing",
    "candidate_search",
    "structures",
    "binding_interval",
    "standby_interval",
    "warnings",
    "coding_footprint",
    "post_footprint",
}
_ENERGY_NUMBERS = {
    "dG_mRNA",
    "dG_cofold_search",
    "dG_search_with_spacing",
    "dG_complex",
    "dG_spacing",
    "dG_start",
    "dG_standby_signed",
    "dG_accessible_complex",
    "dG_total",
    "dG_post_footprint",
}
_ENERGY_NULLABLE = {"dG_mRNA_native_prediction", "dG_cofold_native_prediction"}


def _hex(value: object, length: int, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        raise ValueError(f"{label} must be an exact lowercase {length}-digit hex pin")


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path, digest: str, label: str) -> Any:
    _hex(digest, 64, label + " SHA256")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"{label} file SHA256 mismatch")
    value = json.loads(raw, object_pairs_hook=_object)
    canonical_hash(value)  # Reject nonfinite JSON, including unused cache fields.
    return value


def _rows(value: object, version: str) -> list[dict]:
    if (
        not isinstance(value, dict)
        or value.keys() != {"schema_version", "records"}
        or value["schema_version"] != version
        or not isinstance(value["records"], list)
    ):
        raise ValueError(f"expected closed {version} envelope")
    seen = set()
    for row in value["records"]:
        if not isinstance(row, dict) or not _text(row.get("id")):
            raise ValueError("records require nonempty string IDs")
        if row["id"] in seen:
            raise ValueError("record IDs must be unique")
        seen.add(row["id"])
    return value["records"]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _requests(rows: list[dict]) -> dict[str, RbsRequest]:
    requests = {}
    for row in rows:
        if row.keys() != {"id", "input", "status", "reason"}:
            raise ValueError("input records have missing or unknown fields")
        if row["status"] == "unsupported":
            if row["input"] is not None or not _text(row["reason"]):
                raise ValueError("unsupported input requires null input and a reason")
        elif row["status"] == "ok":
            if row["reason"] is not None:
                raise ValueError("ok input requires null reason")
            request = RbsRequest.from_dict(row["input"])
            if row["input"].get("id") != row["id"]:
                raise ValueError("input ID must exactly match record ID")
            requests[row["id"]] = request
        else:
            raise ValueError("input status must be ok or unsupported")
    return requests


def _core(prediction: object, request: RbsRequest) -> dict[str, str]:
    """Admit complete parent cores; identity checks also cover failed parents."""
    if (
        not isinstance(prediction, dict)
        or prediction.keys() != _CORE_FIELDS
        or prediction["schema_version"] != "1.1"
        or prediction["status"] not in _STATUSES
        or not _text(prediction["id"])
        or not isinstance(prediction["sites"], list)
        or not isinstance(prediction["warnings"], list)
        or any(not isinstance(w, str) for w in prediction["warnings"])
        or not (prediction["reason"] is None or _text(prediction["reason"]))
    ):
        raise ValueError("cache prediction must be a complete context2017 core")
    _hex(prediction["prediction_id"], 64, "parent prediction_id")
    signature = energy_signature(prediction)
    context = prediction["input"]
    expected = asdict(request)
    if not isinstance(context, dict) or context.keys() != expected.keys():
        raise ValueError("cache parent input must be complete")
    # Original raw sequence hashes may differ for scientifically identical DNA/RNA.
    _hex(context["input_sha256"], 64, "parent input SHA256")
    if (
        context["id"] != prediction["id"]
        or not _text(context["id"])
        or not (context["host"] is None or _text(context["host"]))
        or any(
            context[key] != expected[key]
            for key in (
                "sequence",
                "oriented_sequence",
                "normalized_sha256",
                "oriented_sha256",
                "anti_sd",
                "strand",
            )
        )
        or type(context["temperature_c"]) not in (int, float)
        or context["temperature_c"] != request.temperature_c
        or request.start_positions is None
        or len(request.start_positions) != 1
        or not isinstance(context["start_positions"], list)
        or len(context["start_positions"]) != 1
        or type(context["start_positions"][0]) is not int
        or context["start_positions"][0] != request.start_positions[0]
    ):
        raise ValueError("cache parent sequence/settings/explicit start mismatch")
    if len(prediction["sites"]) > 1:
        raise ValueError("cache parent must use exactly one explicit start")
    for site in prediction["sites"]:
        if (
            not isinstance(site, dict)
            or site.keys() != _SITE_FIELDS
            or site["status"] not in _STATUSES
        ):
            raise ValueError("cache parent site must be complete")
        if (
            type(site["oriented_start"]) is not int
            or site["oriented_start"] != request.start_positions[0]
            or site["codon"]
            != request.oriented_sequence[
                request.start_positions[0] : request.start_positions[0] + 3
            ]
        ):
            raise ValueError("cache parent site/start mismatch")
        energies = site["energies"]
        if site["status"] != "ok":
            if energies is not None:
                raise ValueError("unsuccessful cache site requires null energies")
            continue
        # Admit every site's energy contract independently of its parent status.
        if (
            not isinstance(energies, dict)
            or energies.keys() != _ENERGY_NUMBERS | _ENERGY_NULLABLE | {"units"}
            or energies["units"] != "kcal/mol"
        ):
            raise ValueError("cache energy contract requires closed kcal/mol fields")
        for name in sorted(_ENERGY_NUMBERS | _ENERGY_NULLABLE):
            term = energies[name]
            if term is None and name in _ENERGY_NULLABLE:
                continue
            if isinstance(term, bool) or not isinstance(term, (int, float)):
                raise ValueError("successful cache energy features must be finite")
            try:
                finite = math.isfinite(term)
            except OverflowError as exc:
                raise ValueError("successful cache energy exceeds float range") from exc
            if not finite:
                raise ValueError("successful cache energy features must be finite")
    if prediction["status"] == "ok":
        sites = prediction["sites"]
        if len(sites) != 1 or sites[0]["status"] != "ok":
            raise ValueError("successful cache parent site/start mismatch")
    return signature


def infer(
    source: Path,
    model_path: Path,
    *,
    source_sha256: str,
    model_sha256: str,
    code_commit: str,
    cache: Path | None = None,
    cache_sha256: str | None = None,
) -> dict:
    """Admit the whole collection before predicting; retain order and missingness.

    Returns finite JSON-compatible data. Bad pins, wrappers or parent identity
    raise ValueError. Feature coverage and numeric failures remain explicit rows.
    No filesystem writes, backend calls, fitting or calibration occur here.
    """
    _hex(code_commit, 40, "code_commit")
    rows = _rows(_load(source, source_sha256, "source"), INPUT_VERSION)
    requests = _requests(rows)
    model = RidgeModel.from_dict(_load(model_path, model_sha256, "model"))
    domain = validate_model(model)
    kind = model.provenance["feature_kind"]
    parents: dict[str, dict] = {}
    signature = None
    if kind == ENERGY_KIND:
        if cache is None or cache_sha256 is None:
            raise ValueError("energy model requires an exact pinned cache")
        cached = _rows(_load(cache, cache_sha256, "cache"), CACHE_VERSION)
        if any(row.keys() != {"id", "prediction"} for row in cached):
            raise ValueError("cache records have missing or unknown fields")
        parents = {row["id"]: row["prediction"] for row in cached}
        if parents.keys() != requests.keys():
            raise ValueError("cache IDs must exactly cover supported source IDs")
        for identifier, core_prediction in parents.items():
            current = _core(core_prediction, requests[identifier])
            if signature is not None and signature != current:
                raise ValueError("cache mixes model or backend identities")
            signature = current
    elif cache is not None or cache_sha256 is not None:
        raise ValueError("sequence model rejects an energy cache")

    records = []
    for row in rows:
        result: dict[str, Any] = {
            "id": row["id"],
            "status": row["status"],
            "reason": row["reason"],
            "score_log2": None,
            "score": None,
            "features": None,
            "warnings": list(_BASE_WARNINGS),
            "unlearned_feature_changes": [],
            "parent_provenance": None,
            "mechanistic_reference": None,
        }
        records.append(result)
        if row["status"] == "unsupported":
            continue
        request = requests[row["id"]]
        if (
            request.host not in domain["hosts"]
            or request.anti_sd not in domain["anti_sd"]
            or request.temperature_c not in domain["temperatures_c"]
        ):
            result["warnings"].append("outside_declared_training_host_or_settings")
        parent = parents.get(row["id"])
        if parent is not None:
            result["mechanistic_reference"] = parent
            result["parent_provenance"] = {
                "id": parent["id"],
                "prediction_id": parent["prediction_id"],
                "canonical_parent_sha256": canonical_hash(parent),
                "host": parent["input"]["host"],
            }
            if request.host != parent["input"]["host"]:
                result["warnings"].append("host_difference")
            assert signature is not None
            if any(model.provenance[key] != val for key, val in signature.items()):
                result["warnings"].append(
                    "energy_backend_or_model_differs_from_training"
                )
            if parent["status"] != "ok":
                reasons = [parent["reason"], *(s["reason"] for s in parent["sites"])]
                reason = next(
                    (r for r in reasons if _text(r)), "mechanistic_feature_unavailable"
                )
                result.update(status=parent["status"], reason=reason)
                continue
        try:
            values = extract_features(request, kind=kind, prediction=parent)
            result["features"] = {
                "names": list(model.feature_names),
                "values": list(values),
            }
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
            raw = model.predict([values])[0]
            positive = 2.0**raw
            if not math.isfinite(raw) or not math.isfinite(positive) or positive <= 0:
                raise ValueError("learned score exceeds finite positive scale range")
            result.update(status="ok", reason=None, score_log2=raw, score=positive)
        except FeatureError as exc:
            result.update(status="unsupported", reason=str(exc))
        except (ValueError, OverflowError) as exc:
            result.update(status="failed", reason=str(exc))
    output = {
        "schema_version": OUTPUT_VERSION,
        "source_sha256": source_sha256,
        "model_sha256": model_sha256,
        "cache_sha256": cache_sha256,
        "code_commit": code_commit,
        "artifact_sha256": model.to_dict()["artifact_sha256"],
        "feature_kind": kind,
        "rawscore_scale": "log2_assay_response",
        "score_scale": "assay_response",
        "calibration_applied": False,
        "target": {
            "name": model.provenance["target_name"],
            "units": model.provenance["target_units"],
            "training_dataset": model.provenance["dataset_id"],
        },
        "training_domain": domain,
        "training_provenance": dict(model.provenance),
        "records": records,
    }
    output["collection_sha256"] = canonical_hash(output)
    return output


def main(argv=None) -> int:
    """Write only after full admission; print a small summary and explicit exits."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--cache-sha256")
    args = parser.parse_args(argv)
    try:
        for path in (args.source, args.model, args.cache):
            if path is not None and (
                path.resolve() == args.output.resolve()
                or args.output.exists()
                and os.path.samefile(path, args.output)
            ):
                raise ValueError("output must not overwrite an input file")
        result = infer(
            args.source,
            args.model,
            source_sha256=args.source_sha256,
            model_sha256=args.model_sha256,
            code_commit=args.code_commit,
            cache=args.cache,
            cache_sha256=args.cache_sha256,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    except (ValueError, OSError) as exc:
        print(f"rbs-inference: {exc}", file=sys.stderr)
        return 2
    failed = sum(row["status"] != "ok" for row in result["records"])
    print(
        json.dumps(
            {
                "n_records": len(result["records"]),
                "n_unsuccessful": failed,
                "collection_sha256": result["collection_sha256"],
            },
            sort_keys=True,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
