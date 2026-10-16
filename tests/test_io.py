"""Document boundaries, batch isolation and result export semantics."""

import csv
import io
import json

import pytest

from regsite.io import MAX_DOCUMENT_CHARACTERS, load_requests, write_csv, write_json
from regsite.sequence import InputError


@pytest.mark.parametrize("value", [{"sequence": "A"}, 7, None])
def test_single_record_preserved_for_per_record_validation(value):
    assert load_requests(io.StringIO(json.dumps(value))) == [value]


def test_batch_retains_invalid_items_for_isolated_error_reporting():
    records = [{"sequence": "ACG"}, None, {"sequence": "AUG"}]
    assert load_requests(io.StringIO(json.dumps(records))) == records


@pytest.mark.parametrize("text", ["", "{", "NaN", "Infinity", "[]", "[" * 2000])
def test_malformed_documents(text):
    with pytest.raises(InputError):
        load_requests(io.StringIO(text))


def test_document_and_batch_resource_limits():
    with pytest.raises(InputError, match="characters"):
        load_requests(io.StringIO(" " * (MAX_DOCUMENT_CHARACTERS + 1)))
    with pytest.raises(InputError, match="100"):
        load_requests(io.StringIO(json.dumps([{}] * 101)))
    assert len(load_requests(io.StringIO(json.dumps([{}] * 100)))) == 100


def test_json_round_trip_and_nonfinite_rejection():
    stream = io.StringIO()
    record = {"status": "ok", "value": 0.123, "terms": [1, 2]}
    write_json(record, stream)
    assert json.loads(stream.getvalue()) == record
    assert stream.getvalue().endswith("\n")
    with pytest.raises(ValueError):
        write_json({"value": float("nan")}, io.StringIO())


def test_csv_retains_failures_missing_sites_and_zero_scores():
    records = [
        {
            "id": "valid,quoted",
            "status": "ok",
            "sites": [
                {
                    "status": "ok",
                    "start_codon": {"start": 10, "end": 13, "strand": "-"},
                    "codon": "AUG",
                    "tir": 0,
                    "energies": {"dG_total": 0},
                },
                {"status": "no_candidate", "reason": "no binding"},
            ],
        },
        {"id": "invalid", "status": "invalid_input", "reason": "bad sequence"},
        {"status": "no_candidate", "sites": []},
    ]
    stream = io.StringIO()
    write_csv(records, stream)
    rows = list(csv.DictReader(io.StringIO(stream.getvalue())))
    assert len(rows) == 4
    assert rows[0]["id"] == "valid,quoted"
    assert rows[0]["tir"] == rows[0]["dG_total"] == "0"
    assert (rows[0]["start"], rows[0]["end"], rows[0]["strand"]) == ("10", "13", "-")
    assert rows[1]["tir"] == ""
    assert rows[1]["reason"] == "no binding"
    assert rows[2]["reason"] == "bad sequence"
    assert rows[3]["status"] == "no_candidate"
