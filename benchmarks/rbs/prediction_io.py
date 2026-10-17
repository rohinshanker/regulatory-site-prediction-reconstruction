"""Normalize public native-result envelopes without inspecting scoring internals."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.positional_adapters import unique


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
        if core is not None:
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
            prediction_id = core["prediction_id"]
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
