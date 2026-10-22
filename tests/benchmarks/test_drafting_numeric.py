"""Artificial payloads only: no predictor, backend, subprocess or runtime imports."""

import copy
import json
import math
import os
import runpy
import stat
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.rbs import drafting_numeric as n


@pytest.fixture(scope="module")
def panel():
    return n.load_fixture()


@pytest.fixture
def identity(monkeypatch):
    # Simulate a separately frozen schema warning identity using artificial text.
    monkeypatch.setattr(
        n, "WARNINGS", ["Artificial warning alpha.", "Artificial warning beta."]
    )
    return {
        "schema_version": "drafting-candidate-identity-1",
        "model": {**n.MODEL, "implementation_version": "artificial-test-only"},
        "warnings": ["Artificial warning alpha.", "Artificial warning beta."],
        "candidate": {
            "source_commit": "a" * 40,
            "wheel_sha256": "b" * 64,
            "settings_sha256": "c" * 64,
        },
    }


def seal(payload):
    payload["prediction_sha256"] = n.digest(
        n.canonical({k: v for k, v in payload.items() if k != "prediction_sha256"})
    )
    return n.authoritative(payload)


def payload(case, identity):
    expected = case["expected"]
    records = []
    for exp in expected["records"]:
        record = {k: copy.deepcopy(exp[k]) for k in ("index", "id", "status", "input")}
        record.update(reason=None, occupancies=None, throughput=None)
        if exp["status"] == "ok":
            quantities = {
                k: {f: v[f] for f in ("value", "ln_value", "representation")}
                for k, v in exp["quantities"].items()
            }
            record["occupancies"] = {
                k: quantities[k] for k in ("accessible", "folded", "occupied")
            }
            record["throughput"] = {
                "unit": exp["input"]["rate_unit"],
                "quantity": quantities["throughput"],
            }
        else:
            record["reason"] = "artificial_refusal_code"
        records.append(record)
    result = {
        "schema_version": "drafting-result-1",
        "model": copy.deepcopy(identity["model"]),
        "request_sha256": expected["request_sha256"],
        "status": expected["status"],
        "reason": "artificial_envelope_code"
        if expected["status"] == "invalid_input"
        else None,
        "coverage": copy.deepcopy(expected["coverage"]),
        "warnings": identity["warnings"].copy(),
        "records": records,
    }
    seal(result)
    return result


def case_by_id(panel, identifier):
    return next(c for c in panel["cases"] if c["id"] == identifier)


def test_frozen_originals_and_independent_math(panel):
    assert panel["derivation"]["decimal_precision"] == n.DECIMAL_PRECISION == 120
    assert n.digest(n.FIXTURE.read_bytes()) == n.FIXTURE_SHA256
    assert n.denominators(panel["cases"]) == {
        "requests": 30,
        "records": 198,
        "successful_records": 48,
        "invalid_records": 139,
        "unsupported_records": 11,
        "invalid_envelopes": 17,
    }
    submitted = 0
    for case in panel["cases"]:
        try:
            request = n.strict_json(case["wire"].encode())
        except n.Invalid:
            continue
        if isinstance(request, dict) and isinstance(request.get("records"), list):
            submitted += len(request["records"])
        for record in case["expected"]["records"]:
            if record["status"] != "ok":
                continue
            rates = record["input"]["rates"]
            values = n.oracle(rates)
            p1, p2, p3 = n.balance_solution(rates)
            assert list(values.values())[:3] == [p1, p2, p3]
            assert p1 + p2 + p3 == 1
            a, b, f, e = (
                Fraction.from_float(rates[k]) for k in ("a1", "a2", "a_fold", "a_elong")
            )
            assert e * p3 == a * p1 + b * p2 == values["throughput"]
            for key, value in values.items():
                assert n.expectation(value) == record["quantities"][key]
    assert submitted == 305 <= 500
    controls = n.strict_json(
        (n.ROOT / "benchmarks/rbs/kinetics-scalar-fixtures.json").read_bytes()
    )
    for control in controls["cases"]:
        rates = {k: float(v) for k, v in control["rates"].items()}
        values = n.oracle(rates)
        expected = control["expected"]
        assert list(values.values()) == [
            Fraction(expected[k]) for k in ("P1", "P2", "P3", "flux")
        ]
        b, e = (Fraction.from_float(rates[k]) for k in ("a2", "a_elong"))
        limit = 1 / (1 / b + 1 / e)
        assert limit == Fraction(expected["fast_fold_limit_flux"])
        assert values["throughput"] / limit == Fraction(
            expected["ratio_to_fast_fold_limit"]
        )
    with pytest.raises(n.Invalid, match="oracle domain"):
        n.oracle({"a1": 0, "a2": 1, "a_fold": 0, "a_elong": 2})


