"""Artificial-only checks for the independently specified coupling oracle."""

from __future__ import annotations

import ast
import copy
import json
import math
import runpy
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmarks.operon import coupling_reference as ref

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "benchmarks/operon/coupling-numeric-protocol.json"
SOURCE = ROOT / ref.SOURCE_PATHS[1]


@pytest.fixture
def protocol():
    return ref.strict_json(PROTOCOL.read_bytes())


@pytest.fixture
def fixture():
    return ref.build_fixture(PROTOCOL.read_bytes(), SOURCE.read_bytes())


def test_source_arithmetic_exact():
    checked = ref.scalar_checks(ref.strict_json(SOURCE.read_bytes()))
    assert [Decimal(c["total"]) for c in checked] == list(
        map(Decimal, ["1.072", "1.072", "1.22", "2.288", "2.88"])
    )
    assert ref.coefficient(-4) == Decimal("0.0220")
    assert ref.coefficient(25) == Decimal("0.0072")
    assert ref.coefficient(-3) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s.update(schema_version="other"),
        lambda s: s["cases"].pop(),
        lambda s: s["cases"][0].update(k_reinit="0.1"),
        lambda s: s["cases"][0].update(k_p="11"),
        lambda s: s["cases"][0].update(reinitiation_rate="1"),
        lambda s: s["cases"][0].update(total_rate="2"),
        lambda s: s["unsupported_distances_nt"].append(0),
    ],
)
def test_source_failures(mutate):
    source = ref.strict_json(SOURCE.read_bytes())
    mutate(source)
    with pytest.raises(ref.AdmissionError):
        ref.scalar_checks(source)


def test_oracle_independent_limits():
    scores = ref.scalar_oracle(0.0, 0.0, -4)
    assert scores["reinitiation_contribution"]["value"] == 0.22
    assert scores["downstream_total"]["value"] == 1.22
    assert scores["fold_change"]["log_value"] == pytest.approx(math.log(1.22))
    # Common energy changes alter absolute scale, not the equal-energy fold.
    for energy in (-1e6, -2000, 0, 1000, 2000, 1e6):
        result = ref.scalar_oracle(energy, energy, 0)
        assert result["fold_change"]["value"] == 1.072
        assert all(math.isfinite(x["log_value"]) for x in result.values())
        if abs(energy) >= 2000:
            assert result["downstream_total"]["value"] is None
    dominant = ref.scalar_oracle(-1000.0, 1000.0, 3)
    assert dominant["fold_change"]["value"] is None
    assert all(dominant[k]["value"] > 0 for k in ref.SCORES[:-1])
    assert ref.scalar_oracle(0, 0, 26) is None


@pytest.mark.parametrize("energy", [True, "0", math.nan, math.inf, -1000001, 1000001])
def test_energy_guard(energy):
    with pytest.raises(ref.AdmissionError, match="Energy"):
        ref.scalar_oracle(energy, 0, 0)


@pytest.mark.parametrize("distance", [False, 0.0, "0"])
def test_distance_guard(distance):
    with pytest.raises(ref.AdmissionError, match="integer"):
        ref.coefficient(distance)


def test_full_fixture_and_mirrors(fixture):
    records = fixture["expected_records"]
    assert len(records) == 24
    assert sum(r["status"] == "ok" for r in records) == 11
    assert sum(r["status"] == "numerical_range" for r in records) == 7
    assert sum(r["status"] == "unsupported_distance" for r in records) == 6
    assert records[0]["geometry"]["upstream"]["oriented_interval"] == [3, 33]
    assert records[1]["geometry"]["downstream"]["oriented_interval"] == [58, 88]
    assert records[2]["geometry"]["distance_nt"] == -4
    assert records[2]["geometry"]["downstream"]["start_codon"] == "UUG"
    for a, b in zip(records[:5], records[5:10], strict=True):
        assert a["scores"] == b["scores"]
        assert (
            a["geometry"]["oriented_sequence_sha256"]
            == b["geometry"]["oriented_sequence_sha256"]
        )
        for label in ("upstream", "downstream"):
            start, end = a["geometry"][label]["interval"]
            length = b["geometry"]["sequence_length"]
            assert b["geometry"][label]["interval"] == [length - end, length - start]
    # Independent schema use in tests only; the benchmark tool stays stdlib-only.
    import jsonschema

    jsonschema.validate(
        fixture["request"], json.loads((ROOT / ref.SOURCE_PATHS[4]).read_text())
    )


