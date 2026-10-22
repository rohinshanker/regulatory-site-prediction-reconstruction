"""Stationary balances, immutable rational controls, and strict API behavior."""

import copy
import hashlib
import json
import math
import random
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from regsite import __version__, drafting
from regsite.drafting_io import canonical_bytes, canonical_hash


def example():
    return json.loads(Path("examples/drafting-single.json").read_text())


def evaluate(**rates):
    request = example()
    request["records"][0]["rates"].update(rates)
    result = drafting.predict(request)
    assert result["status"] == "complete"
    return result["records"][0]


def test_all_six_immutable_source_fixtures():
    path = Path("benchmarks/rbs/kinetics-scalar-fixtures.json")
    manifest = json.loads(
        Path("benchmarks/rbs/kinetics-source-manifest.json").read_text()
    )
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == manifest["derived_fixture"]["sha256"]
    )
    fixtures = json.loads(path.read_text())
    assert len(fixtures["cases"]) == 6
    for case in fixtures["cases"]:
        rates = {k: float(Fraction(v)) for k, v in case["rates"].items()}
        row = evaluate(**rates)
        actual = [row["occupancies"][k] for k in ("accessible", "folded", "occupied")]
        actual.append(row["throughput"]["quantity"])
        fast_fold_limit = (
            rates["a_elong"] * rates["a2"] / (rates["a_elong"] + rates["a2"])
        )
        assert fast_fold_limit == pytest.approx(
            float(Fraction(case["expected"]["fast_fold_limit_flux"])), rel=1e-11
        )
        assert row["throughput"]["quantity"][
            "value"
        ] / fast_fold_limit == pytest.approx(
            float(Fraction(case["expected"]["ratio_to_fast_fold_limit"])), rel=1e-11
        )
        for quantity, key in zip(actual, ("P1", "P2", "P3", "flux"), strict=True):
            expected = float(Fraction(case["expected"][key]))
            assert quantity["value"] == pytest.approx(expected, rel=1e-11)
            if expected:
                assert quantity["ln_value"] == pytest.approx(
                    math.log(expected), abs=1e-10
                )
            else:
                assert quantity == {
                    "value": 0,
                    "ln_value": None,
                    "representation": "exact_zero",
                }


def test_stationary_balances_clearance_and_finite_fold_limits():
    row = evaluate()
    p1, p2, p3 = (
        row["occupancies"][key]["value"] for key in ("accessible", "folded", "occupied")
    )
    flux = row["throughput"]["quantity"]["value"]
    assert math.fsum((p1, p2, p3)) == pytest.approx(1)
    assert 10 * p3 == pytest.approx((2 + 3) * p1)
    assert 3 * p1 == pytest.approx(p2)
    assert flux == pytest.approx(2 * p1 + p2)
    assert 0 < flux < 10
    assert evaluate(a_fold=0)["throughput"]["quantity"]["value"] == pytest.approx(
        20 / 12
    )
    assert evaluate(a_fold=1e15)["throughput"]["quantity"]["value"] == pytest.approx(
        10 / 11
    )
    assert evaluate(a_elong=1e15)["throughput"]["quantity"]["value"] == pytest.approx(
        5 / 4
    )
    # The finite-clearance result is different from a fast-clearance shortcut.
    assert flux != pytest.approx(5 / 4)
    assert evaluate(a_fold=1e5)["throughput"]["quantity"]["value"] < flux
    for folding in (0, 1e-300, 100, 1e300):
        assert evaluate(a1=1, a_fold=folding)["throughput"]["quantity"][
            "value"
        ] == pytest.approx(10 / 11)


def test_scaling_and_caller_units_provenance_are_preserved_without_mutation():
    request = example()
    request["records"][0].update(
        rate_unit="per_second", rate_provenance="  artificial β  "
    )
    original = copy.deepcopy(request)
    first = drafting.predict(request)["records"][0]
    assert request == original
    assert first["input"]["rate_provenance"] == "  artificial β  "
    assert first["throughput"]["unit"] == "per_second"
    for scale in (1e-300, 7, 1e300):
        second = evaluate(
            **{k: v * scale for k, v in original["records"][0]["rates"].items()}
        )
        for key in first["occupancies"]:
            assert second["occupancies"][key]["value"] == pytest.approx(
                first["occupancies"][key]["value"], rel=1e-11
            )
        assert second["throughput"]["quantity"]["value"] == pytest.approx(
            first["throughput"]["quantity"]["value"] * scale, rel=1e-11, abs=0
        )


SMALLEST = math.ulp(0.0)
LARGEST = sys.float_info.max


