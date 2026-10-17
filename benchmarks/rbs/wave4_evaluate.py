"""Hash-locked aggregate evaluation after all frozen inference collections finish.

No model code is imported. The only measured endpoint read by the join is the
prespecified ordinary observed field; facilitated outcomes are never evaluated.
"""

import argparse
import json
from pathlib import Path

from benchmarks.rbs import wave4_metrics as metrics
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.new_data import public_split, write_new_outputs
from benchmarks.rbs.wave4_collect import (
    checked_bytes,
    control_score,
    encoded,
    normalized,
    request,
    schedule,
)


def common_point(reference, contender, minimum_rows):
    """Descriptive subgroup point only; no interval or extra promotion test."""
    other = metrics.indexed(contender)
    pairs = [
        (r, other[r["id"]])
        for r in reference
        if r["status"] == other[r["id"]]["status"] == "ok" and r["observed"] is not None
    ]
    a = metrics.rho(
        [r["observed"] for r, _ in pairs], [r["predicted"] for r, _ in pairs]
    )
    b = metrics.rho(
        [r["observed"] for r, _ in pairs], [s["predicted"] for _, s in pairs]
    )
    return {
        "n_common_measured": len(pairs),
        "rank_gain": b - a
        if len(pairs) >= minimum_rows and a is not None and b is not None
        else None,
        "interval95": None,
        "role": "descriptive subgroup point only",
    }


def gc_stratum(row):
    """Fixed coding GC bins; no prediction or outcome determines a subgroup."""
    coding = row["sequence"][row["start"] + 3 :]
    value = sum(base in "GC" for base in coding) / len(coding)
    return "low" if value < 0.4 else "middle" if value < 0.6 else "high"


def report(inputs, outcomes, collections, receipt, protocol):
    """Produce aggregate counts, rank uncertainty and one fixed decision."""
    names = {c["id"] for c in receipt["configurations"]}
    if names != collections["records_by_configuration"].keys():
        raise ValueError("Prediction roster differs from frozen receipt")
    joined = {
        name: metrics.join(inputs["records"], outcomes, rows)
        for name, rows in collections["records_by_configuration"].items()
    }
    reference, contender = (receipt["primary"][k] for k in ("reference", "contender"))
    primary = {
        name: [r for r in rows if r["study"] == "Cambray2018"]
        for name, rows in joined.items()
    }
    summaries = {name: metrics.summarize(rows) for name, rows in primary.items()}
    expected = protocol["primary_endpoint"]
    if any(
        s["n_inputs"] != expected["n_inputs"]
        or s["n_observed"] != expected["n_observed"]
        for s in summaries.values()
    ):
        raise ValueError("Primary source denominator changed")
    comparison = metrics.paired(
        primary[reference], primary[contender], protocol["bootstrap"]
    )
    if comparison["n_blocks"] != expected["n_blocks"]:
        raise ValueError("Primary seed-block population changed")
    gate = metrics.advancement(
        comparison,
        summaries[contender],
        protocol["advancement"],
        collections["complete"] and collections["artifacts_unchanged"],
        receipt["software_resource_gates"] is True,
    )
    descriptive = {
        name: metrics.paired(primary[reference], rows, protocol["bootstrap"])
        for name, rows in primary.items()
        if name not in {reference, contender}
    }
    subgroups = {}
    for label in ("low", "middle", "high"):
        selected = {
            name: [r for r in rows if gc_stratum(r) == label]
            for name, rows in primary.items()
        }
        subgroups[label] = {
            "models": {
                name: metrics.summarize(rows) for name, rows in selected.items()
            },
            "primary_pair": common_point(
                selected[reference],
                selected[contender],
                protocol["subgroups"]["minimum_common_rows_to_display_rank_difference"],
            ),
        }
    secondary = {}
    for context in protocol["secondary_endpoints"]["Kuo2020"]:
        selected = {
            name: [
                r for r in rows if r["study"] == "Kuo2020" and r["context"] == context
            ]
            for name, rows in joined.items()
        }
        if any(
            len(rows) != protocol["secondary_endpoints"]["n_inputs_per_context"]
            for rows in selected.values()
        ):
            raise ValueError("Secondary source denominator changed")
        secondary[context] = {
            "role": (
                "exposed secondary, one connected sequence family; "
                "no promotion or independent-family interval"
            ),
            "models": {
                name: metrics.summarize(rows) for name, rows in selected.items()
            },
            "primary_pair": common_point(
                selected[reference],
                selected[contender],
                protocol["subgroups"]["minimum_common_rows_to_display_rank_difference"],
            ),
        }
    return {
        "schema_version": "rbs-wave4-aggregate-1",
        "panel_consumed": True,
        "collection_complete": collections["complete"],
        "artifacts_unchanged": collections["artifacts_unchanged"],
        "primary": {
            "endpoint": "ordinary Cambray protein fluorescence; rank only",
            "models": summaries,
            "contrast": receipt["primary"],
            "comparison": comparison,
            "advancement": gate,
        },
        "descriptive_against_primary_reference": descriptive,
        "descriptive_coding_gc_strata": subgroups,
        "Kuo2020_secondary": secondary,
        "facilitated_cambray_evaluated": False,
        "calibration_fitted": False,
        "outliers_removed": False,
        "scope": (
            "one E. coli local-context study; no native TE, absolute TIR, "
            "hosted parity or universal superiority claim"
        ),
    }


