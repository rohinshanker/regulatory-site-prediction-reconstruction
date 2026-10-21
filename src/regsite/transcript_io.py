"""Strict supplied-transcript input and failure-preserving scalar exports."""

import csv
import io
import json
import math
from typing import BinaryIO

from regsite.transcript import LIMITS, TranscriptError, result_bytes


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise TranscriptError("duplicate JSON key")
        result[key] = value
    return result


def _number(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise TranscriptError("JSON numbers must be finite")
    return value


def load_request(stream: BinaryIO) -> object:
    """Bound actual received bytes before strict UTF-8 JSON decoding."""
    raw = stream.read(int(LIMITS["max_input_json_bytes"]) + 1)
    if len(raw) > LIMITS["max_input_json_bytes"]:
        raise TranscriptError("max_input_json_bytes exceeded by received input")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_number,
            parse_float=_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise TranscriptError(
            "Expected finite UTF-8 JSON without duplicate keys"
        ) from exc


CSV_COLUMNS = (
    "schema_version id request_sha256 prediction_sha256 result_status "
    "coverage_complete row_type component component_status component_reason "
    "requested returned scored missing not_evaluated incompatible annotation_id "
    "construct_start construct_end transcript_offset strand site_index status reason "
    "scalar_name unit value value_reason"
).split()


def csv_text(result: dict) -> str:
    """Retain component summaries and every candidate/scalar, including nulls.

    Full native identities, features and structures remain in the hash-bound JSON.
    CSV coordinates are on the supplied construct, never implicitly genomic.
    """
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    common = {key: result[key] for key in CSV_COLUMNS[:4]}
    common.update(
        result_status=result["status"], coverage_complete=result["coverage"]["complete"]
    )
    for name in ("rbs", "promoter"):
        component = result["components"][name]
        row = dict(
            common,
            component=name,
            component_status=component["status"],
            component_reason=component["reason"],
            **component["coverage"],
        )
        writer.writerow(dict(row, row_type="component"))
        candidates = result["cds" if name == "rbs" else "promoter_candidates"]
        for candidate in candidates:
            detail = dict(
                row,
                row_type="candidate_scalar",
                site_index=candidate["site_index"],
                status=candidate["status"],
                reason=candidate["reason"],
            )
            if name == "rbs":
                detail.update(
                    annotation_id=candidate["annotation"]["id"],
                    construct_start=candidate["annotation"]["range"][0],
                    construct_end=candidate["annotation"]["range"][1],
                    transcript_offset=candidate["transcript_offset"],
                    strand="+",
                )
            else:
                detail.update(
                    construct_start=candidate["construct_tss"],
                    construct_end=candidate["construct_tss"] + 1,
                    strand=candidate["strand"],
                )
            for key, scalar in candidate["scalars"].items():
                writer.writerow(
                    dict(
                        detail,
                        scalar_name=key,
                        unit=scalar["unit"],
                        value=scalar["value"],
                        value_reason=scalar["reason"],
                    )
                )
    return stream.getvalue()


def export_text(result: dict, output_format: str) -> str:
    """Serialize completely and enforce the output cap before writing stdout."""
    if output_format == "json":
        text = result_bytes(result).decode("ascii")
    elif output_format == "csv":
        text = csv_text(result)
    else:
        raise TranscriptError("format must be json or csv")
    if len(text.encode("utf-8")) > LIMITS["max_result_json_bytes"]:
        raise TranscriptError("transcript export exceeds max_result_json_bytes")
    return text