@pytest.mark.parametrize(
    "change,match",
    [
        ({"sequence": "X"}, "RNA"),
        ({"strand": "?"}, "strand"),
        ({"upstream": {"id": "toy-up", "interval": [-1, 29]}}, "interval"),
        ({"upstream": {"id": "toy-up", "interval": [3, 32]}}, "Incomplete"),
    ],
)
def test_geometry_simple_rejections(fixture, change, match):
    record = fixture["request"]["records"][0]
    record.update(change)
    with pytest.raises(ref.AdmissionError, match=match):
        ref.geometry(record)


@pytest.mark.parametrize(
    "start,text,match",
    [(3, "CCC", "start"), (30, "CCC", "stop"), (6, "UAA", "Internal")],
)
def test_geometry_codon_rejections(fixture, start, text, match):
    record = fixture["request"]["records"][0]
    s = record["sequence"]
    record["sequence"] = s[:start] + text + s[start + 3 :]
    with pytest.raises(ref.AdmissionError, match=match):
        ref.geometry(record)


def test_geometry_order_and_same_frame(fixture):
    record = fixture["request"]["records"][0]
    record["upstream"], record["downstream"] = record["downstream"], record["upstream"]
    with pytest.raises(ref.AdmissionError, match="order"):
        ref.geometry(record)
    # Identical CDS intervals also violate the independently required order.
    record = copy.deepcopy(fixture["request"]["records"][0])
    record["downstream"]["interval"] = [3, 33]
    with pytest.raises(ref.AdmissionError, match="order"):
        ref.geometry(record)


@pytest.mark.parametrize(
    "change,match",
    [
        ({"distance_nt": -30}, "bounds"),
        ({"distance_nt": -3}, "overlap"),
        ({"strand": "?"}, "strand"),
        ({"input_style": "?"}, "style"),
    ],
)
def test_construction_guards(protocol, change, match):
    spec = protocol["case_specs"][0]
    spec.update(change)
    with pytest.raises(ref.AdmissionError, match=match):
        ref.artificial_record(spec, "synthetic")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(schema_version="wrong"),
        lambda p: p["numerics"].update(decimal_precision=20),
        lambda p: p["numerics"].update(rounding="other"),
        lambda p: p["numerics"].update(linear_relative_tolerance="1e-6"),
        lambda p: p["equations"].update(beta="1"),
        lambda p: p["source_pins"][ref.SOURCE_PATHS[1]].update(sha256="0" * 64),
        lambda p: p["case_specs"].pop(),
        lambda p: p["case_specs"][0].update(id=p["case_specs"][1]["id"]),
    ],
)
def test_protocol_failures(protocol, mutate):
    mutate(protocol)
    with pytest.raises(ref.AdmissionError):
        ref.build_fixture(ref.pretty(protocol), SOURCE.read_bytes())


@pytest.mark.parametrize(
    "data", [b'{"x":1,"x":2}', b"NaN", b"1e400", b"\xff", b"{}x", b"["]
)
def test_strict_json(data):
    with pytest.raises(ref.AdmissionError):
        ref.strict_json(data)


