"""Public batch contract: independent identities, retention and failure semantics."""

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from regsite import promoter
from regsite import promoter_io as pio

ROOT = Path(__file__).resolve().parents[1]


def request(**changes):
    """A synthetic two-strand example, with no experimental outcome."""
    return {
        "id": "synthetic",
        "sequence": "A" * 200,
        "calibration": "in_vitro",
        "scan": {
            "mode": "positions",
            "positions": [{"strand": "+", "tss": 100}, {"strand": "-", "tss": 129}],
        },
        **changes,
    }


def one(**changes):
    return pio.predict_batch(request(**changes))["results"][0]


@pytest.fixture(autouse=True)
def validate_every_result(monkeypatch):
    """The independent schema must accept every result emitted through public calls."""
    schema = json.loads((ROOT / "schemas/promoter-result-1.0.schema.json").read_text())
    validator = Draft202012Validator(schema)
    original = pio.predict_batch

    def checked(*args, **kwargs):
        result = original(*args, **kwargs)
        validator.validate(result)
        return result

    monkeypatch.setattr(pio, "predict_batch", checked)


@pytest.mark.parametrize(
    "text",
    [
        "{",
        "[] trailing",
        '{"a":1,"a":2}',
        '{"x":NaN}',
        '{"x":Infinity}',
        '{"x":1e999}',
        '"\ud800"',
        "[" * 1500,
    ],
)
def test_bad_json(text):
    with pytest.raises(pio.SetupError):
        pio.load_requests(io.StringIO(text))


def test_input_byte_limit_is_utf8_and_exact(monkeypatch):
    text = '{"unicode":"é"}'
    count = len(text.encode())
    monkeypatch.setitem(pio.LIMITS, "max_input_json_bytes", count)
    assert pio.load_requests(io.StringIO(text)) == {"unicode": "é"}
    monkeypatch.setitem(pio.LIMITS, "max_input_json_bytes", count - 1)
    with pytest.raises(pio.SetupError, match="max_input_json_bytes"):
        pio.load_requests(io.StringIO(text))


@pytest.mark.parametrize(
    "defaults",
    [{"host": None}, {"calibration": None}, {"output": None}, {"host": {"name": ""}}],
)
def test_invalid_defaults_are_setup_errors_even_without_records(defaults):
    with pytest.raises(pio.SetupError, match="invalid defaults"):
        pio.predict_batch({"defaults": defaults, "records": []})


def test_defaults_host_never_selects_calibration():
    r = request()
    del r["calibration"]
    result = pio.predict_batch(
        {"defaults": {"host": {"name": "in vitro"}}, "records": [r]}
    )
    assert result["results"][0]["reasons"] == ["calibration_required"]


def test_projection_requires_explicit_crossing_and_respects_effective_fields(
    monkeypatch,
):
    p = projection()
    del p["origin_crossing"]
    assert one(projection=p)["reasons"] == ["invalid_projection"]
    monkeypatch.setitem(pio.LIMITS, "max_contig_chars", 2)
    assert one(projection=projection())["reasons"] == ["invalid_projection"]
    monkeypatch.setitem(pio.LIMITS, "max_host_name_chars", 2)
    assert one(host={"name": "abc"})["reasons"] == ["invalid_host"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        True,
        {"schema_version": "2"},
        {"records": [], "extra": 1},
        {"records": None},
        {"records": [None] * 101},
        {"records": [], "defaults": []},
        {"records": [], "defaults": {"sequence": "A"}},
        {"metadata": float("nan")},
        {"metadata": object()},
    ],
)
def test_setup_rejections(value):
    with pytest.raises(pio.SetupError):
        pio.predict_batch(value)


