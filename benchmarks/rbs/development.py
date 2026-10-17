"""Release only frozen primary HC development labels; final outcomes stay private."""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.karlsen import assay_value

PARTITIONS = {"development_train", "development_validation", "final"}


def blinded_inputs(inputs_bytes):
    """Remove outcome-correlated workbook order and row numbers from scoring inputs."""
    envelope = deepcopy(json.loads(inputs_bytes))
    envelope["records"] = sorted(envelope["records"], key=lambda row: row["id"])
    for row in envelope["records"]:
        row.pop("source_row", None)
    envelope["source_order_policy"] = (
        "Sorted by input identity; source row numbers withheld because the source "
        "workbook order is outcome-correlated. Evaluator retains full provenance."
    )
    envelope["original_input_envelope_sha256"] = digest(inputs_bytes)
    return envelope


def release(inputs_bytes, outcomes, splits):
    """Check immutable identities before constructing the permitted development view."""
    if digest(inputs_bytes) != splits["input_envelope_sha256"]:
        raise ValueError("Input envelope differs from the frozen split")
    envelope = json.loads(inputs_bytes)
    inputs = {row["id"]: row for row in envelope["records"]}
    assignments = {row["id"]: row for row in splits["records"]}
    if (
        len(inputs) != len(envelope["records"])
        or len(assignments) != len(splits["records"])
        or set(inputs) != set(assignments)
    ):
        raise ValueError("Frozen input identity set mismatch or duplicate")
    seen, hc = set(), {}
    for row in outcomes:
        if (
            row["id"] in seen
            or row["input_id"] not in inputs
            or row["condition"] not in {"HC", "LC"}
        ):
            raise ValueError("Invalid or duplicate private measurement identity")
        seen.add(row["id"])
        if row["condition"] == "HC":
            if row["input_id"] in hc:
                raise ValueError("Multiple HC outcomes for one source input")
            hc[row["input_id"]] = row
    if set(hc) != set(inputs):
        raise ValueError("Missing HC source measurements")
    result = []
    for identity, row in sorted(inputs.items()):
        assignment = assignments[identity]
        if (
            assignment["partition"] not in PARTITIONS
            or assignment["sequence_sha256"] != row["sequence_sha256"]
            or assignment["primary_eligible"] != row["primary_eligible"]
        ):
            raise ValueError("Frozen input metadata differs from source preparation")
        if assignment["partition"] == "final" or not assignment["primary_eligible"]:
            continue
        measurement = assay_value(hc[identity]["observed"])
        result.append(
            {
                "id": identity,
                "source_measurement_id": hc[identity]["id"],
                "study": "Karlsen2018",
                "condition": "HC_minus_5_min",
                "group": assignment["group"],
                "partition": assignment["partition"],
                "sequence": row["sequence"],
                "sequence_sha256": row["sequence_sha256"],
                "start": row["start_position"],
                "observed": measurement["value"],
                "measurement_status": measurement["status"],
                "log_eligible": measurement["log_eligible"],
                "quantity": "relative RPF_RPKM/RNA_RPKM TE proxy",
                "host": row["host"],
                "temperature_celsius": row["temperature_celsius"],
                "anti_sd": row["anti_sd"],
                "warnings": row["warnings"],
                "source_row": row["source_row"],
                "source_file_sha256": row["source_file_sha256"],
            }
        )
    return {
        "schema_version": "native-rbs-development-1",
        "records": result,
        "source": (
            "Karlsen et al.2018, doi:10.1128/mSystems.00126-18; "
            "Figshare10.6084/m9.figshare.6743276.v1 Table S2"
        ),
        "rights": {
            "measurements": "CC-BY-4.0, Karlsen et al. 2018",
            "sequences": "NCBI public sequence records; no blanket CC licence asserted",
        },
        "input_envelope_sha256": digest(inputs_bytes),
        "scope": (
            "Primary chromosome HC only; no final, LC or plasmid outcomes released"
        ),
    }


def main(argv=None):
    """Construct a development-only dataset from a frozen outcome-blind partition."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "private_outcomes", "splits", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--inputs-output", type=Path)
    args = parser.parse_args(argv)
    split_bytes = args.splits.read_bytes()
    result = release(
        args.inputs.read_bytes(),
        json.loads(args.private_outcomes.read_text()),
        json.loads(split_bytes),
    )
    result["split_sha256"] = digest(split_bytes)
    write_json(args.output, result)
    if args.inputs_output is not None:
        write_json(args.inputs_output, blinded_inputs(args.inputs.read_bytes()))
    print(
        json.dumps(
            {
                "n_development": len(result["records"]),
                "split_sha256": result["split_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
