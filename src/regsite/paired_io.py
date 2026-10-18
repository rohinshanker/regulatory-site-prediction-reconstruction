"""Strict paired-request loading and complete scalar comparison exports."""

import csv
import io
import json
import math
from typing import TextIO

from regsite.paired import LIMITS, PairError, result_bytes


def _object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise PairError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise PairError("JSON numbers must be finite")
    return value


def load_request(stream: TextIO) -> object:
    """Bound received UTF-8 bytes as well as the core's canonical input size."""
    maximum = LIMITS["max_input_json_bytes"]
    try:
        text = stream.read(maximum + 1)
        if len(text.encode("utf-8")) > maximum:
            raise PairError("max_input_json_bytes exceeded by received input")
        return json.loads(
            text, object_pairs_hook=_object, parse_float=_float, parse_constant=_float
        )
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise PairError(f"invalid paired JSON: {exc}") from exc


CSV_COLUMNS = (
    "schema_version pair_id calculator result_status request_sha256 prediction_sha256 "
    "diagnostic_only current_roster_status recoded_roster_status "
    "current_expected recoded_expected current_record_status recoded_record_status "
    "comparison_status comparison_reason identity_mismatches "
    "current_candidate_id recoded_candidate_id current_status recoded_status "
    "current_anchor recoded_anchor current_strand recoded_strand "
    "scalar_field unit current_value recoded_value delta_value delta_reason"
).split()


def csv_text(result: dict) -> str:
    """One row per comparison/scalar; zero-row pairs retain a summary row.

    Native structures, complete feature paths and source/model identities remain
    in the JSON output. Every CSV row binds that full result by its SHA-256.
    Empty scalar cells mean unavailable; zero is written as a numeric value.
    """
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    common = {
        key: result[key]
        for key in (
            "schema_version",
            "pair_id",
            "calculator",
            "request_sha256",
            "prediction_sha256",
        )
    }
    common.update(
        result_status=result["status"],
        diagnostic_only=result["coverage"]["diagnostic_only"],
    )
    candidates = {}
    for side in ("current", "recoded"):
        part = result["sides"][side]
        record = part["prediction"]
        if result["calculator"] == "promoter":
            record = record["results"][0]
        common.update(
            {
                f"{side}_roster_status": part["roster_status"],
                f"{side}_expected": result["coverage"][side]["expected"],
                f"{side}_record_status": record["status"],
            }
        )
        candidates[side] = {c["id"]: c for c in part["candidates"]}
    if not result["comparisons"]:
        writer.writerow(
            dict(
                common,
                comparison_status="not_applicable",
                delta_reason="no_comparison_rows",
            )
        )
    for comparison in result["comparisons"]:
        row = dict(
            common,
            comparison_status=comparison["status"],
            comparison_reason=comparison["reason"],
            identity_mismatches=";".join(comparison["identity_mismatches"]),
        )
        sides = {}
        for side in ("current", "recoded"):
            candidate_id = comparison[f"{side}_candidate_id"]
            candidate = candidates[side].get(candidate_id)
            sides[side] = candidate
            row[f"{side}_candidate_id"] = candidate_id
            for key in ("status", "anchor", "strand"):
                row[f"{side}_{key}"] = None if candidate is None else candidate[key]
        for field, delta in comparison["deltas"].items():
            scalar = dict(
                row,
                scalar_field=field,
                unit=delta["unit"],
                delta_value=delta["value"],
                delta_reason=delta["reason"],
            )
            for side, candidate in sides.items():
                scalar[f"{side}_value"] = (
                    None if candidate is None else candidate["scalars"][field]["value"]
                )
            writer.writerow(scalar)
    return stream.getvalue()


def export_text(result: dict, output_format: str) -> str:
    """Serialize completely, check UTF-8 and bound bytes before any stdout write."""
    if output_format == "json":
        text = result_bytes(result).decode("ascii")
    elif output_format == "csv":
        text = csv_text(result)
    else:
        raise PairError("format must be json or csv")
    if len(text.encode("utf-8")) > LIMITS["max_result_json_bytes"]:
        raise PairError("paired export exceeds max_result_json_bytes")
    return text