def test_json_limits_and_encoding():
    assert ref.strict_json(b'{"x":[true,null,2.0]}') == {"x": [True, None, 2.0]}
    assert ref.canonical({"z": "é", "a": 2.0}) == b'{"a":2.0,"z":"\\u00e9"}'
    assert ref.canonical(2) != ref.canonical(2.0)
    assert ref.pretty({"é": [1]}) == b'{\n  "\\u00e9": [\n    1\n  ]\n}\n'
    for data in (
        b" " * (ref.MAX_BYTES + 1),
        b"[" * 34 + b"0" + b"]" * 34,
        b"[" + b"0," * 100000 + b"0]",
    ):
        with pytest.raises(ref.AdmissionError):
            ref.strict_json(data)
    with pytest.raises(ref.AdmissionError):
        ref.strict_json(b"[" * 10000 + b"]" * 10000)


def test_io_atomic_and_identity(tmp_path):
    output = tmp_path / "new.json"
    ref.write_new(output, {"value": 1})
    saved = output.read_bytes()
    assert ref.read_bytes(output, ref.pin(saved)) == saved
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        ref.write_new(output, {"value": 2})
    assert output.read_bytes() == saved
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.json"]
    with pytest.raises(ref.AdmissionError, match="identity"):
        ref.read_bytes(output, {"bytes": 0, "sha256": "0" * 64})
    output.write_bytes(b" " * (ref.MAX_BYTES + 1))
    with pytest.raises(ref.AdmissionError, match="byte"):
        ref.read_bytes(output)
    with pytest.raises(ref.AdmissionError, match="Output"):
        ref.write_new(tmp_path / "huge", "x" * ref.MAX_BYTES)
    with patch.object(ref.os, "fsync", side_effect=OSError("disk failure")):
        with pytest.raises(OSError, match="disk failure"):
            ref.write_new(tmp_path / "failed", {})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.json"]


def test_prepare_and_cli(tmp_path, capsys):
    output = tmp_path / "fixture.json"
    args = [
        "prepare",
        "--protocol",
        str(PROTOCOL),
        "--protocol-sha256",
        ref.sha(PROTOCOL.read_bytes()),
        "--root",
        str(ROOT),
        "--output",
        str(output),
    ]
    assert ref.main(args) == 0
    assert "predictions_executed=0" in capsys.readouterr().out
    assert len(ref.strict_json(output.read_bytes())["expected_records"]) == 24
    assert ref.main(args) == 2
    assert "exists" in capsys.readouterr().err
    args[args.index("--protocol-sha256") + 1] = "0" * 64
    assert ref.main(args) == 2
    assert "trust pin" in capsys.readouterr().err
    with patch.object(sys, "argv", ["coupling-reference", *args]):
        with pytest.raises(SystemExit) as result:
            runpy.run_path(ref.__file__, run_name="__main__")
    assert result.value.code == 2


def test_allowlist_before_public_reads(tmp_path, protocol):
    protocol["source_pins"]["private.json"] = {"bytes": 0, "sha256": "0" * 64}
    data = ref.pretty(protocol)
    file = tmp_path / "protocol.json"
    file.write_bytes(data)
    with pytest.raises(ref.AdmissionError, match="allowlist"):
        ref.prepare(file, ref.sha(data), tmp_path, tmp_path / "out")


def test_semantic_comparison_retains_all_cases(fixture):
    records = copy.deepcopy(fixture["expected_records"])
    assert all(c["conforms"] for c in ref.compare_records(fixture, records))
    records[0]["scores"]["downstream_total"]["value"] = 1.5
    records[5]["geometry"]["upstream"]["interval"][0] += 1
    records[10]["status"] = "ok"
    records[16]["scores"]["downstream_total"]["value"] = 0.0
    cases = ref.compare_records(fixture, records)
    assert len(cases) == 24
    assert [c["index"] for c in cases if not c["conforms"]] == [0, 5, 10, 16]
    assert cases[0]["mismatched_fields"] == ["/scores/downstream_total/value"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop(),
        lambda r: r.reverse(),
        lambda r: r[0].update(index=True),
        lambda r: r[0].update(id="foreign"),
        lambda r: r.__setitem__(0, None),
    ],
)
def test_roster_rejected_before_comparison(fixture, mutate):
    records = copy.deepcopy(fixture["expected_records"])
    mutate(records)
    with pytest.raises(ref.AdmissionError, match="roster"):
        ref.compare_records(fixture, records)


