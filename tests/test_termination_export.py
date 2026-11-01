"""CSV projection checks using original artificial rosters and transport controls."""

import copy
import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from test_termination import FakeBackend, assert_identity, request

from regsite import termination, termination_export, termination_io
from regsite.termination_backend import TerminationBackendError

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    item["case"]: item
    for item in json.loads(
        (ROOT / "benchmarks/termination/native-smoke-manifest.json").read_text()
    )["cases"]
}
HEADER = (
    "csv_schema_version,row_type,schema_version,model_id,implementation_version,"
    "model_sha256,request_sha256,prediction_sha256,result_sha256,result_status,"
    "result_reason,record_index,record_id,record_status,record_reason,sequence_length,"
    "sequence_sha256,attempted,candidate_count,candidate_id,candidate_status,"
    "coordinate_system,strand,hairpin_start,hairpin_end,tail_start,tail_end,confidence,"
    "hairpin_score,tail_score,native_id,native_context,native_printed_confidence,"
    "native_notes\r\n"
)


def rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))


def fixture_candidates(case):
    """Independent native-to-result geometry for previously reviewed controls."""
    result = []
    for item in case["native_candidates"]:
        start = min(item["start_1based"], item["end_1based"]) - 1
        end = max(item["start_1based"], item["end_1based"])
        boundary = item["strand"] == "+" and start == 1
        tail = (end, end + 15) if item["strand"] == "+" else (start - 15, start)
        result.append(
            {
                "candidate_id": "",
                "strand": item["strand"],
                "hairpin": {"start": start, "end": end},
                "tail": {"start": tail[0], "end": tail[1]},
                "status": "boundary_ambiguous" if boundary else "ok",
                "confidence": None if boundary else item["confidence"],
                "hairpin_score": item["hairpin_score"],
                "tail_score": item["tail_score"],
                "native": {
                    "id": f"TERM {item['native_id']}",
                    "context": item["context"],
                    "printed_confidence": None if boundary else item["confidence"],
                    "notes": item["notes"],
                },
            }
        )
    result.sort(key=lambda item: (*item["hairpin"].values(), item["strand"]))
    for index, item in enumerate(result, 1):
        item["candidate_id"] = f"candidate-{index:04d}"
    return result


def fixture_result(monkeypatch, name="positive"):
    case = CASES[name]
    monkeypatch.setattr(
        termination, "parse_output", lambda *_: fixture_candidates(case)
    )
    return termination.predict_termination(
        request({"id": name, "sequence": case["sequence"]}), backend=FakeBackend()
    )