def test_number_form_and_representation_edges(panel):
    cases = [
        case_by_id(panel, f"{form}-number") for form in ("integer", "float", "exponent")
    ]
    assert (
        cases[0]["expected"]["request_sha256"] != cases[1]["expected"]["request_sha256"]
    )
    assert (
        cases[1]["expected"]["request_sha256"] == cases[2]["expected"]["request_sha256"]
    )
    assert cases[0]["expected"]["records"] == cases[1]["expected"]["records"]
    records = case_by_id(panel, "finite-panel")["expected"]["records"]
    assert records[1]["input"]["rates"]["a_fold"] == 0.0
    assert math.copysign(1, records[1]["input"]["rates"]["a_fold"]) == 1
    assert records[5]["quantities"]["accessible"]["representation"] == "underflow"
    assert records[5]["quantities"]["throughput"]["ln_value"] is not None
    assert records[5]["quantities"]["occupied"]["zero_boundary_ambiguous"]
    reps = {q["representation"] for r in records for q in r["quantities"].values()}
    assert reps == {"finite", "underflow", "exact_zero"}


def test_all_artificial_payloads_pass(panel, identity):
    for case in panel["cases"]:
        assert n.check_result(seal(payload(case, identity)), case, identity) == []


@pytest.mark.parametrize(
    "mutation,label",
    [
        (lambda p: p.__setitem__("schema_version", "other"), "result schema"),
        (
            lambda p: p["model"].__setitem__("implementation_version", "other"),
            "model identity",
        ),
        (lambda p: p["warnings"].reverse(), "exact warnings"),
        (lambda p: p.__setitem__("request_sha256", "a" * 64), "request hash"),
        (lambda p: p.__setitem__("status", "partial"), "envelope status"),
        (lambda p: p["coverage"].__setitem__("requested_records", True), "coverage"),
        (lambda p: p["coverage"].__setitem__("evaluated_records", 1.0), "coverage"),
        (lambda p: p.__setitem__("reason", "wrong"), "envelope reason"),
        (lambda p: p.__setitem__("records", {}), "record roster type"),
        (lambda p: p["records"].clear(), "record[0] missing"),
        (
            lambda p: p["records"].append(copy.deepcopy(p["records"][0])),
            "record roster count",
        ),
        (lambda p: p["records"].__setitem__(0, None), "record[0] keys"),
        (lambda p: p["records"][0].__setitem__("unknown", 0), "record[0] keys"),
        (lambda p: p["records"][0].__setitem__("index", True), "record[0] index"),
        (lambda p: p["records"][0].__setitem__("id", "wrong"), "record[0] id"),
        (
            lambda p: p["records"][0].__setitem__("status", "numerical_failure"),
            "record[0] status",
        ),
        (
            lambda p: p["records"][0]["input"]["rates"].__setitem__("a1", 3),
            "record[0] input",
        ),
        (
            lambda p: p["records"][0]["input"].__setitem__(
                "rate_provenance", "trimmed"
            ),
            "record[0] input",
        ),
        (lambda p: p["records"][0].__setitem__("reason", "wrong"), "record[0] reason"),
        (
            lambda p: p["records"][0].__setitem__("occupancies", None),
            "record[0] occupancy keys",
        ),
        (
            lambda p: p["records"][0].__setitem__("throughput", None),
            "record[0] throughput keys",
        ),
        (
            lambda p: p["records"][0]["throughput"].__setitem__("unit", "per_second"),
            "record[0] unit",
        ),
        (
            lambda p: p["records"][0]["occupancies"]["accessible"].__setitem__(
                "value", 0.5
            ),
            "linear tolerance",
        ),
    ],
)
def test_semantic_mutations_rehash_consistently(panel, identity, mutation, label):
    case = panel["cases"][0]
    value = payload(case, identity)
    mutation(value)
    errors = n.check_result(seal(value), case, identity)
    assert any(label in error for error in errors)
    assert "prediction hash" not in errors