@pytest.mark.parametrize(
    "a,b,f,e",
    [
        (SMALLEST, SMALLEST, 0, 2 * SMALLEST),
        (SMALLEST, SMALLEST, LARGEST, LARGEST),
        (1, SMALLEST, LARGEST, 2),
        (1, SMALLEST, LARGEST, 4),
        (10, 10, SMALLEST, 20),
        (1, SMALLEST, LARGEST, LARGEST),
        (LARGEST / 2, SMALLEST, SMALLEST, LARGEST),
        (LARGEST / 2, LARGEST / 4, LARGEST, LARGEST),
        (1e-300, 1e-320, 1e300, 1e-299),
        (math.nextafter(LARGEST, 0), SMALLEST, LARGEST, LARGEST),
    ],
)
def test_entire_binary64_range_against_high_precision_renewal(a, b, f, e):
    row = evaluate(a1=a, a2=b, a_fold=f, a_elong=e)
    # Independent mean-cycle derivation, at enough precision to distinguish
    # either side of the half-minimum-subnormal rounding threshold.
    with localcontext() as context:
        context.prec = 1800
        da, db, df, de = map(Decimal.from_float, (a, b, f, e))
        mean_accessible = 1 / (da + df)
        mean_folded = df / (da + df) / db
        mean_occupied = 1 / de
        cycle = mean_accessible + mean_folded + mean_occupied
        expected = [
            mean_accessible / cycle,
            mean_folded / cycle,
            mean_occupied / cycle,
            1 / cycle,
        ]
        actual = [row["occupancies"][k] for k in ("accessible", "folded", "occupied")]
        actual.append(row["throughput"]["quantity"])
        for quantity, decimal_value in zip(actual, expected, strict=True):
            rounded = float(decimal_value)
            if decimal_value == 0:
                assert quantity["representation"] == "exact_zero"
            else:
                assert quantity["ln_value"] == pytest.approx(
                    float(decimal_value.ln()), abs=1e-10
                )
                if rounded == 0:
                    assert quantity["representation"] == "underflow"
                    assert quantity["value"] is None
                else:
                    assert quantity["representation"] == "finite"
                    assert quantity["value"] == rounded
        for quantity in row["occupancies"].values():
            assert quantity["value"] is None or 0 <= quantity["value"] <= 1


def test_random_finite_rates_and_balance_normalization():
    rng = random.Random(6601)
    for _ in range(100):
        b, a, e = sorted(10 ** rng.uniform(-300, 300) for _ in range(3))
        row = evaluate(a1=a, a2=b, a_fold=10 ** rng.uniform(-300, 300), a_elong=e)
        assert math.fsum(
            q["value"] or 0 for q in row["occupancies"].values()
        ) == pytest.approx(1, abs=1e-15)
        assert row["throughput"]["quantity"]["value"] <= e


def test_underflowed_occupancy_keeps_finite_throughput_and_log():
    row = evaluate(a1=1, a2=SMALLEST, a_fold=LARGEST, a_elong=4)
    assert row["occupancies"]["occupied"]["representation"] == "underflow"
    assert row["throughput"]["quantity"]["value"] == SMALLEST
    assert row["throughput"]["quantity"]["ln_value"] < 0
    row = evaluate(a1=SMALLEST, a2=SMALLEST, a_fold=0, a_elong=2 * SMALLEST)
    assert row["throughput"]["quantity"]["representation"] == "finite"


def test_zero_fold_sign_normalization_and_number_forms():
    request = example()
    request["records"][0]["rates"]["a_fold"] = -0.0
    row = drafting.predict(request)["records"][0]
    assert math.copysign(1, row["input"]["rates"]["a_fold"]) == 1
    assert row["occupancies"]["folded"]["representation"] == "exact_zero"
    assert all(type(v) is float for v in row["input"]["rates"].values())


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        1,
        "x",
        {},
        {"schema_version": "wrong", "records": [None]},
        {"schema_version": "drafting-request-1", "records": None},
        {"schema_version": "drafting-request-1", "records": []},
        {"schema_version": "drafting-request-1", "records": [None] * 101},
        {"schema_version": "drafting-request-1", "records": [None], "extra": 1},
    ],
)
def test_invalid_envelopes_preserve_safe_hash(data):
    result = drafting.predict(data)
    assert result["status"] == "invalid_input"
    assert result["reason"] == "invalid_envelope"
    assert result["request_sha256"] == canonical_hash(data)
    assert result["records"] == [] and result["coverage"] is None


@pytest.mark.parametrize(
    "value",
    [
        float("inf"),
        float("nan"),
        float("-inf"),
        object(),
        (1, 2),
        {1: "value"},
        {"v": {1, 2}},
        pytest.param(10**5000, id="unserializable-huge-int"),
    ],
)
def test_non_json_api_objects_have_no_hash(value):
    result = drafting.predict(value)
    assert result["status"] == "invalid_input" and result["request_sha256"] is None


def test_cyclic_and_deep_api_objects():
    cyclic = []
    cyclic.append(cyclic)
    assert drafting.predict(cyclic)["request_sha256"] is None
    deep = None
    for _ in range(sys.getrecursionlimit() + 100):
        deep = [deep]
    result = drafting.predict(deep)
    assert result["status"] == "invalid_input"
    # Interpreter JSON depth limits differ; safely encoded JSON keeps its hash.
    if result["reason"] == "invalid_envelope":
        assert result["request_sha256"] == canonical_hash(deep)
    else:
        assert result["request_sha256"] is None


