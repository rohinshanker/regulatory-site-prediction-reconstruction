"""Public schemas enforce finite representations and status-dependent missingness."""

import copy
import io
import json
import math
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from regsite import drafting
from regsite.drafting_io import DraftingInputError, canonical_hash, load_request


def validator(name):
    schema = json.loads(Path(f"schemas/drafting-{name}-1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def example():
    return json.loads(Path("examples/drafting-single.json").read_text())


def test_examples_and_all_failure_representations(monkeypatch):
    request_schema, result_schema = validator("request"), validator("result")
    for name in ("single", "batch", "unsupported"):
        request = json.loads(Path(f"examples/drafting-{name}.json").read_text())
        request_schema.validate(request)
        result_schema.validate(drafting.predict(request))
    result_schema.validate(drafting.invalid_result("invalid_transport"))
    for malformed in (None, {"id": "valid"}, {"id": "bad id"}):
        request = example()
        request["records"].append(malformed)
        result_schema.validate(drafting.predict(request))
    request = example()
    request["records"][0]["rates"].update(
        a1=1,
        a2=math.ulp(0.0),
        a_fold=float.fromhex("0x1.fffffffffffffp+1023"),
        a_elong=2,
    )
    result_schema.validate(drafting.predict(request))
    monkeypatch.setattr(drafting.math, "log", lambda value: math.inf)
    result_schema.validate(drafting.predict(example()))


@pytest.mark.parametrize("path", [(), ("records", 0), ("records", 0, "rates")])
def test_request_rejects_unknown_fields(path):
    data = example()
    node = data
    for key in path:
        node = node[key]
    node["extra"] = 1
    assert not validator("request").is_valid(data)
    result = drafting.predict(data)
    assert result["status"] != "complete"


@pytest.mark.parametrize(
    "path,value",
    [
        (("records", 0, "id"), "x\n"),
        (("records", 0, "id"), ""),
        (("records", 0, "rate_provenance"), " \n\t"),
        (("records", 0, "rate_provenance"), "x" * 1025),
        (("records", 0, "rates", "a1"), True),
        (("records",), []),
        (("records",), [None] * 101),
    ],
)
def test_schema_rejects_malformed_fields(path, value):
    data = example()
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert not validator("request").is_valid(data)
    assert drafting.predict(data)["status"] != "complete"


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "bad"),
        (("model", "backend"), {}),
        (("model", "theory_sha256"), "bad"),
        (("model", "rate_origin"), "default"),
        (("model", "id"), "other"),
        (("model", "source_doi"), "other"),
        (("prediction_sha256",), "a" * 64 + "\n"),
        (("request_sha256",), None),
        (("reason",), "hidden_failure"),
        (("coverage",), None),
        (("coverage", "complete"), False),
        (("coverage", "evaluated_records"), True),
        (("warnings",), []),
        (("records", 0, "index"), 100),
        (("records", 0, "id"), None),
        (("records", 0, "status"), "invalid_input"),
        (("records", 0, "reason"), "hidden_failure"),
        (("records", 0, "occupancies"), None),
        (("records", 0, "occupancies", "accessible", "value"), 1.1),
        (("records", 0, "occupancies", "accessible", "ln_value"), 1),
        (("records", 0, "occupancies", "accessible", "value"), None),
        (
            ("records", 0, "occupancies", "folded"),
            {"value": 0, "ln_value": None, "representation": "exact_zero"},
        ),
        (("records", 0, "throughput", "quantity", "value"), 0),
        (("records", 0, "throughput", "quantity", "ln_value"), None),
        (("records", 0, "throughput", "quantity", "ln_value"), math.inf),
        (("records", 0, "throughput", "quantity", "representation"), "underflow"),
        (("records", 0, "throughput", "quantity", "extra"), 1),
        (("status",), "partial"),
        (("status",), "invalid_input"),
    ],
)
def test_result_rejects_corrupted_states(path, value):
    result = copy.deepcopy(drafting.predict(example()))
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert not validator("result").is_valid(result)


def test_exact_zero_only_for_zero_fold_boundary():
    request = example()
    request["records"][0]["rates"]["a_fold"] = 0
    result = drafting.predict(request)
    validator("result").validate(result)
    result["records"][0]["occupancies"]["folded"] = {
        "value": None,
        "ln_value": -800,
        "representation": "underflow",
    }
    assert not validator("result").is_valid(result)


def test_refusals_require_reasons_and_no_values():
    request = example()
    request["records"][0]["rates"]["a1"] = 0
    result = drafting.predict(request)
    result["records"][0]["occupancies"] = drafting.predict(example())["records"][0][
        "occupancies"
    ]
    assert not validator("result").is_valid(result)
    invalid = drafting.invalid_result("reason")
    invalid["reason"] = None
    assert not validator("result").is_valid(invalid)


with localcontext() as context:
    context.prec = 80
    ZERO_ROUNDING_LOG = float(-1075 * Decimal(2).ln())
LOG_TOLERANCE = 1e-10
QUANTITY_PATHS = [
    ("occupancies", "accessible"),
    ("occupancies", "folded"),
    ("occupancies", "occupied"),
    ("throughput", "quantity"),
]


def result_with_quantity(path, quantity):
    result = drafting.predict(example())
    result["records"][0][path[0]][path[1]] = quantity
    del result["prediction_sha256"]
    result["prediction_sha256"] = canonical_hash(result)
    return result


@pytest.mark.parametrize("path", QUANTITY_PATHS)
@pytest.mark.parametrize(
    "log_value",
    [0, 100, -700, math.nextafter(ZERO_ROUNDING_LOG + LOG_TOLERANCE, math.inf)],
)
def test_impossible_underflow_logs_rejected_everywhere(path, log_value):
    result = result_with_quantity(
        path, {"value": None, "ln_value": log_value, "representation": "underflow"}
    )
    assert not validator("result").is_valid(result)


