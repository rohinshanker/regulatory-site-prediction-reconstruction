"""Strict public conditional-aptamer JSON boundary and component orchestration."""

import json
import math
import re
import time
from importlib.resources import files
from pathlib import Path
from typing import cast

from regsite import __version__
from regsite.conditional_backend import (
    digest,
    fold_state,
    new_state,
    refuse,
    validate_demands,
    verify_backend,
)
from regsite.conditional_math import (
    ConditionalError,
    check_deadline,
    difference,
    evaluate_response,
)

PARAMETER_SHA256 = "551ca4da7af67303b74e494f56d4cf9b643b32a449792a8bb54c5b41cce662e8"
SOURCE_MANIFEST_SHA256 = (
    "ac4d7be48ba856dc6a713829425b584ffd55551743b10c51049de0ec70dc2f6e"
)
CONVENTION_ID = (
    "natural_logs_equal_rna_complex_volume_explicit_molar_standard_"
    "strict_positive_zero_uncorrected_binary64_certified_min_total_bracket_2"
)
PROFILES = {"canonical_structure_pair", "supplied_energy_response"}
INPUT_LIMIT = 65_536
RESULT_LIMIT = 1_000_000


def invalid_result(code: str = "invalid_json", message: str = "Invalid JSON") -> dict:
    """Create the exact result shape for a transport-level rejection.

    Transport callers must supply short fixed diagnostics, without raw request
    text, local paths, or credentials. Parsed requests go to predict_conditional.
    """
    result: dict = dict(
        schema_version="conditional-aptamer-result-1",
        id=None,
        profile=None,
        input=None,
        provenance=None,
        settings=None,
        model=dict(
            id="conditional-aptamer-1",
            implementation_version=__version__,
            source_manifest_sha256=SOURCE_MANIFEST_SHA256,
            parameter_sha256=PARAMETER_SHA256,
            backend=None,
            convention_id=CONVENTION_ID,
        ),
        request_sha256=None,
        status="invalid_input",
        reasons=[],
        warnings=[],
        errors=[],
        states=[],
        structural_cost_kcal_mol=None,
        response=None,
        complete=False,
    )
    _error(result, ConditionalError(code, message, "invalid_input"))
    return result


def result_bytes(result: dict) -> bytes:
    """Serialize authoritative finite JSON, enforcing the inclusive result cap."""
    raw = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if len(raw) > RESULT_LIMIT:
        raise ConditionalError(
            "result_limit", "Result exceeds 1000000 authoritative bytes"
        )
    return raw


def _error(result: dict, error: ConditionalError) -> None:
    if error.code not in result["reasons"]:
        result["reasons"].append(error.code)
        result["errors"].append({"code": error.code, "message": str(error)})
    priorities = {
        "ok": 0,
        "no_mrna": 1,
        "failed": 2,
        "unsupported": 3,
        "invalid_input": 4,
    }
    if priorities[error.status] >= priorities[result["status"]]:
        result["status"] = error.status


def _warn(result: dict, code: str, message: str) -> None:
    if not any(warning["code"] == code for warning in result["warnings"]):
        result["warnings"].append({"code": code, "message": message})


def _parsed_bytes(document: object) -> bytes:
    count = 0

    def walk(value, depth):
        nonlocal count
        count += 1
        if depth > 16 or count > 20_000:
            refuse("input_limit", "JSON nesting or node limit exceeded")
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str:
                    refuse("invalid_json", "JSON object keys must be strings")
                walk(key, depth + 1)
                walk(child, depth + 1)
        elif type(value) is list:
            for child in value:
                walk(child, depth + 1)
        elif type(value) is str:
            if len(value) > INPUT_LIMIT:
                refuse("input_limit", "JSON string exceeds input byte limit")
        elif type(value) is float:
            if not math.isfinite(value):
                refuse("invalid_json", "JSON numbers must be finite")
        elif type(value) is int:
            if value.bit_length() > 200_000:
                refuse("input_limit", "JSON integer exceeds input byte limit")
        elif value is not None and type(value) is not bool:
            refuse("invalid_json", "Only raw JSON-compatible types are accepted")

    walk(document, 0)
    chunks, size = [], 0
    try:
        for chunk in json.JSONEncoder(
            sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).iterencode(document):
            raw = chunk.encode("utf-8")
            size += len(raw)
            if size > INPUT_LIMIT:
                refuse("input_limit", "Request exceeds 65536 canonical bytes")
            chunks.append(raw)
    except ValueError as exc:
        if isinstance(exc, ConditionalError):
            raise
        refuse("invalid_json", "Request cannot be serialized as bounded JSON")
    return b"".join(chunks)


