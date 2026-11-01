"""Literal tabular contracts for artificial conditional component results."""

import copy
import csv
import hashlib
import io
import json
import socket
import subprocess

import pytest

from regsite import conditional, conditional_backend, conditional_math
from regsite import conditional_export as export
from regsite.conditional_math import ConditionalError

COLUMNS = tuple(
    "csv_schema_version row_type schema_version id profile request_sha256 "
    "json_sha256 model_id implementation_version source_manifest_sha256 "
    "parameter_sha256 convention_id backend_sha256 result_status complete "
    "state_count response_present structural_cost_kcal_mol reasons_json "
    "warnings_json errors_json state_index state_id state_status state_reasons_json "
    "sequence_sha256 constraint_sha256 structure pairs_json fold_energy_kcal_mol "
    "efn2_energy_kcal_mol ligand_binding_kcal_mol switching_kcal_mol log_ar_max "
    "ar_max ar_conc ar_actual metastability_factor metastability_applied "
    "occupancy_mode occupancy_status occupancy_fraction mrna_free_molar "
    "ligand_free_molar complex_molar mrna_balance_error_molar "
    "ligand_balance_error_molar volume_mrna_free volume_ligand_free volume_complex "
    "volume_sum solver_iterations bracket_low_molar bracket_high_molar "
    "scaled_residual".split()
)


def decoded(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))


def structural():
    result = conditional.invalid_result()
    result.update(
        id="artificial-structure",
        profile="canonical_structure_pair",
        request_sha256="a" * 64,
        status="ok",
        complete=True,
        reasons=[],
        errors=[],
        structural_cost_kcal_mol=0.0,
        states=[
            {
                "id": identity,
                "status": "ok",
                "reasons": [],
                "sequence_sha256": "b" * 64,
                "constraint_sha256": constraint,
                "structure": "((...))",
                "pairs": [[0, 6], [1, 5]],
                "fold_energy_kcal_mol": None,
                "efn2_energy_kcal_mol": 0.0,
                "jobs": [],
            }
            for identity, constraint in (
                ("unconstrained", None),
                ("constraint_compatible", "c" * 64),
            )
        ],
    )
    result["model"]["backend"] = {
        "fold_sha256": "d" * 64,
        "efn2_sha256": "e" * 64,
        "table_manifest_sha256": "f" * 64,
    }
    return result


def scalar():
    result = conditional.invalid_result()
    result.update(
        id="artificial-response",
        profile="supplied_energy_response",
        request_sha256="1" * 64,
        status="ok",
        complete=True,
        reasons=[],
        errors=[],
        structural_cost_kcal_mol=2.0,
        response={
            "ligand_binding_kcal_mol": -2.0,
            "switching_kcal_mol": 0.0,
            "log_ar_max": -1.3862943611198906,
            "ar_max": 0.25,
            "ar_conc": 0.25,
            "ar_actual": 0.25,
            "metastability_factor": 1.0,
            "metastability_applied": False,
            "occupancy": {
                "mode": "supplied_fraction",
                "status": "ok",
                "fraction": 1.0,
                "concentrations": None,
                "volume_fractions": None,
                "solver": None,
            },
        },
    )
    return result


def volume():
    result = scalar()
    result["response"]["occupancy"] = {
        "mode": "published2015_volume",
        "status": "ok",
        "fraction": 0.2,
        "concentrations": {
            "mrna_free_molar": 0.8,
            "ligand_free_molar": 0.8,
            "complex_molar": 0.2,
            "mrna_balance_error_molar": 0.0,
            "ligand_balance_error_molar": -0.0,
        },
        "volume_fractions": {
            "mrna_free": 0.4,
            "ligand_free": 0.2,
            "complex": 0.1,
            "sum": 0.7,
        },
        "solver": {
            "iterations": 42,
            "bracket_molar": [0.199999999999, 0.200000000001],
            "scaled_residual": -1.25e-13,
        },
    }
    return result


