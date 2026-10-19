"""Bounded Promoter requests, deterministic identities and complete-roster results.

The pure model lives in :mod:`regsite.promoter`. This module owns validation,
batch budgets and exports; rejected records never acquire inferred settings.
"""

import csv
import hashlib
import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TextIO
from urllib.parse import quote

from regsite import __version__, promoter

LIMITS = {
    "max_input_json_bytes": 4_000_000,
    "max_records_per_batch": 100,
    "max_id_chars": 128,
    "max_host_name_chars": 200,
    "max_contig_chars": 128,
    "max_raw_sequence_chars_per_record": 50_000,
    "max_normalized_bases_per_record": 5_000,
    "max_normalized_bases_per_batch": 100_000,
    "max_planned_sites_per_record": 1_000,
    "max_planned_sites_per_batch": 4_000,
    "max_all_state_sites_per_record": 100,
    "max_all_states_per_record": 2_000,
    "max_all_states_per_batch": 2_000,
    "max_result_json_bytes": 67_108_864,
    "max_metadata_json_bytes": 4_096,
    "max_metadata_depth": 4,
    "default_seconds_per_record": 30.0,
    "max_seconds_per_record": 120.0,
    "default_seconds_per_batch": 300.0,
    "max_seconds_per_batch": 3600.0,
}
STATUSES = ("ok", "no_candidate", "unsupported", "invalid_input", "failed")
UNSUPPORTED = frozenset(
    (
        "sigma",
        "sigma_factor",
        "sigma_levels",
        "temperature",
        "temperature_c",
        "design",
        "optimize",
        "k",
        "beta",
    )
)
FIELDS = frozenset(
    (
        "id",
        "sequence",
        "calibration",
        "host",
        "scan",
        "projection",
        "output",
        "model",
        "metadata",
    )
)
OUTPUT_DEFAULTS = {"states": "selected", "legacy_keys": False, "elements": True}
NORMALIZATION = "ascii-whitespace-uppercase-u-to-t-1"
SOURCE_QUIRKS = {
    "reverse_key_l_minus_t": "Corrected local base L-1-t; legacy L-t diagnostic only.",
    "arbitrary_scan_gap_omitted": "Always retain the one-base UP/hex35 gap.",
    "sigma_levels_ignored": "No sigma input accepted; source metadata had no effect.",
    "unknown_organism_default_beta": "Calibration required, never inferred from host.",
    "one_state_per_tss_public": "All coordinate-eligible states available on request.",
    "unused_spacer_coefficients": "Preserve unused 336..338; use source quadratic.",
    "paper_code_difference": "Follow code: UP=24; discriminator lengths 6..10.",
}


class SetupError(ValueError):
    """An atomic input/options/integrity error: no result may be emitted."""


class LimitError(promoter.InputError):
    """A rejected field with the exact effective limit and observed size."""

    def __init__(self, name: str, observed: int, field: str) -> None:
        super().__init__("limit_exceeded", field)
        self.limit = name
        self.observed = observed


def canonical_bytes(value: object) -> bytes:
    """Encode finite Python JSON for identities, without a trailing newline."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def canonical_hash(value: object) -> str:
    """Hash exactly the public compact canonical representation."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def result_bytes(value: object) -> bytes:
    """Return the authoritative pretty representation, including its single LF."""
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SetupError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(token: str) -> None:
    raise SetupError(f"nonfinite JSON number: {token}")


def load_requests(stream: TextIO) -> object:
    """Read bounded UTF-8 JSON; reject duplicate keys and nonfinite numbers."""
    text = stream.read(int(LIMITS["max_input_json_bytes"]) + 1)
    try:
        if len(text.encode("utf-8")) > LIMITS["max_input_json_bytes"]:
            raise SetupError("max_input_json_bytes exceeded")
        value = json.loads(
            text, object_pairs_hook=_unique_pairs, parse_constant=_nonfinite
        )
        # Also rejects an overflowing exponent, such as 1e999, anywhere in metadata.
        canonical_bytes(value)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SetupError(str(exc)) from exc
    return value