def _object(value, keys: str) -> dict:
    if type(value) is not dict:
        refuse("invalid_object", "Expected a JSON object")
    wanted = set(keys.split())
    if set(value) - wanted:
        refuse("unexpected_field", "Unknown object field")
    if wanted - set(value):
        refuse("missing_field", "Required field absent")
    return value


def _text(value, maximum: int = 128) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        refuse("invalid_string", "Expected a nonempty bounded string")
    return value


def _number(value, lower=None, upper=None, positive: bool = False) -> float:
    try:
        number = float(value) if type(value) in (int, float) else math.nan
    except OverflowError:
        number = math.nan
    if (
        not math.isfinite(number)
        or (positive and number <= 0)
        or (lower is not None and number < lower)
        or (upper is not None and number > upper)
    ):
        refuse(
            "invalid_number",
            "Number is nonfinite, boolean, or outside its declared bounds",
        )
    return number


def _integer(value, lower: int, upper: int) -> int:
    if type(value) is not int:
        refuse("invalid_position", "Expected a genuine integer")
    if not lower <= value <= upper:
        refuse("position_out_of_range", "Integer outside declared bounds")
    return value


def _profile(value) -> str:
    value = _text(value)
    if value not in PROFILES:
        refuse("unsupported_profile", "Conditional profile is not admitted", True)
    return value


def _provenance(value) -> dict:
    value = _object(value, "kind reference")
    if value["kind"] not in ("user_supplied", "synthetic"):
        refuse(
            "invalid_provenance", "Provenance kind must be user_supplied or synthetic"
        )
    _text(value["reference"], 1024)
    return value


def _mode(value: dict) -> str:
    if "mode" not in value:
        refuse("missing_field", "Required mode field absent")
    return _text(value["mode"])


def _settings(value, profile: str) -> dict:
    structural = profile == "canonical_structure_pair"
    value = _object(
        value,
        "seconds_per_job seconds_total"
        if structural
        else "seconds_total max_iterations",
    )
    total = _number(
        value["seconds_total"], upper=480 if structural else 30, positive=True
    )
    if structural:
        per_job = _number(
            value["seconds_per_job"], upper=min(120, total), positive=True
        )
        return {"seconds_total": total, "seconds_per_job": per_job}
    return {
        "seconds_total": total,
        "max_iterations": _integer(value["max_iterations"], 1, 256),
    }


def _structural_input(value) -> tuple[dict, dict]:
    value = _object(value, "sequence aptamer temperature_kelvin")
    sequence = _text(value["sequence"], 200)
    if any(base not in "ACGU" for base in sequence):
        refuse("unsupported_base", "Sequence must contain uppercase ACGU only")
    temperature = _number(value["temperature_kelvin"], positive=True)
    aptamer = _object(value["aptamer"], "id range constraint")
    _text(aptamer["id"])
    span = aptamer["range"]
    if type(span) is not list or len(span) != 2:
        refuse("invalid_range", "Aptamer requires a half-open range")
    start = _integer(span[0], 0, len(sequence) - 1)
    end = _integer(span[1], start + 1, len(sequence))
    constraint = aptamer["constraint"]
    if type(constraint) is not dict:
        refuse("invalid_object", "Constraint must be an object")
    mode = _mode(constraint)
    pairs, unpaired = [], []
    if mode == "full":
        _object(constraint, "mode structure")
        structure = _text(constraint["structure"], 200)
        if len(structure) != end - start:
            refuse("structure_length_mismatch", "Structure must match aptamer span")
        stack = []
        for point, symbol in enumerate(structure, start):
            if symbol == "(":
                stack.append(point)
            elif symbol == ")":
                if not stack:
                    refuse("unbalanced_structure", "Unbalanced parentheses")
                pairs.append([stack.pop(), point])
            elif symbol == ".":
                unpaired.append(point)
            else:
                refuse(
                    "unsupported_structure_symbol",
                    "Only nested (). notation is admitted",
                    True,
                )
        if stack:
            refuse("unbalanced_structure", "Unbalanced parentheses")
    elif mode == "partial":
        _object(constraint, "mode pairs unpaired")
        if (
            type(constraint["pairs"]) is not list
            or type(constraint["unpaired"]) is not list
        ):
            refuse("invalid_constraint", "Partial demands must be arrays")
        for pair in constraint["pairs"]:
            if type(pair) is not list or len(pair) != 2:
                refuse("invalid_pair", "Pairs require two relative points")
            pairs.append([start + _integer(p, 0, end - start - 1) for p in pair])
        unpaired = [
            start + _integer(p, 0, end - start - 1) for p in constraint["unpaired"]
        ]
    else:
        refuse("invalid_mode", "Constraint mode is not admitted", True)
    demands = validate_demands(sequence, pairs, unpaired)
    if temperature != 310.15:
        refuse(
            "unsupported_temperature",
            "Original canonical fixtures admit only 310.15 K",
            True,
        )
    return value, demands


