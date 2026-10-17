"""Bounded JSON request loading and portable result serialization."""

import csv
import json
from typing import TextIO

from regsite.sequence import InputError

MAX_DOCUMENT_CHARACTERS = 2_000_000
MAX_BATCH_RECORDS = 100
CSV_FIELDS = (
    "id",
    "status",
    "site_status",
    "start",
    "end",
    "strand",
    "codon",
    "tir",
    "dG_total",
    "reason",
)


def _reject_constant(value: str) -> None:
    raise InputError(f"non-finite JSON number is not allowed: {value}")


def load_requests(stream: TextIO) -> list[object]:
    """Load one request or a bounded list; validation remains per record.

    An invalid record in an otherwise readable batch does not prevent valid
    records being evaluated. Malformed or oversized documents fail as a whole.
    """
    text = stream.read(MAX_DOCUMENT_CHARACTERS + 1)
    if len(text) > MAX_DOCUMENT_CHARACTERS:
        raise InputError("JSON input exceeds 2,000,000 characters")
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise InputError(f"invalid JSON: {exc}") from exc
    records = value if isinstance(value, list) else [value]
    if not 1 <= len(records) <= MAX_BATCH_RECORDS:
        raise InputError("a batch must contain 1–100 records")
    return records


def write_json(value: object, stream: TextIO) -> None:
    """Write deterministic JSON, rejecting NaN/Infinity instead of exporting it."""
    json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def write_csv(records: list[dict], stream: TextIO) -> None:
    """Write one row per site, retaining a row for records without any site.

    CSV is a compact summary. JSON is the complete provenance/energy/structure
    format. Coordinates use the normalized input sequence orientation.
    """
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        sites = record.get("sites", [])
        for site in sites or [{}]:
            interval = site.get("start_codon", {})
            energies = site.get("energies") or {}
            writer.writerow(
                {
                    "id": record.get("id", ""),
                    "status": record["status"],
                    "site_status": site.get("status", ""),
                    "start": interval.get("start", ""),
                    "end": interval.get("end", ""),
                    "strand": interval.get("strand", ""),
                    "codon": site.get("codon", ""),
                    "tir": site.get("tir", ""),
                    "dG_total": energies.get("dG_total", ""),
                    "reason": site.get("reason", record.get("reason", "")),
                }
            )
