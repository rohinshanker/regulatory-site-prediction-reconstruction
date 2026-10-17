"""Three fixed development diagnostics for an already selected native model.

No selection, final outcomes, full-size refit or new weights. Expected SHA256s
admit exact model/report/cache bytes; they are caller assertions, not signatures.
Run from the clean code commit supplied by the caller. Scientific execution
requires a separately approved protocol budget; synthetic tests do not spend it.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import median
from typing import Any

from experiments.rbs import native_training as native
from regsite.features import FeatureError, extract_features, feature_names
from regsite.learned import validate_model
from regsite.learning import RidgeModel
from regsite.partitioned_training import fit_partitioned
from regsite.provenance import canonical_hash
from regsite.training import DEFAULT_PENALTIES, grouped_losses

GROUP_PREFIX = "wave2-learning-curve-20261017:"
FRACTIONS = (0.25, 0.5, 0.75)


def _hex(value: object, length: int, label: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        raise ValueError(f"{label} must be an exact lowercase {length}-digit digest")


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and -math.inf < value < math.inf
    )


def _features(records, requests, cached, kind):
    """Reproduce native admission, including its explicit unsupported exclusions."""
    values, failures, cores = {}, [], []
    energy = kind == native.KINDS[1]
    for key in sorted(records):
        core = cached[key].get("prediction") if energy else None
        if core is not None:
            native._matching_context(requests[key], core)
            cores.append(core)
        if energy and cached[key]["status"] != "ok":
            status = cached[key]["status"]
            reason = cached[key].get("reason") or "native_prediction_unsuccessful"
        else:
            try:
                values[key] = extract_features(
                    requests[key], kind=kind, prediction=core
                )
                continue
            except FeatureError as exc:
                if energy:
                    raise
                status, reason = "unsupported", str(exc)
        failures.append(
            {
                "id": key,
                "partition": records[key]["partition"],
                "status": status,
                "reason": reason,
            }
        )
    return values, failures, cores


def _verify_selection(model, report, records, values, failures, kind, signature, cores):
    """Verify identities and reproduce selected scores without another fit."""
    provenance = model.provenance
    expected = {
        "dataset_id": "karlsen2018-development:" + native.SOURCE_SHA256,
        "split_id": native.SPLIT_SHA256,
        "data_role": "development",
        "feature_kind": kind,
        "target_name": "Karlsen2018 HC relative RPF_RPKM/RNA_RPKM TE assay proxy",
        "target_units": "log2 relative TE proxy; not an initiation rate",
        **signature,
    }
    if kind == native.KINDS[1]:
        expected["context_results_sha256"] = canonical_hash(cores)
    elif any(key.startswith(("energy_", "context_")) for key in provenance):
        raise ValueError("sequence model contains unexpected energy provenance")
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError("selected model data/feature/cache provenance mismatch")
    domain = validate_model(model)
    if domain != {
        "hosts": [native.HOST],
        "anti_sd": ["ACCUCCUUU"],
        "temperatures_c": [30],
    }:
        raise ValueError("selected model training domain mismatch")
    for key in ("code_commit", "data_commit"):
        _hex(provenance.get(key), 40, key)
    ids = {
        part: [key for key in sorted(values) if records[key]["partition"] == part]
        for part in native.COUNTS
    }
    train_ids, validation_ids = ids["development_train"], ids["development_validation"]
    if not train_ids or not validation_ids:
        raise ValueError(
            "selected cohort requires nonempty train/validation partitions"
        )
    artifact_sha = model.to_dict()["artifact_sha256"]
    expected_report = {
        "schema_version": "rbs-partitioned-development-1",
        "dataset_id": expected["dataset_id"],
        "data_role": "development",
        "source_sha256": native.SOURCE_SHA256,
        "split_sha256": native.SPLIT_SHA256,
        "feature_kind": kind,
        "code_commit": provenance["code_commit"],
        "data_commit": provenance["data_commit"],
        "artifact_sha256": artifact_sha,
        "selected_artifact_sha256": artifact_sha,
        "train_ids": train_ids,
        "validation_ids": validation_ids,
        "train_groups": [records[key]["group"] for key in train_ids],
        "validation_groups": [records[key]["group"] for key in validation_ids],
        "declared_source_total": native.SOURCE_TOTAL,
        "development_total": len(records),
        "failures": failures,
        "excluded_development_ids": [row["id"] for row in failures],
        "coverage": {
            part: {
                "eligible": count,
                "retained": len(ids[part]),
                "failed": count - len(ids[part]),
                "fraction": len(ids[part]) / count,
            }
            for part, count in native.COUNTS.items()
        },
        "weights": "train-only; no post-selection refit",
        "calibration": "median train residual; never refit on validation/final",
        "selection": "minimum validation row MAE, then RMSE, then stronger penalty",
    }
    if any(report.get(key) != value for key, value in expected_report.items()):
        raise ValueError("selection report identity/cohort/exclusions mismatch")
    configurations = report.get("configurations")
    selected = report.get("selected_index")
    if (
        not isinstance(configurations, list)
        or len(configurations) != 4
        or type(selected) is not int
        or not 0 <= selected < 4
    ):
        raise ValueError("selection report requires the original four configurations")
    targets = [math.log2(records[key]["observed"]) for key in validation_ids]
    for config, penalty in zip(configurations, DEFAULT_PENALTIES, strict=True):
        if not isinstance(config, dict):
            raise ValueError("invalid selection configuration")
        predictions = config.get("validation_predictions_log2")
        if (
            not _finite(config.get("penalty_per_observation"))
            or config["penalty_per_observation"] != penalty
            or not _finite(config.get("calibration_log2"))
            or not isinstance(predictions, list)
            or len(predictions) != len(targets)
            or not all(_finite(value) for value in predictions)
        ):
            raise ValueError("invalid selection penalty/calibration/predictions")
        mae, rmse = grouped_losses(targets, predictions, ["validation"] * len(targets))
        if (
            not _finite(config.get("validation_mae_log2"))
            or not _finite(config.get("validation_rmse_log2"))
            or config["validation_mae_log2"] != mae
            or config["validation_rmse_log2"] != rmse
        ):
            raise ValueError("selection report losses disagree with predictions")
    if selected != min(
        range(4),
        key=lambda i: (
            configurations[i]["validation_mae_log2"],
            configurations[i]["validation_rmse_log2"],
            -configurations[i]["penalty_per_observation"],
        ),
    ):
        raise ValueError("selection report selected_index disagrees with its rule")
    chosen = configurations[selected]
    if model.penalty != chosen["penalty_per_observation"] * len(train_ids):
        raise ValueError("selected model penalty disagrees with selection report")
    # This mirrors fit_ridge's public input-fingerprint contract, without fitting.
    fingerprint = canonical_hash(
        {
            "version": model.version,
            "rows": [[float(v) for v in values[key]] for key in train_ids],
            "responses_log2": [
                math.log2(records[key]["observed"]) for key in train_ids
            ],
            "feature_names": model.feature_names,
            "record_ids": train_ids,
            "penalty": model.penalty,
            "provenance": dict(provenance),
        }
    )
    if model.training_sha256 != fingerprint:
        raise ValueError("selected model training fingerprint mismatch")
    offset = median(
        math.log2(records[key]["observed"]) - prediction
        for key, prediction in zip(
            train_ids, model.predict([values[key] for key in train_ids]), strict=True
        )
    )
    predictions = [
        value + offset
        for value in model.predict([values[key] for key in validation_ids])
    ]
    if (
        not _finite(report.get("selected_calibration_log2"))
        or report["selected_calibration_log2"] != offset
        or chosen["calibration_log2"] != offset
        or chosen["validation_predictions_log2"] != predictions
    ):
        raise ValueError("selected model calibration/predictions disagree with report")
    return train_ids, validation_ids, chosen


def diagnose(
    source: Path,
    splits: Path,
    model_path: Path,
    selection: Path,
    output: Path,
    *,
    kind: str,
    model_sha256: str,
    selection_sha256: str,
    code_commit: str,
    context_predictions: Path | None = None,
    predictions_sha256: str | None = None,
) -> dict:
    """Admit all inputs, fit exactly three nested subsets, then write one JSON."""
    feature_names(kind)
    _hex(code_commit, 40, "diagnostic code_commit")
    _hex(model_sha256, 64, "model SHA256")
    _hex(selection_sha256, 64, "selection SHA256")
    energy = kind == native.KINDS[1]
    if energy:
        _hex(predictions_sha256, 64, "energy cache SHA256")
        if context_predictions is None:
            raise ValueError("energy kind requires an admitted cache path")
    elif context_predictions is not None or predictions_sha256 is not None:
        raise ValueError("sequence kind does not use an energy cache")
    inputs = [source, splits, model_path, selection]
    if context_predictions is not None:
        inputs.append(context_predictions)
    if output.resolve() in {path.resolve() for path in inputs}:
        raise ValueError("diagnostic output must not overwrite admitted inputs")
    model = RidgeModel.from_dict(native._pinned(model_path, model_sha256, "model"))
    report = native._pinned(selection, selection_sha256, "selection report")
    records, assignments, requests = native._development(source, splits)
    cached: dict[str, dict] = {}
    signature: dict[str, str] = {}
    if energy:
        assert context_predictions is not None and predictions_sha256 is not None
        cached, signature = native._cache(
            context_predictions, predictions_sha256, assignments
        )
        if report.get("admitted_cache_sha256") != predictions_sha256:
            raise ValueError("selection report admitted cache mismatch")
    elif "admitted_cache_sha256" in report:
        raise ValueError("sequence report contains unexpected cache provenance")
    values, failures, cores = _features(records, requests, cached, kind)
    train_ids, validation_ids, chosen = _verify_selection(
        model, report, records, values, failures, kind, signature, cores
    )
    groups = sorted(
        {records[key]["group"] for key in train_ids},
        key=lambda group: (
            hashlib.sha256((GROUP_PREFIX + group).encode()).hexdigest(),
            group,
        ),
    )
    if len(groups) < 4:
        raise ValueError(
            "learning curve requires at least four admitted training groups"
        )
    result: dict[str, Any] = {
        "schema_version": "rbs-native-learning-curve-1",
        "data_role": "development",
        "feature_kind": kind,
        "diagnostic_code_commit": code_commit,
        "selected_model_sha256": model_sha256,
        "selection_report_sha256": selection_sha256,
        "selected_artifact_sha256": model.to_dict()["artifact_sha256"],
        "selected_provenance": dict(model.provenance),
        "source_sha256": native.SOURCE_SHA256,
        "split_sha256": native.SPLIT_SHA256,
        "group_order_prefix": GROUP_PREFIX,
        "ordered_training_groups": groups,
        "train_ids": train_ids,
        "validation_ids": validation_ids,
        "validation_groups": report["validation_groups"],
        "excluded_development_ids": report["excluded_development_ids"],
        "failures": failures,
        "coverage": report["coverage"],
        "penalty_per_observation": chosen["penalty_per_observation"],
        "full_training_reference": {
            "source": "verified selection report; no refit",
            "row_count": len(train_ids),
            "group_count": len(groups),
            **chosen,
        },
        "points": [],
        "warnings": [
            "one_deterministic_subsampling_curve",
            "not_independent_test_accuracy",
            "not_new_model_selection",
            "no_new_finalist_or_weights",
        ],
    }
    if energy:
        result["admitted_cache_sha256"] = predictions_sha256
    for fraction in FRACTIONS:
        subset_groups = groups[: max(1, math.floor(fraction * len(groups)))]
        admitted_groups = set(subset_groups)
        subset_ids = [
            key for key in train_ids if records[key]["group"] in admitted_groups
        ]
        _, diagnostic = fit_partitioned(
            [values[key] for key in subset_ids],
            [math.log2(records[key]["observed"]) for key in subset_ids],
            [values[key] for key in validation_ids],
            [math.log2(records[key]["observed"]) for key in validation_ids],
            feature_names=feature_names(kind),
            train_ids=subset_ids,
            validation_ids=validation_ids,
            train_groups=[records[key]["group"] for key in subset_ids],
            validation_groups=report["validation_groups"],
            provenance=model.provenance,
            penalties=(chosen["penalty_per_observation"],),
        )
        result["points"].append(
            {
                "fraction": fraction,
                "row_count": len(subset_ids),
                "group_count": len(subset_groups),
                "train_ids": subset_ids,
                "train_groups": subset_groups,
                **diagnostic["configurations"][0],
            }
        )
    contents = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(contents, encoding="utf-8")
    return result


def main(argv=None):
    """Write a diagnostic only; admission or fitting errors exit 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "splits", "model_path", "selection", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--kind", choices=native.KINDS, required=True)
    for name in ("model-sha256", "selection-sha256", "code-commit"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--context-predictions", type=Path)
    parser.add_argument("--predictions-sha256")
    args = parser.parse_args(argv)
    try:
        report = diagnose(**vars(args))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"native learning curve: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