def _basis(value) -> dict:
    value = _object(value, "rna ribosome")
    for basis in value.values():
        _object(
            basis, "source_id model_id parameter_sha256 backend_sha256 sequence_sha256"
        )
        _text(basis["source_id"])
        if basis["model_id"] is not None:
            _text(basis["model_id"])
        for key in ("parameter_sha256", "backend_sha256", "sequence_sha256"):
            if basis[key] is not None and (
                type(basis[key]) is not str
                or re.fullmatch("[0-9a-f]{64}", basis[key]) is None
            ):
                refuse(
                    "invalid_hash",
                    "Energy identities require lowercase SHA-256 or null",
                )
    return value


def _response_input(value) -> dict:
    value = _object(
        value,
        "temperature_kelvin beta_mol_per_kcal energies energy_basis affinity occupancy",
    )
    _number(value["temperature_kelvin"], positive=True)
    _number(value["beta_mol_per_kcal"], positive=True)
    energies = _object(
        value["energies"],
        "rna_off_kcal_mol rna_on_kcal_mol ribosome_off_kcal_mol ribosome_on_kcal_mol",
    )
    for energy in energies.values():
        _number(energy)
    if energies["rna_on_kcal_mol"] < energies["rna_off_kcal_mol"]:
        refuse(
            "negative_structural_cost",
            "ON-state subset minimum cannot have lower RNA energy",
            True,
        )
    _basis(value["energy_basis"])
    affinity = value["affinity"]
    if type(affinity) is not dict:
        refuse("invalid_object", "Affinity must be an object")
    mode = _mode(affinity)
    if mode == "kd":
        _object(affinity, "mode kd_molar standard_molar")
        _number(affinity["kd_molar"], positive=True)
    elif mode == "delta_g":
        _object(affinity, "mode delta_g_kcal_mol standard_molar")
        _number(affinity["delta_g_kcal_mol"])
    else:
        refuse("unsupported_affinity", "Affinity mode not admitted", True)
    _number(affinity["standard_molar"], positive=True)
    occupancy = value["occupancy"]
    if type(occupancy) is not dict:
        refuse("invalid_object", "Occupancy must be an object")
    mode = _mode(occupancy)
    if mode == "supplied_fraction":
        _object(occupancy, "mode fraction")
        _number(occupancy["fraction"], lower=0, upper=1)
    elif mode == "published2015_volume":
        _object(
            occupancy,
            "mode mrna_total_molar ligand_total_molar solvent_molar "
            "mrna_relative_volume ligand_relative_volume",
        )
        for name in ("mrna_total_molar", "ligand_total_molar"):
            _number(occupancy[name], lower=0)
        for name in ("solvent_molar", "mrna_relative_volume", "ligand_relative_volume"):
            _number(occupancy[name], positive=True)
    else:
        refuse("unsupported_occupancy", "Occupancy mode not admitted", True)
    return value