@pytest.mark.parametrize(
    "option,value",
    [
        ("seconds_per_record", False),
        ("seconds_per_record", 0),
        ("seconds_per_record", 120.1),
        ("seconds_per_record", float("nan")),
        ("seconds_per_batch", -1),
        ("seconds_per_batch", float("inf")),
        ("seconds_per_batch", "20"),
        ("cli_calibration", "other"),
        ("cli_states", "other"),
        ("output_format", "other"),
    ],
)
def test_invalid_options(option, value):
    with pytest.raises(pio.SetupError):
        pio.predict_batch(request(), **{option: value})


def test_identity_exact_payload_and_normalization():
    value = request(sequence=" a\n" * 200, metadata={"x": [1.0, "é"]})
    result = pio.predict_batch(value, seconds_per_record=20)
    record = result["results"][0]
    assert record["input"] == {
        "raw_sha256": hashlib.sha256(value["sequence"].encode()).hexdigest(),
        "normalized_dna_sha256": hashlib.sha256(b"A" * 200).hexdigest(),
        "length": 200,
        "normalization": "ascii-whitespace-uppercase-u-to-t-1",
    }
    model, identity = pio.model_identity(promoter.load_parameters())
    assert result["model"] == model
    assert set(identity) == {
        "id",
        "implementation_version",
        "parameter_json_sha256",
        "coefficient_array_sha256",
        "intercept_array_sha256",
        "source_commit",
    }

    def digest(v):
        return hashlib.sha256(
            json.dumps(
                v,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    scope = digest(
        {
            "schema_version": "1.0",
            "model": identity,
            "calibration": {"profile": "in_vitro", "host": None},
            "normalized_dna_sha256": hashlib.sha256(b"A" * 200).hexdigest(),
            "projection": None,
        }
    )
    assert record["prediction_id"] == digest(
        {"scope_id": scope, "scan": value["scan"], "output": pio.OUTPUT_DEFAULTS}
    )
    assert record["sites"][0]["site_id"] == f"psite1:{scope[:32]}:+:100"
    assert record["sites"][0]["selected"]["state_id"].endswith(":d6s17")
    assert result["batch"]["batch_id"] == digest(
        {
            "input": value,
            "model": {
                k: identity[k]
                for k in ("id", "implementation_version", "parameter_json_sha256")
            },
            "limits": pio.LIMITS,
            "seconds_per_record": 20.0,
            "seconds_per_batch": 300.0,
            "cli_calibration": None,
            "cli_states": None,
        }
    )
    renamed = pio.predict_batch(value | {"id": "other", "metadata": {}})
    assert renamed["results"][0]["prediction_id"] == record["prediction_id"]
    assert renamed["batch"]["batch_id"] != result["batch"]["batch_id"]
    assert one()["input"]["normalization"] == record["input"]["normalization"]


def test_all_states_and_output_defaults_replace_atomically():
    value = {
        "defaults": {
            "calibration": "in_vitro",
            "host": {"name": "in vitro"},
            "output": {"states": "all", "legacy_keys": True},
        },
        "records": [
            request(output={"elements": False}),
            request(id="other", output={"states": "all", "legacy_keys": True}),
        ],
    }
    result = pio.predict_batch(value)
    first, second = result["results"]
    assert "states" not in first["sites"][0]
    assert "elements" not in first["sites"][0]["selected"]
    assert first["calibration"]["host"] == {"name": "in vitro", "taxon_id": None}
    site = second["sites"][0]
    assert len(site["states"]) == 30 and sum(s["selected"] for s in site["states"]) == 1
    assert site["tie_count"] == 5
    assert site["legacy_source_key"] == 100
    assert second["sites"][1]["legacy_source_key"] == 130
    assert all("elements" not in s for s in site["states"])
    assert second["warnings"][-1]["code"] == "legacy_key_not_coordinate"


def test_cli_defaults_and_conflicts():
    value = request()
    del value["calibration"]
    assert (
        pio.predict_batch(value, cli_calibration="in_vitro", cli_states="all")[
            "results"
        ][0]["status"]
        == "ok"
    )
    for kwargs in ({"cli_calibration": "ecoli_mg1655"}, {"output_format": "csv"}):
        with pytest.raises(pio.SetupError):
            pio.predict_batch(request(output={"states": "all"}), **kwargs)
    with pytest.raises(pio.SetupError, match="states conflicts"):
        pio.predict_batch(request(output={"states": "all"}), cli_states="selected")
    with pytest.raises(pio.SetupError, match="calibration conflicts"):
        pio.predict_batch(
            {"defaults": {"calibration": "in_vitro"}, "records": []},
            cli_calibration="ecoli_mg1655",
        )
    assert (
        pio.predict_batch({"records": [None]}, cli_states="all")["results"][0]["status"]
        == "invalid_input"
    )
    assert (
        pio.predict_batch(request(output=None), cli_states="all")["results"][0][
            "status"
        ]
        == "invalid_input"
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"id": 1}, "invalid_id"),
        ({"id": "a\n"}, "invalid_id"),
        ({"id": "a" * 129}, "invalid_id"),
        ({"what": 1}, "unknown_field"),
        ({"sequence": 1}, "invalid_type"),
        ({"sequence": ""}, "empty_sequence"),
        ({"sequence": "AN"}, "ambiguous_base"),
        ({"sequence": "A?"}, "invalid_character"),
        ({"sequence": "TU"}, "mixed_dna_rna"),
        ({"sequence": "A" * 5001}, "limit_exceeded"),
        ({"sequence": " " * 50001}, "limit_exceeded"),
        ({"calibration": None}, "invalid_calibration"),
        ({"host": None}, "invalid_host"),
        ({"host": {"name": "a", "taxon_id": None}}, "invalid_host"),
        ({"output": None}, "invalid_output_option"),
        ({"output": {"x": 1}}, "invalid_output_option"),
        ({"output": {"states": []}}, "invalid_output_option"),
        ({"output": {"elements": 1}}, "invalid_output_option"),
        ({"metadata": None}, "invalid_type"),
        ({"metadata": {"a": "x" * 4096}}, "limit_exceeded"),
        ({"metadata": {"a": [{"b": [{"c": 0}]}]}}, "limit_exceeded"),
        ({"model": {}}, "invalid_type"),
        ({"model": {"id": "x", "parameter_json_sha256": "bad"}}, "invalid_type"),
        ({"projection": None}, "invalid_projection"),
    ],
)
def test_record_errors(changes, code):
    record = one(**changes)
    assert record["status"] == "invalid_input"
    assert code in record["reasons"]
    assert record["prediction_id"] is None and record["coverage"] is None
    assert record["sites"] == []


