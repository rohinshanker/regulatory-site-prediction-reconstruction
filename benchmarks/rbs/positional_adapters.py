"""Input-only candidate expansion and genomic Prodigal call projection."""

import argparse
import json
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number


def unique(rows):
    """Index a complete identity set, rejecting duplicate or empty identifiers."""
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows) or any(
        not isinstance(key, str) or not key for key in result
    ):
        raise ValueError("Invalid or duplicate identity")
    return result


def expand(queries):
    """Supply every observable candidate to the unchanged strength adapter."""
    unique(queries)
    result = []
    for query in queries:
        starts = query["start_positions"]
        if len(set(starts)) != len(starts) or any(
            type(start) is not int or start < 0 for start in starts
        ):
            raise ValueError("Invalid candidate universe")
        for start in starts:
            result.append(
                {
                    **query,
                    "id": query["id"] + ":candidate:" + str(start),
                    "query_id": query["id"],
                    "start": start,
                }
            )
    return result


def regroup(queries, predictions):
    """Restore query universes without dropping unsuccessful or missing starts."""
    expected = unique(expand(queries))
    supplied = unique(predictions)
    if set(supplied) - set(expected):
        raise ValueError("Unknown candidate prediction")
    output = {row["id"]: {"id": row["id"], "candidates": []} for row in queries}
    for identity, row in expected.items():
        prediction = supplied.get(identity, {})
        status = prediction.get("status", "not_evaluated")
        if status not in {
            "ok",
            "failed",
            "unsupported",
            "no_candidate",
            "not_evaluated",
        }:
            raise ValueError("Unknown candidate status")
        score = prediction.get("predicted") if status == "ok" else None
        if status == "ok" and (not finite_number(score) or score <= 0):
            raise ValueError("Successful supplied-start score must be positive")
        output[row["query_id"]]["candidates"].append(
            {"start": row["start"], "status": status, "score": score}
        )
    return list(output.values())


def parse_prodigal(text, genome_lengths):
    """Read complete GFF CDS calls; exclude partial boundary calls explicitly.

    GFF is one-based inclusive. On minus strand, translated stop's first base is
    low+2 (zero-based) and translated start is high (zero-based).
    """
    calls, partial = {}, 0
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 9 or fields[2] != "CDS":
            raise ValueError("Expected Prodigal nine-field CDS GFF")
        genome, _, _, low, high, _, strand, phase, attributes = fields
        low, high = int(low) - 1, int(high) - 1
        attrs = dict(item.split("=", 1) for item in attributes.split(";") if item)
        if (
            genome not in genome_lengths
            or not 0 <= low <= high < genome_lengths[genome]
            or strand not in {"+", "-"}
            or phase != "0"
            or attrs.get("partial") not in {"00", "01", "10", "11"}
        ):
            raise ValueError("Invalid Prodigal coordinates or complete-call metadata")
        if attrs["partial"] != "00":
            partial += 1
            continue
        if (high - low + 1) % 3:
            raise ValueError("Complete CDS length is not a multiple of three")
        start, stop = (low, high - 2) if strand == "+" else (high, low + 2)
        key = (genome, strand, stop)
        if key in calls:
            raise ValueError("Multiple Prodigal calls for the same terminal stop")
        calls[key] = start
    return calls, partial


def project_prodigal(queries, calls, genome_lengths):
    """Rank the single genome call at a matching stop, with no annotation lookup.

    No same-stop call or a start outside the frozen universe yields unsupported
    candidates, never an all-zero tie that could accidentally count as recovery.
    """
    unique(queries)
    output = []
    for query in queries:
        candidates, selected = [], None
        if query["start_positions"]:
            genome = query["genome_id"]
            key = (
                genome,
                query["genomic_strand"],
                query["genomic_stop_first_zero_based"],
            )
            if key in calls:
                sign = 1 if query["genomic_strand"] == "+" else -1
                selected = (
                    sign * (calls[key] - query["oriented_first_genomic_zero_based"])
                ) % genome_lengths[genome]
            valid = selected in query["start_positions"]
            for start in query["start_positions"]:
                candidates.append(
                    {
                        "start": start,
                        "status": "ok" if valid else "unsupported",
                        "score": int(start == selected) if valid else None,
                    }
                )
        output.append(
            {"id": query["id"], "candidates": candidates, "selected_start": selected}
        )
    return output


def main(argv=None):
    """Expand or regroup an explicitly hashed, input-only candidate panel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("expand", "regroup"))
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--predictions", type=Path)
    args = parser.parse_args(argv)
    raw = args.inputs.read_bytes()
    if digest(raw) != args.input_sha256:
        raise ValueError("Frozen query input hash mismatch")
    queries = json.loads(raw)["records"]
    payload = {"query_input_sha256": digest(raw)}
    if args.operation == "expand":
        if args.predictions is not None:
            parser.error("expand does not read predictions")
        payload["records"] = expand(queries)
    else:
        if args.predictions is None:
            parser.error("regroup requires predictions")
        predictions = args.predictions.read_bytes()
        payload.update(
            prediction_sha256=digest(predictions),
            records=regroup(queries, json.loads(predictions)["records"]),
        )
    write_json(args.output, payload)


if __name__ == "__main__":
    main()
