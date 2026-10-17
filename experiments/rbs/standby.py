"""Reproduce the two predeclared 2014 development-only ridge ablations."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from regsite.contracts import RbsRequest
from regsite.features import extract_features, feature_names
from regsite.learned import validate_model
from regsite.training import fit_grouped

SOURCE_SHA256 = "d74967eb964f1797138076ed12a35ef5f44c0ac3e87241e5186505503fd698f4"
HOST = "Escherichia coli DH10B (configuration only)"
KINDS = ("sequence-v1", "context-energy-sequence-v1")


def training_requests(records: list[dict]) -> list[RbsRequest]:
    """Use only supplied sequences/starts, with the source's declared host settings."""
    return [
        RbsRequest.from_dict(
            {
                "id": row["id"],
                "sequence": row["sequence"],
                "start_positions": [row["start"]],
                "anti_sd": "ACCUCCUUA",
                "temperature_c": 37,
                "host": HOST,
            }
        )
        for row in records
    ]


def train(
    source: Path, context_predictions: Path, output: Path, code_commit: str
) -> dict:
    """Require exact public data and matching frozen predictions; never drop rows."""
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("2014 development source hash mismatch")
    if not re.fullmatch("[0-9a-f]{40}", code_commit):
        raise ValueError("code_commit must be an exact Git SHA")
    records = json.loads(source_bytes)["records"]
    requests = training_requests(records)
    cached_bytes = context_predictions.read_bytes()
    cached = json.loads(cached_bytes)["results"]
    predictions = {p["id"]: p for p in cached}
    if len(predictions) != len(cached) or set(predictions) != {r.id for r in requests}:
        raise ValueError("prediction cache must cover exactly the development IDs")
    targets = []
    for row in records:
        if (
            type(row["observed"]) not in (int, float)
            or not 0 < row["observed"] < math.inf
        ):
            raise ValueError(
                "development assay responses must be positive finite numbers"
            )
        targets.append(math.log2(row["observed"]))
    provenance = {
        "dataset_id": "standby2014:" + SOURCE_SHA256,
        "split_id": "22-source-families-leave-one-family-out",
        "data_role": "development",
        "data_licence": "CC-BY-3.0; Espah Borujeni et al. 2014 doi:10.1093/nar/gkt1139",
        "target_name": "mean mRFP1 fluorescence (translation proxy)",
        "target_units": "log2 source fluorescence arbitrary units",
        "training_domain": json.dumps(
            {"hosts": [HOST], "anti_sd": ["ACCUCCUUA"], "temperatures_c": [37]}
        ),
        "code_commit": code_commit,
        "context_predictions_sha256": hashlib.sha256(cached_bytes).hexdigest(),
        "feature_recipe": "19 sequence features; optional five context2017 energies",
    }
    results, files = {}, {}
    for kind in KINDS:
        features = [
            extract_features(r, kind=kind, prediction=predictions[r.id])
            for r in requests
        ]
        model, report = fit_grouped(
            features,
            targets,
            feature_names=feature_names(kind),
            record_ids=[r.id for r in requests],
            groups=[r["family"] for r in records],
            provenance={**provenance, "feature_kind": kind},
        )
        validate_model(model)
        artifact = model.to_dict()
        files[f"{kind}.json"] = artifact
        files[f"{kind}-selection.json"] = report
        selected = report["configurations"][report["selected_index"]]
        results[kind] = {
            "artifact_sha256": artifact["artifact_sha256"],
            "selected_penalty_per_observation": selected["penalty_per_observation"],
            "family_mae_log2": selected["family_mae_log2"],
            "row_rmse_log2": selected["row_rmse_log2"],
        }
    output.mkdir(parents=True, exist_ok=True)
    for name, contents in files.items():
        (output / name).write_text(
            json.dumps(contents, indent=2, sort_keys=True) + "\n"
        )
    return {
        "data_role": "development",
        "models": results,
        "warnings": ["not_independent_test_accuracy"],
    }


def main(argv=None):
    """Train from the pinned public data and an independently reproducible cache."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("context_predictions", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args(argv)
    result = train(args.source, args.context_predictions, args.output, args.code_commit)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
