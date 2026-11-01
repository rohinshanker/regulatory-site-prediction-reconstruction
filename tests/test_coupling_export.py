"""Complete native projection, identity, coordinate and transport checks."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from regsite import coupling, coupling_export, coupling_io

HEADER = (
    "csv_schema_version,row_type,schema_version,model_id,implementation_version,"
    "model_sha256,request_sha256,prediction_sha256,json_sha256,result_status,"
    "result_reason,seconds_total,requested_records,returned_records,successful_records,"
    "failed_or_unsupported_records,not_evaluated_records,warnings_json,record_index,"
    "record_id,record_status,record_reason,coordinate_system,strand,sequence_length,"
    "sequence_sha256,oriented_sequence_sha256,distance_nt,upstream_id,upstream_start,"
    "upstream_end,upstream_oriented_start,upstream_oriented_end,upstream_start_codon,"
    "upstream_stop_codon,downstream_id,downstream_start,downstream_end,"
    "downstream_oriented_start,downstream_oriented_end,downstream_start_codon,"
    "downstream_stop_codon,upstream_total_kcal_mol,downstream_independent_total_kcal_mol,"
    "beta_mol_per_kcal,energy_provenance,coefficient,upstream_independent_value,"
    "upstream_independent_log_value,downstream_independent_value,"
    "downstream_independent_log_value,reinitiation_contribution_value,"
    "reinitiation_contribution_log_value,downstream_total_value,downstream_total_log_value,"
    "fold_change_value,fold_change_log_value,unfolding_correction"
)


def example(name="single"):
    return json.loads(Path(f"examples/coupling-{name}.json").read_text())


def rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))


def test_exact_header_roster_shared_identity_and_no_mutation():
    result = coupling.predict_coupling(example("batch"))
    original = copy.deepcopy(result)
    raw = coupling_export.csv_bytes(result)
    assert result == original and coupling_export.csv_bytes(result) == raw
    assert raw.startswith((HEADER + "\r\n").encode()) and raw.endswith(b"\r\n")
    assert len(HEADER.split(",")) == 58
    actual = rows(raw)
    assert [row["row_type"] for row in actual] == ["result"] + ["record"] * 3
    assert [row["record_id"] for row in actual[1:]] == [
        "separated",
        "overlap",
        "reverse_overlap",
    ]
    assert [row["record_index"] for row in actual[1:]] == ["0", "1", "2"]
    assert all(actual[0][key] == "" for key in HEADER.split(",")[18:])
    native = coupling_io.result_bytes(result)
    model_bytes = json.dumps(
        result["model"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    for row in actual:
        assert row["csv_schema_version"] == "coupling-csv-1"
        assert row["schema_version"] == "coupling-result-1"
        assert row["model_id"] == result["model"]["id"]
        assert (
            row["implementation_version"] == result["model"]["implementation_version"]
        )
        assert row["model_sha256"] == hashlib.sha256(model_bytes).hexdigest()
        assert row["request_sha256"] == result["request_sha256"]
        assert row["prediction_sha256"] == result["prediction_sha256"]
        assert row["json_sha256"] == hashlib.sha256(native).hexdigest()
        assert row["json_sha256"] != hashlib.sha256(native[:-1]).hexdigest()
        assert row["result_status"] == "complete" and row["result_reason"] == ""
        assert row["seconds_total"] == "10"
        assert row["requested_records"] == row["returned_records"] == "3"
        assert row["successful_records"] == "3"
        assert (
            row["failed_or_unsupported_records"] == row["not_evaluated_records"] == "0"
        )
        assert json.loads(row["warnings_json"]) == result["warnings"]


def test_both_coordinate_orientations_and_every_native_field():
    result = coupling.predict_coupling(example("batch"))
    actual = rows(coupling_export.csv_bytes(result))[1:]
    for row, record in zip(actual, result["records"], strict=True):
        g = record["geometry"]
        assert row["coordinate_system"] == "fragment-relative-0-based-half-open"
        for key in (
            "strand",
            "sequence_length",
            "sequence_sha256",
            "oriented_sequence_sha256",
            "distance_nt",
        ):
            assert row[key] == str(g[key])
        for name in ("upstream", "downstream"):
            cds = g[name]
            for key in ("id", "start_codon", "stop_codon"):
                assert row[f"{name}_{key}"] == cds[key]
            assert [int(row[f"{name}_{key}"]) for key in ("start", "end")] == cds[
                "interval"
            ]
            assert [
                int(row[f"{name}_oriented_{key}"]) for key in ("start", "end")
            ] == cds["oriented_interval"]
        for key in (
            "upstream_total_kcal_mol",
            "downstream_independent_total_kcal_mol",
            "beta_mol_per_kcal",
        ):
            assert row[key] == str(record["energies"][key])
        assert row["energy_provenance"] == record["energies"]["provenance"]
        assert row["coefficient"] == str(record["coefficient"])
        for name, quantity in record["scores"].items():
            for key, value in quantity.items():
                assert row[f"{name}_{key}"] == str(value)
        assert row["unfolding_correction"] == ""
    assert actual[1]["distance_nt"] == actual[2]["distance_nt"] == "-4"
    assert actual[2]["strand"] == "-"
    assert (actual[2]["upstream_start"], actual[2]["upstream_end"]) == ("5", "14")
    assert (
        actual[2]["upstream_oriented_start"],
        actual[2]["upstream_oriented_end"],
    ) == ("0", "9")


def test_mixed_failures_keep_all_records_fields_and_native_denominators():
    request = example("batch")
    request["records"][1]["energies"]["upstream_total_kcal_mol"] = 1000000
    request["records"][2]["sequence"] = "C" * 14
    request["records"].append(example("unsupported")["records"][0])
    request["records"].extend([{"id": "malformed"}, None])
    result = coupling.predict_coupling(request)
    actual = rows(coupling_export.csv_bytes(result))
    assert [r["record_status"] for r in actual[1:]] == [
        "ok",
        "numerical_range",
        "unsupported_geometry",
        "unsupported_distance",
        "invalid_input",
        "invalid_input",
    ]
    for row in actual:
        assert row["result_status"] == "partial" and row["result_reason"] == ""
        assert row["requested_records"] == row["returned_records"] == "6"
        assert row["successful_records"] == "1"
        assert row["failed_or_unsupported_records"] == "5"
        assert row["not_evaluated_records"] == "0"
    for row, record in zip(actual[1:], result["records"], strict=True):
        assert row["record_reason"] == (record["reason"] or "")
    assert actual[2]["upstream_independent_value"] == ""
    assert actual[2]["upstream_independent_log_value"] == "-450000.0"
    assert actual[2]["downstream_independent_value"] == "1.0"
    assert actual[4]["coefficient"] == actual[4]["downstream_total_value"] == ""
    assert actual[4]["strand"] == "+" and actual[4]["energy_provenance"]
    for row in (actual[3], actual[5], actual[6]):
        assert all(row[key] == "" for key in HEADER.split(",")[22:])
    assert actual[5]["record_id"] == "malformed" and actual[6]["record_id"] == ""


def test_deadline_retains_every_unattempted_record_with_no_geometry():
    result = coupling.predict_coupling(
        example("batch"), clock=iter([0, 11, 11, 11]).__next__
    )
    actual = rows(coupling_export.csv_bytes(result))
    assert len(actual) == 4
    for row in actual:
        assert row["not_evaluated_records"] == "3"
        assert row["successful_records"] == row["failed_or_unsupported_records"] == "0"
    for row in actual[1:]:
        assert row["record_status"] == "not_evaluated"
        assert row["record_reason"] == "time_budget_exhausted"
        assert all(row[key] == "" for key in HEADER.split(",")[22:])


@pytest.mark.parametrize(
    "value", [None, [], {}, {"schema_version": "coupling-request-1", "records": []}]
)
def test_invalid_envelope_and_null_coverage(value):
    result = coupling.predict_coupling(value)
    actual = rows(coupling_export.csv_bytes(result))
    assert len(actual) == 1 and actual[0]["result_status"] == "invalid_input"
    assert actual[0]["result_reason"] == "invalid_envelope"
    assert all(actual[0][key] == "" for key in HEADER.split(",")[11:17])


def test_null_request_and_empty_warnings():
    result = coupling.invalid_result("invalid_json_or_input_limit")
    result["warnings"] = []  # A formatting control, not a new admitted producer model.
    row = rows(coupling_export.csv_bytes(result))[0]
    assert row["request_sha256"] == "" and row["warnings_json"] == "[]"


def test_number_spelling_text_and_unicode_are_preserved():
    request = example()
    request["settings"]["seconds_total"] = 10.0
    request["records"][0]["energies"]["upstream_total_kcal_mol"] = -0.0
    text = '=SUM(1,2), "quoted"\r\nβ\n😀\r  trailing  '
    request["records"][0]["energies"]["provenance"] = text
    result = coupling.predict_coupling(request)
    raw = coupling_export.csv_bytes(result)
    row = rows(raw)[1]
    assert row["seconds_total"] == "10.0"
    assert row["upstream_total_kcal_mol"] == "-0.0"
    assert row["downstream_independent_log_value"] == "-0.0"
    assert row["energy_provenance"] == text
    assert b'""quoted""' in raw and "β\n😀".encode() in raw


def test_native_json_cap_is_checked_before_csv(monkeypatch):
    result = coupling.predict_coupling(example())
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", 1)
    with pytest.raises(coupling_io.CouplingInputError, match="output byte limit"):
        coupling_export.csv_bytes(result)


def test_exact_csv_cap_and_one_byte_over(monkeypatch):
    request = example()
    request["records"] = [None] * 100
    result = coupling.predict_coupling(request)
    raw = coupling_export.csv_bytes(result)
    assert len(coupling_io.result_bytes(result)) < len(raw)
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", len(raw))
    assert coupling_export.csv_bytes(result) == raw
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(coupling_io.CouplingInputError, match="output byte limit"):
        coupling_export.csv_bytes(result)


def test_utf8_buffer_counts_encoded_bytes_and_keeps_prior_rows(monkeypatch):
    buffer = coupling_export._Buffer()
    monkeypatch.setattr(coupling_io, "OUTPUT_LIMIT", 4)
    assert buffer.write("😀") == 1
    with pytest.raises(coupling_io.CouplingInputError, match="output byte limit"):
        buffer.write("x")
    assert bytes(buffer.data) == "😀".encode()


def test_surrogate_refuses_csv_without_changing_native_json():
    request = example()
    request["records"][0]["energies"]["provenance"] = "artificial \ud800"
    result = coupling.predict_coupling(request)
    assert result["status"] == "complete"
    native = coupling_io.result_bytes(result)
    assert b"\\ud800" in native
    with pytest.raises(coupling_io.CouplingInputError, match="not UTF-8"):
        coupling_export.csv_bytes(result)
    assert coupling_io.result_bytes(result) == native