def test_prediction_hash_and_unknown_keys(panel, identity):
    case = panel["cases"][0]
    value = payload(case, identity)
    value["prediction_sha256"] = "wrong"
    assert n.check_result(n.authoritative(value), case, identity) == ["prediction hash"]
    value["extra"] = 3
    assert n.check_result(seal(value), case, identity) == ["result envelope keys"]
    case = case_by_id(panel, "refusal-panel")
    value = payload(case, identity)
    value["records"][0]["occupancies"] = {}
    value["records"][0]["reason"] = None
    errors = n.check_result(seal(value), case, identity)
    assert "record[0] refusal null quantities" in errors
    assert "record[0] reason" in errors
    case = case_by_id(panel, "empty-roster")
    value = payload(case, identity)
    value["reason"] = None
    assert n.check_result(seal(value), case, identity) == ["envelope reason"]


@pytest.mark.parametrize(
    "exact,changes,label",
    [
        (Fraction(1, 3), {"extra": 1}, "quantity keys"),
        (Fraction(1, 3), {"representation": "underflow"}, "representation"),
        (Fraction(0), {"value": None}, "exact zero value/log"),
        (Fraction(0), {"value": True}, "exact zero value/log"),
        (Fraction(0), {"value": 1}, "exact zero value/log"),
        (Fraction(0), {"ln_value": 0}, "exact zero value/log"),
        (Fraction(1, 3), {"ln_value": None}, "finite log tolerance"),
        (Fraction(1, 3), {"ln_value": 2}, "finite log tolerance"),
        (Fraction(1, 3), {"value": None}, "positive finite linear value"),
        (Fraction(1, 3), {"value": 0}, "positive finite linear value"),
        (Fraction(1, 3), {"value": 2}, "positive finite linear value"),
        (Fraction(1, 3), {"value": 0.4}, "linear tolerance"),
        (Fraction(1, 2**1100), {"value": 0}, "underflow null"),
        (
            Fraction.from_float(math.ulp(0.0)),
            {"value": 2 * math.ulp(0.0)},
            "linear tolerance",
        ),
    ],
)
def test_quantity_mutations(exact, changes, label):
    expected = n.expectation(exact)
    value = {k: expected[k] for k in ("value", "ln_value", "representation")}
    value.update(changes)
    assert label in n.quantity_errors(value, expected, True)


def test_quantity_intervals():
    for exact in (
        Fraction(0),
        Fraction(1, 3),
        Fraction(3),
        Fraction(1, 2**1100),
        Fraction.from_float(math.ulp(0.0)),
    ):
        expected = n.expectation(exact)
        value = {k: expected[k] for k in ("value", "ln_value", "representation")}
        assert n.quantity_errors(value, expected, False) == []
    expected = n.expectation(Fraction(1, 2))
    value = {
        "value": 0.5 + 1e-12,
        "ln_value": expected["ln_value"] + 1e-11,
        "representation": "finite",
    }
    assert n.quantity_errors(value, expected, True) == []
    assert n.quantity_errors(None, expected, True) == ["quantity keys"]
    assert not n.number(10**400)
    assert not n.number(True)
    assert not n.equal([1], [])
    assert not n.equal({"a": 0}, {"b": 0})
    assert not n.equal(0.0, 0)
    assert n.equal(0, 0.0)
    assert not n.equal(-0.0, 0.0)
    assert n.equal(2**53 + 1, float(2**53))


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"\xef\xbb\xbf{}",
        b'{"a":1,"a":2}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"{",
        b"[" * 1100,
    ],
)
def test_strict_json_bad(raw):
    with pytest.raises(n.Invalid):
        n.strict_json(raw)