@pytest.mark.parametrize(
    "scan,code",
    [
        (None, "invalid_scan"),
        ({}, "invalid_scan"),
        ({"mode": "scan"}, "invalid_scan"),
        ({"mode": "scan", "range": None, "strands": ["+"]}, "invalid_scan"),
        ({"mode": "scan", "range": [0], "strands": ["+"]}, "invalid_scan"),
        ({"mode": "scan", "range": [True, 2], "strands": ["+"]}, "invalid_scan"),
        ({"mode": "scan", "range": [0.5, 2], "strands": ["+"]}, "invalid_scan"),
        ({"mode": "scan", "range": [0, "2"], "strands": ["+"]}, "invalid_scan"),
        ({"mode": "scan", "range": [-1, 2], "strands": ["+"]}, "range_out_of_bounds"),
        ({"mode": "scan", "range": [2, 1], "strands": ["+"]}, "range_out_of_bounds"),
        ({"mode": "scan", "range": [0, 201], "strands": ["+"]}, "range_out_of_bounds"),
        ({"mode": "scan", "range": [0, 2], "strands": []}, "invalid_strand"),
        ({"mode": "scan", "range": [0, 2], "strands": "++"}, "invalid_strand"),
        ({"mode": "scan", "range": [0, 2], "strands": ["+", "+"]}, "invalid_strand"),
        ({"mode": "scan", "range": [0, 2], "strands": [{}]}, "invalid_strand"),
        ({"mode": "positions", "positions": None}, "invalid_scan"),
        ({"mode": "positions", "positions": [{}]}, "invalid_scan"),
        ({"mode": "positions", "positions": [None]}, "invalid_scan"),
        (
            {"mode": "positions", "positions": [{"strand": "x", "tss": 1}]},
            "invalid_strand",
        ),
        (
            {"mode": "positions", "positions": [{"strand": "+", "tss": -1}]},
            "position_out_of_range",
        ),
        (
            {"mode": "positions", "positions": [{"strand": "+", "tss": 200}]},
            "position_out_of_range",
        ),
        (
            {"mode": "positions", "positions": [{"strand": "+", "tss": 1}] * 2},
            "duplicate_position",
        ),
    ],
)
def test_scan_rejections(scan, code):
    record = one(scan=scan)
    assert code in record["reasons"] and record["scan"] is None