def model_identity(params: promoter.PromoterParameters) -> tuple[dict, dict]:
    """Return the full public model and its exact six-key hashing identity."""
    identity = {
        "id": promoter.MODEL_ID,
        "implementation_version": __version__,
        "parameter_json_sha256": params.parameter_json_sha256,
        "coefficient_array_sha256": params.array_sha256["coefficients"],
        "intercept_array_sha256": params.array_sha256["intercept"],
        "source_commit": params.source_commit,
    }
    model = {
        "id": identity["id"],
        "implementation_version": __version__,
        "kind": "historical_equation_reconstruction",
        "source": {
            "repository": "https://github.com/hsalis/SalisLabCode",
            "commit": params.source_commit,
            "path": "Promoter_Calculator",
            "reference_fork_commit": "0fe5f6f0fb2befc087556afa575f7241afd98fbf",
        },
        "licence": "GPL-3.0-or-later",
        "parameters": {
            "parameter_json_sha256": params.parameter_json_sha256,
            "array_sha256": dict(params.array_sha256),
            "coefficient_count": len(params.coefficients),
            "intercept_count": 1,
            "unused_coefficient_indices": list(params.unused_indices),
        },
        "term_source_names": dict(promoter.TERM_SOURCE_NAMES),
        "terms_unit": promoter.TERMS_UNIT,
        "terms_semantics": promoter.TERMS_SEMANTICS,
        "source_quirks": [
            {"id": key, "behavior": value} for key, value in SOURCE_QUIRKS.items()
        ],
        "not_modeled": [
            "sigma_factor",
            "temperature",
            "host_specific_calibration",
            "probability",
            "absolute_rate",
            "free_energy",
        ],
        "claims": dict.fromkeys(
            (
                "physical_free_energy",
                "absolute_rate",
                "probability",
                "native_accuracy_evaluated",
                "hosted_parity",
            ),
            False,
        ),
    }
    return model, identity


def _integer(value: object, code: str, field: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
        or value != int(value)
    ):
        raise promoter.InputError(code, field)
    return int(value)


def _limit(name: str, observed: int, field: str) -> None:
    if observed > LIMITS[name]:
        raise LimitError(name, observed, field)