def test_result_transport_and_authoritative_bounds(panel, identity):
    case = panel["cases"][0]
    assert (
        "wire result exceeds"
        in n.check_result(b" " * (n.OUTPUT_LIMIT + 1), case, identity)[0]
    )
    # Compact wire fits, authoritative pretty escaping does not.
    raw = json.dumps({"x": "\U0001f9ec" * 350000}, ensure_ascii=False).encode()
    assert len(raw) < n.OUTPUT_LIMIT
    assert "authoritative result exceeds" in n.check_result(raw, case, identity)[0]
    assert n.check_result(b"null", case, identity) == ["result envelope keys"]
    assert "strict JSON" in n.check_result(b"\xff", case, identity)[0]


def test_request_hash_and_validation_additional_edges():
    assert n.expected_request(b'{"records":[1e309]}')["request_sha256"] is None
    assert n.expected_request(b'{"records":[]}')["request_sha256"] is not None
    assert (
        n.normalized(
            {
                "id": "x",
                "rates": {"a1": 1, "a2": True, "a_fold": 0, "a_elong": 2},
                "rate_unit": "per_second",
                "rate_provenance": "x",
            }
        )
        is None
    )
    assert (
        n.normalized(
            {
                "id": "x",
                "rates": {"a1": math.inf, "a2": 1, "a_fold": 0, "a_elong": 2},
                "rate_unit": "per_second",
                "rate_provenance": "x",
            }
        )
        is None
    )


