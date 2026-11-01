"""Every-record projection, native identities and bounded CSV transport."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

from regsite import drafting, drafting_export, drafting_io

HEADER = (
    "csv_schema_version,row_type,schema_version,model_id,implementation_version,"
    "source_doi,theory_sha256,backend_json,rate_origin,request_sha256,"
    "prediction_sha256,json_sha256,result_status,result_reason,requested_records,"
    "evaluated_records,successful_records,complete,warnings_json,record_index,"
    "record_id,record_status,record_reason,rate_unit,rate_provenance,a1,a2,a_fold,"
    "a_elong,accessible_value,accessible_ln_value,accessible_representation,"
    "folded_value,folded_ln_value,folded_representation,occupied_value,"
    "occupied_ln_value,occupied_representation,throughput_unit,throughput_value,"
    "throughput_ln_value,throughput_representation"
)


def example(name="single"):
    return json.loads(Path(f"examples/drafting-{name}.json").read_text())


def rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode(), newline="")))


def test_exact_header_order_shared_metadata_and_native_bytes():
    result = drafting.predict(example("batch"))
    original = copy.deepcopy(result)
    native = drafting_io.result_bytes(result)
    raw = drafting_export.csv_bytes(result)
    assert raw.startswith((HEADER + "\r\n").encode())
    assert raw.endswith(b"\r\n")
    assert len(HEADER.split(",")) == 42
    assert result == original
    assert drafting_export.csv_bytes(result) == raw
    actual = rows(raw)
    assert [row["row_type"] for row in actual] == ["result"] + ["record"] * 3
    assert [row["record_id"] for row in actual[1:]] == [
        "artificial-1",
        "zero-folding",
        "equal-binding",
    ]
    assert [row["record_index"] for row in actual[1:]] == ["0", "1", "2"]
    for row in actual:
        assert row["csv_schema_version"] == "drafting-csv-1"
        assert row["schema_version"] == result["schema_version"]
        for column, key in (
            ("model_id", "id"),
            ("implementation_version", "implementation_version"),
            ("source_doi", "source_doi"),
            ("theory_sha256", "theory_sha256"),
            ("rate_origin", "rate_origin"),
        ):
            assert row[column] == result["model"][key]
        assert row["backend_json"] == ""
        assert row["request_sha256"] == result["request_sha256"]
        assert row["prediction_sha256"] == result["prediction_sha256"]
        assert row["json_sha256"] == hashlib.sha256(native).hexdigest()
        assert row["json_sha256"] != hashlib.sha256(native.rstrip(b"\n")).hexdigest()
        assert row["result_status"] == "complete" and row["result_reason"] == ""
        assert row["requested_records"] == row["evaluated_records"] == "3"
        assert row["successful_records"] == "3" and row["complete"] == "true"
        assert json.loads(row["warnings_json"]) == result["warnings"]
    assert all(actual[0][column] == "" for column in HEADER.split(",")[19:])
    for row, record in zip(actual[1:], result["records"], strict=True):
        assert row["record_status"] == "ok" and row["record_reason"] == ""
        for name in ("rate_unit", "rate_provenance"):
            assert row[name] == record["input"][name]
        for name, value in record["input"]["rates"].items():
            assert row[name] == str(value)
        assert row["throughput_unit"] == record["throughput"]["unit"]
        for name, quantity in {
            **record["occupancies"],
            "throughput": record["throughput"]["quantity"],
        }.items():
            for key, value in quantity.items():
                assert row[f"{name}_{key}"] == ("" if value is None else str(value))
    assert {row["rate_unit"] for row in actual[1:]} == {"per_second", "per_model_time"}


def test_exact_zero_underflow_and_subnormal_remain_distinct():
    request = example("batch")
    request["records"][0]["rates"] = {
        "a1": 1,
        "a2": 5e-324,
        "a_fold": 1e308,
        "a_elong": 4,
    }
    request["records"][1]["rates"]["a_fold"] = -0.0
    result = drafting.predict(request)
    assert result["status"] == "complete"
    actual = rows(drafting_export.csv_bytes(result))
    assert actual[1]["accessible_value"] == ""
    assert float(actual[1]["accessible_ln_value"]) < -1000
    assert actual[1]["accessible_representation"] == "underflow"
    assert actual[1]["occupied_value"] == ""
    assert actual[1]["occupied_representation"] == "underflow"
    assert actual[1]["throughput_value"] == "5e-324"
    assert actual[1]["throughput_representation"] == "finite"
    assert actual[2]["folded_value"] == actual[2]["a_fold"] == "0.0"
    assert actual[2]["folded_ln_value"] == ""
    assert actual[2]["folded_representation"] == "exact_zero"


def test_every_failed_record_is_retained_with_coverage_and_inputs(monkeypatch):
    request = example("batch")
    request["records"].extend([{"id": "malformed"}, None])
    request["records"][1]["rates"]["a1"] = 100
    original = drafting._stationary

    def stationary(rates):
        if rates["a1"] == 1:
            raise OverflowError("artificial numerical failure")
        return original(rates)

    monkeypatch.setattr(drafting, "_stationary", stationary)
    result = drafting.predict(request)
    actual = rows(drafting_export.csv_bytes(result))
    assert [row["record_status"] for row in actual[1:]] == [
        "ok",
        "unsupported_domain",
        "numerical_failure",
        "invalid_input",
        "invalid_input",
    ]
    assert [row["record_index"] for row in actual[1:]] == ["0", "1", "2", "3", "4"]
    assert [row["record_id"] for row in actual[1:]] == [
        "artificial-1",
        "zero-folding",
        "equal-binding",
        "malformed",
        "",
    ]
    for row in actual:
        assert row["result_status"] == "partial" and row["complete"] == "false"
        assert row["requested_records"] == row["evaluated_records"] == "5"
        assert row["successful_records"] == "1"
    for row, record in zip(actual[2:], result["records"][1:], strict=True):
        assert row["record_reason"] == record["reason"]
        assert all(row[column] == "" for column in HEADER.split(",")[29:])
    assert actual[2]["a1"] == "100.0" and actual[3]["a1"] == "1.0"
    assert actual[4]["rate_unit"] == actual[5]["rate_provenance"] == ""


@pytest.mark.parametrize(
    "value", [None, [], {}, {"schema_version": "drafting-request-1", "records": []}]
)
def test_invalid_envelope_has_one_metadata_row_and_unknown_coverage(value):
    result = drafting.predict(value)
    actual = rows(drafting_export.csv_bytes(result))
    assert len(actual) == 1
    row = actual[0]
    assert row["row_type"] == "result" and row["result_status"] == "invalid_input"
    assert row["result_reason"] == result["reason"]
    assert row["requested_records"] == row["successful_records"] == ""
    assert row["evaluated_records"] == row["complete"] == ""


def test_transport_refusal_retains_null_request_hash():
    result = drafting.invalid_result("invalid_json_or_input_limit")
    row = rows(drafting_export.csv_bytes(result))[0]
    assert row["request_sha256"] == ""
    assert row["prediction_sha256"] == result["prediction_sha256"]


def test_zero_success_is_not_null_coverage():
    result = drafting.predict(example("unsupported"))
    actual = rows(drafting_export.csv_bytes(result))
    assert actual[0]["requested_records"] == "1"
    assert actual[0]["successful_records"] == "0"
    assert actual[0]["complete"] == "false"


def test_quotes_newlines_unicode_and_formula_like_text_are_not_rewritten():
    request = example()
    provenance = '=SUM(1,2), "quoted"\r\nβ\n😀\r  trailing  '
    request["records"][0]["rate_provenance"] = provenance
    result = drafting.predict(request)
    raw = drafting_export.csv_bytes(result)
    assert rows(raw)[1]["rate_provenance"] == provenance
    assert b'""quoted""' in raw and "β\n😀".encode() in raw


def test_structured_metadata_uses_compact_sorted_finite_ascii_json():
    result = drafting.invalid_result("artificial")
    # Exercise projection formatting only, not admission of a new backend model.
    result["model"]["backend"] = {"z": "β", "a": False}
    result["warnings"] = []
    row = rows(drafting_export.csv_bytes(result))[0]
    assert row["backend_json"] == '{"a":false,"z":"\\u03b2"}'
    assert row["warnings_json"] == "[]"


def test_native_json_ceiling_is_checked_before_csv(monkeypatch):
    result = drafting.predict(example())
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", 1)
    with pytest.raises(drafting_io.DraftingInputError, match="output_byte_limit"):
        drafting_export.csv_bytes(result)


def test_exact_csv_cap_and_one_byte_over(monkeypatch):
    result = drafting.predict(example("batch"))
    raw = drafting_export.csv_bytes(result)
    assert len(drafting_io.result_bytes(result)) < len(raw)
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(raw))
    assert drafting_export.csv_bytes(result) == raw
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(drafting_io.DraftingInputError, match="output_byte_limit"):
        drafting_export.csv_bytes(result)


def test_utf8_buffer_counts_bytes_instead_of_characters(monkeypatch):
    buffer = drafting_export._Buffer()
    monkeypatch.setattr(drafting_io, "OUTPUT_LIMIT", 4)
    assert buffer.write("😀") == 1 and bytes(buffer.data) == "😀".encode()
    with pytest.raises(drafting_io.DraftingInputError, match="output_byte_limit"):
        buffer.write("x")
    assert bytes(buffer.data) == "😀".encode()


def test_lone_surrogate_cannot_escape_as_partial_csv():
    request = example()
    request["records"][0]["rate_provenance"] = "artificial \ud800"
    result = drafting.predict(request)
    assert result["status"] == "complete"
    assert b"\\ud800" in drafting_io.result_bytes(result)
    with pytest.raises(drafting_io.DraftingInputError, match="csv_text_not_utf8"):
        drafting_export.csv_bytes(result)


def test_nonfinite_native_result_is_rejected_before_projection():
    result = drafting.invalid_result("artificial")
    result["warnings"] = [float("nan")]
    with pytest.raises(
        drafting_io.DraftingInputError, match="result_is_not_finite_json"
    ):
        drafting_export.csv_bytes(result)
