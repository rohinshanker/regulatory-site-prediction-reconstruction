"""Normalize public native-result envelopes without inspecting scoring internals."""

import argparse
import json
import math
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.positional_adapters import unique


def learned_predictions(source, prepared_bytes, result, model_sha, artifact_sha):
    """Audit the public cached-inference boundary without reading model features.

    The source is an independently frozen supplied-context table. Prepared input
    rows are checked against it, then exact source/model identities bind outputs.
    No calibration, training implementation or feature arithmetic is imported.
    """
    original = unique(source)
    prepared = unique(json.loads(prepared_bytes)["records"])
    output = unique(result["records"])
    if (
        set(original) != set(prepared)
        or set(original) != set(output)
        or result["source_sha256"] != digest(prepared_bytes)
        or result["model_sha256"] != model_sha
        or result["artifact_sha256"] != artifact_sha
        or result["calibration_applied"] is not False
    ):
        raise ValueError("Learned collection source/model/calibration identity drift")
    predictions = []
    for identity, row in original.items():
        request = prepared[identity]["input"]
        inferred = output[identity]
        status, value = inferred["status"], inferred["score"]
        if status not in {"ok", "failed", "unsupported", "no_candidate"}:
            raise ValueError("Unknown learned collection status")
        if request is not None and (
            request["id"] != identity
            or request["sequence"].replace("U", "T") != row["sequence"]
            or request.get("strand", "+") != "+"
            or request["start_positions"] != [row["start_position"]]
            or request["temperature_c"] != row["temperature_celsius"]
            or request["anti_sd"] != row["anti_sd"]
            or request["host"] != row["host"]
        ):
            raise ValueError("Prepared learned input differs from frozen scenario")
        if status == "ok":
            if (
                request is None
                or prepared[identity]["status"] != "ok"
                or not finite_number(value)
                or value <= 0
                or not finite_number(inferred["score_log2"])
                or not math.isclose(
                    math.log2(value), inferred["score_log2"], rel_tol=0.0, abs_tol=1e-12
                )
            ):
                raise ValueError("Successful learned score lacks valid input/scale")
        elif value is not None or inferred["score_log2"] is not None:
            raise ValueError("Failed learned row must not supply a score")
        predictions.append(
            {
                "id": identity,
                "status": status,
                "predicted": value,
                "reason": inferred["reason"],
                "scenario_verified": request is not None,
            }
        )
    return predictions


def native_predictions(inputs, result):
    """Keep every source row and the wrapper status; verify supplied-start identity."""
    source, output = unique(inputs["records"]), unique(result["results"])
    if result["mode"] != "supplied_start" or set(source) != set(output):
        raise ValueError("Native result mode/identity set differs from supplied inputs")
    predictions = []
    for identity, original in source.items():
        row = output[identity]
        status = row["status"]
        if status not in {
            "ok",
            "failed",
            "unsupported",
            "no_candidate",
            "invalid_input",
        }:
            raise ValueError("Unknown native result status")
        if (
            row["evidence"]["id"] != identity
            or row["evidence"]["sequence_sha256"] != original["sequence_sha256"]
        ):
            raise ValueError("Native result source-evidence identity drift")
        core, value, prediction_id = row["prediction"], None, None
        verified = core is not None and core["input"] is not None
        if core is not None:
            prediction_id = core["prediction_id"]
        if verified:
            request = core["input"]
            if (
                original["sequence"] is None
                or request["oriented_sequence"].replace("U", "T")
                != original["sequence"]
                or request["oriented_sha256"] != digest(request["oriented_sequence"])
                or request["strand"] != "+"
                or request["start_positions"] != [original["start_position"]]
                or request["temperature_c"] != original["temperature_celsius"]
                or request["anti_sd"] != original["anti_sd"]
            ):
                raise ValueError("Native core request differs from frozen scenario")
            sites = core["sites"]
            if len(sites) > 1 or (
                sites and sites[0]["oriented_start"] != original["start_position"]
            ):
                raise ValueError("Native result changed the supplied start")
            if status == "ok":
                if len(sites) != 1 or sites[0]["status"] != "ok":
                    raise ValueError(
                        "Successful native row lacks its successful supplied site"
                    )
                value = sites[0]["tir"]
        if status == "ok" and (not finite_number(value) or value <= 0):
            raise ValueError("Successful native score must be positive and finite")
        predictions.append(
            {
                "id": identity,
                "status": "failed" if status == "invalid_input" else status,
                "predicted": value,
                "source_status": status,
                "source_prediction_id": prediction_id,
                "scenario_verified": verified,
                "reason": row.get("reason"),
            }
        )
    return predictions


def main(argv=None):
    """Reject input/output byte drift before producing a normalized private table."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "predictions", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--prediction-sha256", required=True)
    args = parser.parse_args(argv)
    source, raw = args.inputs.read_bytes(), args.predictions.read_bytes()
    if digest(source) != args.input_sha256 or digest(raw) != args.prediction_sha256:
        raise ValueError("Frozen prediction/input artifact hash mismatch")
    result = json.loads(raw)
    write_json(
        args.output,
        {
            "schema_version": "normalized-native-predictions-1",
            "input_sha256": digest(source),
            "prediction_sha256": digest(raw),
            "adapter_sha256": digest(Path(__file__).read_bytes()),
            "source_execution": result["execution"],
            "records": native_predictions(json.loads(source), result),
        },
    )


if __name__ == "__main__":
    main()