def test_missing_fields_and_continuity():
    result = pio.predict_batch(
        {
            "records": [
                None,
                {},
                request(),
                request(),
                request(id="unsupported", temperature=37),
                request(id="invalid", temperature=37, what=2),
            ]
        }
    )
    records = result["results"]
    assert [r["status"] for r in records] == [
        "invalid_input",
        "invalid_input",
        "ok",
        "invalid_input",
        "unsupported",
        "invalid_input",
    ]
    assert set(records[1]["reasons"]) == {
        "missing_field",
        "calibration_required",
        "scan_required",
    }
    assert records[3]["id"] == "synthetic" and records[3]["reasons"] == ["duplicate_id"]
    assert result["batch"]["complete"] is True
    assert (
        one(model={"id": "other", "parameter_json_sha256": "0" * 64})["status"]
        == "unsupported"
    )
    assert (
        one(
            model={
                "id": promoter.MODEL_ID,
                "parameter_json_sha256": promoter.PARAMETER_JSON_SHA256,
            }
        )["status"]
        == "ok"
    )


def projection(**changes):
    return {
        "contig": "chr",
        "origin": 500,
        "contig_length": 1000,
        "topology": "linear",
        "origin_crossing": False,
        **changes,
    }


def test_projection_conflicts_and_rejected_field_nulls():
    result = pio.predict_batch(
        {
            "records": [
                request(projection=projection()),
                request(id="other", projection=projection(contig_length=2000)),
            ]
        }
    )
    assert result["results"][1]["projection"] is None
    assert result["results"][1]["reasons"] == ["contig_metadata_conflict"]
    record = one(sequence="?", projection=projection(), metadata={"a": []})
    assert record["projection"] is None and record["scan"] is None
    assert record["input"]["raw_sha256"] == hashlib.sha256(b"?").hexdigest()
    assert record["input"]["normalization"] is None
    assert record["metadata"] == {"a": []} and record["calibration"] is not None
    record = one(what=1, metadata={})
    assert record["input"]["length"] == 200 and record["metadata"] == {}
    assert one()["metadata"] is None
    a = one(projection=projection())
    b = one(projection=projection(origin=700, sequence_strand="-"))
    assert a["prediction_id"] != b["prediction_id"]
    assert b["sites"][0]["genomic"]["strand"] == "-"


def test_limit_accounting_and_empty_noop(monkeypatch):
    assert pio.predict_batch({"records": []})["batch"]["record_count"] == 0
    monkeypatch.setitem(pio.LIMITS, "max_normalized_bases_per_batch", 200)
    result = pio.predict_batch(
        {"records": [request(sequence="?"), request(id="good"), request(id="over")]}
    )
    assert [r["status"] for r in result["results"]] == [
        "invalid_input",
        "ok",
        "invalid_input",
    ]
    error = result["results"][2]["errors"][0]
    assert (error["limit"], error["observed"]) == (
        "max_normalized_bases_per_batch",
        400,
    )