def _output(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - OUTPUT_DEFAULTS.keys():
        raise promoter.InputError("invalid_output_option", "output")
    resolved = OUTPUT_DEFAULTS | value
    if (
        resolved["states"] not in ("selected", "all")
        or type(resolved["legacy_keys"]) is not bool
        or type(resolved["elements"]) is not bool
    ):
        raise promoter.InputError("invalid_output_option", "output")
    return resolved


def _scan(value: object, length: int | None) -> tuple[dict, list[tuple[str, int]]]:
    if not isinstance(value, dict):
        raise promoter.InputError("invalid_scan", "scan")
    mode = value.get("mode")
    if mode == "scan":
        if set(value) != {"mode", "range", "strands"}:
            raise promoter.InputError("invalid_scan", "scan")
        bounds, strands = value["range"], value["strands"]
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise promoter.InputError("invalid_scan", "scan.range")
        a, b = [_integer(x, "invalid_scan", "scan.range") for x in bounds]
        if a < 0 or b < a or (length is not None and b > length):
            raise promoter.InputError("range_out_of_bounds", "scan.range")
        if (
            not isinstance(strands, list)
            or not strands
            or any(s not in ("+", "-") for s in strands)
            or len(set(strands)) != len(strands)
        ):
            raise promoter.InputError("invalid_strand", "scan.strands")
        _limit("max_planned_sites_per_record", (b - a) * len(strands), "scan")
        return {"mode": mode, "range": [a, b], "strands": strands}, [
            (strand, f) for strand in strands for f in range(a, b)
        ]
    if mode != "positions" or set(value) != {"mode", "positions"}:
        raise promoter.InputError("invalid_scan", "scan")
    positions = value["positions"]
    if not isinstance(positions, list):
        raise promoter.InputError("invalid_scan", "scan.positions")
    _limit("max_planned_sites_per_record", len(positions), "scan.positions")
    planned = []
    seen = set()
    for i, position in enumerate(positions):
        path = f"scan.positions[{i}]"
        if not isinstance(position, dict) or set(position) != {"strand", "tss"}:
            raise promoter.InputError("invalid_scan", path)
        strand = position["strand"]
        if strand not in ("+", "-"):
            raise promoter.InputError("invalid_strand", path + ".strand")
        f = _integer(position["tss"], "invalid_scan", path + ".tss")
        if f < 0 or (length is not None and f >= length):
            raise promoter.InputError("position_out_of_range", path + ".tss")
        if (strand, f) in seen:
            raise promoter.InputError("duplicate_position", path)
        seen.add((strand, f))
        planned.append((strand, f))
    return {
        "mode": mode,
        "positions": [{"strand": s, "tss": f} for s, f in planned],
    }, planned


def _metadata(value: object) -> dict:
    if not isinstance(value, dict):
        raise promoter.InputError("invalid_type", "metadata")
    # Iterative depth checking is bounded before JSON serialization can recurse.
    pending: list[tuple[dict | list, int]] = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        _limit("max_metadata_depth", depth, "metadata")
        values = item.values() if isinstance(item, dict) else item
        pending.extend((v, depth + 1) for v in values if isinstance(v, (dict, list)))
    _limit("max_metadata_json_bytes", len(canonical_bytes(value)), "metadata")
    return value


def _utf8(value: str, code: str, field: str) -> bytes:
    """Reject unpaired surrogate text locally, preserving valid sibling records."""
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise promoter.InputError(code, field, exc.start, value[exc.start]) from exc


def _calibration(profile: Any, host: Any) -> promoter.Calibration:
    if isinstance(host, dict) and isinstance(host.get("name"), str):
        if len(host["name"]) > LIMITS["max_host_name_chars"]:
            raise promoter.InputError("invalid_host", "host.name")
        _utf8(host["name"], "invalid_host", "host.name")
    return promoter.resolve_calibration(profile, host)


def _projection(value: object, length: int | None) -> dict | None:
    required = {
        "contig",
        "origin",
        "contig_length",
        "topology",
        "origin_crossing",
    }
    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or set(value) - required - {"sequence_strand"}
    ):
        raise promoter.InputError("invalid_projection", "projection")
    contig = value["contig"]
    if (
        not isinstance(contig, str)
        or not 1 <= len(contig) <= LIMITS["max_contig_chars"]
    ):
        raise promoter.InputError("invalid_projection", "projection.contig")
    _utf8(contig, "invalid_projection", "projection.contig")
    size = _integer(
        value["contig_length"], "invalid_projection", "projection.contig_length"
    )
    origin = _integer(value["origin"], "invalid_projection", "projection.origin")
    if (
        size < 1
        or not 0 <= origin < size
        or value.get("sequence_strand", "+") not in ("+", "-")
        or value["topology"] not in ("linear", "circular")
        or type(value["origin_crossing"]) is not bool
        or (value["topology"] == "linear" and value["origin_crossing"])
    ):
        raise promoter.InputError("invalid_projection", "projection")
    # With unknown sequence length, no extent/crossing decision is justified.
    return None if length is None else promoter.check_projection(value, length)


def _error(exc: promoter.InputError) -> dict:
    error = {"code": exc.code, "field": exc.field, "message": str(exc)}
    for name in ("index", "character", "limit", "observed"):
        value = getattr(exc, name, None)
        if value is not None:
            error[name] = value
    return error


@dataclass
class PreparedRecord:
    """Validated computation plus result fields retained through every failure."""

    result: dict
    sequence: str | None
    calibration: promoter.Calibration | None
    output: dict | None
    planned: list[tuple[str, int]]
    scope_id: str | None = None