def test_object_cap_is_independent_and_inclusive(monkeypatch):
    request = example()
    size = len(canonical_bytes(request))
    monkeypatch.setattr(drafting, "OBJECT_LIMIT", size)
    assert drafting.predict(request)["status"] == "complete"
    monkeypatch.setattr(drafting, "OBJECT_LIMIT", size - 1)
    result = drafting.predict(request)
    assert result["reason"] == "api_object_byte_limit"
    assert result["request_sha256"] is None
    assert drafting.predict("x" * 1_048_577)["request_sha256"] is None


@pytest.mark.parametrize(
    "record", [None, [], {}, {"id": "valid"}, {"id": "invalid id"}]
)
def test_malformed_records_keep_full_roster(record):
    request = example()
    request["records"] += [record, {**request["records"][0], "id": "last"}]
    result = drafting.predict(request)
    assert result["status"] == "partial"
    assert result["coverage"] == dict(
        requested_records=3, evaluated_records=3, successful_records=2, complete=False
    )
    assert [row["index"] for row in result["records"]] == [0, 1, 2]
    failed = result["records"][1]
    assert failed["status"] == "invalid_input" and failed["input"] is None
    assert failed["occupancies"] is None and failed["throughput"] is None
    assert failed["id"] == ("valid" if record == {"id": "valid"} else None)


@pytest.mark.parametrize(
    "path,bad",
    [
        (("id",), None),
        (("id",), "x\n"),
        (("id",), ""),
        (("id",), "x" * 129),
        (("id",), 3),
        (("rate_unit",), []),
        (("rate_unit",), "unknown"),
        (("rate_provenance",), " \t\n"),
        (("rate_provenance",), "x" * 1025),
        (("rate_provenance",), None),
        (("rates",), []),
        (("rates",), {}),
        (("rates", "a1"), True),
        (("rates", "a1"), "2"),
        (("rates", "a1"), None),
        (("rates", "a1"), 10**400),
    ],
)
def test_malformed_fields(path, bad):
    request = example()
    node = request["records"][0]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = bad
    row = drafting.predict(request)["records"][0]
    assert row["status"] == "invalid_input" and row["input"] is None


def test_nonfinite_conversion_defense(monkeypatch):
    # JSON finiteness normally catches these before normalization; directly
    # exercise the conversion guard to keep it robust against future callers.
    request = example()
    request["records"][0]["rates"]["a1"] = math.inf
    monkeypatch.setattr(drafting, "canonical_bytes", lambda value: b"{}")
    assert drafting.predict(request)["records"][0]["reason"] == "invalid_rate"


@pytest.mark.parametrize(
    "rates",
    [
        dict(a1=0),
        dict(a2=0),
        dict(a2=-1),
        dict(a2=3),
        dict(a_elong=2),
        dict(a_elong=1),
        dict(a_fold=-SMALLEST),
    ],
)
def test_unsupported_finite_domain_retains_normalized_input(rates):
    request = example()
    request["records"][0]["rates"].update(rates)
    row = drafting.predict(request)["records"][0]
    assert row["status"] == "unsupported_domain"
    assert row["input"] is not None and row["occupancies"] is None
    assert row["throughput"] is None


def test_duplicate_valid_ids_reject_envelope_even_when_record_malformed():
    request = example()
    request["records"].append({"id": request["records"][0]["id"]})
    result = drafting.predict(request)
    assert result["reason"] == "duplicate_record_id" and result["records"] == []
    request["records"] = [{"id": "bad id"}] * 2
    assert len(drafting.predict(request)["records"]) == 2


@pytest.mark.parametrize(
    "failure", [math.inf, math.nan, OverflowError("outside range")]
)
def test_numerical_failure_is_typed_and_never_leaks_nonfinite(monkeypatch, failure):
    def log(value):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(drafting.math, "log", log)
    result = drafting.predict(example())
    row = result["records"][0]
    assert row["status"] == "numerical_failure"
    assert row["input"] is not None and row["occupancies"] is row["throughput"] is None
    assert result["status"] == "partial"
    json.dumps(result, allow_nan=False)


def test_complete_identity_hashes_every_field_and_is_deterministic():
    request = example()
    result = drafting.predict(request)
    assert result == drafting.predict(copy.deepcopy(request))
    assert result["request_sha256"] == canonical_hash(request)
    digest = result.pop("prediction_sha256")
    assert (
        digest
        == hashlib.sha256(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )
    assert result["model"]["implementation_version"] == __version__
    assert result["model"]["backend"] is None and len(result["warnings"]) == 4
    assert result["model"]["theory_sha256"] == drafting.THEORY_SHA256
    request["records"][0]["rates"]["a1"] = 2.0
    assert drafting.predict(request)["request_sha256"] != result["request_sha256"]
    assert drafting.predict(request)["records"] == result["records"]
    for key in result:
        changed = copy.deepcopy(result)
        changed[key] = "changed"
        assert canonical_hash(changed) != digest


def test_maximum_valid_roster_id_and_provenance_bounds():
    request = example()
    base = request["records"][0]
    request["records"] = [
        {
            **base,
            "id": f"{i}:" + "x" * (127 - len(str(i))),
            "rate_provenance": "β" * 1024,
        }
        for i in range(100)
    ]
    assert drafting.predict(request)["coverage"]["successful_records"] == 100