def test_literal_header_and_single_invalid_envelope():
    result = conditional.invalid_result()
    raw = export.csv_bytes(result)
    assert export.CSV_COLUMNS == COLUMNS and len(COLUMNS) == 55
    assert raw.startswith((",".join(COLUMNS) + "\r\n").encode())
    assert raw.endswith(b"\r\n") and not raw.startswith(b"\xef\xbb\xbf")
    rows = decoded(raw)
    assert len(rows) == 1 and rows[0]["row_type"] == "result"
    row = rows[0]
    assert row["csv_schema_version"] == "conditional-csv-1"
    assert row["schema_version"] == "conditional-aptamer-result-1"
    assert row["result_status"] == "invalid_input" and row["complete"] == "false"
    assert row["state_count"] == "0" and row["response_present"] == "false"
    assert row["request_sha256"] == row["id"] == row["profile"] == ""
    assert row["state_status"] == row["occupancy_status"] == ""
    assert json.loads(row["reasons_json"]) == ["invalid_json"]
    assert json.loads(row["errors_json"]) == result["errors"]
    assert row["warnings_json"] == "[]"


@pytest.mark.parametrize("factory", [structural, scalar, volume])
def test_complete_native_json_and_model_identities_repeat_without_mutation(factory):
    result = factory()
    before = copy.deepcopy(result)
    native = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode()
    expected_hash = hashlib.sha256(native).hexdigest()
    backend = result["model"]["backend"]
    backend_hash = (
        hashlib.sha256(
            json.dumps(backend, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if backend is not None
        else ""
    )
    raw = export.csv_bytes(result)
    assert export.csv_bytes(result) == raw and result == before
    for row in decoded(raw):
        assert row["json_sha256"] == expected_hash
        assert row["backend_sha256"] == backend_hash
        assert row["request_sha256"] == result["request_sha256"]
        assert row["model_id"] == result["model"]["id"]
        for field in (
            "implementation_version",
            "source_manifest_sha256",
            "parameter_sha256",
            "convention_id",
        ):
            assert row[field] == result["model"][field]
        assert row["profile"] == result["profile"]
    assert "prediction_sha256" not in COLUMNS and "result_sha256" not in COLUMNS


def test_structural_order_coordinates_absent_energy_and_zero():
    result = structural()
    rows = decoded(export.csv_bytes(result))
    assert [r["row_type"] for r in rows] == ["result", "state", "state"]
    assert rows[0]["state_count"] == "2"
    assert rows[0]["structural_cost_kcal_mol"] == "0.0"
    assert rows[0]["response_present"] == "false"
    for index, state in enumerate(rows[1:]):
        assert state["state_index"] == str(index)
        assert state["state_id"] == result["states"][index]["id"]
        assert state["state_status"] == "ok" and state["state_reasons_json"] == "[]"
        assert state["structure"] == "((...))"
        assert state["pairs_json"] == "[[0,6],[1,5]]"
        assert state["fold_energy_kcal_mol"] == ""
        assert state["efn2_energy_kcal_mol"] == "0.0"
        assert state["sequence_sha256"] == "b" * 64
        assert state["ar_actual"] == state["structural_cost_kcal_mol"] == ""
    assert rows[1]["constraint_sha256"] == ""
    assert rows[2]["constraint_sha256"] == "c" * 64
    result["states"].reverse()
    assert [r["state_id"] for r in decoded(export.csv_bytes(result))[1:]] == [
        "constraint_compatible",
        "unconstrained",
    ]


def test_omitted_provenance_settings_and_job_receipts_remain_hash_bound():
    result = structural()
    before = decoded(export.csv_bytes(result))
    result["provenance"] = {"kind": "synthetic", "reference": "artificial control"}
    result["settings"] = {"seconds_per_job": 1.0, "seconds_total": 4.0}
    result["states"][0]["jobs"] = [
        {
            "program": "Fold",
            "status": "ok",
            "exit_code": 0,
            "timed_out": False,
            "stdout_sha256": "2" * 64,
            "stderr_sha256": "3" * 64,
        }
    ]
    after = decoded(export.csv_bytes(result))
    expected = hashlib.sha256(conditional.result_bytes(result)).hexdigest()
    for original, changed in zip(before, after, strict=True):
        assert changed["json_sha256"] == expected
        assert original.pop("json_sha256") != changed.pop("json_sha256")
        assert original == changed


@pytest.mark.parametrize(
    "status", ["invalid_input", "unsupported", "failed", "no_mrna"]
)
def test_incomplete_results_keep_result_status_and_diagnostics(status):
    result = conditional.invalid_result("synthetic_reason", "synthetic failure")
    result["status"] = status
    row = decoded(export.csv_bytes(result))[0]
    assert row["result_status"] == status and row["complete"] == "false"
    assert json.loads(row["errors_json"]) == [
        {"code": "synthetic_reason", "message": "synthetic failure"}
    ]


def test_failed_then_unstarted_state_and_empty_vs_null_pairs_survive():
    result = structural()
    result.update(status="failed", complete=False, structural_cost_kcal_mol=None)
    result["states"][0].update(
        status="failed", reasons=["backend_timeout"], pairs=[], structure="......."
    )
    result["states"][1].update(
        status="not_run", structure=None, pairs=None, efn2_energy_kcal_mol=None
    )
    rows = decoded(export.csv_bytes(result))
    assert [r["state_status"] for r in rows] == ["", "failed", "not_run"]
    assert rows[1]["pairs_json"] == "[]" and rows[2]["pairs_json"] == ""
    assert rows[1]["state_reasons_json"] == '["backend_timeout"]'
    assert rows[2]["state_reasons_json"] == "[]"
    assert rows[2]["efn2_energy_kcal_mol"] == rows[0]["structural_cost_kcal_mol"] == ""


def test_supplied_fraction_repression_direction_and_distinct_correction():
    rows = decoded(export.csv_bytes(scalar()))
    assert [r["row_type"] for r in rows] == ["result", "response"]
    assert rows[0]["state_count"] == "0" and rows[0]["response_present"] == "true"
    row = rows[1]
    assert row["ligand_binding_kcal_mol"] == "-2.0"
    assert row["switching_kcal_mol"] == "0.0"
    assert row["log_ar_max"] == "-1.3862943611198906"
    assert row["ar_max"] == row["ar_conc"] == row["ar_actual"] == "0.25"
    assert row["metastability_factor"] == "1.0"
    assert row["metastability_applied"] == "false"
    assert row["occupancy_mode"] == "supplied_fraction"
    assert row["occupancy_status"] == "ok" and row["occupancy_fraction"] == "1.0"
    for name in COLUMNS[42:]:
        assert row[name] == ""


def test_volume_concentrations_bracket_and_native_units_are_direct_values():
    row = decoded(export.csv_bytes(volume()))[1]
    expected = {
        "occupancy_mode": "published2015_volume",
        "occupancy_fraction": "0.2",
        "mrna_free_molar": "0.8",
        "ligand_free_molar": "0.8",
        "complex_molar": "0.2",
        "mrna_balance_error_molar": "0.0",
        "ligand_balance_error_molar": "-0.0",
        "volume_mrna_free": "0.4",
        "volume_ligand_free": "0.2",
        "volume_complex": "0.1",
        "volume_sum": "0.7",
        "solver_iterations": "42",
        "bracket_low_molar": "0.199999999999",
        "bracket_high_molar": "0.200000000001",
        "scaled_residual": "-1.25e-13",
    }
    assert {key: row[key] for key in expected} == expected


def test_failed_numeric_result_preserves_partial_log_bracket_and_null_boolean():
    result = volume()
    result.update(status="failed", complete=False, reasons=["numerical_range"])
    response = result["response"]
    response.update(
        log_ar_max=710.0,
        ar_max=None,
        ar_conc=None,
        ar_actual=None,
        switching_kcal_mol=None,
        metastability_factor=None,
        metastability_applied=None,
    )
    response["occupancy"].update(status="failed", fraction=None)
    row = decoded(export.csv_bytes(result))[1]
    assert row["result_status"] == row["occupancy_status"] == "failed"
    assert row["log_ar_max"] == "710.0" and row["ligand_binding_kcal_mol"] == "-2.0"
    assert row["ar_max"] == row["ar_conc"] == row["ar_actual"] == ""
    assert row["switching_kcal_mol"] == row["metastability_applied"] == ""
    assert row["occupancy_fraction"] == ""
    assert row["solver_iterations"] == "42" and row["scaled_residual"] == "-1.25e-13"


def test_no_mrna_keeps_real_zero_concentrations_and_undefined_ratios():
    result = volume()
    result.update(status="no_mrna", complete=False, reasons=["no_mrna"])
    response = result["response"]
    response.update(ar_conc=None, ar_actual=None)
    occupancy = response["occupancy"]
    occupancy.update(status="no_mrna", fraction=None)
    occupancy["concentrations"].update(mrna_free_molar=0.0, complex_molar=0.0)
    occupancy["solver"] = dict(
        iterations=0, bracket_molar=[0.0, 0.0], scaled_residual=None
    )
    row = decoded(export.csv_bytes(result))[1]
    assert row["occupancy_status"] == row["result_status"] == "no_mrna"
    assert row["occupancy_fraction"] == row["ar_conc"] == row["ar_actual"] == ""
    assert row["mrna_free_molar"] == row["complex_molar"] == "0.0"
    assert row["solver_iterations"] == "0" and row["bracket_low_molar"] == "0.0"
    assert row["bracket_high_molar"] == "0.0" and row["scaled_residual"] == ""


def test_true_correction_zero_fraction_and_extreme_finite_decimal_spelling():
    result = scalar()
    result["response"].update(
        metastability_applied=True,
        metastability_factor=5e-324,
        ar_max=1.7976931348623157e308,
    )
    result["response"]["occupancy"]["fraction"] = 0.0
    row = decoded(export.csv_bytes(result))[1]
    assert row["metastability_applied"] == "true"
    assert row["metastability_factor"] == "5e-324"
    assert float(row["ar_max"]) == 1.7976931348623157e308
    assert row["occupancy_fraction"] == "0.0"


def test_quotes_cr_lf_unicode_diagnostics_and_order_round_trip():
    result = conditional.invalid_result()
    result["id"] = 'µ,"control"\r\nsecond\rthird\nfourth'
    result["reasons"] = ["z_reason", "a_reason"]
    result["warnings"] = [
        {"code": "z", "message": 'β,"quoted"\r\nline'},
        {"code": "a", "message": ""},
    ]
    raw = export.csv_bytes(result)
    assert 'µ,""control""\r\nsecond'.encode() in raw
    row = decoded(raw)[0]
    assert row["id"] == result["id"]
    assert json.loads(row["warnings_json"]) == result["warnings"]
    assert row["reasons_json"] == '["z_reason","a_reason"]'
    assert len(list(csv.reader(io.StringIO(raw.decode(), newline="")))) == 2


def test_lone_surrogate_is_json_preserving_output_error():
    result = conditional.invalid_result()
    result["id"] = "\ud800"
    assert b"\\ud800" in conditional.result_bytes(result)
    with pytest.raises(OSError, match="UTF-8 encodable"):
        export.csv_bytes(result)


@pytest.mark.parametrize("offset", [0, 1])
def test_csv_complete_encoded_limit_is_inclusive(monkeypatch, offset):
    result = conditional.invalid_result()
    raw = export.csv_bytes(result)
    assert len(raw) > len(conditional.result_bytes(result))
    monkeypatch.setattr(conditional, "RESULT_LIMIT", len(raw) + offset)
    assert export.csv_bytes(result) == raw


def test_csv_one_byte_over_cap_fails_after_native_json_fits(monkeypatch):
    result = conditional.invalid_result()
    limit = len(export.csv_bytes(result)) - 1
    monkeypatch.setattr(conditional, "RESULT_LIMIT", limit)
    assert len(conditional.result_bytes(result)) <= limit
    with pytest.raises(ConditionalError, match="CSV exceeds") as error:
        export.csv_bytes(result)
    assert error.value.code == "result_limit"


def test_authoritative_json_cap_precedes_csv_buffer(monkeypatch):
    result = conditional.invalid_result()
    monkeypatch.setattr(
        conditional, "RESULT_LIMIT", len(conditional.result_bytes(result)) - 1
    )

    def forbidden():
        raise AssertionError("CSV started before native JSON admission")

    monkeypatch.setattr(export, "_Buffer", forbidden)
    with pytest.raises(ConditionalError, match="authoritative bytes"):
        export.csv_bytes(result)


def test_buffer_counts_utf8_bytes_without_partial_failed_write(monkeypatch):
    monkeypatch.setattr(conditional, "RESULT_LIMIT", 4)
    buffer = export._Buffer()
    assert buffer.write("µ") == 1 and buffer.data == "µ".encode()
    assert buffer.write("é") == 1 and len(buffer.data) == 4
    with pytest.raises(ConditionalError):
        buffer.write("x")
    assert buffer.data == "µé".encode()


def test_projection_does_not_execute_scientific_network_or_subprocess_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("export attempted execution")

    monkeypatch.setattr(conditional, "predict_conditional", forbidden)
    monkeypatch.setattr(conditional_backend, "verify_backend", forbidden)
    monkeypatch.setattr(conditional_math, "evaluate_response", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    assert len(decoded(export.csv_bytes(structural()))) == 3
    assert len(decoded(export.csv_bytes(volume()))) == 2