@pytest.mark.parametrize(
    "expected,observed,path,passes",
    [
        ({"a": 1}, None, "", False),
        ({"a": 1}, {"b": 1}, "", False),
        ([1], {}, "", False),
        ([1], [], "", False),
        (1.0, True, "", False),
        (1.0, math.inf, "", False),
        (1.0, 10**1000, "", False),
        (1.0, 2.0, "", False),
        (1.0, 1, "", True),
        (None, 0, "", False),
        (0, False, "", False),
        (0.0, 0.5e-12, "/scores/q/log_value", True),
        (0.0, 2e-12, "/scores/q/log_value", False),
        (1e-200, 0.0, "/scores/q/value", False),
        (1e-200, 1.0000000000005e-200, "/scores/q/value", True),
        (1e-200, 1.000000000002e-200, "/scores/q/value", False),
        (math.ulp(0.0), 5 * math.ulp(0.0), "/scores/q/value", True),
        (math.ulp(0.0), 6 * math.ulp(0.0), "/scores/q/value", False),
    ],
)
def test_comparison_types_and_fixed_tolerances(expected, observed, path, passes):
    assert (not ref.differences(expected, observed, path)) is passes


def test_fixture_exact_pin_and_determinism(fixture):
    committed = ROOT / "benchmarks/operon/coupling-numeric-fixtures.json"
    assert committed.read_bytes() == ref.pretty(fixture)
    assert fixture["protocol"] == ref.pin(PROTOCOL.read_bytes())
    assert fixture["source_scalar_fixture"] == ref.pin(SOURCE.read_bytes())
    assert len(fixture["source_checks"]) == 5


def test_expected_records_obey_public_schema(fixture):
    import jsonschema

    schema = json.loads((ROOT / ref.SOURCE_PATHS[5]).read_text())
    model = {
        key: value["const"]
        for key, value in schema["properties"]["model"]["properties"].items()
        if "const" in value
    }
    model.update(implementation_version="artificial-test", backend=None)
    result = {
        "schema_version": "coupling-result-1",
        "model": model,
        "request_sha256": "0" * 64,
        "prediction_sha256": "0" * 64,
        "status": "partial",
        "reason": None,
        "settings": fixture["request"]["settings"],
        "coverage": {
            "requested": 24,
            "returned": 24,
            "successful": 11,
            "failed_or_unsupported": 13,
            "not_evaluated": 0,
        },
        "warnings": ["artificial-schema-only"] * 4,
        "records": fixture["expected_records"],
    }
    jsonschema.validate(result, schema)