def predict_conditional(
    document: object, backend_root: str | Path | None = None
) -> dict:
    """Validate a raw finite JSON request, then compute its admitted components."""
    started = time.monotonic()
    result = invalid_result()
    result.update(status="ok", reasons=[], errors=[])
    try:
        raw = _parsed_bytes(document)
    except ConditionalError as exc:
        _error(result, exc)
        return result
    result["request_sha256"] = digest(raw)
    document = json.loads(raw)
    if type(document) is not dict:
        _error(
            result,
            ConditionalError(
                "invalid_object", "Request must be an object", "invalid_input"
            ),
        )
        return result
    try:
        _object(document, "schema_version id profile input provenance settings")
        if document["schema_version"] != "conditional-aptamer-request-1":
            refuse("unsupported_schema", "Request schema is not admitted", True)
    except ConditionalError as exc:
        _error(result, exc)
    for key, validator in (
        ("id", _text),
        ("profile", _profile),
        ("provenance", _provenance),
    ):
        try:
            result[key] = validator(document.get(key))
        except ConditionalError as exc:
            _error(result, exc)
    demands: dict | None = None
    if result["profile"] is not None:
        for key in ("settings", "input"):
            try:
                if key == "settings":
                    result[key] = _settings(document.get(key), result["profile"])
                elif result["profile"] == "canonical_structure_pair":
                    result[key], demands = _structural_input(document.get(key))
                else:
                    result[key] = _response_input(document.get(key))
            except ConditionalError as exc:
                _error(result, exc)
    if result["errors"]:
        return result
    data, settings = result["input"], result["settings"]
    deadline = started + settings["seconds_total"]
    _warn(
        result,
        "no_native_calibration",
        "No native-host or biological accuracy calibration is established",
    )
    try:
        check_deadline(deadline)
        parameter_raw = (
            files("regsite").joinpath("data/conditional-parameters-1.json").read_bytes()
        )
        if digest(parameter_raw) != PARAMETER_SHA256:
            raise ConditionalError(
                "parameter_integrity", "Conditional parameter identity mismatch"
            )
        parameters = json.loads(parameter_raw)
        if result["profile"] == "supplied_energy_response":
            _warn(
                result,
                "supplied_energies",
                "Energy pairs and their common bases are caller assertions",
            )
            _warn(
                result,
                "assumed_occupancy",
                "Occupancy fractions or volume/concentration inputs are supplied "
                "assumptions",
            )
            _warn(
                result,
                "piecewise_zero_boundary",
                "Strict-positive correction leaves zero uncorrected; the positive-side "
                "limit is discontinuous",
            )
            _warn(
                result,
                "affinity_beta_convention",
                "An explicit affinity standard does not equate physical Kd with "
                "apparent-beta volume occupancy",
            )
            if any(
                value is None
                for basis in data["energy_basis"].values()
                for value in basis.values()
            ):
                _warn(
                    result,
                    "unverified_energy_basis",
                    "Some common energy-basis identities are unknown",
                )
            response, cost, errors = evaluate_response(data, settings, deadline)
            result.update(response=response, structural_cost_kcal_mol=cost)
            occupancy = response["occupancy"]
            if occupancy["status"] == "no_mrna":
                result.update(status="no_mrna", reasons=["no_mrna"])
            if (
                occupancy["volume_fractions"] is not None
                and occupancy["volume_fractions"]["sum"] > 1
            ):
                _warn(
                    result,
                    "volume_sum_above_one",
                    "Literal volume fractions sum above one; no extra packing law is "
                    "imposed",
                )
            for error in errors:
                _error(result, error)
        else:
            demands = cast(dict, demands)
            sequence = data["sequence"]
            _warn(
                result,
                "published_backend_difference",
                "Original RNAstructure canonical folding differs from the published "
                "ViennaRNA configurations",
            )
            _warn(
                result,
                "structural_component_only",
                "Structural feasibility does not establish ligand binding or switching "
                "efficacy",
            )
            if not demands["pairs"] and not demands["unpaired"]:
                _warn(
                    result,
                    "empty_constraint",
                    "Empty partial demands are a no-op control",
                )
            states = [
                new_state("unconstrained", sequence, None),
                new_state("constraint_compatible", sequence, demands),
            ]
            result["states"] = states
            root, identity = verify_backend(backend_root, parameters, deadline)
            result["model"]["backend"] = identity
            for state, required in zip(states, (None, demands), strict=True):
                try:
                    fold_state(root, sequence, required, state, settings, deadline)
                    if state["fold_energy_kcal_mol"] is None:
                        _warn(
                            result,
                            "fold_energy_absent",
                            "A Fold header energy is absent; it is not assumed zero",
                        )
                    elif state["fold_energy_kcal_mol"] != state["efn2_energy_kcal_mol"]:
                        _warn(
                            result,
                            "fold_efn2_difference",
                            "Fold and simple efn2 energies differ within the same "
                            "backend",
                        )
                except (ConditionalError, OSError, UnicodeError, ValueError) as exc:
                    error = (
                        exc
                        if isinstance(exc, ConditionalError)
                        else ConditionalError(
                            "backend_output", "Backend output is missing or malformed"
                        )
                    )
                    state.update(status="failed", reasons=[error.code])
                    _error(result, error)
                    break
            if all(state["status"] == "ok" for state in states):
                cost = difference(
                    states[1]["efn2_energy_kcal_mol"], states[0]["efn2_energy_kcal_mol"]
                )
                if cost < 0:
                    raise ConditionalError(
                        "negative_structural_cost",
                        "Constrained energy is below unconstrained energy",
                    )
                result["structural_cost_kcal_mol"] = cost
        check_deadline(deadline)
    except (ConditionalError, OSError) as exc:
        _error(
            result,
            exc
            if isinstance(exc, ConditionalError)
            else ConditionalError(
                "backend_unavailable", "Required local resource unavailable"
            ),
        )
    result["complete"] = result["status"] == "ok"
    result_bytes(result)
    return result
