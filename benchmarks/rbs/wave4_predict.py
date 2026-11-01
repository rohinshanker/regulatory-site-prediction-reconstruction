"""One-request public inference bridge, including the isolated Python3.9 oracle.

No scoring equations or learned features are implemented here. Raw upstream
results remain in the private stdout receipt alongside the normalized score.
"""

import argparse
import contextlib
import hashlib
import io
import json
import sys
import tempfile

from benchmarks.rbs import comparators
from benchmarks.rbs.metrics import finite_number


def input_check(request):
    """Require the fixed, explicit supplied-start interface used by this wave."""
    starts = request["start_positions"]
    sequence = request["sequence"]
    if (
        not isinstance(request["id"], str)
        or not request["id"]
        or not isinstance(sequence, str)
        or set(sequence) - set("ACGT")
        or not isinstance(starts, list)
        or len(starts) != 1
        or type(starts[0]) is not int
        or not 0 <= starts[0] <= len(sequence) - 3
        or request["strand"] != "+"
        or request["anti_sd"] != "ACCUCCUUA"
        or request["temperature_c"] != 37
        or type(request["temperature_c"]) not in (int, float)
        or not isinstance(request["host"], str)
    ):
        raise ValueError("Request differs from the frozen supplied-start contract")


def normalize_core(result, request, kind, expected_model, expected_artifact):
    """Audit only public output identity, coordinates, native scale and failures."""
    status = result["status"]
    if result["id"] != request["id"] or status not in {
        "ok",
        "failed",
        "unsupported",
        "invalid_input",
        "no_candidate",
    }:
        raise ValueError("Runtime identity/status mismatch")
    supplied = result["input"]
    if supplied is not None and (
        supplied["oriented_sequence"].replace("U", "T") != request["sequence"]
        or list(supplied["start_positions"]) != request["start_positions"]
        or supplied["strand"] != "+"
        or supplied["anti_sd"] != request["anti_sd"]
        or supplied["temperature_c"] != request["temperature_c"]
        or supplied["host"] != request["host"]
    ):
        raise ValueError("Runtime changed the supplied input/settings")
    reason = result["reason"] or ""
    if kind == "mechanistic":
        if result["model"]["id"] != expected_model:
            raise ValueError("Runtime model identity mismatch")
        sites = result["sites"]
        if len(sites) > 1 or (
            sites and sites[0]["oriented_start"] != request["start_positions"][0]
        ):
            raise ValueError("Runtime returned a different supplied start")
        score = sites[0]["tir"] if sites else None
        if status == "ok" and (
            len(sites) != 1
            or sites[0]["status"] != "ok"
            or not finite_number(score)
            or score <= 0
        ):
            raise ValueError(
                "Successful runtime record lacks a valid supplied-site score"
            )
        if sites:
            reason = sites[0]["reason"] or reason
    else:
        if (
            result["artifact_sha256"] != expected_artifact
            or result["feature_kind"] != "sequence-v1"
            or result["score_scale"] != "log2_assay_response"
            or result["mechanistic_reference"] is not None
        ):
            raise ValueError("Learned artifact/feature/scale contract mismatch")
        score = result["score_log2"]
        start = request["start_positions"][0]
        if status == "ok" and result["start_codon"] != {
            "start": start,
            "end": start + 3,
            "strand": "+",
        }:
            raise ValueError("Learned start-codon coordinates mismatch")
    if (status == "ok" and (supplied is None or not finite_number(score))) or (
        status != "ok" and score is not None
    ):
        raise ValueError("Runtime success/failure score semantics mismatch")
    return {"status": status, "predicted": score, "reason": reason}


def infer(args, request):
    """Execute frozen public APIs/CLI; the parent enforces a process deadline."""
    input_check(request)
    if args.kind in {"ostir", "rebeca"}:
        engine = (
            comparators.ostir_engine()
            if args.kind == "ostir"
            else comparators.rebeca_engine(args.rebeca_root)
        )
        raw = comparators.predict(
            {**request, "start": request["start_positions"][0]}, args.kind, engine
        )
        return {k: raw.get(k, "") for k in ("status", "predicted", "reason")}, raw
    if args.kind == "mechanistic":
        from regsite.backend import RnaStructure
        from regsite.rbs import predict

        backend = RnaStructure.open(args.engine)
        if backend.identity["variant"] != args.backend_variant:
            raise ValueError("Backend variant differs from freeze")
        raw = predict(request, backend, profile=args.profile, seconds=args.seconds)
    else:
        from regsite.learned_cli import main as learned_main

        capture = io.StringIO()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(request, handle)
            handle.flush()
            with contextlib.redirect_stdout(capture):
                code = learned_main(
                    [args.model, handle.name, "--seconds-per-record", str(args.seconds)]
                )
        if code not in (0, 1):
            raise ValueError("Learned CLI setup failed")
        envelope = json.loads(capture.getvalue())
        if len(envelope["results"]) != 1:
            raise ValueError("Learned CLI returned wrong record count")
        raw = envelope["results"][0]
    return normalize_core(
        raw, request, args.kind, args.expected_model, args.expected_artifact
    ), raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("mechanistic", "learned", "ostir", "rebeca"))
    for key in (
        "engine",
        "profile",
        "backend-variant",
        "expected-model",
        "model",
        "expected-artifact",
        "rebeca-root",
    ):
        parser.add_argument("--" + key)
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args(argv)
    needed = {
        "mechanistic": ("engine", "profile", "backend_variant", "expected_model"),
        "learned": ("model", "expected_artifact"),
        "rebeca": ("rebeca_root",),
        "ostir": (),
    }
    if (
        any(not getattr(args, name) for name in needed[args.kind])
        or not finite_number(args.seconds)
        or args.seconds <= 0
    ):
        parser.error(
            "Required frozen model/backend settings or positive deadline missing"
        )
    packet = sys.stdin.buffer.read()
    request = json.loads(packet)
    with contextlib.redirect_stdout(sys.stderr):
        result, raw = infer(args, request)
    output = {
        "id": request["id"],
        "input_sha256": hashlib.sha256(packet).hexdigest(),
        **result,
        "upstream_result": raw,
    }
    print(json.dumps(output, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