def test_tool_import_boundary():
    tree = ast.parse(Path(ref.__file__).read_text())
    imports = {
        name.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for name in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imports <= {
        "__future__",
        "argparse",
        "hashlib",
        "json",
        "math",
        "os",
        "re",
        "pathlib",
        "sys",
        "tempfile",
        "decimal",
        "typing",
    }
    assert not any(
        name == "regsite" or name.startswith("regsite.") for name in sys.modules
    )


def artificial_envelope(fixture):
    return {
        "schema_version": "coupling-result-1",
        "model": {"independent_test_only": True},
        "request_sha256": "0" * 64,
        "prediction_sha256": "0" * 64,
        "status": "partial",
        "reason": None,
        "settings": fixture["request"]["settings"],
        "coverage": {
            "requested": 24,
            "returned": 24,
            "successful": 11,
            "failed_or_unsupported": 13,
            "not_evaluated": 0,
        },
        "warnings": ["artificial-only"] * 4,
        "records": copy.deepcopy(fixture["expected_records"]),
    }


def set_path(value, path, replacement):
    parts = path.split("/")
    for part in parts[:-1]:
        value = value[int(part)] if isinstance(value, list) else value[part]
    value[int(parts[-1]) if isinstance(value, list) else parts[-1]] = replacement


def test_all_record_statuses_and_accounting(fixture):
    result = artificial_envelope(fixture)
    ref.result_accounting(result)
    for status in ("invalid_input", "unsupported_geometry", "not_evaluated"):
        r = result["records"][0]
        r.update(
            status=status,
            reason="time_budget_exhausted"
            if status == "not_evaluated"
            else "artificial",
            geometry=None,
            energies=None,
            coefficient=None,
            scores=None,
        )
        result["coverage"].update(
            successful=10,
            failed_or_unsupported=14 - (status == "not_evaluated"),
            not_evaluated=int(status == "not_evaluated"),
        )
        ref.result_accounting(result)
        cases = ref.compare_records(fixture, result["records"])
        assert len(cases) == 24 and not cases[0]["conforms"]
    r["id"] = None
    ref.record_shape(r)
    result = artificial_envelope(fixture)
    result["records"] = result["records"][:1]
    result["coverage"] = {
        "requested": 1,
        "returned": 1,
        "successful": 1,
        "failed_or_unsupported": 0,
        "not_evaluated": 0,
    }
    result["status"] = "complete"
    ref.result_accounting(result)


@pytest.mark.parametrize(
    "path,value",
    [
        ("schema_version", "wrong"),
        ("reason", "unexpected"),
        ("settings/seconds_total", False),
        ("settings/seconds_total", 0),
        ("settings/seconds_total", 61),
        ("settings", {}),
        ("warnings", []),
        ("warnings", [1, 2, 3, 4]),
        ("request_sha256", None),
        ("prediction_sha256", "ABC"),
        ("records", []),
        ("records", None),
        ("status", "complete"),
        ("coverage/successful", 12),
        ("coverage/not_evaluated", False),
        ("records/0/index", True),
        ("records/0/id", "invalid space"),
        ("records/0/id", None),
        ("records/0/status", "invented"),
        ("records/0/unfolding_correction", 0),
        ("records/0/reason", "bad"),
        ("records/0/geometry/sequence_sha256", "f" * 63),
        ("records/0/geometry/strand", "?"),
        ("records/0/geometry/distance_nt", 0.0),
        ("records/0/geometry/sequence_length", 0),
        ("records/0/geometry/upstream/id", ""),
        ("records/0/geometry/upstream/interval", [True, 33]),
        ("records/0/geometry/upstream/oriented_interval", [3, 100001]),
        ("records/0/geometry/upstream/start_codon", "AAA"),
        ("records/0/geometry/upstream/stop_codon", "CCC"),
        ("records/0/energies/upstream_total_kcal_mol", 1000001),
        ("records/0/energies/beta_mol_per_kcal", 1),
        ("records/0/energies/provenance", ""),
        ("records/0/coefficient", 0.22),
        ("records/0/scores/downstream_total/log_value", math.inf),
        ("records/0/scores/downstream_total/value", 0.0),
        ("records/0/scores/downstream_total/value", None),
        ("records/10/coefficient", 0.0072),
        ("records/16/reason", "wrong"),
    ],
)
def test_structure_and_accounting_mutations(fixture, path, value):
    result = artificial_envelope(fixture)
    set_path(result, path, value)
    with pytest.raises(ref.AdmissionError):
        ref.result_accounting(result)


def test_failed_record_contradictions(fixture):
    record = copy.deepcopy(fixture["expected_records"][0])
    record.update(status="invalid_input", reason=None)
    with pytest.raises(ref.AdmissionError, match="Failure reason"):
        ref.record_shape(record)
    record["reason"] = "invalid"
    with pytest.raises(ref.AdmissionError, match="null fields"):
        ref.record_shape(record)
    record.update(
        geometry=None,
        energies=None,
        scores=None,
        coefficient=None,
        status="not_evaluated",
    )
    with pytest.raises(ref.AdmissionError, match="Deadline reason"):
        ref.record_shape(record)
