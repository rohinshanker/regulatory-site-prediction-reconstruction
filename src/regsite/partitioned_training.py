"""Train-only ridge fits selected on an explicit independent development partition."""

import math
from collections.abc import Mapping
from statistics import median

from regsite.learning import RidgeModel, fit_ridge
from regsite.training import DEFAULT_PENALTIES, grouped_losses


def fit_partitioned(
    train_rows: list,
    train_log2: list,
    validation_rows: list,
    validation_log2: list,
    *,
    feature_names: tuple[str, ...],
    train_ids: list[str],
    validation_ids: list[str],
    train_groups: list[str],
    validation_groups: list[str],
    provenance: Mapping[str, str],
    penalties: tuple[float, ...] = DEFAULT_PENALTIES,
) -> tuple[RidgeModel, dict]:
    """Select on fixed validation records, retaining train-only weights.

    Apply a median training residual offset only to selection predictions. The
    raw ridge artifact remains unchanged; the returned explicit calibration must
    be frozen and independently reproduced by the evaluator. No validation or
    final data fit scaling, coefficients, intercepts or calibration.
    """
    if (
        not isinstance(penalties, tuple)
        or not 1 <= len(penalties) <= 4
        or any(
            type(v) not in (int, float) or not math.isfinite(v) or v <= 0
            for v in penalties
        )
        or len(set(penalties)) != len(penalties)
    ):
        raise ValueError("penalties must be 1..4 unique finite positive values")
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("data_role") != "development"
    ):
        raise ValueError("partitioned fitting requires development data_role")
    for rows, ids, groups in (
        (train_rows, train_ids, train_groups),
        (validation_rows, validation_ids, validation_groups),
    ):
        if (
            not isinstance(rows, list)
            or not 1 <= len(rows) <= 10000
            or not isinstance(ids, list)
            or not isinstance(groups, list)
            or len(ids) != len(rows)
            or len(groups) != len(rows)
            or any(
                not isinstance(s, str) or not s.strip() or len(s) > 256
                for s in ids + groups
            )
            or len(set(ids)) != len(ids)
        ):
            raise ValueError("partition rows require unique IDs and one group per row")
    if set(train_ids) & set(validation_ids) or set(train_groups) & set(
        validation_groups
    ):
        raise ValueError("training and validation IDs/groups must be disjoint")
    if (
        not isinstance(validation_log2, list)
        or len(validation_log2) != len(validation_rows)
        or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in validation_log2
        )
    ):
        raise ValueError("validation targets must be finite log2 numbers")
    candidates, models = [], []
    for penalty in penalties:
        model = fit_ridge(
            train_rows,
            train_log2,
            feature_names=feature_names,
            record_ids=train_ids,
            penalty=penalty * len(train_rows),
            provenance=provenance,
        )
        offset = median(
            y - p for y, p in zip(train_log2, model.predict(train_rows), strict=True)
        )
        values = [score + offset for score in model.predict(validation_rows)]
        if not math.isfinite(offset) or any(not math.isfinite(p) for p in values):
            raise ValueError("training calibration exceeds finite numeric range")
        # One group computes ordinary row MAE, the predeclared native endpoint.
        mae, rmse = grouped_losses(
            validation_log2, values, ["validation"] * len(values)
        )
        candidates.append(
            {
                "penalty_per_observation": penalty,
                "calibration_log2": offset,
                "validation_mae_log2": mae,
                "validation_rmse_log2": rmse,
                "validation_predictions_log2": values,
            }
        )
        models.append(model)
    selected = min(
        range(len(candidates)),
        key=lambda i: (
            candidates[i]["validation_mae_log2"],
            candidates[i]["validation_rmse_log2"],
            -candidates[i]["penalty_per_observation"],
        ),
    )
    return models[selected], {
        "schema_version": "rbs-partitioned-development-1",
        "data_role": "development",
        "train_ids": list(train_ids),
        "validation_ids": list(validation_ids),
        "train_groups": list(train_groups),
        "validation_groups": list(validation_groups),
        "selected_index": selected,
        "configurations": candidates,
        "selection": "minimum validation row MAE, then RMSE, then stronger penalty",
        "calibration": "median train residual; never refit on validation/final",
        "weights": "train-only; no post-selection refit",
        "dataset_id": provenance["dataset_id"],
    }
