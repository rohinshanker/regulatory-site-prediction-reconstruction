"""Bounded CSV projection of producer-owned supplied-rate drafting results."""

import csv
import hashlib
import json
from collections.abc import Iterator

from regsite import drafting_io
from regsite.drafting_io import DraftingInputError

CSV_COLUMNS = (
    "csv_schema_version",
    "row_type",
    "schema_version",
    "model_id",
    "implementation_version",
    "source_doi",
    "theory_sha256",
    "backend_json",
    "rate_origin",
    "request_sha256",
    "prediction_sha256",
    "json_sha256",
    "result_status",
    "result_reason",
    "requested_records",
    "evaluated_records",
    "successful_records",
    "complete",
    "warnings_json",
    "record_index",
    "record_id",
    "record_status",
    "record_reason",
    "rate_unit",
    "rate_provenance",
    "a1",
    "a2",
    "a_fold",
    "a_elong",
    "accessible_value",
    "accessible_ln_value",
    "accessible_representation",
    "folded_value",
    "folded_ln_value",
    "folded_representation",
    "occupied_value",
    "occupied_ln_value",
    "occupied_representation",
    "throughput_unit",
    "throughput_value",
    "throughput_ln_value",
    "throughput_representation",
)


class _Buffer:
    """Accumulate complete UTF-8 CSV rows under the native byte ceiling."""

    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, text: str) -> int:
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise DraftingInputError("csv_text_not_utf8") from exc
        if len(self.data) + len(raw) > drafting_io.OUTPUT_LIMIT:
            raise DraftingInputError("output_byte_limit")
        self.data.extend(raw)
        return len(text)


def _rows(result: dict, json_sha256: str) -> Iterator[dict]:
    model = result["model"]
    shared = {
        "csv_schema_version": "drafting-csv-1",
        "schema_version": result["schema_version"],
        "model_id": model["id"],
        "implementation_version": model["implementation_version"],
        "source_doi": model["source_doi"],
        "theory_sha256": model["theory_sha256"],
        "backend_json": model["backend"],
        "rate_origin": model["rate_origin"],
        "request_sha256": result["request_sha256"],
        "prediction_sha256": result["prediction_sha256"],
        "json_sha256": json_sha256,
        "result_status": result["status"],
        "result_reason": result["reason"],
        "warnings_json": result["warnings"],
        **(result["coverage"] or {}),
    }
    yield {**shared, "row_type": "result"}
    for record in result["records"]:
        supplied = record["input"] or {}
        throughput = record["throughput"] or {}
        row = {
            **shared,
            "row_type": "record",
            "record_index": record["index"],
            "record_id": record["id"],
            "record_status": record["status"],
            "record_reason": record["reason"],
            "rate_unit": supplied.get("rate_unit"),
            "rate_provenance": supplied.get("rate_provenance"),
            "throughput_unit": throughput.get("unit"),
            **supplied.get("rates", {}),
        }
        quantities = {
            **(record["occupancies"] or {}),
            "throughput": throughput.get("quantity", {}),
        }
        for name, quantity in quantities.items():
            row.update((f"{name}_{key}", value) for key, value in quantity.items())
        yield row


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return str(value)


def csv_bytes(result: dict) -> bytes:
    """Project a producer result completely and bind its authoritative JSON bytes.

    This is not a public result validator or predictor. Native JSON and CSV each
    obey the existing result cap; encoding failure raises DraftingInputError
    before output. Nulls are blank and native numerical triples remain distinct.
    """
    native = drafting_io.result_bytes(result)
    buffer = _Buffer()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in _rows(result, hashlib.sha256(native).hexdigest()):
        writer.writerow([_cell(row.get(column)) for column in CSV_COLUMNS])
    return bytes(buffer.data)