@pytest.mark.parametrize(
    "limit,value,all_states",
    [
        ("max_planned_sites_per_record", 1, False),
        ("max_planned_sites_per_batch", 1, False),
        ("max_all_state_sites_per_record", 1, True),
        ("max_all_states_per_record", 59, True),
        ("max_all_states_per_batch", 59, True),
    ],
)
def test_every_computation_budget(limit, value, all_states, monkeypatch):
    monkeypatch.setitem(pio.LIMITS, limit, value)
    record = one(output={"states": "all" if all_states else "selected"})
    assert record["status"] == "invalid_input"
    assert any(e.get("limit") == limit for e in record["errors"])


def test_scan_order_integral_normalization_and_edges():
    record = one(scan={"mode": "scan", "range": [56.0, 60.0], "strands": ["+", "-"]})
    assert [s["state_count"] for s in record["sites"][:4]] == [0, 0, 1, 3]
    assert [(s["strand"], s["tss"]["forward_base"]) for s in record["sites"]] == [
        (s, f) for s in ("+", "-") for f in range(56, 60)
    ]
    assert record["coverage"]["partial_state_sites"] == 2
    assert record["coverage"]["insufficient_context_sites"] == 2
    assert record["coverage"]["complete"] and not record["coverage"]["complete_context"]
    assert record["scan"]["range"] == [56, 60]
    for count in (0, 1, 4, 12):
        r = one(
            sequence="A" * (count + 86),
            scan={"mode": "scan", "range": [67, 67 + count], "strands": ["+"]},
        )
        assert len(r["sites"]) == count and r["coverage"]["complete_context"]
    assert (
        one(
            sequence="A" * 77,
            scan={"mode": "positions", "positions": [{"strand": "+", "tss": 58}]},
        )["status"]
        == "no_candidate"
    )


def test_deadline_precedence_retention_and_completed_record():
    # batch starts at 0, first record starts 0; first site at 0, second at 3.
    clock = iter([0, 0, 0, 3, 3, 3, 3])
    empty = request(id="empty", scan={"mode": "positions", "positions": []})
    value = {
        "records": [
            request(),
            empty,
            request(id="later"),
            empty | {"id": "bad", "what": 1},
        ]
    }
    result = pio.predict_batch(value, seconds_per_batch=2, clock=lambda: next(clock))
    first, zero, later, bad = result["results"]
    assert [s["status"] for s in first["sites"]] == ["ok", "failed"]
    assert first["coverage"]["unattempted_sites"] == 1
    assert later["coverage"]["unattempted_sites"] == 2
    assert zero["reasons"] == ["empty_scan"] and zero["coverage"]["complete"]
    assert zero["coverage"]["truncation"] is None
    assert bad["status"] == "invalid_input"
    clock = iter([0, 0, 0, 0, 5, 5, 5])
    result = pio.predict_batch(
        {"records": [request(), request(id="later")]},
        seconds_per_batch=2,
        clock=lambda: next(clock),
    )
    assert [r["status"] for r in result["results"]] == ["ok", "failed"]


def test_real_tight_deadline_all_state_retention():
    result = pio.predict_batch(
        request(output={"states": "all"}), seconds_per_record=1e-300
    )
    record = result["results"][0]
    assert record["status"] == "failed"
    assert all(
        s["states"] == [] and not s["attempted"] and s["state_count"] == 30
        for s in record["sites"]
    )


def test_nonfinite_attempted_failure(monkeypatch):
    def failed(local, strand, f, params, cal, *, keep_states):
        return promoter.SiteResult(
            strand,
            f,
            f if strand == "+" else len(local) - 1 - f,
            len(local),
            "failed",
            "nonfinite_arithmetic",
            30,
            None,
            None,
            () if keep_states else None,
            cal,
        )

    monkeypatch.setattr(promoter, "score_site", failed)
    record = one()
    assert record["coverage"]["failed_sites"] == 2
    assert record["coverage"]["unattempted_sites"] == 0
    assert record["coverage"]["truncation"]["reason"] == "nonfinite_arithmetic"


