"""Descriptive condition transfer with frozen scores and separate train-only scales."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs import strength
from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.development import PARTITIONS
from benchmarks.rbs.metrics import cluster_mae_interval, finite_number
from benchmarks.rbs.native_evaluation import checked_json
from benchmarks.rbs.positional_adapters import unique


def report(records, models, offsets, conditions, *, repetitions=2000):
    """Evaluate final families per phase; never pool repeated genes as replicates.

    HC-transfer offsets come from the frozen primary training cohort. A separate
    descriptive scale uses only this condition's development-training families.
    Neither changes model weights or selects a contender.
    """
    if (
        not conditions
        or len(set(conditions)) != len(conditions)
        or set(r["condition"] for r in records) != set(conditions)
        or set(models) != set(offsets)
        or not models
        or any(not finite_number(v) for v in offsets.values())
    ):
        raise ValueError("Incomplete fixed condition/model/offset roster")
    cohorts = {
        c: unique([r for r in records if r["condition"] == c]) for c in conditions
    }
    first = cohorts[conditions[0]]
    metadata = {k: (r["partition"], r["group"]) for k, r in first.items()}
    if any(r["partition"] not in PARTITIONS for r in records) or any(
        {k: (r["partition"], r["group"]) for k, r in cohort.items()} != metadata
        for cohort in cohorts.values()
    ):
        raise ValueError("Condition cohorts or frozen family assignments differ")
    group_partitions = {}
    for row in first.values():
        group_partitions.setdefault(row["group"], set()).add(row["partition"])
    if any(len(values) != 1 for values in group_partitions.values()):
        raise ValueError("Frozen homology group crosses partitions")
    inferred = {name: unique(rows) for name, rows in models.items()}
    if any(set(rows) - set(first) for rows in inferred.values()):
        raise ValueError("Prediction outside admitted condition cohort")
    output = {}
    for condition, cohort in cohorts.items():
        train = [r for r in cohort.values() if r["partition"] == "development_train"]
        target = [r for r in cohort.values() if r["partition"] == "final"]
        if not train or not target:
            raise ValueError("Both frozen training and final families required")
        train_ids, final_ids = {r["id"] for r in train}, {r["id"] for r in target}
        values = {}
        for name, prediction in inferred.items():
            fit = strength.fit_intercept(
                train, [r for k, r in prediction.items() if k in train_ids]
            )
            selected = [r for k, r in prediction.items() if k in final_ids]
            values[name] = {"condition_training_calibration": fit}
            for mode, offset in [
                ("frozen_HC_transfer", offsets[name]),
                ("condition_train_intercept", fit["offset_log2"]),
            ]:
                joined, _ = strength.pairs(target, selected, offset)
                values[name][mode] = {
                    **strength.evaluate(target, selected, offset),
                    "descriptive_family_mae_log2_95": cluster_mae_interval(
                        joined, repetitions=repetitions
                    ),
                }
        output[condition] = {
            "n_train": len(train),
            "n_final": len(target),
            "n_final_groups": len({r["group"] for r in target}),
            "models": values,
        }
    return {
        "conditions": output,
        "scope": "secondary descriptive transfer; no model selection or pooled phases",
        "uncertainty_scope": (
            "homology-group sampling; not replicate noise; intervals not simultaneous"
        ),
        "frozen_HC_offsets_log2": offsets,
        "bootstrap_repetitions": repetitions,
        "bootstrap_seed": 20261016,
    }


def main(argv=None):
    """Read a pre-frozen private secondary manifest and write aggregate results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    root = args.manifest.parent
    if manifest["final_roster_frozen"] is not True:
        raise ValueError("Secondary evaluation requires the unified roster freeze")
    output = report(
        checked_json(manifest["cases"], root)["records"],
        {
            name: checked_json(spec, root)["records"]
            for name, spec in manifest["models"].items()
        },
        manifest["frozen_HC_offsets_log2"],
        manifest["conditions"],
        repetitions=manifest["bootstrap_repetitions"],
    )
    output.update(
        manifest_sha256=digest(raw),
        evaluator_sha256=digest(Path(__file__).read_bytes()),
    )
    write_json(args.output, output)


if __name__ == "__main__":
    main()
