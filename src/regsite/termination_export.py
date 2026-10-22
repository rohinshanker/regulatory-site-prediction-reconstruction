"""Bounded tabular projection of producer-owned intrinsic-termination results."""

import csv
from collections.abc import Iterator

from regsite import termination_io
from regsite.termination_io import TerminationInputError, canonical_hash

CSV_COLUMNS = (
    "csv_schema_version",
    "row_type",
    "schema_version",
    "model_id",
    "implementation_version",
    "model_sha256",
    "request_sha256",
    "prediction_sha256",
    "result_sha256",
    "result_status",
    "result_reason",
    "record_index",
    "record_id",
    "record_status",
    "record_reason",
    "sequence_length",
    "sequence_sha256",
    "attempted",
    "candidate_count",
    "candidate_id",
    "candidate_status",
    "coordinate_system",
    "strand",
    "hairpin_start",
    "hairpin_end",
    "tail_start",
    "tail_end",
    "confidence",
    "hairpin_score",
    "tail_score",
    "native_id",
    "native_context",
    "native_printed_confidence",
    "native_notes",
)
Cell = str | int | bool | None


class _Buffer:
    """Accumulate complete UTF-8 CSV rows without exceeding the output ceiling."""

    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, text: str) -> int:
        raw = text.encode("utf-8")
        if len(self.data) + len(raw) > termination_io.OUTPUT_LIMIT:
            raise TerminationInputError("output byte limit exceeded")
        self.data.extend(raw)
        return len(text)


def _rows(result: dict) -> Iterator[dict[str, Cell]]:
    model = result["model"]
    envelope = {
        "csv_schema_version": "termination-csv-1",
        "schema_version": result["schema_version"],
        "model_id": model["id"],
        "implementation_version": model["implementation_version"],
        "model_sha256": canonical_hash(model),
        "request_sha256": result["request_sha256"],
        "prediction_sha256": result["prediction_sha256"],
        "result_sha256": result["result_sha256"],
        "result_status": result["status"],
        "result_reason": result["reason"],
        "coordinate_system": "fragment-relative-0-based-half-open",
    }
    yield {**envelope, "row_type": "envelope"}
    for record in result["records"]:
        input_metadata = record["input"] or {}
        candidates = record["candidates"]
        shared = {
            **envelope,
            "record_index": record["index"],
            "record_id": record["id"],
            "record_status": record["status"],
            "record_reason": record["reason"],
            "sequence_length": input_metadata.get("sequence_length"),
            "sequence_sha256": input_metadata.get("sequence_sha256"),
            "attempted": record["attempted"],
            "candidate_count": None if candidates is None else len(candidates),
        }
        yield {**shared, "row_type": "record"}
        for candidate in candidates or []:
            yield {
                **shared,
                "row_type": "candidate",
                "candidate_id": candidate["candidate_id"],
                "candidate_status": candidate["status"],
                "strand": candidate["strand"],
                "hairpin_start": candidate["hairpin"]["start"],
                "hairpin_end": candidate["hairpin"]["end"],
                "tail_start": candidate["tail"]["start"],
                "tail_end": candidate["tail"]["end"],
                "confidence": candidate["confidence"],
                "hairpin_score": candidate["hairpin_score"],
                "tail_score": candidate["tail_score"],
                "native_id": candidate["native"]["id"],
                "native_context": candidate["native"]["context"],
                "native_printed_confidence": candidate["native"]["printed_confidence"],
                "native_notes": candidate["native"]["notes"],
            }


def _cell(value: Cell) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def csv_bytes(result: dict) -> bytes:
    """Serialize a producer result completely; preserve hashes, rows and nulls.

    This projection does not import, validate or re-score external results. Null
    and inapplicable cells are empty; row types and statuses retain their meaning.
    Raises TerminationInputError if the encoded CSV exceeds the JSON output cap.
    """
    buffer = _Buffer()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in _rows(result):
        writer.writerow([_cell(row.get(column)) for column in CSV_COLUMNS])
    return bytes(buffer.data)