def audit_execution(prediction, row, config, stdout, stderr):
    """Substantiate normalized numbers from raw results or deterministic controls."""
    actual = {k: prediction[k] for k in ("status", "predicted", "reason")}
    execution, exit_code = prediction["execution"], prediction["exit_code"]
    internal = config["kind"] in {"constant", "gc_content"}
    empty = not stdout and not stderr
    if execution == "not_run":
        expected = dict(status="not_run", predicted=None, reason="collection_deadline")
        valid = empty and exit_code is None and prediction["seconds"] == 0
    elif internal:
        expected = dict(
            status="ok", predicted=control_score(row, config["kind"]), reason=""
        )
        valid = execution == "control" and exit_code is None and empty
    elif execution == "returned":
        expected = normalized(stdout, encoded(request(row)))
        valid = type(exit_code) is int and exit_code == 0
    else:
        expected = dict(status="failed", predicted=None, reason=execution)
        if execution == "invalid_output":
            valid = type(exit_code) is int and exit_code == 0
            try:
                normalized(stdout, encoded(request(row)))
            except (ValueError, KeyError, TypeError, OverflowError):
                pass
            else:
                valid = False
        elif execution == "process_start":
            valid = exit_code is None and empty
        elif execution in {"process_exit", "timeout"}:
            valid = type(exit_code) is int and exit_code != 0
            if execution == "timeout":
                expected = dict(
                    status="timeout", predicted=None, reason=prediction["reason"]
                )
                valid = valid and prediction["reason"] in {
                    "record_deadline",
                    "collection_deadline",
                }
        else:
            valid = False
    if not valid or actual != expected:
        raise ValueError(
            "Normalized prediction is inconsistent with execution evidence"
        )


def audit_prediction_receipts(inputs, collection, receipt, directory):
    """Check exact identity joins, request/config hashes and raw per-job evidence."""
    by_model = {
        key: metrics.indexed(rows)
        for key, rows in collection["records_by_configuration"].items()
    }
    source = metrics.indexed(inputs["records"])
    if set(by_model) != {c["id"] for c in receipt["configurations"]} or any(
        rows.keys() != source.keys() for rows in by_model.values()
    ):
        raise ValueError("Collection model/input identity drift")
    # All semantic checks must precede reserved-label access. Null synthetic
    # observations reuse the same join validator without reading any outcomes.
    absent = [{"id": row["id"], "observed": None} for row in inputs["records"]]
    for rows in by_model.values():
        metrics.join(inputs["records"], absent, list(rows.values()))
    for number, (row, config) in enumerate(
        schedule(inputs["records"], receipt["configurations"])
    ):
        prediction = by_model[config["id"]][row["id"]]
        if prediction["input_sha256"] != digest(encoded(request(row))) or prediction[
            "configuration_sha256"
        ] != digest(encoded(config)):
            raise ValueError("Prediction request/configuration hash drift")
        stem = directory / f"job-{number:06d}"
        if stem.with_suffix(".json").read_bytes() != encoded(prediction):
            raise ValueError("Per-job receipt differs from collection")
        evidence = {}
        for suffix in ("stdout", "stderr"):
            evidence[suffix] = checked_bytes(
                {
                    "path": str(stem.with_suffix("." + suffix)),
                    "sha256": prediction[suffix + "_sha256"],
                }
            )
        audit_execution(prediction, row, config, evidence["stdout"], evidence["stderr"])


def evaluate(manifest):
    """Verify every public/private byte identity before the first measured join."""
    protocol_raw = checked_bytes(manifest["protocol"])
    protocol = json.loads(protocol_raw)
    inputs_raw = checked_bytes(manifest["inputs"])
    inputs = json.loads(inputs_raw)
    split_raw = checked_bytes(manifest["split"])
    receipt_raw = checked_bytes(manifest["receipt"])
    receipt = json.loads(receipt_raw)
    collection_raw = checked_bytes(manifest["collection"])
    collection = json.loads(collection_raw)
    if (
        manifest["inputs"]["sha256"] != protocol["input_file_sha256"]
        or manifest["split"]["sha256"] != protocol["split_file_sha256"]
        or public_split(inputs) != json.loads(split_raw)
        or collection["freeze_sha256"] != digest(receipt_raw)
        or collection["protocol_sha256"] != digest(protocol_raw)
        or collection["input_sha256"] != digest(inputs_raw)
        or collection["collector_sha256"] != receipt["collector_sha256"]
        or receipt["protocol"]["sha256"] != digest(protocol_raw)
        or receipt["inputs"]["sha256"] != digest(inputs_raw)
        or receipt["evaluation_authorized"] is not True
        or not all(
            receipt["acknowledgements"].get(who)
            for who in ("A_protocol", "B_candidate")
        )
        or manifest["outcomes"]["sha256"] != protocol["private_outcomes_sha256"]
    ):
        raise ValueError("Evaluation freeze/input/selection identity drift")
    audit_prediction_receipts(
        inputs, collection, receipt, Path(manifest["collection"]["path"]).parent
    )
    # This is the only label load; every model/input/receipt audit precedes it.
    outcomes = json.loads(checked_bytes(manifest["outcomes"]))
    result = report(inputs, outcomes, collection, receipt, protocol)
    result["identities"] = {name: spec["sha256"] for name, spec in manifest.items()}
    result["evaluator_sha256"] = digest(Path(__file__).read_bytes())
    result["metric_code_sha256"] = digest(Path(metrics.__file__).read_bytes())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("new_aggregate", type=Path)
    args = parser.parse_args(argv)
    result = evaluate(json.loads(args.manifest.read_text()))
    write_new_outputs([(args.new_aggregate, result)])
    print(
        json.dumps(
            {
                "advance": result["primary"]["advancement"]["advance"],
                "aggregate_sha256": digest(args.new_aggregate.read_bytes()),
            }
        )
    )


if __name__ == "__main__":
    main()
