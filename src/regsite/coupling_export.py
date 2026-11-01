"""Bounded, identity-bound CSV projection of producer-owned coupling results."""

import csv
import hashlib
import json
from collections.abc import Iterator

from regsite import coupling_io
from regsite.coupling_io import CouplingInputError

CSV_COLUMNS = (
    "csv_schema_version",
    "row_type",
    "schema_version",
    "model_id",
    "implementation_version",
    "model_sha256",
    "request_sha256",
    "prediction_sha256",
    "json_sha256",
    "result_status",
    "result_reason",
    "seconds_total",
    "requested_records",
    "returned_records",
    "successful_records",
    "failed_or_unsupported_records",
    "not_evaluated_records",
    "warnings_json",
    "record_index",
    "record_id",
    "record_status",
    "record_reason",
    "coordinate_system",
    "strand",
    "sequence_length",
    "sequence_sha256",
    "oriented_sequence_sha256",
    "distance_nt",
    "upstream_id",
    "upstream_start",
    "upstream_end",
    "upstream_oriented_start",
    "upstream_oriented_end",
    "upstream_start_codon",
    "upstream_stop_codon",
    "downstream_id",
    "downstream_start",
    "downstream_end",
    "downstream_oriented_start",
    "downstream_oriented_end",
    "downstream_start_codon",
    "downstream_stop_codon",
    "upstream_total_kcal_mol",
    "downstream_independent_total_kcal_mol",
    "beta_mol_per_kcal",
    "energy_provenance",
    "coefficient",
    "upstream_independent_value",
    "upstream_independent_log_value",
    "downstream_independent_value",
    "downstream_independent_log_value",
    "reinitiation_contribution_value",
    "reinitiation_contribution_log_value",
    "downstream_total_value",
    "downstream_total_log_value",
    "fold_change_value",
    "fold_change_log_value",
    "unfolding_correction",
)


class _Buffer:
    """Accumulate complete UTF-8 CSV rows under the native byte ceiling."""

    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, text: str) -> int:
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise CouplingInputError("CSV text is not UTF-8 encodable") from exc
        if len(self.data) + len(raw) > coupling_io.OUTPUT_LIMIT:
            raise CouplingInputError("output byte limit exceeded")
        self.data.extend(raw)
        return len(text)


def _rows(result: dict, json_sha256: str) -> Iterator[dict]:
    coverage = result["coverage"] or {}
    shared = {
        "csv_schema_version": "coupling-csv-1",
        "schema_version": result["schema_version"],
        "model_id": result["model"]["id"],
        "implementation_version": result["model"]["implementation_version"],
        "model_sha256": coupling_io.canonical_hash(result["model"]),
        "request_sha256": result["request_sha256"],
        "prediction_sha256": result["prediction_sha256"],
        "json_sha256": json_sha256,
        "result_status": result["status"],
        "result_reason": result["reason"],
        "seconds_total": (result["settings"] or {}).get("seconds_total"),
        "warnings_json": result["warnings"],
        **{f"{key}_records": value for key, value in coverage.items()},
    }
    yield {**shared, "row_type": "result"}
    for record in result["records"]:
        geometry = record["geometry"] or {}
        energies = record["energies"] or {}
        row = {
            **shared,
            "row_type": "record",
            **{
                f"record_{key}": record[key]
                for key in ("index", "id", "status", "reason")
            },
            "coordinate_system": (
                "fragment-relative-0-based-half-open" if geometry else None
            ),
            **{
                key: geometry.get(key)
                for key in (
                    "strand",
                    "sequence_length",
                    "sequence_sha256",
                    "oriented_sequence_sha256",
                    "distance_nt",
                )
            },
            **energies,
            "energy_provenance": energies.get("provenance"),
            "coefficient": record["coefficient"],
            "unfolding_correction": record["unfolding_correction"],
        }
        for name in ("upstream", "downstream"):
            cds = geometry.get(name) or {}
            start, end = cds.get("interval", (None, None))
            oriented_start, oriented_end = cds.get("oriented_interval", (None, None))
            row.update(
                (f"{name}_{key}", value)
                for key, value in {
                    "id": cds.get("id"),
                    "start": start,
                    "end": end,
                    "oriented_start": oriented_start,
                    "oriented_end": oriented_end,
                    "start_codon": cds.get("start_codon"),
                    "stop_codon": cds.get("stop_codon"),
                }.items()
            )
        for name, quantity in (record["scores"] or {}).items():
            row.update((f"{name}_{key}", value) for key, value in quantity.items())
        yield row


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return str(value)


def csv_bytes(result: dict) -> bytes:
    """Project every producer record without modifying native hashes or values.

    This is not an external result validator. Both native JSON and complete CSV
    must fit the existing ceiling; encoding or size failures precede output.
    """
    native = coupling_io.result_bytes(result)
    buffer = _Buffer()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in _rows(result, hashlib.sha256(native).hexdigest()):
        writer.writerow([_cell(row.get(column)) for column in CSV_COLUMNS])
    return bytes(buffer.data)
