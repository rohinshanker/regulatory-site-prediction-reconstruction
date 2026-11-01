"""Bounded CSV projection of producer-owned conditional component results."""

import csv
import hashlib
import json
from collections.abc import Iterator

from regsite import conditional
from regsite.conditional_math import ConditionalError

CSV_COLUMNS = (
    "csv_schema_version",
    "row_type",
    "schema_version",
    "id",
    "profile",
    "request_sha256",
    "json_sha256",
    "model_id",
    "implementation_version",
    "source_manifest_sha256",
    "parameter_sha256",
    "convention_id",
    "backend_sha256",
    "result_status",
    "complete",
    "state_count",
    "response_present",
    "structural_cost_kcal_mol",
    "reasons_json",
    "warnings_json",
    "errors_json",
    "state_index",
    "state_id",
    "state_status",
    "state_reasons_json",
    "sequence_sha256",
    "constraint_sha256",
    "structure",
    "pairs_json",
    "fold_energy_kcal_mol",
    "efn2_energy_kcal_mol",
    "ligand_binding_kcal_mol",
    "switching_kcal_mol",
    "log_ar_max",
    "ar_max",
    "ar_conc",
    "ar_actual",
    "metastability_factor",
    "metastability_applied",
    "occupancy_mode",
    "occupancy_status",
    "occupancy_fraction",
    "mrna_free_molar",
    "ligand_free_molar",
    "complex_molar",
    "mrna_balance_error_molar",
    "ligand_balance_error_molar",
    "volume_mrna_free",
    "volume_ligand_free",
    "volume_complex",
    "volume_sum",
    "solver_iterations",
    "bracket_low_molar",
    "bracket_high_molar",
    "scaled_residual",
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _Buffer:
    """Accumulate complete UTF-8 records under the native result byte ceiling."""

    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, text: str) -> int:
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise OSError("CSV text is not UTF-8 encodable") from exc
        if len(self.data) + len(raw) > conditional.RESULT_LIMIT:
            raise ConditionalError("result_limit", "CSV exceeds result byte limit")
        self.data.extend(raw)
        return len(text)


def _response_row(response: dict) -> dict:
    occupancy = response["occupancy"]
    concentrations = occupancy["concentrations"] or {}
    volumes = occupancy["volume_fractions"] or {}
    solver = occupancy["solver"] or {}
    bracket = solver.get("bracket_molar", (None, None))
    row = {
        key: response[key]
        for key in (
            "ligand_binding_kcal_mol",
            "switching_kcal_mol",
            "log_ar_max",
            "ar_max",
            "ar_conc",
            "ar_actual",
            "metastability_factor",
            "metastability_applied",
        )
    }
    row.update(
        row_type="response",
        occupancy_mode=occupancy["mode"],
        occupancy_status=occupancy["status"],
        occupancy_fraction=occupancy["fraction"],
        volume_mrna_free=volumes.get("mrna_free"),
        volume_ligand_free=volumes.get("ligand_free"),
        volume_complex=volumes.get("complex"),
        volume_sum=volumes.get("sum"),
        solver_iterations=solver.get("iterations"),
        bracket_low_molar=bracket[0],
        bracket_high_molar=bracket[1],
        scaled_residual=solver.get("scaled_residual"),
    )
    row.update(
        (key, concentrations.get(key))
        for key in (
            "mrna_free_molar",
            "ligand_free_molar",
            "complex_molar",
            "mrna_balance_error_molar",
            "ligand_balance_error_molar",
        )
    )
    return row


def _rows(result: dict, json_sha256: str) -> Iterator[dict]:
    model = result["model"]
    backend = model["backend"]
    shared = {
        "csv_schema_version": "conditional-csv-1",
        "schema_version": result["schema_version"],
        "id": result["id"],
        "profile": result["profile"],
        "request_sha256": result["request_sha256"],
        "json_sha256": json_sha256,
        "model_id": model["id"],
        "implementation_version": model["implementation_version"],
        "source_manifest_sha256": model["source_manifest_sha256"],
        "parameter_sha256": model["parameter_sha256"],
        "convention_id": model["convention_id"],
        "backend_sha256": None
        if backend is None
        else hashlib.sha256(_json(backend).encode("ascii")).hexdigest(),
        "result_status": result["status"],
        "complete": result["complete"],
    }
    yield {
        **shared,
        "row_type": "result",
        "state_count": len(result["states"]),
        "response_present": result["response"] is not None,
        "structural_cost_kcal_mol": result["structural_cost_kcal_mol"],
        "reasons_json": result["reasons"],
        "warnings_json": result["warnings"],
        "errors_json": result["errors"],
    }
    for index, state in enumerate(result["states"]):
        yield {
            **shared,
            "row_type": "state",
            "state_index": index,
            "state_id": state["id"],
            "state_status": state["status"],
            "state_reasons_json": state["reasons"],
            "sequence_sha256": state["sequence_sha256"],
            "constraint_sha256": state["constraint_sha256"],
            "structure": state["structure"],
            "pairs_json": state["pairs"],
            "fold_energy_kcal_mol": state["fold_energy_kcal_mol"],
            "efn2_energy_kcal_mol": state["efn2_energy_kcal_mol"],
        }
    if result["response"] is not None:
        yield {**shared, **_response_row(result["response"])}


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return _json(value)
    return str(value)


def csv_bytes(result: dict) -> bytes:
    """Project one producer result completely, retaining its exact JSON hash.

    This is not an external result validator or predictor. Both native JSON and
    CSV obey the existing result cap. Null/inapplicable cells are empty; native
    empty arrays remain []. Unencodable UTF-8 text raises OSError before output.
    """
    native = conditional.result_bytes(result)
    buffer = _Buffer()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in _rows(result, hashlib.sha256(native).hexdigest()):
        writer.writerow([_cell(row.get(column)) for column in CSV_COLUMNS])
    return bytes(buffer.data)
