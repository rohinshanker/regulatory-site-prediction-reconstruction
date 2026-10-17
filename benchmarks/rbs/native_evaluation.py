"""Hash-locked, train-calibrated aggregate reports without model-selection logic."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs import strength
from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.development import PARTITIONS
from benchmarks.rbs.metrics import summary
from benchmarks.rbs.positional_adapters import unique


def native_cases(input_bytes, outcomes, splits, condition="HC"):
    """Admit primary frozen Karlsen cases; never filter on model success."""
    if condition not in {"HC", "LC"}:
        raise ValueError("Unknown source condition")
    if digest(input_bytes) != splits["input_envelope_sha256"]:
        raise ValueError("Frozen source input hash mismatch")
    inputs = unique(json.loads(input_bytes)["records"])
    assignments = unique(splits["records"])
    if set(inputs) != set(assignments):
        raise ValueError("Frozen identity set mismatch")
    unique(outcomes)
    measurements = {}
    for row in outcomes:
        key = (row["input_id"], row["condition"])
        if (
            key in measurements
            or row["input_id"] not in inputs
            or row["condition"] not in {"HC", "LC"}
        ):
            raise ValueError("Invalid source measurement mapping")
        measurements[key] = row["observed"]
    if set(measurements) != {(key, value) for key in inputs for value in ("HC", "LC")}:
        raise ValueError("Incomplete source condition measurements")
    records = []
    for identity, row in sorted(inputs.items()):
        assignment = assignments[identity]
        if (
            assignment["partition"] not in PARTITIONS
            or assignment["sequence_sha256"] != row["sequence_sha256"]
            or assignment["primary_eligible"] != row["primary_eligible"]
        ):
            raise ValueError("Frozen metadata mismatch")
        if not row["primary_eligible"]:
            continue
        records.append(
            {
                "id": identity,
                "observed": measurements[(identity, condition)],
                "group": assignment["group"],
                "partition": assignment["partition"],
                "subgroups": [
                    "start_codon:"
                    + (
                        row["start_codon"]
                        if row["start_codon"] in {"ATG", "GTG", "TTG"}
                        else "other"
                    ),
                    "strand:" + row["strand"],
                    "protein_length:"
                    + (
                        "discrepant"
                        if "source_uniprot_length_differs_from_current_protein"
                        in row["warnings"]
                        else "agreement"
                    ),
                ],
            }
        )
    return records


def _coverage_diagnostics(reference, contender):
    """Describe already joined cases; never select a reference from these values."""
    ref, con = {r["id"]: r for r in reference}, {r["id"]: r for r in contender}
    common = [key for key in ref if ref[key]["status"] == con[key]["status"] == "ok"]
    n_ref = sum(r["status"] == "ok" for r in reference)
    n_con = sum(r["status"] == "ok" for r in contender)
    dropped = n_ref - len(common)
    return {
        "n_all_log_eligible": len(ref),
        "n_historical_success": n_ref,
        "n_contender_success": n_con,
        "n_common_success": len(common),
        "historical_valid_cases_dropped": dropped,
        "historical_common_metrics": summary([ref[key] for key in common]),
        "contender_common_metrics": summary([con[key] for key in common]),
        "reference_selection_coverage_eligible": bool(ref)
        and dropped == 0
        and n_con >= n_ref
        and n_con / len(ref) >= 0.95,
    }


def report(records, models, configuration, stage="development_validation"):
    """Apply fixed calibration and prespecified final contrasts once.

    Model selection and outcome-independent eligibility occur before this API.
    All source labels are retained privately; the return value is aggregate only.
    Final authorization is a recorded roster freeze, not a permission prompt.
    """
    if stage not in {"development_validation", "final"}:
        raise ValueError("Unknown report stage")
    if stage == "final" and configuration.get("final_roster_frozen") is not True:
        raise ValueError("Final evaluation requires a frozen contender roster")
    identities = unique(records)
    if any(row["partition"] not in PARTITIONS for row in records):
        raise ValueError("Unknown frozen partition")
    if not models or any(not isinstance(name, str) or not name for name in models):
        raise ValueError("Nonempty named model roster required")
    roles = [configuration[key] for key in ("champion", "baseline", "upstream")]
    historical = configuration["historical"]
    original_upstream = configuration["original_upstream"]
    constant = configuration["constant"]
    if (
        any(
            name not in models
            for name in [*roles, historical, original_upstream, constant]
        )
        or roles[1] == roles[2]
        or roles[2] == constant
    ):
        raise ValueError(
            "Frozen contrast roles must name available distinct references"
        )
    if (
        len({row["predicted"] for row in models[constant] if row["status"] == "ok"})
        != 1
    ):
        raise ValueError("Declared constant model must have constant successful scores")
    train = [r for r in records if r["partition"] == "development_train"]
    target = [r for r in records if r["partition"] == stage]
    if not target:
        raise ValueError("No cases in the requested frozen partition")
    train_ids, target_ids = {r["id"] for r in train}, {r["id"] for r in target}
    output, joined = {}, {}
    for name, predictions in models.items():
        inferred = unique(predictions)
        if set(inferred) - set(identities):
            raise ValueError("Model prediction outside admitted source identities")
        fit = strength.fit_intercept(
            train, [r for r in predictions if r["id"] in train_ids]
        )
        selected = [r for r in predictions if r["id"] in target_ids]
        output[name] = {
            "calibration": fit,
            "evaluation": strength.evaluate(target, selected, fit["offset_log2"]),
        }
        joined[name], _ = strength.pairs(target, selected, fit["offset_log2"])
    contrasts = {}
    if stage == "final":
        for reference in sorted({*roles[1:], historical, original_upstream}):
            comparison = strength.paired_comparison(
                joined[reference],
                joined[roles[0]],
                repetitions=configuration["bootstrap_repetitions"],
                seed=configuration["bootstrap_seed"],
                confidence=0.975,
                worthwhile_gain=0.2,
            )
            eligible_ids = {r["id"] for r in joined[reference]}
            memberships = {
                r["id"]: r["subgroups"] for r in target if r["id"] in eligible_ids
            }
            subgroups = strength.subgroup_gates(
                joined[reference], joined[roles[0]], memberships
            )
            applicable = [
                r["gate"] for r in subgroups.values() if r["gate"] is not None
            ]
            comparison.update(
                subgroup_results=subgroups,
                subgroup_gate=bool(applicable) and all(applicable),
                confirmatory=reference in roles[1:],
            )
            if reference == constant:
                comparison["spearman_gate"] = None
                comparison["rank_comparison"] = (
                    "not applicable: constant correlation is undefined"
                )
            contrasts[reference] = comparison
        for reference in roles[1:]:
            comparison = contrasts[reference]
            comparison.update(
                historical_coverage_gate=contrasts[historical]["coverage_gate"],
                historical_spearman_gate=contrasts[historical]["spearman_gate"],
                upstream_spearman_gate=contrasts[roles[2]]["spearman_gate"],
            )
            comparison["all_prespecified_gates_pass"] = (
                reference == constant or comparison["spearman_gate"]
            ) and all(
                comparison[key]
                for key in (
                    "coverage_gate",
                    "historical_coverage_gate",
                    "historical_spearman_gate",
                    "upstream_spearman_gate",
                    "statistical_and_practical_gain",
                    "subgroup_gate",
                )
            )
    return {
        "stage": stage,
        "configuration": configuration,
        "n_train": len(train),
        "n_evaluated": len(target),
        "n_evaluation_groups": len({r["group"] for r in target}),
        "models": output,
        "historical_common_case_diagnostics": {
            name: _coverage_diagnostics(joined[historical], rows)
            for name, rows in joined.items()
        },
        "champion_contrasts": {
            name: value for name, value in contrasts.items() if value["confirmatory"]
        },
        "descriptive_champion_contrasts": {
            name: contrasts[name]
            for name in (historical, original_upstream)
            if name in contrasts and not contrasts[name]["confirmatory"]
        },
        "multiplicity": "two prespecified contrasts; individual 97.5% intervals",
        "uncertainty_scope": "homology-group sampling, not biological replicate noise",
    }


def checked_json(specification, root):
    """Read a manifest-pinned local artifact, rejecting any byte drift."""
    raw = (root / specification["path"]).read_bytes()
    if digest(raw) != specification["sha256"]:
        raise ValueError("Evaluation artifact hash mismatch")
    return json.loads(raw)


def main(argv=None):
    """Evaluate a pinned private case/prediction bundle into aggregate JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--stage", choices=("development_validation", "final"), required=True
    )
    args = parser.parse_args(argv)
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    root = args.manifest.parent
    records = checked_json(manifest["cases"], root)["records"]
    models = {
        name: checked_json(specification, root)["records"]
        for name, specification in manifest["models"].items()
    }
    result = report(records, models, manifest["configuration"], args.stage)
    result.update(
        manifest_sha256=digest(raw),
        evaluator_sha256=digest(Path(__file__).read_bytes()),
    )
    write_json(args.output, result)


if __name__ == "__main__":
    main()
