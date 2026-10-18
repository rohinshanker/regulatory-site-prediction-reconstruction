"""Strict input decoding and loss-aware portable scalar comparisons."""

import csv
import io
import json

import pytest
from test_paired import document

from regsite import paired, paired_io


@pytest.mark.parametrize(
    "text",
    [
        '{"a":1,"a":2}',
        '{"a":NaN}',
        '{"a":Infinity}',
        '{"a":1e999}',
        "[",
        "\ud800",
        "[" * 2000,
    ],
)
def test_bad_json(text):
    with pytest.raises(paired.PairError, match="invalid paired JSON"):
        paired_io.load_request(io.StringIO(text))


def test_strict_loading_and_received_byte_boundary(monkeypatch):
    raw = '{"a":1.5,"b":[false,null,"µ"]}'
    maximum = len(raw.encode("utf-8"))
    monkeypatch.setitem(paired.LIMITS, "max_input_json_bytes", maximum)
    assert paired_io.load_request(io.StringIO(raw)) == json.loads(raw)
    with pytest.raises(paired.PairError, match="received input"):
        paired_io.load_request(io.StringIO(raw + " "))
    # Reading is bounded even if the stream has much more trailing whitespace.
    stream = io.StringIO(" " * 1000)
    with pytest.raises(paired.PairError, match="received input"):
        paired_io.load_request(stream)
    assert stream.tell() == maximum + 1


def test_decode_error_is_a_pair_error():
    stream = io.TextIOWrapper(io.BytesIO(b"\xff"), encoding="utf-8")
    with pytest.raises(paired.PairError, match="invalid paired JSON"):
        paired_io.load_request(stream)


def rows(result):
    return list(csv.DictReader(io.StringIO(paired_io.export_text(result, "csv"))))


def test_real_unchanged_csv_and_json_bind_full_result():
    result = paired.predict_pair(document())
    exported = rows(result)
    assert len(exported) == 24  # Two candidates, twelve published scalar terms.
    assert list(exported[0]) == paired_io.CSV_COLUMNS
    assert {r["prediction_sha256"] for r in exported} == {result["prediction_sha256"]}
    assert {r["delta_value"] for r in exported} <= {"0", "0.0"}
    assert all(r["current_value"] and r["recoded_value"] for r in exported)
    assert {r["diagnostic_only"] for r in exported} == {"False"}
    assert paired_io.export_text(result, "json").encode("ascii") == paired.result_bytes(
        result
    )


def test_unpaired_csv_preserves_missing_side_and_empty_score():
    request = document()
    request["recoded_request"]["scan"]["positions"] = [{"strand": "+", "tss": 101}]
    exported = rows(paired.predict_pair(request))
    assert len(exported) == 36
    for row in exported:
        assert row["comparison_status"] == "unmatched"
        assert row["delta_value"] == ""
        assert bool(row["current_candidate_id"]) != bool(row["recoded_candidate_id"])
        absent = "recoded" if row["current_candidate_id"] else "current"
        assert row[absent + "_value"] == row[absent + "_status"] == ""


@pytest.mark.parametrize("invalid", [False, True])
def test_no_comparisons_distinguishes_empty_from_unknown(invalid):
    request = document()
    for side in paired.SIDES:
        request[side + "_request"]["scan"] = (
            {} if invalid else {"mode": "positions", "positions": []}
        )
    exported = rows(paired.predict_pair(request))
    assert len(exported) == 1
    assert exported[0]["current_expected"] == ("" if invalid else "0")
    assert exported[0]["current_roster_status"] == ("unknown" if invalid else "known")
    assert exported[0]["comparison_status"] == "not_applicable"
    assert exported[0]["delta_reason"] == "no_comparison_rows"


def test_rbs_record_export_uses_original_status():
    # Reuse the full predictor-free empty RBS roster; no backend work is required.
    from pathlib import Path

    from regsite.backend import RnaStructure

    result = paired.predict_pair(
        document("rbs"), RnaStructure(Path("."), {"fixture": "empty-roster"})
    )
    exported = rows(result)
    assert exported[0]["current_record_status"] == "no_candidate"
    assert exported[0]["current_expected"] == "0"


def test_export_format_and_exact_byte_limit(monkeypatch):
    result = paired.predict_pair(document())
    text = paired_io.export_text(result, "csv")
    monkeypatch.setitem(
        paired.LIMITS, "max_result_json_bytes", len(text.encode("utf-8"))
    )
    assert paired_io.export_text(result, "csv") == text
    monkeypatch.setitem(
        paired.LIMITS, "max_result_json_bytes", len(text.encode("utf-8")) - 1
    )
    with pytest.raises(paired.PairError, match="export exceeds"):
        paired_io.export_text(result, "csv")
    with pytest.raises(paired.PairError, match="format must"):
        paired_io.export_text(result, "xml")
