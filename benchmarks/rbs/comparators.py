"""Optional, pinned upstream inference adapters; no runtime model reimplementation."""

import argparse
import importlib.metadata
import importlib.util
import json
import math
import time
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number

REBECA_FILES = {
    "model/sequence_model.py": (
        "eeadfd15c67aeb492287d3b9fed8ce0c232eb4c37f72e3e7a32a47d85f1d9444"
    ),
    "data/dataset.py": (
        "882a98300eea06e68a7a255fb5e15f1c7d4663103d52935575d5cf7c5ad5e518"
    ),
    "experiments/exp_67_true/config.yml": (
        "7a51403d34ee04650a5afa801972f10e066307cf1cbc244118812967fb92308c"
    ),
    "experiments/exp_67_true/best_model_124605_seed_3.pth": (
        "5b17912c6a177db87dfc5008ecebb6c13c2095747748eface1fc72fa46b43b9b"
    ),
}


def verify_files(root, pins):
    """Reject any drift in external upstream code, configuration or weights."""
    for name, expected in pins.items():
        if digest((Path(root) / name).read_bytes()) != expected:
            raise ValueError("Upstream artifact hash mismatch: " + name)


def load_module(name, path):
    """Import only an explicitly pinned source path, without editing upstream code."""
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def rebeca_engine(root):
    """Load the deposited scalar exp67 checkpoint using its unchanged architecture."""
    import pandas as pd
    import torch
    import yaml

    root = Path(root)
    verify_files(root, REBECA_FILES)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(3)
    config = yaml.safe_load((root / "experiments/exp_67_true/config.yml").read_text())
    architecture = load_module("pinned_rebeca_model", root / "model/sequence_model.py")
    encoding = load_module("pinned_rebeca_data", root / "data/dataset.py")
    model = getattr(architecture, config["architecture"]["name"])(
        **config["param_architecture"]
    )
    state = torch.load(
        root / "experiments/exp_67_true/best_model_124605_seed_3.pth",
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(state, strict=True)
    model.eval()

    def infer(utr):
        frame = pd.DataFrame({"UTR": [utr], "unused_target": [float("nan")]})
        dataset = getattr(encoding, config["dataset"])(
            utr_max_length=30, df_given=frame
        )
        tensor, _, _ = dataset[0]
        with torch.inference_mode():
            output = model(tensor.unsqueeze(0))
        if tuple(output.shape) != (1, 1):
            raise ValueError("Unexpected upstream scalar output shape")
        return float(output.item())

    return infer


def ostir_engine():
    """Use the released library; its API fixes folding temperature at 37°C."""
    if (
        importlib.metadata.version("OSTIR") != "1.1.3"
        or importlib.metadata.version("ViennaRNA") != "2.7.2"
    ):
        raise ValueError("Optional OSTIR/ViennaRNA versions differ from the smoke")
    pins = json.loads(Path(__file__).with_name("comparator-artifacts.json").read_text())
    distribution = importlib.metadata.distribution("OSTIR")
    verify_files(distribution.locate_file(""), pins["OSTIR"]["files"])
    from ostir import run_ostir

    return run_ostir


def supplied_input(row):
    """Admit explicit DNA/RNA sequence/start only; no hidden coordinate repair."""
    sequence = row.get("sequence")
    start = row.get("start", row.get("start_position"))
    if (
        not isinstance(sequence, str)
        or not sequence
        or type(start) is not int
        or not 0 <= start <= len(sequence) - 3
    ):
        raise ValueError("Missing or invalid supplied sequence/start")
    sequence = sequence.upper().replace("U", "T")
    if set(sequence) - set("ACGT"):
        raise ValueError("Ambiguous sequence is unsupported by upstream encoders")
    return sequence, start


def predict(row, name, engine):
    """Preserve upstream units and failures; never substitute a fallback model."""
    if name not in {"rebeca", "ostir"}:
        raise ValueError("Unknown upstream comparator")
    result = {"id": row["id"], "status": "unsupported", "predicted": None}
    try:
        sequence, start = supplied_input(row)
    except ValueError as error:
        return {**result, "reason": str(error)}
    try:
        if name == "rebeca":
            native = engine(sequence[:start])
            if not finite_number(native):
                raise ValueError("Nonfinite upstream log-fluorescence")
            value = math.exp(native)
            result.update(
                native_output=native,
                native_unit="mean_ln_fluorescence",
                predicted_unit="exp_mean_ln_fluorescence",
                preprocessing=(
                    "upstream last30 UTR excluding start; "
                    "short inputs right padded with zero-encoded Z"
                ),
                temperature_mode="not an input feature",
            )
        else:
            asd = row.get("anti_sd")
            if (
                not isinstance(asd, str)
                or len(asd) != 9
                or set(asd.upper()) - set("ACGTU")
            ):
                raise ValueError("Invalid nine-base anti-SD")
            requested = row.get("temperature_celsius", row.get("temperature_c"))
            if (requested is not None and not finite_number(requested)) or (
                "temperature_celsius" in row
                and "temperature_c" in row
                and row["temperature_celsius"] != row["temperature_c"]
            ):
                raise ValueError(
                    "Invalid or conflicting requested temperature metadata"
                )
            output = engine(
                sequence,
                start=start + 1,
                end=start + 1,
                name=row["id"],
                aSD=asd,
                threads=1,
                decimal_places=8,
                circular=False,
            )
            if not output:
                return {
                    **result,
                    "status": "no_candidate",
                    "reason": "Upstream returned no supplied-start candidate",
                }
            if len(output) != 1 or output[0]["start_position"] != start + 1:
                raise ValueError("Upstream candidate does not match supplied start")
            value = output[0]["expression"]
            result.update(
                native_output=output[0],
                predicted_unit="upstream_relative_expression",
                temperature_celsius=37.0,
                requested_temperature_celsius=requested,
                anti_sd=asd.upper().replace("T", "U"),
                temperature_mode="upstream API fixed37C",
            )
        if not finite_number(value) or value <= 0:
            raise ValueError("Upstream score must be positive and finite")
        result.update(status="ok", predicted=value)
    except (ValueError, KeyError, RuntimeError, OverflowError) as error:
        result.update(status="failed", reason=type(error).__name__)
    return result


def main(argv=None):
    """Run in a separate optional upstream environment, writing predictions only."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=("rebeca", "ostir"))
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rebeca-root", type=Path)
    args = parser.parse_args(argv)
    if args.model == "rebeca" and args.rebeca_root is None:
        parser.error(
            "rebeca requires --rebeca-root pointing to pinned external artifacts"
        )
    engine = (
        rebeca_engine(args.rebeca_root) if args.model == "rebeca" else ostir_engine()
    )
    raw = args.inputs.read_bytes()
    inputs = json.loads(raw)["records"]
    identities = [row["id"] for row in inputs]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate input identities")
    started = time.perf_counter()
    results = [predict(row, args.model, engine) for row in inputs]
    payload = {
        "schema_version": "rbs-upstream-predictions-1",
        "model": args.model,
        "input_sha256": digest(raw),
        "adapter_sha256": digest(Path(__file__).read_bytes()),
        "records": results,
        "elapsed_seconds": time.perf_counter() - started,
        "upstream_artifacts": REBECA_FILES
        if args.model == "rebeca"
        else {"OSTIR": "1.1.3", "ViennaRNA": "2.7.2", "temperature_celsius": 37.0},
    }
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "n_inputs": len(inputs),
                "n_ok": sum(r["status"] == "ok" for r in results),
                "output_sha256": digest(args.output.read_bytes()),
            }
        )
    )


if __name__ == "__main__":
    main()