def test_bounded_regular_reads(tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_bytes(b"abc")
    assert n.read_bounded(file, 3) == b"abc"
    with pytest.raises(n.Invalid, match="byte limit"):
        n.read_bounded(file, 2)
    with pytest.raises(n.Invalid, match="cannot read"):
        n.read_bounded(tmp_path / "missing", 3)
    with pytest.raises(n.Invalid, match="cannot read"):
        n.read_bounded(tmp_path, 3)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(n.Invalid, match="not a regular"):
        n.read_bounded(fifo, 3)
    link = tmp_path / "link"
    link.symlink_to(file)
    with pytest.raises(n.Invalid, match="cannot read"):
        n.read_bounded(link, 3)
    monkeypatch.setattr(
        n.os, "fstat", lambda fd: SimpleNamespace(st_mode=stat.S_IFREG, st_size=0)
    )
    with pytest.raises(n.Invalid, match="grew beyond"):
        n.read_bounded(file, 2)


def test_fixture_trust(tmp_path, monkeypatch):
    file = tmp_path / "fixture"
    file.write_text("{}")
    with pytest.raises(n.Invalid, match="SHA-256 mismatch"):
        n.load_fixture(file)
    monkeypatch.setattr(n, "FIXTURE_SHA256", n.digest(file.read_bytes()))
    with pytest.raises(n.Invalid, match="fixture structure"):
        n.load_fixture(file)


@pytest.mark.parametrize(
    "mutation,label",
    [
        (lambda p: p.__setitem__("schema_version", "other"), "schema/pins"),
        (lambda p: p.__setitem__("cases", []), "case bound"),
        (lambda p: p["cases"].__setitem__(0, {}), "case shape"),
        (lambda p: p["cases"][0].__setitem__("id", p["cases"][1]["id"]), "case ID"),
        (lambda p: p["cases"][0].__setitem__("id", None), "case ID"),
        (lambda p: p["cases"][0].__setitem__("trailing_spaces", -1), "wire recipe"),
        (lambda p: p["cases"][0].__setitem__("wire", None), "wire recipe"),
        (lambda p: p["cases"][0].__setitem__("expected", {}), "expectations"),
        (lambda p: p.__setitem__("denominators", {}), "denominators"),
    ],
)
def test_fixture_structure_mutations(panel, tmp_path, monkeypatch, mutation, label):
    value = copy.deepcopy(panel)
    mutation(value)
    file = tmp_path / "fixture"
    file.write_bytes(json.dumps(value, ensure_ascii=False).encode())
    monkeypatch.setattr(n, "FIXTURE_SHA256", n.digest(file.read_bytes()))
    # Re-encoding pretty fixtures need not fit the published fixture wire bound.
    monkeypatch.setattr(n, "FIXTURE_LIMIT", len(file.read_bytes()))
    with pytest.raises(n.Invalid, match=label):
        n.load_fixture(file)


def test_source_pin_failure(panel, tmp_path, monkeypatch):
    real = n.read_bounded
    monkeypatch.setattr(
        n,
        "read_bounded",
        lambda p, limit: (
            b"wrong" if p == n.ROOT / next(iter(n.PINS)) else real(p, limit)
        ),
    )
    with pytest.raises(n.Invalid, match="source pin mismatch"):
        n.load_fixture()


def identity_file(tmp_path, identity):
    path = tmp_path / "identity.json"
    path.write_bytes(n.authoritative(identity))
    return path, n.digest(path.read_bytes())


def test_identity_positive_and_hash(tmp_path, identity):
    path, sha = identity_file(tmp_path, identity)
    assert n.load_identity(path, sha) == identity
    with pytest.raises(n.Invalid, match="SHA-256"):
        n.load_identity(path, "wrong")
    with pytest.raises(n.Invalid, match="SHA-256"):
        n.load_identity(path, "0" * 64)


@pytest.mark.parametrize(
    "mutation,label",
    [
        (lambda r: r.__setitem__("schema_version", "other"), "receipt schema"),
        (lambda r: r.__setitem__("extra", 0), "receipt schema"),
        (
            lambda r: r["model"].__setitem__("backend", "folding"),
            "public model identity",
        ),
        (
            lambda r: r["model"].__setitem__("implementation_version", " "),
            "public model identity",
        ),
        (lambda r: r.__setitem__("warnings", []), "exact public warning"),
        (lambda r: r.__setitem__("warnings", ["x", "x"]), "exact public warning"),
        (lambda r: r.__setitem__("warnings", [None]), "exact public warning"),
        (lambda r: r.__setitem__("warnings", [" "]), "exact public warning"),
        (
            lambda r: r["candidate"].__setitem__("source_commit", "bad"),
            "candidate claims",
        ),
        (lambda r: r["candidate"].__setitem__("wheel_sha256", 1), "candidate claims"),
        (
            lambda r: r["candidate"].__setitem__("settings_sha256", "bad"),
            "candidate claims",
        ),
    ],
)
def test_identity_mutations(tmp_path, identity, mutation, label):
    mutation(identity)
    path, sha = identity_file(tmp_path, identity)
    with pytest.raises(n.Invalid, match=label):
        n.load_identity(path, sha)


def test_result_paths(panel):
    assert n.result_paths(["integer-number=a=b"], panel["cases"]) == {
        "integer-number": Path("a=b")
    }
    for specs in (
        ["unknown=x"],
        ["integer-number"],
        ["integer-number="],
        ["integer-number=a", "integer-number=b"],
    ):
        with pytest.raises(n.Invalid):
            n.result_paths(specs, panel["cases"])


def test_report_missing_and_transport(panel, identity, tmp_path):
    outcome = n.report(panel, identity, {})
    assert outcome["passed_requests"] == outcome["credited_records"] == 0
    assert outcome["expected"] == panel["denominators"]
    assert len(outcome["cases"]) == 30
    outcome = n.report(panel, identity, {panel["cases"][0]["id"]: tmp_path / "missing"})
    assert outcome["transport_failures"] == 1
    assert outcome["cases"][0]["credited_records"] == 0
    assert len(outcome["cases"]) == 30


def test_atomic_private_no_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "report"
    original = tmp_path / "input"
    original.write_bytes(b"original")
    with pytest.raises(n.Invalid, match="protected input"):
        n.write_report(original, b"new", [original])
    n.write_report(path, b"complete", [])
    assert path.read_bytes() == b"complete"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(n.Invalid, match="cannot publish"):
        n.write_report(path, b"overwrite", [])
    assert path.read_bytes() == b"complete"
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(n.Invalid, match="cannot publish"):
        n.write_report(link, b"new", [])
    assert not (tmp_path / "missing").exists()
    with pytest.raises(n.Invalid, match="cannot publish"):
        n.write_report(tmp_path / "no-parent" / "report", b"new", [])
    assert not list(tmp_path.glob(".drafting-numeric-*"))


def test_cli_all_cases_and_failures(panel, identity, tmp_path, capsys):
    path, sha = identity_file(tmp_path, identity)
    args = ["--identity", str(path), "--identity-sha256", sha]
    result_args = []
    for i, case in enumerate(panel["cases"]):
        result = tmp_path / f"result-{i}"
        result.write_bytes(seal(payload(case, identity)))
        result_args += ["--result", f"{case['id']}={result}"]
    assert n.main(args + result_args) == 0
    successful = json.loads(capsys.readouterr().out)
    assert successful["credited_records"] == 198 and successful["all_passed"]
    assert successful["identity_sha256"] == sha
    changed = payload(panel["cases"][0], identity)
    changed["records"][0]["throughput"]["unit"] = "wrong"
    (tmp_path / "result-0").write_bytes(seal(changed))
    assert n.main(args + result_args) == 1
    mutated = json.loads(capsys.readouterr().out)
    assert mutated["credited_records"] == 197
    assert mutated["passed_requests"] == 29
    assert len(mutated["cases"]) == 30
    assert mutated["cases"][0]["failures"] == ["record[0] unit"]
    assert n.main(args) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["expected"] == successful["expected"]
    assert failed["credited_records"] == 0 and not failed["all_passed"]
    output = tmp_path / "report"
    assert n.main(args + ["--output", str(output)]) == 1
    assert json.loads(output.read_bytes()) == failed
    assert capsys.readouterr().out == ""
    assert n.main(args + ["--output", str(output)]) == 2
    assert "cannot publish" in capsys.readouterr().err
    assert (
        n.main(args + ["--result", f"{panel['cases'][0]['id']}={tmp_path}/absent"]) == 2
    )
    transport = json.loads(capsys.readouterr().out)
    assert transport["transport_failures"] == 1 and len(transport["cases"]) == 30
    assert n.main(args + ["--result", "unknown=file"]) == 2
    assert "frozen CASE=PATH" in capsys.readouterr().err
    assert n.main(["--identity", str(path), "--identity-sha256", "0" * 64]) == 2
    assert "receipt SHA-256" in capsys.readouterr().err


def test_cli_usage_and_script(identity, panel, tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        n.main([])
    assert exc.value.code == 2
    identity["warnings"] = panel["derivation"]["warning_identity"]["warnings"]
    path, sha = identity_file(tmp_path, identity)
    monkeypatch.setattr(
        sys, "argv", [n.__file__, "--identity", str(path), "--identity-sha256", sha]
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(n.__file__, run_name="__main__")
    assert exc.value.code == 1
    assert not json.loads(capsys.readouterr().out)["all_passed"]


def test_script_non_main_branch():
    namespace = runpy.run_path(n.__file__, run_name="artificial_import_only")
    assert namespace["DECIMAL_PRECISION"] == 120


def test_public_warning_receipt_from_coordinator(tmp_path, panel):
    declared = panel["derivation"]["warning_identity"]
    assert declared["warnings"] == n.WARNINGS
    assert declared["source"] == n.WARNING_SOURCE
    assert declared["candidate_version_supplied_by_A"] == "0.12.0rc1"
    receipt = {
        "schema_version": "drafting-candidate-identity-1",
        "model": {**n.MODEL, "implementation_version": "0.12.0rc1"},
        "warnings": n.WARNINGS,
        "candidate": {
            "source_commit": n.WARNING_SOURCE["source_commit"],
            "wheel_sha256": "a" * 64,
            "settings_sha256": "b" * 64,
        },
    }
    path, sha = identity_file(tmp_path, receipt)
    assert n.load_identity(path, sha) == receipt
    receipt["warnings"] = ["Invented warning text"]
    path, sha = identity_file(tmp_path, receipt)
    with pytest.raises(n.Invalid, match="exact public warning identity"):
        n.load_identity(path, sha)


def test_throughput_survives_occupied_underflow():
    tiny = math.ulp(0.0)
    rates = {
        "a1": tiny,
        "a2": tiny,
        "a_fold": sys.float_info.max,
        "a_elong": sys.float_info.max,
    }
    values = n.oracle(rates)
    assert float(values["occupied"]) == 0
    assert values["throughput"] > Fraction.from_float(tiny) / 2
    assert float(values["throughput"]) == tiny
    assert abs(n.expectation(values["throughput"])["ln_value"] - math.log(tiny)) < 1e-10


def test_no_predictor_modules_loaded():
    assert not any(
        name == "regsite" or name.startswith("regsite.") for name in sys.modules
    )
