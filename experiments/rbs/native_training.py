"""Frozen Karlsen HC development recipe; never load final assay outcomes.

One invocation fits one frozen feature kind on development-train and selects on
development-validation. Commit arguments assert the caller's clean data/code
checkouts. Partial prediction coverage requires the coordinator's paired-coverage
decision; a successful fit does not establish eligibility or scientific accuracy.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from regsite.contracts import RbsRequest
from regsite.features import FeatureError, extract_features, feature_names
from regsite.learned import validate_model
from regsite.partitioned_training import fit_partitioned
from regsite.provenance import canonical_hash, consistent_energy_signature

SOURCE_SHA256 = "53ba87998de7e3d423fb7d6818db48a1bf93ede98bdb46bb6137b0119cfa39a4"
SPLIT_SHA256 = "d989341afcb3e463112e85134a322086d968a4cea6ad4b9cb4fa8cc893312409"
SOURCE_TOTAL = 2530
COUNTS = {"development_train": 1465, "development_validation": 479}
HOST = "Synechocystis sp. PCC 6803"
KINDS = ("sequence-v1", "context-energy-sequence-v1")
STATUSES = {"ok", "failed", "unsupported", "invalid_input", "no_candidate"}


def _index(rows: object, label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{label} must contain records")
    result = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"].strip()
            or row["id"] in result
        ):
            raise ValueError(f"{label} requires unique nonempty IDs")
        result[row["id"]] = row
    return result


def _pinned(path: Path, expected: str, label: str) -> dict:
    contents = path.read_bytes()
    if hashlib.sha256(contents).hexdigest() != expected:
        raise ValueError(f"{label} hash mismatch against admitted artifact")
    result = json.loads(contents)
    if not isinstance(result, dict):
        raise ValueError(f"{label} must be a JSON object")
    return result


def _development(source: Path, splits: Path) -> tuple[dict, dict, dict]:
    data = _pinned(source, SOURCE_SHA256, "development source")
    frozen = _pinned(splits, SPLIT_SHA256, "split")
    if (
        data.get("schema_version") != "native-rbs-development-1"
        or frozen.get("schema_version") != "native-rbs-splits-1"
        or data.get("split_sha256") != SPLIT_SHA256
        or not isinstance(data.get("input_envelope_sha256"), str)
        or data["input_envelope_sha256"] != frozen.get("input_envelope_sha256")
    ):
        raise ValueError("development source/split provenance mismatch")
    records = _index(data.get("records"), "development source")
    assignments = _index(frozen.get("records"), "split")
    if len(assignments) != SOURCE_TOTAL:
        raise ValueError("split source total mismatch")
    groups: dict[str, str] = {}
    for row in assignments.values():
        group, partition = row.get("group"), row.get("partition")
        if (
            not isinstance(group, str)
            or not group.strip()
            or partition not in {*COUNTS, "final"}
            or type(row.get("primary_eligible")) is not bool
            or group in groups
            and groups[group] != partition
        ):
            raise ValueError("split groups/partitions are invalid or overlap")
        groups[group] = partition
    eligible = {
        key
        for key, row in assignments.items()
        if row["primary_eligible"] and row["partition"] in COUNTS
    }
    if set(records) != eligible or any(
        sum(assignments[key]["partition"] == part for key in eligible) != count
        for part, count in COUNTS.items()
    ):
        raise ValueError("development IDs/partition counts differ from frozen split")
    requests = {}
    for key, row in records.items():
        assignment = assignments[key]
        if (
            row.get("group") != assignment["group"]
            or row.get("partition") != assignment["partition"]
            or not isinstance(row.get("sequence"), str)
            or hashlib.sha256(row["sequence"].encode()).hexdigest()
            != row.get("sequence_sha256")
            or row["sequence_sha256"] != assignment.get("sequence_sha256")
            or row.get("study") != "Karlsen2018"
            or row.get("condition") != "HC_minus_5_min"
            or row.get("measurement_status") != "positive"
            or row.get("log_eligible") is not True
            or row.get("quantity") != "relative RPF_RPKM/RNA_RPKM TE proxy"
            or row.get("host") != HOST
            or type(row.get("temperature_celsius")) not in (int, float)
            or row["temperature_celsius"] != 30
            or row.get("anti_sd") != "ACCUCCUUU"
            or type(row.get("start")) is not int
        ):
            raise ValueError(f"development record identity/settings mismatch: {key}")
        observed = row.get("observed")
        if (
            isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not 0 < observed < math.inf
        ):
            raise ValueError("development TE proxy must be positive finite numbers")
        requests[key] = RbsRequest.from_dict(
            {
                "id": key,
                "sequence": row["sequence"],
                "start_positions": [row["start"]],
                "host": row["host"],
                "temperature_c": row["temperature_celsius"],
                "anti_sd": row["anti_sd"],
            }
        )
    return records, assignments, requests


def _cache(path: Path, expected: str, assignments: dict) -> tuple[dict, dict]:
    envelope = _pinned(path, expected, "energy cache")
    cached = _index(envelope.get("results"), "energy cache")
    if set(cached) != set(assignments):
        raise ValueError("energy cache must cover exactly all frozen source IDs")
    cores = []
    for key, row in cached.items():
        core = row.get("prediction")
        if (
            row.get("status") not in STATUSES
            or row.get("status") == "ok"
            and not isinstance(core, dict)
            or core is not None
            and (
                not isinstance(core, dict)
                or core.get("id") != key
                or core.get("status") != row["status"]
            )
        ):
            raise ValueError(f"energy cache wrapper/core identity mismatch: {key}")
        if core is not None:
            cores.append(core)
    return cached, consistent_energy_signature(cores)


def _matching_context(request: RbsRequest, core: dict) -> None:
    # Native extraction already normalized DNA/T to RNA/U. Raw input hashes may
    # therefore differ legitimately; validate normalized scientific inputs.
    context = core.get("input")
    expected = {
        "sequence": request.sequence,
        "normalized_sha256": request.normalized_sha256,
        "oriented_sequence": request.oriented_sequence,
        "oriented_sha256": request.oriented_sha256,
        "strand": request.strand,
        "anti_sd": request.anti_sd,
        "temperature_c": request.temperature_c,
        "host": request.host,
        "start_positions": list(request.start_positions or ()),
    }
    if not isinstance(context, dict) or any(
        context.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(f"energy cache input/settings mismatch: {request.id}")


def train(
    source: Path,
    splits: Path,
    output: Path,
    code_commit: str,
    data_commit: str,
    *,
    kind: str,
    context_predictions: Path | None = None,
    predictions_sha256: str | None = None,
) -> dict:
    """Validate admission, fit one ablation, and write weights/report after success.

    Energy caches contain the full source input panel but no outcomes. All core
    predictions must share one compatible model/backend identity; only released
    development IDs can enter features, losses, calibration or model selection.
    """
    feature_names(kind)
    for value in (code_commit, data_commit):
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{40}", value):
            raise ValueError("code_commit and data_commit must be exact Git SHAs")
    energy = kind == KINDS[1]
    if energy != (context_predictions is not None and predictions_sha256 is not None):
        raise ValueError("energy kind requires cache path and admitted cache SHA256")
    if not energy and (
        context_predictions is not None or predictions_sha256 is not None
    ):
        raise ValueError("sequence kind does not use an energy cache")
    records, assignments, requests = _development(source, splits)
    cached: dict[str, dict] = {}
    signature: dict[str, str] = {}
    if energy:
        assert context_predictions is not None and predictions_sha256 is not None
        cached, signature = _cache(context_predictions, predictions_sha256, assignments)
    values, failures, selected_cores = {}, [], []
    for key in sorted(records):
        request = requests[key]
        core = cached[key].get("prediction") if energy else None
        if core is not None:
            _matching_context(request, core)
            selected_cores.append(core)
        if energy and cached[key]["status"] != "ok":
            failures.append(
                {
                    "id": key,
                    "partition": records[key]["partition"],
                    "status": cached[key]["status"],
                    "reason": cached[key].get("reason")
                    or "native_prediction_unsuccessful",
                }
            )
            continue
        try:
            values[key] = extract_features(request, kind=kind, prediction=core)
        except FeatureError as exc:
            # An ok cache with mismatching or corrupt features fails admission.
            # Unsupported sequence contexts remain explicit coverage failures.
            if energy:
                raise
            failures.append(
                {
                    "id": key,
                    "partition": records[key]["partition"],
                    "status": "unsupported",
                    "reason": str(exc),
                }
            )
    ids = {
        part: [key for key in sorted(values) if records[key]["partition"] == part]
        for part in COUNTS
    }
    train_ids, validation_ids = ids["development_train"], ids["development_validation"]
    provenance = {
        "dataset_id": "karlsen2018-development:" + SOURCE_SHA256,
        "split_id": SPLIT_SHA256,
        "data_role": "development",
        "data_licence": "CC-BY-4.0; Karlsen et al. 2018 doi:10.1128/mSystems.00126-18; "
        "Figshare doi:10.6084/m9.figshare.6743276.v1 Table S2",
        "sequence_rights": "NCBI public sequence facts; no blanket CC licence asserted",
        "target_name": "Karlsen2018 HC relative RPF_RPKM/RNA_RPKM TE assay proxy",
        "target_units": "log2 relative TE proxy; not an initiation rate",
        "training_domain": json.dumps(
            {
                "hosts": [HOST],
                "anti_sd": ["ACCUCCUUU"],
                "temperatures_c": [30],
            },
            sort_keys=True,
        ),
        "code_commit": code_commit,
        "data_commit": data_commit,
        "feature_kind": kind,
        **signature,
    }
    if energy:
        provenance["context_results_sha256"] = canonical_hash(selected_cores)
    model, report = fit_partitioned(
        [values[key] for key in train_ids],
        [math.log2(records[key]["observed"]) for key in train_ids],
        [values[key] for key in validation_ids],
        [math.log2(records[key]["observed"]) for key in validation_ids],
        feature_names=feature_names(kind),
        train_ids=train_ids,
        validation_ids=validation_ids,
        train_groups=[records[key]["group"] for key in train_ids],
        validation_groups=[records[key]["group"] for key in validation_ids],
        provenance=provenance,
        penalties=(0.01, 0.1, 1.0, 10.0),
    )
    validate_model(model)
    artifact = model.to_dict()
    report.update(
        {
            "artifact_sha256": artifact["artifact_sha256"],
            "feature_kind": kind,
            "source_sha256": SOURCE_SHA256,
            "split_sha256": SPLIT_SHA256,
            "code_commit": code_commit,
            "data_commit": data_commit,
            "declared_source_total": SOURCE_TOTAL,
            "development_total": len(records),
            "failures": failures,
            "excluded_development_ids": [row["id"] for row in failures],
            "excluded_source_records": [
                {
                    "id": key,
                    "partition": row["partition"],
                    "reason": "final_input_only"
                    if row["partition"] == "final"
                    else "nonprimary_input_only",
                    "prediction_status": cached[key]["status"]
                    if energy
                    else "not_requested",
                    "prediction_reason": cached[key].get("reason") if energy else None,
                }
                for key, row in sorted(assignments.items())
                if key not in records
            ],
            "coverage": {
                part: {
                    "eligible": count,
                    "retained": len(ids[part]),
                    "failed": count - len(ids[part]),
                    "fraction": len(ids[part]) / count,
                }
                for part, count in COUNTS.items()
            },
            "warnings": [
                "not_independent_test_accuracy",
                "paired_eligibility_requires_coordinator_decision",
            ],
        }
    )
    if energy:
        report["admitted_cache_sha256"] = predictions_sha256
    # Serialize both before touching output: no files on admission/fitting failure.
    files = {
        f"{kind}.json": json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False),
        f"{kind}-selection.json": json.dumps(
            report, indent=2, sort_keys=True, allow_nan=False
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, contents in files.items():
        (output / name).write_text(contents + "\n", encoding="utf-8")
    return report


def main(argv=None):
    """Fit one admitted native development ablation, with no final evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "splits", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--data-commit", required=True)
    parser.add_argument("--context-predictions", type=Path)
    parser.add_argument("--predictions-sha256")
    args = parser.parse_args(argv)
    try:
        report = train(
            args.source,
            args.splits,
            args.output,
            args.code_commit,
            args.data_commit,
            kind=args.kind,
            context_predictions=args.context_predictions,
            predictions_sha256=args.predictions_sha256,
        )
    except (ValueError, OSError) as exc:
        parser.exit(2, f"native training: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
