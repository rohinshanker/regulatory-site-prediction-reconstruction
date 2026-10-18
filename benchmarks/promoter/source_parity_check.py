"""Receipt-bound public-result comparison for the frozen synthetic source panel.

This module performs no inference and reads no native/final outcomes. Numerical
expectations come only from the independent, pre-candidate source artifacts.
"""

import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from benchmarks.promoter import runtime_adapter as adapter
from benchmarks.promoter import source_parity
from benchmarks.promoter.native_inputs import strict_json

REQUEST_SHA256 = "fbc5b8b9c99c7ffc4558ff5a423c1b7bdd237a7ebc993aac9505890c4a9c89d3"
EXPECTATIONS_SHA256 = "bc7121f05f7b1a87e93995bd627a1a44a808e09b5167236c75fd5547eb6f33fc"
SOURCE_COMMIT = "46da9132740bce30bccd107f02808adf2215e2f0"


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _same(actual, expected, path):
    if adapter.runtime_canonical_bytes(actual) != adapter.runtime_canonical_bytes(
        expected
    ):
        raise ValueError(f"Source parity mismatch: {path}")


def _compare(actual, expected, path, numerical=False):
    """Exact shape/types except finite learned terms and scores at 1e-12."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError(f"Source parity object keys: {path}")
        for key, value in expected.items():
            _compare(
                actual[key],
                value,
                f"{path}.{key}",
                numerical
                or key
                in (
                    "terms",
                    "log_relative_transcription_score",
                    "relative_transcription_score",
                ),
            )
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"Source parity array length/type: {path}")
        for index, value in enumerate(expected):
            _compare(actual[index], value, f"{path}[{index}]", numerical)
    elif numerical:
        if (
            type(actual) not in (int, float)
            or not -sys.float_info.max <= actual <= sys.float_info.max
            or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        ):
            raise ValueError(f"Source parity numeric mismatch: {path}")
    else:
        _same(actual, expected, path)


def _assets():
    request = (source_parity.ROOT / "source-parity-request.json").read_bytes()
    expected = (source_parity.ROOT / "source-parity-expectations.json").read_bytes()
    if (_hash(request), _hash(expected)) != (REQUEST_SHA256, EXPECTATIONS_SHA256):
        raise ValueError("Frozen source parity asset identity mismatch")
    return request, strict_json(request), strict_json(expected)


def check(raw, manifest):
    """Validate a complete public CLI result against a separately frozen receipt.

    The manifest is the existing native adapter's explicit identity/settings
    receipt shape. For this mixed-profile panel both CLI defaults must be null;
    profiles and output options are supplied by each frozen record. The manifest's
    native packing settings are not applied to this single source-parity batch.
    Failure raises ValueError; a partial or missing record can never pass.
    """
    adapter.check_manifest(manifest)
    identity, settings = manifest["identity"], manifest["settings"]
    if settings["cli_calibration"] is not None or settings["cli_states"] is not None:
        raise ValueError("Source parity requires null CLI calibration/states defaults")
    model = identity["identity_model"]
    parameters = strict_json(
        (source_parity.ROOT / "reference-parameters.json").read_bytes()
    )
    _same(
        [
            model["source_commit"],
            model["coefficient_array_sha256"],
            model["intercept_array_sha256"],
        ],
        [
            SOURCE_COMMIT,
            parameters["array_sha256"]["coefficients"],
            parameters["array_sha256"]["intercept"],
        ],
        "source/array identity",
    )
    request_raw, request, expectations = _assets()
    limits = settings["runtime_limits"]
    if len(raw) > limits["max_result_json_bytes"]:
        raise ValueError("Source parity wire result byte cap exceeded")
    result = strict_json(raw)
    authoritative = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if len(authoritative) > limits["max_result_json_bytes"]:
        raise ValueError("Source parity authoritative result byte cap exceeded")
    adapter._exact_keys(result, adapter.RESULT_KEYS, "source parity result")
    _same(result["schema_version"], "1.0", "schema_version")
    adapter.check_model(result["model"], identity)
    records = result["results"]
    if not isinstance(records, list) or len(records) != expectations["n_records"]:
        raise ValueError("Source parity needs every record exactly once")
    for record, req, expected in zip(
        records, request["records"], expectations["expectations"], strict=True
    ):
        adapter._exact_keys(record, adapter.RECORD_KEYS, "source parity record")
        name = req["id"]
        calibration = adapter.expected_calibration(req["calibration"], None)
        scope, prediction = adapter.prediction_identity(req, calibration, model)
        count = expected["state_count"]
        reason = None if count else "insufficient_context"
        for key, value in {
            "id": name,
            "status": expected["status"],
            "prediction_id": prediction,
            "calibration": calibration,
            "scan": req["scan"],
            "projection": req["projection"],
            "metadata": None,
            "errors": [],
            "input": {
                "raw_sha256": _hash(req["sequence"].encode()),
                "normalized_dna_sha256": _hash(req["sequence"].encode()),
                "length": len(req["sequence"]),
                "normalization": adapter.NORMALIZATION,
            },
        }.items():
            _same(record[key], value, f"{name}.{key}")
        if (
            not isinstance(record["reasons"], list)
            or not all(isinstance(code, str) for code in record["reasons"])
            or (not count and "insufficient_context" not in record["reasons"])
        ):
            raise ValueError(f"Source parity reasons: {name}")
        if not isinstance(record["warnings"], list) or (
            "legacy_key_not_coordinate" not in record["warnings"]
        ):
            raise ValueError(f"Source parity legacy warning: {name}")
        site_id = (
            f"psite1:{scope[:32]}:{expected['strand']}:"
            f"{expected['tss']['forward_base']}"
        )
        site = {
            key: copy.deepcopy(expected[key])
            for key in (
                "status",
                "strand",
                "tss",
                "legacy_source_key",
                "genomic",
                "context",
                "state_count",
                "tie_count",
                "states",
                "selected",
            )
        }
        site.update(
            site_id=site_id,
            reason=reason,
            complete_state_set=count == 30,
            attempted=True,
        )
        for state in [*site["states"], *([site["selected"]] if count else [])]:
            state["state_id"] = (
                f"{site_id}:d{state['discriminator_length']}s{state['spacer_length']}"
            )
        _compare(record["sites"], [site], f"{name}.sites")
        adapter.check_coverage(record["coverage"], expected["status"], [site])
    adapter.check_batch_summary(
        result["batch"],
        records,
        settings,
        adapter.batch_id(request, settings, identity),
    )
    return {
        "schema_version": "promoter-source-parity-audit-1",
        "candidate_commit": identity["candidate_commit"],
        "wheel_sha256": identity["wheel_sha256"],
        "manifest_sha256": adapter.runtime_sha256(manifest),
        "request_sha256": _hash(request_raw),
        "expectations_sha256": EXPECTATIONS_SHA256,
        "result_sha256": _hash(raw),
        "authoritative_result_sha256": _hash(authoritative),
        "tool_sha256": _hash(Path(__file__).read_bytes()),
        "adapter_tool_sha256": adapter.tool_sha256(),
        "records_passed": len(records),
        "states_passed": expectations["n_states"],
        "no_candidate_records": sum(
            not r["state_count"] for r in expectations["expectations"]
        ),
        "absolute_tolerance": 1e-12,
        "relative_tolerance": 1e-12,
        "scope": "synthetic source parity; no native accuracy or hosted equivalence",
    }