def _prepare(
    raw: object, identity: dict, ids: set, contigs: dict, totals: Counter
) -> PreparedRecord:
    result: dict = {
        "id": None,
        "status": "invalid_input",
        "reasons": [],
        "prediction_id": None,
        "input": dict.fromkeys(
            ("raw_sha256", "normalized_dna_sha256", "length", "normalization")
        ),
        "calibration": None,
        "scan": None,
        "coverage": None,
        "sites": [],
        "projection": None,
        "warnings": [],
        "errors": [],
        "metadata": None,
    }
    item = PreparedRecord(result, None, None, None, [])
    errors = result["errors"]

    def check(function: Callable, *args: Any) -> Any:
        try:
            return function(*args)
        except promoter.InputError as exc:
            errors.append(_error(exc))
            return None

    if not isinstance(raw, dict):
        errors.append(_error(promoter.InputError("invalid_type", "record")))
        result["reasons"] = ["invalid_type"]
        return item
    for field in sorted(set(raw) - FIELDS - UNSUPPORTED):
        errors.append(_error(promoter.InputError("unknown_field", field)))
    for field in ("id", "sequence"):
        if field not in raw:
            errors.append(_error(promoter.InputError("missing_field", field)))
    identifier = raw.get("id")
    if (
        isinstance(identifier, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", identifier)
        and len(identifier) <= LIMITS["max_id_chars"]
    ):
        result["id"] = identifier
        if identifier in ids:
            errors.append(_error(promoter.InputError("duplicate_id", "id")))
        ids.add(identifier)
    elif "id" in raw:
        errors.append(_error(promoter.InputError("invalid_id", "id")))

    def sequence() -> str:
        value = raw["sequence"]
        if not isinstance(value, str):
            raise promoter.InputError("invalid_type", "sequence")
        try:
            raw_bytes = value.encode("utf-8")
        except UnicodeEncodeError:
            # No UTF-8 byte identity exists; normalization reports the first error.
            raw_bytes = None
        if raw_bytes is not None:
            result["input"]["raw_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        _limit("max_raw_sequence_chars_per_record", len(value), "sequence")
        normalized = promoter.normalize_dna(value, max_length=len(value))
        _limit("max_normalized_bases_per_record", len(normalized), "sequence")
        return normalized

    if "sequence" in raw:
        item.sequence = check(sequence)
    if item.sequence is not None:
        result["input"].update(
            normalized_dna_sha256=hashlib.sha256(item.sequence.encode()).hexdigest(),
            length=len(item.sequence),
            normalization=NORMALIZATION,
        )
    length = result["input"]["length"]
    if "calibration" not in raw:
        errors.append(
            _error(promoter.InputError("calibration_required", "calibration"))
        )
    elif "host" in raw and raw["host"] is None:
        errors.append(_error(promoter.InputError("invalid_host", "host")))
    else:
        item.calibration = check(_calibration, raw["calibration"], raw.get("host"))
        if item.calibration is not None:
            result["calibration"] = item.calibration.to_dict()
            result["warnings"].extend(item.calibration.warnings)
    item.output = check(_output, raw.get("output", {}))
    if item.output is not None and item.output["legacy_keys"]:
        result["warnings"].append(
            {
                "code": "legacy_key_not_coordinate",
                "message": "legacy_source_key is not a base index.",
            }
        )
    if "scan" not in raw:
        errors.append(_error(promoter.InputError("scan_required", "scan")))
    else:
        scan = check(_scan, raw["scan"], length)
        # No resolved scan can claim normalized bounds if normalization failed.
        if scan is not None and length is not None:
            result["scan"], item.planned = scan
    if "projection" in raw:
        result["projection"] = check(_projection, raw["projection"], length)
    projection = result["projection"]
    if projection is not None:
        contig = projection["contig"]
        fingerprint = (projection["contig_length"], projection["topology"])
        if contig in contigs and contigs[contig] != fingerprint:
            errors.append(
                _error(promoter.InputError("contig_metadata_conflict", "projection"))
            )
            result["projection"] = None
        else:
            contigs[contig] = fingerprint
    if "metadata" in raw:
        result["metadata"] = check(_metadata, raw["metadata"])
    unsupported = [
        _error(promoter.InputError("unsupported_control", field))
        for field in sorted(set(raw) & UNSUPPORTED)
    ]
    if "model" in raw:
        pin = raw["model"]
        if (
            not isinstance(pin, dict)
            or set(pin) != {"id", "parameter_json_sha256"}
            or not isinstance(pin["id"], str)
            or not pin["id"]
            or not isinstance(pin["parameter_json_sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", pin["parameter_json_sha256"]) is None
        ):
            errors.append(_error(promoter.InputError("invalid_type", "model")))
        elif any(pin[k] != identity[k] for k in pin):
            unsupported.append(
                _error(promoter.InputError("model_unavailable", "model"))
            )
    if not errors and not unsupported:
        assert length is not None and item.output is not None
        counts = {
            "max_normalized_bases_per_batch": length,
            "max_planned_sites_per_batch": len(item.planned),
        }
        if item.output["states"] == "all":
            states = sum(
                len(promoter.eligible_states(length, f if s == "+" else length - 1 - f))
                for s, f in item.planned
            )
            check(_limit, "max_all_state_sites_per_record", len(item.planned), "scan")
            check(_limit, "max_all_states_per_record", states, "output.states")
            counts["max_all_states_per_batch"] = states
        for key, count in counts.items():
            check(_limit, key, totals[key] + count, "batch")
        if not errors:
            totals.update(counts)
    if errors or unsupported:
        result["status"] = "invalid_input" if errors else "unsupported"
        errors.extend(unsupported)
        result["reasons"] = list(dict.fromkeys(e["code"] for e in errors))
        return item
    assert item.calibration is not None
    item.scope_id = canonical_hash(
        {
            "schema_version": "1.0",
            "model": identity,
            "calibration": {
                key: result["calibration"][key] for key in ("profile", "host")
            },
            "normalized_dna_sha256": result["input"]["normalized_dna_sha256"],
            "projection": result["projection"],
        }
    )
    result["prediction_id"] = canonical_hash(
        {"scope_id": item.scope_id, "scan": result["scan"], "output": item.output}
    )
    result["status"] = "no_candidate"
    _summarize(result)
    return item


def _summarize(result: dict) -> None:
    sites = result["sites"]
    scored = sum(s["status"] == "ok" for s in sites)
    failed = sum(s["status"] == "failed" and s["attempted"] for s in sites)
    unattempted = sum(not s["attempted"] for s in sites)
    reasons = list(dict.fromkeys(s["reason"] for s in sites if s["reason"] is not None))
    result["status"] = (
        "failed" if failed + unattempted else ("ok" if scored else "no_candidate")
    )
    result["reasons"] = (
        [] if result["status"] == "ok" else (reasons if sites else ["empty_scan"])
    )
    result["coverage"] = {
        "planned_sites": len(sites),
        "scored_sites": scored,
        "partial_state_sites": sum(
            s["status"] == "ok" and s["state_count"] < 30 for s in sites
        ),
        "insufficient_context_sites": sum(s["status"] == "no_candidate" for s in sites),
        "failed_sites": failed,
        "unattempted_sites": unattempted,
        "complete_context": all(s["complete_state_set"] for s in sites),
        "complete": not (failed + unattempted),
        "truncation": None
        if not failed + unattempted
        else {
            "reason": next(s["reason"] for s in sites if s["status"] == "failed"),
            "attempted_sites": len(sites) - unattempted,
            "planned_sites": len(sites),
        },
    }


def predict(
    request: PreparedRecord,
    params: promoter.PromoterParameters,
    *,
    seconds: float,
    clock: Callable[[], float] = time.monotonic,
    batch_deadline: float = math.inf,
) -> dict:
    """Score one validated record; preserve every candidate when a deadline ends."""
    result = request.result
    if result["status"] in ("invalid_input", "unsupported") or not request.planned:
        return result
    assert request.sequence is not None and request.calibration is not None
    assert request.output is not None and request.scope_id is not None
    deadline = min(clock() + seconds, batch_deadline)
    length = len(request.sequence)
    keep_states = request.output["states"] == "all"
    for strand, f in request.planned:
        t = f if strand == "+" else length - 1 - f
        if clock() >= deadline:
            site = promoter.SiteResult(
                strand,
                f,
                t,
                length,
                "failed",
                "deadline_exceeded",
                len(promoter.eligible_states(length, t)),
                None,
                None,
                () if keep_states else None,
                request.calibration,
            ).to_dict(
                elements=request.output["elements"], projection=result["projection"]
            )
            site["attempted"] = False
        else:
            site = promoter.score_site(
                request.sequence,
                strand,
                f,
                params,
                request.calibration,
                keep_states=keep_states,
            ).to_dict(
                elements=request.output["elements"], projection=result["projection"]
            )
        site_id = f"psite1:{request.scope_id[:32]}:{strand}:{f}"
        site["site_id"] = site_id
        for state in [site["selected"], *site.get("states", [])]:
            if state is not None:
                state["state_id"] = (
                    f"{site_id}:d{state['discriminator_length']}"
                    f"s{state['spacer_length']}"
                )
        if request.output["legacy_keys"]:
            site["legacy_source_key"] = promoter.legacy_source_key(length, strand, t)
        result["sites"].append(site)
    _summarize(result)
    return result


def _envelope(value: object) -> tuple[list, dict]:
    if not isinstance(value, dict):
        raise SetupError("input must be a single object or records envelope")
    if value.get("schema_version", "1.0") != "1.0":
        raise SetupError("schema_version_unsupported")
    if "records" not in value:
        return [{k: v for k, v in value.items() if k != "schema_version"}], {}
    if set(value) - {"schema_version", "records", "defaults"}:
        raise SetupError("unknown_field in envelope")
    records, defaults = value["records"], value.get("defaults", {})
    if not isinstance(records, list) or len(records) > LIMITS["max_records_per_batch"]:
        raise SetupError("records must be a list within max_records_per_batch")
    if not isinstance(defaults, dict) or set(defaults) - {
        "calibration",
        "host",
        "output",
    }:
        raise SetupError("invalid defaults object")
    try:
        if "calibration" in defaults or "host" in defaults:
            if "host" in defaults and defaults["host"] is None:
                raise promoter.InputError("invalid_host", "defaults.host")
            # This profile validates host shape only; it never supplies a default.
            _calibration(defaults.get("calibration", "in_vitro"), defaults.get("host"))
        if "output" in defaults:
            _output(defaults["output"])
    except promoter.InputError as exc:
        raise SetupError(f"invalid defaults: {exc}") from exc
    return records, defaults


def predict_batch(
    value: object,
    params: promoter.PromoterParameters | None = None,
    *,
    seconds_per_record: float | None = None,
    seconds_per_batch: float | None = None,
    cli_calibration: str | None = None,
    cli_states: str | None = None,
    output_format: str = "json",
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Validate all records before scoring; return a bounded authoritative object."""
    try:
        canonical_bytes(value)
    except (ValueError, TypeError, RecursionError) as exc:
        raise SetupError(f"input must be finite JSON: {exc}") from exc
    records, defaults = _envelope(value)
    deadlines = []
    for name, supplied in (
        ("record", seconds_per_record),
        ("batch", seconds_per_batch),
    ):
        supplied = (
            LIMITS[f"default_seconds_per_{name}"] if supplied is None else supplied
        )
        if (
            isinstance(supplied, bool)
            or not isinstance(supplied, (int, float))
            or not 0 < supplied <= LIMITS[f"max_seconds_per_{name}"]
        ):
            raise SetupError(f"invalid seconds_per_{name}")
        deadlines.append(float(supplied))
    record_seconds, batch_seconds = deadlines
    if cli_calibration not in (None, "ecoli_mg1655", "in_vitro"):
        raise SetupError("invalid CLI calibration")
    if cli_states not in (None, "selected", "all"):
        raise SetupError("invalid CLI states")
    if output_format not in ("json", "csv", "gff3"):
        raise SetupError("invalid output format")
    merged = []
    # Conflicts are checked even on invalid records and overridden file defaults.
    for raw in [defaults, *records]:
        if not isinstance(raw, dict):
            continue
        if (
            cli_calibration is not None
            and "calibration" in raw
            and raw["calibration"] != cli_calibration
        ):
            raise SetupError("CLI calibration conflicts with file")
        output = raw.get("output")
        if (
            cli_states is not None
            and isinstance(output, dict)
            and "states" in output
            and output["states"] != cli_states
        ):
            raise SetupError("CLI states conflicts with file")
    for raw in records:
        if isinstance(raw, dict):
            raw = defaults | raw
            if cli_calibration is not None:
                raw.setdefault("calibration", cli_calibration)
            if cli_states is not None:
                output = raw.get("output", {})
                if isinstance(output, dict):
                    raw["output"] = {"states": cli_states} | output
            if (
                output_format == "csv"
                and isinstance(raw.get("output"), dict)
                and raw["output"].get("states") == "all"
            ):
                raise SetupError("CSV cannot represent output.states all")
        merged.append(raw)
    params = promoter.load_parameters() if params is None else params
    model, identity = model_identity(params)
    ids: set = set()
    contigs: dict = {}
    totals: Counter = Counter()
    prepared = [_prepare(raw, identity, ids, contigs, totals) for raw in merged]
    batch_deadline = clock() + batch_seconds
    results = [
        predict(
            item,
            params,
            seconds=record_seconds,
            clock=clock,
            batch_deadline=batch_deadline,
        )
        for item in prepared
    ]
    result = {
        "schema_version": "1.0",
        "model": model,
        "batch": {
            "batch_id": canonical_hash(
                {
                    "input": value,
                    "model": {
                        k: identity[k]
                        for k in (
                            "id",
                            "implementation_version",
                            "parameter_json_sha256",
                        )
                    },
                    "limits": LIMITS,
                    "seconds_per_record": record_seconds,
                    "seconds_per_batch": batch_seconds,
                    "cli_calibration": cli_calibration,
                    "cli_states": cli_states,
                }
            ),
            "record_count": len(results),
            "status_counts": {
                s: sum(r["status"] == s for r in results) for s in STATUSES
            },
            "complete": all(r["status"] != "failed" for r in results),
            "limits": dict(LIMITS),
            "seconds_per_record": record_seconds,
            "seconds_per_batch": batch_seconds,
        },
        "results": results,
    }
    if len(result_bytes(result)) > LIMITS["max_result_json_bytes"]:
        raise SetupError("max_result_json_bytes exceeded")
    return result


def write_json(result: dict, stream: TextIO) -> None:
    """Write the authoritative pretty JSON with exactly one LF."""
    stream.write(result_bytes(result).decode("utf-8"))


CSV_COLUMNS = (
    "record_id record_status prediction_id site_id strand forward_base oriented_base "
    "sequence_strand genomic_contig genomic_base genomic_strand site_status reason "
    "attempted state_count complete_state_set tie_count "
    "discriminator_length spacer_length "
    "score_hex10 score_hex35 score_discriminator score_extended10 score_itr score_up "
    "score_spacer score_intercept score_total score_binding "
    "log_relative_transcription_score relative_transcription_score score_status "
    "calibration_profile host_status warning_codes"
).split()


def write_csv(result: dict, stream: TextIO) -> None:
    """Export every planned site and missing score using standard CSV quoting."""
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for record in result["results"]:
        calibration = record["calibration"] or {}
        for site in record["sites"] or [{}]:
            selected = site.get("selected") or {}
            genomic = site.get("genomic") or {}
            row = {
                "record_id": record["id"],
                "record_status": record["status"],
                "prediction_id": record["prediction_id"],
                "calibration_profile": calibration.get("profile"),
                "host_status": calibration.get("host_status"),
                "warning_codes": ";".join(w["code"] for w in record["warnings"]),
                "site_status": site.get("status"),
                "sequence_strand": genomic.get("sequence_strand"),
                **{
                    f"genomic_{k}": genomic.get(k) for k in ("contig", "base", "strand")
                },
                **{
                    k: site.get(k)
                    for k in (
                        "site_id",
                        "strand",
                        "reason",
                        "attempted",
                        "state_count",
                        "complete_state_set",
                        "tie_count",
                    )
                },
                **site.get("tss", {}),
                **{
                    k: selected.get(k)
                    for k in (
                        "discriminator_length",
                        "spacer_length",
                        "log_relative_transcription_score",
                        "relative_transcription_score",
                        "score_status",
                    )
                },
                **{
                    f"score_{k}": selected.get("terms", {}).get(k)
                    for k in (
                        "hex10",
                        "hex35",
                        "discriminator",
                        "extended10",
                        "itr",
                        "up",
                        "spacer",
                        "intercept",
                        "total",
                        "binding",
                    )
                },
            }
            writer.writerow(row)


def _escape(value: object) -> str:
    # urllib always leaves '~' unescaped, but it is not in GFF3's seqid alphabet.
    return quote(str(value), safe=".:^*$@!+_?-|").replace("~", "%7E")


def write_gff3(result: dict, stream: TextIO) -> None:
    """Export projected model windows as generic regions, never measured promoters."""
    stream.write("##gff-version 3\n")
    seen = set()
    for record in result["results"]:
        projection = record["projection"]
        if projection is None:
            stream.write(
                f"# record={_escape(record['id'])} export_reason=projection_required "
                f"sites={len(record['sites'])}\n"
            )
            continue
        contig, size = projection["contig"], projection["contig_length"]
        seqid = _escape(contig)
        if contig not in seen:
            seen.add(contig)
            stream.write(f"##sequence-region {seqid} 1 {size}\n")
            circular = str(projection["topology"] == "circular").lower()
            stream.write(
                f"{seqid}\tregsite-promoter\tregion\t1\t{size}\t.\t.\t.\t"
                f"ID=landmark:{seqid};Is_circular={circular};contig_length={size}\n"
            )
        if not record["sites"]:
            stream.write(
                f"# record={_escape(record['id'])} status={record['status']} sites=0\n"
            )
        for site in record["sites"]:
            selected = site["selected"]
            if selected is None:
                stream.write(
                    f"# site={_escape(site['site_id'])} status={site['status']} "
                    f"reason={site['reason']}\n"
                )
                continue
            genomic = site["genomic"]
            windows = {"tss": [[genomic["base"], genomic["base"] + 1]]}
            windows.update(
                {
                    k: selected["genomic_intervals"][k]
                    for k in ("hex35", "hex10", "UP", "spacer", "discriminator", "itr")
                }
            )
            for name, runs in windows.items():
                if len(runs) == 1:
                    start, end = runs[0]
                else:
                    start = max(run[0] for run in runs)
                    end = min(run[1] for run in runs) + size
                attrs = {
                    "ID": f"{site['site_id']}:record:{record['id']}:{name}",
                    "Name": name,
                    "model_window": "true",
                    "model_element": name,
                    "site_id": site["site_id"],
                    "record_id": record["id"],
                    "local_strand": site["strand"],
                    "sequence_strand": genomic["sequence_strand"],
                    "log_relative_transcription_score": selected[
                        "log_relative_transcription_score"
                    ],
                }
                attributes = ";".join(f"{k}={_escape(v)}" for k, v in attrs.items())
                stream.write(
                    f"{seqid}\tregsite-promoter\tregion\t{start + 1}\t{end}"
                    f"\t.\t{genomic['strand']}\t.\t{attributes}\n"
                )