@pytest.mark.parametrize("path", QUANTITY_PATHS)
@pytest.mark.parametrize(
    "log_value",
    [
        ZERO_ROUNDING_LOG - 1e-10,
        ZERO_ROUNDING_LOG,
        math.nextafter(ZERO_ROUNDING_LOG, math.inf),
        ZERO_ROUNDING_LOG + LOG_TOLERANCE / 2,
        ZERO_ROUNDING_LOG + LOG_TOLERANCE,
        -800,
    ],
)
def test_underflow_tie_and_log_tolerance_are_inclusive(path, log_value):
    # A rounded log can be slightly above the true tie. This applies to the
    # throughput quantity as well as occupancies; no unit-dependent cutoff.
    result = result_with_quantity(
        path, {"value": None, "ln_value": log_value, "representation": "underflow"}
    )
    validator("result").validate(result)


@pytest.mark.parametrize("path", QUANTITY_PATHS)
@pytest.mark.parametrize("direction", [-1, 0, 1])
def test_exact_rational_neighbors_of_zero_rounding_tie(path, direction):
    tie = Fraction(1, 1 << 1075)
    exact = tie * (1 + Fraction(direction, 1 << 52))
    quantity = drafting._quantity(exact)
    assert abs(quantity["ln_value"] - ZERO_ROUNDING_LOG) < LOG_TOLERANCE
    if direction > 0:
        assert quantity["representation"] == "finite"
        assert quantity["value"] == math.ulp(0.0)
    else:
        assert quantity["representation"] == "underflow"
        assert quantity["value"] is None
    validator("result").validate(result_with_quantity(path, quantity))


@pytest.mark.parametrize("clearance,representation", [(2, "finite"), (4, "underflow")])
def test_real_stationary_occupancy_on_both_sides_of_tie(clearance, representation):
    request = example()
    request["records"][0]["rates"].update(
        a1=1, a2=math.ulp(0.0), a_fold=sys.float_info.max, a_elong=clearance
    )
    result = drafting.predict(request)
    assert (
        result["records"][0]["occupancies"]["occupied"]["representation"]
        == representation
    )
    validator("result").validate(result)


# Largest finite binary64 spacing is 2^971, so halfway to the next power of
# two is max + 2^970. At that exact integer tie, conversion overflows; the
# preceding integer still rounds to max. These are test inputs, not API cutoffs.
MAX_FINITE_INTEGER = int(sys.float_info.max)
HALF_LAST_SPACING = 1 << 970
RATE_KEYS = ["a1", "a2", "a_fold", "a_elong"]


@pytest.mark.parametrize("key", RATE_KEYS)
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("offset", [1, HALF_LAST_SPACING - 1])
def test_request_integer_neighbors_round_to_finite_binary64(key, sign, offset):
    request = example()
    raw_integer = sign * (MAX_FINITE_INTEGER + offset)
    request["records"][0]["rates"][key] = raw_integer
    # Exercise actual JSON transport without pre-normalizing the integer.
    parsed = load_request(io.BytesIO(json.dumps(request, allow_nan=False).encode()))
    assert parsed["records"][0]["rates"][key] == raw_integer
    validator("request").validate(parsed)
    assert float(raw_integer) == sign * sys.float_info.max
    result = drafting.predict(parsed)
    row = result["records"][0]
    expected = (
        "ok" if sign > 0 and key in ("a_fold", "a_elong") else "unsupported_domain"
    )
    assert row["status"] == expected
    assert row["input"]["rates"][key] == sign * sys.float_info.max
    validator("result").validate(result)
    # Only request structure was broadened; normalized results retain bounds.
    row["input"]["rates"][key] = raw_integer
    assert not validator("result").is_valid(result)


@pytest.mark.parametrize("key", RATE_KEYS)
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("magnitude", [MAX_FINITE_INTEGER + HALF_LAST_SPACING, 10**400])
def test_numeric_structure_defers_actual_conversion_overflow_to_runtime(
    key, sign, magnitude
):
    request = example()
    request["records"][0]["rates"][key] = sign * magnitude
    validator("request").validate(request)
    with pytest.raises(OverflowError):
        float(sign * magnitude)
    parsed = load_request(io.BytesIO(json.dumps(request, allow_nan=False).encode()))
    result = drafting.predict(parsed)
    assert result["status"] == "partial"
    assert result["request_sha256"] == canonical_hash(request)
    assert result["records"][0]["reason"] == "invalid_rate"
    assert result["records"][0]["input"] is None
    validator("result").validate(result)


@pytest.mark.parametrize("key", RATE_KEYS)
@pytest.mark.parametrize("boolean", [False, True])
def test_numeric_structure_still_rejects_booleans(key, boolean):
    request = example()
    request["records"][0]["rates"][key] = boolean
    assert not validator("request").is_valid(request)
    result = drafting.predict(request)
    assert result["records"][0]["reason"] == "invalid_rate"
    validator("result").validate(result)


@pytest.mark.parametrize(
    "token",
    ["NaN", "Infinity", "-Infinity", "1e309", "-1e309", "1.7976931348623159e308"],
)
def test_strict_transport_rejects_nonfinite_rate_tokens(token):
    request = example()
    request["records"][0]["rates"]["a_fold"] = "RAW_NUMBER"
    raw = json.dumps(request).replace('"RAW_NUMBER"', token).encode()
    with pytest.raises(DraftingInputError):
        load_request(io.BytesIO(raw))