def test_exact_header_row_order_binding_and_no_mutation(monkeypatch):
    result = fixture_result(monkeypatch)
    before = copy.deepcopy(result)
    raw = termination_export.csv_bytes(result)
    assert raw.startswith(HEADER.encode())
    assert raw.endswith(b"\r\n") and not raw.startswith(b"\xef\xbb\xbf")
    actual = rows(raw)
    assert [row["row_type"] for row in actual] == [
        "envelope",
        "record",
        "candidate",
        "candidate",
    ]
    assert [row["candidate_id"] for row in actual] == [
        "",
        "",
        "candidate-0001",
        "candidate-0002",
    ]
    expected_model_hash = hashlib.sha256(
        json.dumps(result["model"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    for row in actual:
        assert len(row) == 34 and None not in row
        assert row["csv_schema_version"] == "termination-csv-1"
        assert row["schema_version"] == "termination-result-1"
        assert row["model_id"] == "transtermhp-2.09-fragment-1"
        assert (
            row["implementation_version"] == result["model"]["implementation_version"]
        )
        assert row["model_sha256"] == expected_model_hash
        for key in ("request_sha256", "prediction_sha256", "result_sha256"):
            assert row[key] == result[key]
        assert row["result_status"] == "complete" and row["result_reason"] == ""
        assert row["coordinate_system"] == "fragment-relative-0-based-half-open"
    for row in actual[1:]:
        assert row["record_id"] == "positive" and row["record_index"] == "0"
        assert row["record_status"] == "ok" and row["record_reason"] == ""
        assert row["sequence_length"] == "191"
        assert (
            row["sequence_sha256"]
            == hashlib.sha256(CASES["positive"]["sequence"].encode()).hexdigest()
        )
        assert row["attempted"] == "true" and row["candidate_count"] == "2"
    assert actual[0]["record_index"] == actual[0]["attempted"] == ""
    assert result == before
    assert_identity(result)
    assert termination_export.csv_bytes(result) == raw


def test_both_strands_keep_half_open_boundaries_and_native_spelling(monkeypatch):
    actual = rows(termination_export.csv_bytes(fixture_result(monkeypatch)))[2:]
    assert [
        tuple(
            row[key]
            for key in (
                "strand",
                "hairpin_start",
                "hairpin_end",
                "tail_start",
                "tail_end",
                "confidence",
                "hairpin_score",
                "tail_score",
                "native_id",
                "native_context",
                "native_printed_confidence",
                "native_notes",
            )
        )
        for row in actual
    ] == [
        (
            "-",
            "71",
            "85",
            "56",
            "71",
            "43",
            "-2.3",
            "-3.10057",
            "TERM 1",
            "f",
            "43",
            "opp_overlap 81",
        ),
        (
            "+",
            "80",
            "96",
            "96",
            "111",
            "100",
            "-11.8",
            "-7.14698",
            "TERM 2",
            "F",
            "100",
            "opp_overlap 72",
        ),
    ]
    assert int(actual[0]["hairpin_end"]) > int(actual[1]["hairpin_start"])


@pytest.mark.parametrize("context", ["F", "G"])
def test_boundary_ambiguity_retains_nulls_and_overlapping_candidates(
    monkeypatch, context
):
    result = fixture_result(monkeypatch, "boundary_mixed")
    result["records"][0]["candidates"][0]["native"]["context"] = context
    actual = rows(termination_export.csv_bytes(result))[2:]
    assert len(actual) == 3
    assert actual[0]["hairpin_start"] == "1" and actual[0]["hairpin_end"] == "60"
    assert actual[0]["tail_start"] == "60" and actual[0]["tail_end"] == "75"
    assert actual[0]["candidate_status"] == "boundary_ambiguous"
    assert actual[0]["confidence"] == actual[0]["native_printed_confidence"] == ""
    assert actual[0]["native_context"] == context
    assert [row["native_id"] for row in actual] == ["TERM 1", "TERM 2", "TERM 3"]


@pytest.mark.parametrize(
    "reason,request_hash",
    [("invalid_envelope", "a" * 64), ("invalid_json_or_input_limit", None)],
)
def test_invalid_envelope_has_one_metadata_row(reason, request_hash):
    result = termination.invalid_result(reason, request_hash)
    actual = rows(termination_export.csv_bytes(result))
    assert len(actual) == 1
    assert actual[0]["row_type"] == "envelope"
    assert actual[0]["result_status"] == "invalid_input"
    assert actual[0]["result_reason"] == reason
    assert actual[0]["request_sha256"] == (request_hash or "")
    assert actual[0]["record_id"] == actual[0]["candidate_count"] == ""


def test_invalid_unsupported_and_backend_failures_keep_roster_order():
    result = termination.predict_termination(
        request(
            None,
            {"id": "z", "sequence": "N"},
            {"id": "a", "sequence": "AC"},
            {"id": "zero-search", "sequence": "AC" * 37 + "A"},
            {"id": "backend", "sequence": "AC" * 40},
        )
    )
    actual = rows(termination_export.csv_bytes(result))
    assert len(actual) == 6
    assert [row["record_index"] for row in actual[1:]] == ["0", "1", "2", "3", "4"]
    assert [row["record_id"] for row in actual[1:]] == [
        "",
        "z",
        "a",
        "zero-search",
        "backend",
    ]
    assert [row["record_status"] for row in actual[1:]] == [
        "invalid_input",
        "invalid_input",
        "unsupported_domain",
        "unsupported_domain",
        "backend_failure",
    ]
    assert [row["record_reason"] for row in actual[1:]] == [
        "invalid_record",
        "invalid_sequence_alphabet",
        "sequence_length_outside_domain",
        "no_search_positions",
        "backend_unavailable",
    ]
    assert [row["sequence_length"] for row in actual[1:]] == ["", "", "2", "75", "80"]
    assert all(
        row["candidate_count"] == "" and row["attempted"] == "false"
        for row in actual[1:]
    )
    assert all(row["result_status"] == "partial" for row in actual)


@pytest.mark.parametrize(
    "code",
    [
        "native_timeout",
        "native_output_limit",
        "native_output_invalid",
        "native_nonzero_exit",
        "native_candidate_limit",
    ],
)
def test_attempted_backend_failure_survives(code):
    result = termination.predict_termination(
        request(), backend=FakeBackend(TerminationBackendError("test", code=code))
    )
    row = rows(termination_export.csv_bytes(result))[1]
    assert row["record_status"] == "backend_failure"
    assert row["record_reason"] == code and row["attempted"] == "true"
    assert row["candidate_count"] == row["candidate_id"] == ""


def test_unattempted_deadline_keeps_record_without_input_metadata():
    times = iter([0, 2])
    result = termination.predict_termination(
        request(max_seconds=1), clock=lambda: next(times)
    )
    row = rows(termination_export.csv_bytes(result))[1]
    assert row["record_status"] == "not_evaluated"
    assert row["record_reason"] == "time_budget_exhausted"
    assert row["record_id"] == "fragment" and row["attempted"] == "false"
    assert (
        row["sequence_sha256"] == row["sequence_length"] == row["candidate_count"] == ""
    )


def test_successful_empty_search_has_zero_count_and_no_candidate_row(monkeypatch):
    result = fixture_result(monkeypatch, "negative")
    actual = rows(termination_export.csv_bytes(result))
    assert len(actual) == 2
    assert actual[1]["record_status"] == "ok" and actual[1]["candidate_count"] == "0"
    assert actual[1]["attempted"] == "true" and actual[1]["candidate_id"] == ""


def test_each_records_candidates_follow_their_record_without_resorting(monkeypatch):
    monkeypatch.setattr(
        termination,
        "parse_output",
        lambda raw, sequence: (
            fixture_candidates(CASES["positive"])
            if sequence == CASES["positive"]["sequence"]
            else []
        ),
    )
    result = termination.predict_termination(
        request(
            {"id": "z", "sequence": CASES["positive"]["sequence"]},
            {"id": "a", "sequence": CASES["negative"]["sequence"]},
            {"id": "m", "sequence": CASES["positive"]["sequence"]},
        ),
        backend=FakeBackend(),
    )
    actual = rows(termination_export.csv_bytes(result))
    assert [
        (row["row_type"], row["record_index"], row["record_id"], row["candidate_id"])
        for row in actual
    ] == [
        ("envelope", "", "", ""),
        ("record", "0", "z", ""),
        ("candidate", "0", "z", "candidate-0001"),
        ("candidate", "0", "z", "candidate-0002"),
        ("record", "1", "a", ""),
        ("record", "2", "m", ""),
        ("candidate", "2", "m", "candidate-0001"),
        ("candidate", "2", "m", "candidate-0002"),
    ]


def test_numeric_zero_score_text_and_empty_native_note(monkeypatch):
    result = fixture_result(monkeypatch, "tie27of100")
    candidate = result["records"][0]["candidates"][0]
    candidate.update(confidence=0, hairpin_score="-2.00000e+0", tail_score="-3.100570")
    candidate["native"]["printed_confidence"] = 0
    row = rows(termination_export.csv_bytes(result))[2]
    assert row["confidence"] == row["native_printed_confidence"] == "0"
    assert row["hairpin_score"] == "-2.00000e+0" and row["tail_score"] == "-3.100570"
    assert row["native_notes"] == ""


def test_csv_quotes_commas_quotes_and_newlines_without_text_rewriting(monkeypatch):
    # Wire-format control only; this text is not claimed to be a native note.
    result = fixture_result(monkeypatch)
    text = 'comma, "quote"\r\nline\rreturn\nnext λ'
    result["records"][0]["candidates"][0]["native"]["notes"] = text
    raw = termination_export.csv_bytes(result)
    assert b'"comma, ""quote""\r\nline\rreturn\nnext \xce\xbb"' in raw
    assert rows(raw)[2]["native_notes"] == text
    assert len(rows(raw)) == 4


def test_exact_encoded_cap_and_one_byte_over(monkeypatch):
    result = fixture_result(monkeypatch)
    result["records"][0]["candidates"][0]["native"]["notes"] = "λ\n"
    raw = termination_export.csv_bytes(result)
    monkeypatch.setattr(termination_io, "OUTPUT_LIMIT", len(raw))
    assert termination_export.csv_bytes(result) == raw
    monkeypatch.setattr(termination_io, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(termination_io.TerminationInputError, match="output byte limit"):
        termination_export.csv_bytes(result)


def test_header_alone_can_exceed_limit(monkeypatch):
    monkeypatch.setattr(termination_io, "OUTPUT_LIMIT", len(HEADER.encode()) - 1)
    with pytest.raises(termination_io.TerminationInputError, match="output byte limit"):
        termination_export.csv_bytes(termination.invalid_result("invalid_envelope"))


def test_buffer_counts_bytes_but_reports_characters(monkeypatch):
    monkeypatch.setattr(termination_io, "OUTPUT_LIMIT", 2)
    buffer = termination_export._Buffer()
    assert buffer.write("λ") == 1
    assert buffer.data == b"\xce\xbb"
    with pytest.raises(termination_io.TerminationInputError):
        buffer.write("a")
    assert buffer.data == b"\xce\xbb"
