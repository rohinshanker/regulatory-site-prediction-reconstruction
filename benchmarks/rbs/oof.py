"""Independently audit public grouped-development prediction/selection reports."""

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number, summary
from benchmarks.rbs.positional_adapters import unique


def audit(dataset, selection):
    """Recompute submitted OOF metrics, without reading weights or training code."""
    source = unique(dataset["records"])
    identities, groups = selection["record_ids"], selection["groups"]
    if (
        len(identities) != len(source)
        or len(set(identities)) != len(identities)
        or set(identities) != set(source)
        or len(groups) != len(identities)
        or any(
            source[key]["family"] != group
            for key, group in zip(identities, groups, strict=True)
        )
        or selection["n_records"] != len(identities)
        or selection["n_groups"] != len(set(groups))
    ):
        raise ValueError("OOF source identity/family mismatch")
    results = []
    for configuration in selection["configurations"]:
        values = configuration["out_of_fold_log2"]
        if len(values) != len(identities) or any(not finite_number(v) for v in values):
            raise ValueError("Invalid OOF prediction vector")
        rows, errors = [], defaultdict(list)
        for identity, group, value in zip(identities, groups, values, strict=True):
            target = source[identity]["observed"]
            rows.append(
                {
                    "id": identity,
                    "observed": target,
                    "predicted": 2**value,
                    "status": "ok",
                }
            )
            errors[group].append(abs(value - math.log2(target)))
        metrics = summary(rows)
        family_mae = statistics.mean(statistics.mean(v) for v in errors.values())
        if not math.isclose(
            family_mae, configuration["family_mae_log2"], rel_tol=0, abs_tol=1e-12
        ) or not math.isclose(
            metrics["rmse_log2"],
            configuration["row_rmse_log2"],
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError("Reported OOF metric does not reproduce")
        results.append(
            {
                "penalty": configuration["penalty_per_observation"],
                "family_mae_log2": family_mae,
                "metrics": metrics,
            }
        )
    if not results:
        raise ValueError("No submitted OOF configurations")
    selected = min(
        range(len(results)),
        key=lambda i: (
            results[i]["family_mae_log2"],
            results[i]["metrics"]["rmse_log2"],
            -results[i]["penalty"],
        ),
    )
    if (
        type(selection["selected_index"]) is not int
        or selected != selection["selected_index"]
    ):
        raise ValueError("Submitted selection violates the declared metric/tie rule")
    return {
        "n_records": len(identities),
        "n_groups": len(set(groups)),
        "configurations": results,
        "selected_index": selected,
        "scope": (
            "submitted OOF prediction/metric audit, not independent training "
            "or fold-isolation verification"
        ),
    }


def main(argv=None):
    """Pin both public inputs and emit an independently recomputed aggregate."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "selection", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    data, selected = args.dataset.read_bytes(), args.selection.read_bytes()
    result = audit(json.loads(data), json.loads(selected))
    result.update(dataset_sha256=digest(data), selection_sha256=digest(selected))
    write_json(args.output, result)


if __name__ == "__main__":
    main()
