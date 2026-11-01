"""Bounded binary input and loss-aware exports for explicit transcript results."""

import csv
import hashlib
import io
import json

import pytest
from test_transcript import annotation, document
from test_transcript import backend as backend

from regsite import transcript as runtime
from regsite import transcript_io as transport


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{",
        b"{}{}",
        b"\xff",
        b'{"a":1,"a":2}',
        b'{"a":{"b":1,"b":2}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"[" * 2000,
        b"1" * 5000,
    ],
)
def test_invalid_wire_is_atomic(raw):
    with pytest.raises(runtime.TranscriptError, match="finite UTF-8 JSON"):
        transport.load_request(io.BytesIO(raw))


def test_strict_loading_counts_received_utf8_crlf_bytes(monkeypatch):
    raw = '{"a":1.5,"b":[false,null,"µ"]}\r\n'.encode()
    monkeypatch.setitem(runtime.LIMITS, "max_input_json_bytes", len(raw))
    assert transport.load_request(io.BytesIO(raw)) == json.loads(raw)
    stream = io.BytesIO(raw + b" " * 10000)
    with pytest.raises(runtime.TranscriptError, match="received input"):
        transport.load_request(stream)
    assert stream.tell() == len(raw) + 1


def rows(result):
    return list(csv.DictReader(io.StringIO(transport.export_text(result, "csv"))))


def test_all_scalars_and_component_summaries_bind_full_json(backend):
    result = runtime.predict_transcript(document(), backend)
    exported = rows(result)
    assert list(exported[0]) == transport.CSV_COLUMNS
    assert len(exported) == 2 + len(result["cds"][0]["scalars"]) + sum(
        len(candidate["scalars"]) for candidate in result["promoter_candidates"]
    )
    assert {row["request_sha256"] for row in exported} == {
        hashlib.sha256(runtime.canonical_bytes(result["request"])).hexdigest()
    }
    assert {row["prediction_sha256"] for row in exported} == {
        result["prediction_sha256"]
    }
    assert {row["id"] for row in exported} == {"test α"}
    assert {row["coverage_complete"] for row in exported} == {"True"}
    assert {row["component"] for row in exported if row["row_type"] == "component"} == {
        "rbs",
        "promoter",
    }
    for row in exported:
        if row["row_type"] != "candidate_scalar":
            continue
        candidates = result[
            "cds" if row["component"] == "rbs" else "promoter_candidates"
        ]
        item = candidates[int(row["site_index"])]
        scalar = item["scalars"][row["scalar_name"]]
        assert row["value"] == ("" if scalar["value"] is None else str(scalar["value"]))
        assert row["value_reason"] == (scalar["reason"] or "")
        assert row["unit"] == scalar["unit"]
        if row["component"] == "rbs":
            assert row["annotation_id"] == "gene"
            assert (row["construct_start"], row["construct_end"]) == ("40", "100")
            assert row["transcript_offset"] == "20"
        else:
            assert row["annotation_id"] == row["transcript_offset"] == ""
            assert (row["construct_start"], row["construct_end"]) == ("100", "101")
    assert transport.export_text(result, "json").encode(
        "ascii"
    ) == runtime.result_bytes(result)


def test_empty_scan_and_incompatible_cds_remain_visible_without_backend():
    request = document()
    request["cds"] = [annotation("before", 1, 4)]
    request["promoter"]["scan"]["positions"] = []
    result = runtime.predict_transcript(request)
    exported = rows(result)
    summaries = {
        row["component"]: row for row in exported if row["row_type"] == "component"
    }
    assert summaries["rbs"]["component_status"] == "not_applicable"
    assert summaries["rbs"]["incompatible"] == "1"
    assert summaries["promoter"]["component_status"] == "no_candidate"
    assert summaries["promoter"]["requested"] == "0"
    assert len(exported) == 2 + len(result["cds"][0]["scalars"])
    for row in exported:
        if row["row_type"] == "candidate_scalar":
            assert row["status"] == "incompatible_transcript"
            assert row["reason"] == "start_before_transcript"
            assert row["transcript_offset"] == "-19"
            assert row["site_index"] == row["value"] == ""
            assert row["value_reason"] == "incompatible_transcript"


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_inclusive_utf8_export_limit(monkeypatch, backend, output_format):
    result = runtime.predict_transcript(document(), backend)
    text = transport.export_text(result, output_format)
    maximum = len(text.encode("utf-8"))
    monkeypatch.setitem(runtime.LIMITS, "max_result_json_bytes", maximum)
    assert transport.export_text(result, output_format) == text
    monkeypatch.setitem(runtime.LIMITS, "max_result_json_bytes", maximum - 1)
    with pytest.raises(runtime.TranscriptError, match="export exceeds"):
        transport.export_text(result, output_format)
    with pytest.raises(runtime.TranscriptError, match="format must"):
        transport.export_text(result, "gff3")