def test_authoritative_bytes_limit_and_json(monkeypatch):
    result = pio.predict_batch(request(metadata={"é": 1}))
    stream = io.StringIO()
    pio.write_json(result, stream)
    expected = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    )
    assert stream.getvalue() == expected and "\\u00e9" in expected
    assert pio.result_bytes(result) == expected.encode()
    assert pio.result_bytes(result) == pio.result_bytes(
        pio.predict_batch(request(metadata={"é": 1}))
    )
    # Cap itself changes the serialized limits field, so solve for its own size.
    cap = len(expected.encode())
    for _ in range(3):
        result["batch"]["limits"]["max_result_json_bytes"] = cap
        cap = len(pio.result_bytes(result))
    monkeypatch.setitem(pio.LIMITS, "max_result_json_bytes", cap)
    actual = pio.predict_batch(request(metadata={"é": 1}))
    assert len(pio.result_bytes(actual)) == cap
    monkeypatch.setitem(pio.LIMITS, "max_result_json_bytes", cap - 1)
    with pytest.raises(pio.SetupError, match="max_result_json_bytes"):
        pio.predict_batch(request(metadata={"é": 1}), output_format="csv")


def test_csv_retains_nulls_and_column_order():
    result = pio.predict_batch(
        {
            "records": [
                request(
                    scan={"mode": "scan", "range": [57, 59], "strands": ["+"]},
                    projection=projection(),
                ),
                request(id="empty", scan={"mode": "positions", "positions": []}),
                {},
            ]
        }
    )
    stream = io.StringIO()
    pio.write_csv(result, stream)
    reader = csv.DictReader(io.StringIO(stream.getvalue()))
    rows = list(reader)
    assert reader.fieldnames == pio.CSV_COLUMNS
    assert len(rows) == 4
    assert rows[0]["score_total"] == "" and rows[0]["state_count"] == "0"
    assert rows[1]["genomic_base"] == "558" and rows[1]["genomic_strand"] == "+"
    assert rows[2]["site_id"] == "" and rows[3]["record_id"] == ""


def test_gff3_linear_circular_comments_and_escaping():
    values = [
        request(id="plain"),
        request(id="linear", projection=projection(contig="chr;é")),
        request(
            id="same",
            projection=projection(contig="chr;é"),
            scan={"mode": "positions", "positions": []},
        ),
        request(
            id="circular",
            projection=projection(
                origin=950, topology="circular", origin_crossing=True
            ),
        ),
        request(
            id="edge",
            projection=projection(),
            scan={"mode": "positions", "positions": [{"strand": "+", "tss": 0}]},
        ),
        request(
            id="wrapped-minus",
            projection=projection(
                contig="minus",
                origin=50,
                sequence_strand="-",
                topology="circular",
                origin_crossing=True,
            ),
        ),
    ]
    # Give the linear edge a distinct contig from the circular records.
    values[4]["projection"]["contig"] = "edge"
    result = pio.predict_batch({"records": values})
    stream = io.StringIO()
    pio.write_gff3(result, stream)
    text = stream.getvalue()
    assert "export_reason=projection_required sites=2" in text
    assert "chr%3B%C3%A9" in text and text.count("##sequence-region chr%3B%C3%A9") == 1
    assert (
        "status=no_candidate sites=0" in text and "reason=insufficient_context" in text
    )
    rows = [line.split("\t") for line in text.splitlines() if not line.startswith("#")]
    assert all(row[2] == "region" and row[5] == "." for row in rows)
    assert any(row[0] == "chr" and int(row[4]) > 1000 for row in rows)
    assert any(row[6] == "-" and "model_element=hex35" in row[8] for row in rows)
    assert any(
        row[3:5] == ["566", "571"] and "model_element=hex35" in row[8] for row in rows
    )
