"""Reuse fixed upstream predictions only for exactly matching supplied scenarios."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.positional_adapters import unique


def scenario(row, *, strand_is_genomic=False):
    """Canonical input-only key; host spelling is provenance, never a predictor."""
    sequence = row["sequence"]
    if sequence is None:
        return None
    start, temperature = row["start_position"], row["temperature_celsius"]
    if (
        digest(sequence) != row["sequence_sha256"]
        or row["strand"] not in ({"+", "-"} if strand_is_genomic else {"+"})
        or type(start) is not int
        or not 0 <= start <= len(sequence) - 3
        or not finite_number(temperature)
        or not isinstance(row["anti_sd"], str)
        or not row["anti_sd"]
    ):
        raise ValueError("Invalid supplied scenario identity")
    return sequence, start, row["anti_sd"], temperature


def plan(targets, parents):
    """Choose lexicographically first exact parent before reading any scores.

    Karlsen native-rbs-evidence-1 sequences are already transcript-oriented;
    their strand field is genomic provenance, as its source contract specifies.
    Diurnal v2 moves genomic provenance into a separate field and uses strand+.
    """
    unique(targets)
    parent_index = unique(parents)
    by_scenario = {}
    for identity in sorted(parent_index):
        key = scenario(parent_index[identity], strand_is_genomic=True)
        if key is not None:
            by_scenario.setdefault(key, identity)
    mapping, new = [], []
    for row in targets:
        key = scenario(row)
        kind, parent = "unsupported", None
        if row["primary_eligible"] and key is not None:
            parent = by_scenario.get(key)
            kind = "reused" if parent is not None else "new"
            if kind == "new":
                new.append(row)
        mapping.append({"id": row["id"], "kind": kind, "parent_id": parent})
    return mapping, new


def combine(targets, parents, old_predictions, new_predictions):
    """Keep failures and parent metadata; never prefer a successful tied parent."""
    mapping, new = plan(targets, parents)
    old, fresh = unique(old_predictions), unique(new_predictions)
    parent_index, target_index = unique(parents), unique(targets)
    if set(old) != set(parent_index) or set(fresh) != {row["id"] for row in new}:
        raise ValueError("Prediction identities differ from planned source sets")
    results = []
    for row in mapping:
        identity, parent, kind = row["id"], row["parent_id"], row["kind"]
        if kind == "unsupported":
            result = {
                "status": "unsupported",
                "predicted": None,
                "reason": "Outside admitted primary diurnal context cohort",
            }
        else:
            result = dict(old[parent] if kind == "reused" else fresh[identity])
        results.append(
            {
                **result,
                "id": identity,
                "context_reuse": {
                    **row,
                    "original_host": parent_index[parent]["host"] if parent else None,
                    "target_host": target_index[identity]["host"],
                    "parent_score_selection": (
                        "lexicographic ID before reading predictions"
                    ),
                },
            }
        )
    return results


def main(argv=None):
    """Prepare novel-only inputs or combine hash-pinned upstream output envelopes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "combine"))
    for name in ("targets", "parents", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--target-sha256", required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--parent-predictions", type=Path)
    parser.add_argument("--new-predictions", type=Path)
    parser.add_argument("--parent-prediction-sha256")
    parser.add_argument("--new-prediction-sha256")
    args = parser.parse_args(argv)
    target_raw, parent_raw = args.targets.read_bytes(), args.parents.read_bytes()
    if (
        digest(target_raw) != args.target_sha256
        or digest(parent_raw) != args.parent_sha256
    ):
        raise ValueError("Frozen source input hash mismatch")
    targets, parents = (
        json.loads(target_raw)["records"],
        json.loads(parent_raw)["records"],
    )
    mapping, new = plan(targets, parents)
    prepared = {
        "schema_version": "context-reuse-inputs-1",
        "records": new,
        "target_sha256": digest(target_raw),
        "parent_sha256": digest(parent_raw),
    }
    if args.operation == "prepare":
        if any(
            value is not None
            for value in (
                args.parent_predictions,
                args.new_predictions,
                args.parent_prediction_sha256,
                args.new_prediction_sha256,
            )
        ):
            parser.error("prepare does not accept predictions")
        write_json(args.output, prepared)
        return
    if any(
        value is None
        for value in (
            args.parent_predictions,
            args.new_predictions,
            args.parent_prediction_sha256,
            args.new_prediction_sha256,
        )
    ):
        parser.error("combine requires both prediction files and frozen SHA-256 pins")
    old_raw, new_raw = (
        args.parent_predictions.read_bytes(),
        args.new_predictions.read_bytes(),
    )
    if (
        digest(old_raw) != args.parent_prediction_sha256
        or digest(new_raw) != args.new_prediction_sha256
    ):
        raise ValueError("Frozen upstream prediction hash mismatch")
    old, fresh = json.loads(old_raw), json.loads(new_raw)
    prepared_raw = (
        json.dumps(prepared, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    if (
        old["input_sha256"] != digest(parent_raw)
        or fresh["input_sha256"] != digest(prepared_raw)
        or old["model"] != fresh["model"]
        or old["adapter_sha256"] != fresh["adapter_sha256"]
        or old["upstream_artifacts"] != fresh["upstream_artifacts"]
    ):
        raise ValueError("Upstream source/model/adapter drift")
    write_json(
        args.output,
        {
            "schema_version": "reused-upstream-predictions-1",
            "model": old["model"],
            "input_sha256": digest(target_raw),
            "parent_input_sha256": digest(parent_raw),
            "parent_predictions_sha256": digest(old_raw),
            "new_predictions_sha256": digest(new_raw),
            "reuse_adapter_sha256": digest(Path(__file__).read_bytes()),
            "upstream_artifacts": old["upstream_artifacts"],
            "mapping": mapping,
            "records": combine(targets, parents, old["records"], fresh["records"]),
        },
    )


if __name__ == "__main__":
    main()
