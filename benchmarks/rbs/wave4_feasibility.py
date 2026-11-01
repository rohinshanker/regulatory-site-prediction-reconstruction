"""Reproduce outcome-free resampling feasibility on the frozen input grouping."""

import argparse
import json
import random
from pathlib import Path

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.new_data import write_new_outputs
from benchmarks.rbs.wave4_metrics import advancement, join, paired, summarize


def simulate(inputs, protocol):
    """Use invented labels/noise only; this is not a biological power estimate."""
    source = sorted(
        (r for r in inputs["records"] if r["study"] == "Cambray2018"),
        key=lambda r: r["id"],
    )
    rng = random.Random(42026018)
    latent = {key: rng.gauss(0, 1) for key in sorted({r["group"] for r in source})}
    labels, baseline = [], []
    contenders = {
        name: []
        for name in (
            "identical",
            "constant",
            "small_noise_reduction",
            "large_noise_reduction",
        )
    }
    for index, row in enumerate(source):
        y = latent[row["group"]] + rng.gauss(0, 0.5)
        noise = rng.gauss(0, 1)
        labels.append({"id": row["id"], "observed": None if index < 3 else y})
        pred = {
            "id": row["id"],
            "status": "ok",
            "predicted": y + 1.5 * noise,
            "seconds": 0,
            "reason": "",
        }
        baseline.append(pred)
        for name, value in (
            ("identical", pred["predicted"]),
            ("constant", 1),
            ("small_noise_reduction", y + 1.3 * noise),
            ("large_noise_reduction", y + 0.5 * noise),
        ):
            contenders[name].append({**pred, "predicted": value})
    reference = join(source, labels, baseline)
    result = {}
    for name, predictions in contenders.items():
        rows = join(source, labels, predictions)
        comparison = paired(reference, rows, protocol["bootstrap"])
        result[name] = {
            "comparison": comparison,
            "gate": advancement(
                comparison, summarize(rows), protocol["advancement"], True, True
            ),
        }
    return {
        "schema_version": "rbs-wave4-synthetic-feasibility-1",
        "uses_experimental_labels": False,
        "generation_seed": 42026018,
        "n_inputs": len(source),
        "n_blocks": len(latent),
        "missing_rule": (
            "first three sorted input IDs, synthetic only; not source missingness"
        ),
        "interpretation": (
            "fixed invented correlated-noise scenarios demonstrate computable "
            "bounds/undefined cases, not measured biological power or a noise ceiling"
        ),
        "protocol_sha256": digest(json.dumps(protocol, sort_keys=True)),
        "results": result,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "protocol", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    raw = args.inputs.read_bytes()
    protocol = json.loads(args.protocol.read_text())
    if digest(raw) != protocol["input_file_sha256"]:
        raise ValueError("Frozen input hash mismatch")
    result = simulate(json.loads(raw), protocol)
    write_new_outputs([(args.output, result)])


if __name__ == "__main__":
    main()
