"""Bounded development-only grouped selection for transparent ridge models.

Leave-one-group-out validation refits scaling and the intercept inside every
training fold. The selection loss is the mean of group mean absolute log2 errors;
row RMSE and then stronger regularization break exact ties. These are development
selection diagnostics, not an unbiased final-test performance estimate.
"""

import math
import sys
from collections import defaultdict
from collections.abc import Mapping

from regsite.learning import RidgeModel, fit_ridge

DEFAULT_PENALTIES = (0.01, 0.1, 1.0, 10.0)


def grouped_losses(targets: list[float], predictions: list[float], groups: list[str]):
    """Return group-balanced MAE and row RMSE on already validated finite rows."""
    errors: dict[str, list[float]] = defaultdict(list)
    for target, prediction, group in zip(targets, predictions, groups, strict=True):
        errors[group].append(abs(target - prediction))
    try:
        mae = math.fsum(math.fsum(e) / len(e) for e in errors.values()) / len(errors)
        rmse = math.sqrt(
            math.fsum(e * e for values in errors.values() for e in values)
            / len(targets)
        )
    except OverflowError as exc:
        raise ValueError("development loss exceeds finite numeric range") from exc
    if not math.isfinite(mae) or not math.isfinite(rmse):
        raise ValueError("development loss exceeds finite numeric range")
    return mae, rmse


def fit_grouped(
    rows: list,
    responses_log2: list,
    *,
    feature_names: tuple[str, ...],
    record_ids: list[str],
    groups: list[str],
    provenance: Mapping[str, str],
    penalties: tuple[float, ...] = DEFAULT_PENALTIES,
) -> tuple[RidgeModel, dict]:
    """Select at most four per-observation penalties, then fit all development.

    The objective uses sum of squared residuals, so each fit passes lambda times
    its training-row count to fit_ridge. At most 100 groups are permitted. All
    records must be eligible before this function is called; there is no silent
    exclusion, imputation, random row split or final-outcome access.
    """
    if (
        not isinstance(provenance, Mapping)
        or provenance.get("data_role") != "development"
    ):
        raise ValueError("grouped fitting requires explicit development data_role")
    if (
        not isinstance(penalties, tuple)
        or not 1 <= len(penalties) <= 4
        or any(
            type(value) not in (int, float) or not 0 < value <= sys.float_info.max
            for value in penalties
        )
        or len(set(penalties)) != len(penalties)
    ):
        raise ValueError("penalties must be 1..4 unique finite positive values")
    if (
        not isinstance(groups, list)
        or not isinstance(rows, list)
        or len(groups) != len(rows)
        or any(not isinstance(g, str) or not g.strip() or len(g) > 256 for g in groups)
        or not 3 <= len(set(groups)) <= 100
    ):
        raise ValueError("groups require one nonempty label per row and 3..100 groups")
    candidates = []
    models = []
    for penalty in penalties:
        # This also validates every numeric input and ID before any fold is fit.
        model = fit_ridge(
            rows,
            responses_log2,
            feature_names=feature_names,
            record_ids=record_ids,
            penalty=penalty * len(rows),
            provenance=provenance,
        )
        predictions = [0.0] * len(rows)
        for group in sorted(set(groups)):
            train = [i for i, g in enumerate(groups) if g != group]
            test = [i for i, g in enumerate(groups) if g == group]
            fold = fit_ridge(
                [rows[i] for i in train],
                [responses_log2[i] for i in train],
                feature_names=feature_names,
                record_ids=[record_ids[i] for i in train],
                penalty=penalty * len(train),
                provenance={**provenance, "split_id": f"leave-group-out:{group}"},
            )
            for i, score in zip(
                test, fold.predict([rows[i] for i in test]), strict=True
            ):
                predictions[i] = score
        mae, rmse = grouped_losses(responses_log2, predictions, groups)
        candidates.append(
            {
                "penalty_per_observation": penalty,
                "family_mae_log2": mae,
                "row_rmse_log2": rmse,
                "out_of_fold_log2": predictions,
            }
        )
        models.append(model)
    selected = min(
        range(len(candidates)),
        key=lambda i: (
            candidates[i]["family_mae_log2"],
            candidates[i]["row_rmse_log2"],
            -candidates[i]["penalty_per_observation"],
        ),
    )
    return models[selected], {
        "schema_version": "rbs-grouped-development-1",
        "dataset_id": provenance["dataset_id"],
        "data_role": "development",
        "selection": "minimum family MAE, then row RMSE, then stronger penalty",
        "n_records": len(rows),
        "n_groups": len(set(groups)),
        "record_ids": list(record_ids),
        "groups": list(groups),
        "selected_index": selected,
        "configurations": candidates,
        "warnings": ["selection_diagnostics_not_independent_final_test"],
    }
