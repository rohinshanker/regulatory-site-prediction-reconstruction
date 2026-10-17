"""Analytical ridge solutions, artifact integrity and bounded numeric failures."""

import json
import math
from collections.abc import Hashable
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from hashlib import sha256

import pytest

from regsite.learning import MAX_FEATURES, MAX_ROWS, RidgeModel, _solve, _sum, fit_ridge


def fit(**changes):
    arguments = {
        "rows": [[1], [3]],
        "responses_log2": [2, 6],
        "feature_names": ["feature"],
        "record_ids": ["a", "b"],
        "penalty": 2,
        "provenance": {"dataset_id": "synthetic", "split_id": "train"},
    }
    return fit_ridge(**(arguments | changes))


def test_analytical_ridge_with_unpenalized_intercept_and_new_rows():
    model = fit()
    assert model.means == (2.0,)
    assert model.scales == (1.0,)
    assert model.intercept == 4.0
    assert model.coefficients == pytest.approx((1.0,))
    assert model.predict([[0], [5]]) == pytest.approx((2, 7))
    assert model.score_scale == "log2_assay_response"
    # Shrinkage affects the slope, never the intercept/target mean.
    assert fit(penalty=1e100).intercept == 4.0
    assert fit(penalty=1e100).coefficients[0] < 1e-90


def test_correlated_multicolumn_solution_and_feature_order():
    # X'X standardized = [[3, 1.5], [1.5, 3]], X'y = [3*sqrt(1.5), 0].
    model = fit(
        rows=[[-1, -1], [0, 1], [1, 0]],
        responses_log2=[4, 4, 7],
        feature_names=["x", "z"],
        record_ids=["a", "b", "c"],
        penalty=1,
    )
    assert model.means == (0, 0)
    assert model.scales == pytest.approx((math.sqrt(2 / 3),) * 2)
    assert model.coefficients == pytest.approx(
        (12 * math.sqrt(1.5) / 13.75, -4.5 * math.sqrt(1.5) / 13.75)
    )
    assert model.predict([[2, -1], [0, 0]]) == pytest.approx((5 + 42.75 / 13.75, 5))
    assert model.predict([[-1, 2]]) != model.predict([[2, -1]])


def test_constants_single_row_and_collinearity():
    model = fit(rows=[[9, 1], [9, 3]], feature_names=["constant", "variable"])
    assert model.scales == (0, 1)
    assert model.coefficients == pytest.approx((0, 1))
    assert model.predict([[1234, 0]]) == pytest.approx((2,))
    constant = fit(responses_log2=[-3, -3])
    assert constant.coefficients == (0,)
    assert constant.predict([[100]]) == (-3,)
    single = fit(
        rows=[[0, 1e308]],
        responses_log2=[1e308],
        feature_names=["zero", "constant"],
        record_ids=["only"],
    )
    assert single.scales == (0, 0)
    assert single.predict([[1, -1e308]]) == (1e308,)
    duplicate = fit(rows=[[1, 1], [3, 3]], feature_names=["x", "duplicate"])
    assert duplicate.coefficients == pytest.approx((2 / 3, 2 / 3))


@pytest.mark.parametrize(
    "rows, targets, penalty",
    [
        ([[1, 1], [3, 3], [4, 4]], [2, 6, 7], 1e-15),
        ([[0, 0], [1, 1 + 1e-9], [2, 2], [3, 3 - 1e-9]], [0, 1, 3, 2], 1e-14),
    ],
)
def test_nearly_dependent_features_fail_closed(rows, targets, penalty):
    with pytest.raises(ValueError, match="ill-conditioned Cholesky pivot"):
        fit(
            rows=rows,
            responses_log2=targets,
            record_ids=[str(i) for i in range(len(rows))],
            feature_names=["x", "y"],
            penalty=penalty,
        )


@pytest.mark.parametrize("magnitude", [1.0, 1e-200])
def test_relative_pivot_guard_on_both_sides_of_threshold(magnitude):
    # The second pivot/diagonal is approximately delta. Scaling the entire
    # system preserves this ratio, so an absolute pivot cutoff would be wrong.
    def gram(delta):
        return [[magnitude, magnitude], [magnitude, magnitude * (1 + delta)]]

    with pytest.raises(ValueError, match="ill-conditioned Cholesky pivot"):
        _solve(gram(2**-34), [0, 0])
    assert _solve(gram(2**-32), [0, 0]) == (0, 0)


def exact_two_feature_solution(rows, targets, model):
    """Independent rational 2x2 inverse in the model's stored coordinates."""
    count = len(rows)
    columns = [
        [(Fraction(row[j]) - Fraction(center)) / Fraction(scale) for row in rows]
        for j, (center, scale) in enumerate(zip(model.means, model.scales, strict=True))
    ]
    offsets = [sum(column) / count for column in columns]
    u, v = [
        [value - offset for value in column]
        for column, offset in zip(columns, offsets, strict=True)
    ]
    average = sum(map(Fraction, targets)) / count
    y = [Fraction(value) - average for value in targets]
    a = sum(value * value for value in u) + Fraction(model.penalty)
    b = sum(x * z for x, z in zip(u, v, strict=True))
    c = sum(value * value for value in v) + Fraction(model.penalty)
    d = sum(x * value for x, value in zip(u, y, strict=True))
    e = sum(z * value for z, value in zip(v, y, strict=True))
    determinant = a * c - b * b
    weights = ((d * c - e * b) / determinant, (e * a - d * b) / determinant)
    intercept = average - sum(x * w for x, w in zip(offsets, weights, strict=True))
    return tuple(map(float, weights)), float(intercept)


@pytest.mark.parametrize(
    "rows, penalty",
    [
        ([[-1, -1], [-1, 1], [1, -1], [1, 1]], 1e-15),
        ([[0, 0], [1, 1 + 1e-9], [2, 2], [3, 3 - 1e-9]], 1e-8),
    ],
)
def test_conditioning_guard_accepts_justified_solutions(rows, penalty):
    targets = [0, 1, 3, 2]
    model = fit(
        rows=rows,
        responses_log2=targets,
        record_ids=list("abcd"),
        feature_names=["x", "y"],
        penalty=penalty,
    )
    weights, intercept = exact_two_feature_solution(rows, targets, model)
    assert model.coefficients == pytest.approx(weights, rel=1e-6, abs=1e-10)
    assert model.intercept == pytest.approx(intercept, rel=1e-6, abs=1e-10)
    assert model.predict([model.means]) == pytest.approx(
        (intercept,), rel=1e-6, abs=1e-10
    )
    # An off-span row exposes coefficient errors hidden by training predictions.
    off_span = [[model.means[0] + model.scales[0], model.means[1]]]
    assert model.predict(off_span) == pytest.approx((intercept + weights[0],), rel=1e-6)


def test_constant_column_with_tiny_penalty_is_not_ill_conditioned():
    model = fit(rows=[[1, 1], [1, 3]], feature_names=["constant", "x"], penalty=1e-15)
    assert model.coefficients == pytest.approx((0, 2))
    assert model.predict([[1e308, 2]]) == (4,)


def test_roundtrip_fingerprint_and_metadata_immutability():
    metadata = {"dataset_id": "synthetic", "split_id": "train", "note": "nonsecret"}
    model = fit(provenance=metadata)
    artifact = model.to_dict()
    restored = RidgeModel.from_dict(json.loads(json.dumps(artifact, allow_nan=False)))
    assert restored == model
    assert restored.predict([[5]]) == model.predict([[5]])
    assert restored.to_dict() == artifact
    metadata["note"] = "changed"
    artifact["provenance"]["note"] = "also changed"
    artifact["means"][0] = 999
    assert model.provenance["note"] == "nonsecret"
    assert model.means == (2,)
    with pytest.raises(TypeError):
        model.provenance["note"] = "mutable?"
    with pytest.raises(FrozenInstanceError):
        model.intercept = 999
    assert fit().to_dict() == fit().to_dict()
    assert fit(rows=((1.0,), (3.0,)), responses_log2=(2.0, 6.0), penalty=2.0) == fit()
    assert fit(provenance={"split_id": "train", "dataset_id": "synthetic"}) == fit()
    # Independently reproduce the canonical training input digest.
    inputs = {
        "version": model.version,
        "rows": [[1.0], [3.0]],
        "responses_log2": [2.0, 6.0],
        "feature_names": ["feature"],
        "record_ids": ["a", "b"],
        "penalty": 2.0,
        "provenance": {"dataset_id": "synthetic", "split_id": "train"},
    }
    canonical = json.dumps(
        inputs, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    assert fit().training_sha256 == sha256(canonical.encode()).hexdigest()


def test_model_is_explicitly_unhashable_with_json_portability():
    model = fit()
    assert model.__hash__ is None
    assert not isinstance(model, Hashable)
    with pytest.raises(TypeError, match="unhashable type: 'RidgeModel'"):
        hash(model)
    assert RidgeModel.from_dict(json.loads(json.dumps(model.to_dict()))) == model


@pytest.mark.parametrize(
    "change",
    [
        {"rows": [[1], [4]]},
        {"responses_log2": [2, 7]},
        {"feature_names": ["other"]},
        {"record_ids": ["b", "a"]},
        {"penalty": 1},
        {"provenance": {"dataset_id": "other", "split_id": "train"}},
        {"provenance": {"dataset_id": "synthetic", "split_id": "other"}},
        {"rows": [[3], [1]], "responses_log2": [6, 2], "record_ids": ["b", "a"]},
    ],
)
def test_fingerprint_detects_each_input_change(change):
    assert fit(**change).training_sha256 != fit().training_sha256


@pytest.mark.parametrize(
    "bad", [True, False, "1", None, float("nan"), float("inf"), -float("inf"), 10**400]
)
@pytest.mark.parametrize("field", ["rows", "responses_log2", "penalty"])
def test_non_numeric_and_nonfinite_inputs(field, bad):
    value = {"rows": [[1], [bad]], "responses_log2": [bad, 6], "penalty": bad}[field]
    with pytest.raises(ValueError, match="finite|number|range"):
        fit(**{field: value})


@pytest.mark.parametrize(
    "change, message",
    [
        ({"rows": []}, "rows"),
        ({"rows": "matrix"}, "rows"),
        ({"rows": [[1]] * (MAX_ROWS + 1)}, "rows"),
        ({"rows": [[1], []]}, "row"),
        ({"rows": [[1], [1, 2]]}, "row"),
        ({"rows": [1, 2]}, "row"),
        ({"responses_log2": []}, "responses_log2"),
        ({"responses_log2": [2]}, "exactly"),
        ({"responses_log2": [2, 6, 9]}, "responses_log2"),
        ({"feature_names": []}, "feature_names"),
        ({"feature_names": ["x"] * (MAX_FEATURES + 1)}, "feature_names"),
        ({"feature_names": ["x", "x"]}, "unique"),
        ({"feature_names": [""]}, "nonempty"),
        ({"feature_names": [" \t"]}, "nonempty"),
        ({"feature_names": [False]}, "nonempty"),
        ({"feature_names": ["x" * 257]}, "256"),
        ({"record_ids": ["a", "a"]}, "unique"),
        ({"record_ids": ["a", ""]}, "nonempty"),
        ({"record_ids": ["a", None]}, "nonempty"),
        ({"record_ids": ["a"]}, "number of rows"),
        ({"record_ids": ["a", "b", "c"]}, "number of rows"),
        ({"record_ids": []}, "record_ids"),
        ({"penalty": 0}, "positive"),
        ({"penalty": -1}, "positive"),
        ({"provenance": None}, "provenance"),
        ({"provenance": {}}, "provenance"),
        ({"provenance": {str(i): "v" for i in range(33)}}, "provenance"),
        ({"provenance": {"dataset_id": "d", "other": "x"}}, "split_id"),
        ({"provenance": {"dataset_id": "d", "split_id": ""}}, "nonempty"),
        ({"provenance": {"dataset_id": "d", "split_id": False}}, "nonempty"),
        ({"provenance": {"dataset_id": "d", "split_id": "s", 1: "x"}}, "nonempty"),
        ({"provenance": {"dataset_id": "d", "split_id": "x" * 1025}}, "1024"),
    ],
)
def test_input_dimensions_names_metadata_and_penalty(change, message):
    with pytest.raises(ValueError, match=message):
        fit(**change)


@pytest.mark.parametrize(
    "field, bad, message",
    [
        ("version", "new", "version"),
        ("version", True, "version"),
        ("score_scale", "energy", "score_scale"),
        ("feature_names", [""], "nonempty"),
        ("means", [], "means"),
        ("means", [True], "boolean"),
        ("scales", [-1], "nonnegative"),
        ("scales", [0], "constant"),
        ("scales", [float("nan")], "finite"),
        ("coefficients", [float("inf")], "finite"),
        ("intercept", False, "boolean"),
        ("penalty", 0, "positive"),
        ("training_sha256", "bad", "SHA-256"),
        ("training_sha256", "A" * 64, "SHA-256"),
        ("training_sha256", 12, "SHA-256"),
        ("provenance", {}, "provenance"),
        ("coefficients", [1.5], "checksum"),
        ("intercept", 999, "checksum"),
        ("provenance", {"dataset_id": "changed", "split_id": "train"}, "checksum"),
        ("training_sha256", "a" * 64, "checksum"),
        ("artifact_sha256", "bad", "checksum"),
        ("artifact_sha256", None, "checksum"),
    ],
)
def test_artifact_schema_numeric_and_checksum_tampering(field, bad, message):
    with pytest.raises(ValueError, match=message):
        RidgeModel.from_dict(fit().to_dict() | {field: bad})


def test_artifact_fields_and_direct_constructor_are_validated():
    artifact = fit().to_dict()
    for invalid in (
        None,
        [],
        artifact | {"extra": 1},
        {k: v for k, v in artifact.items() if k != "penalty"},
    ):
        with pytest.raises(ValueError, match="fields"):
            RidgeModel.from_dict(invalid)
    with pytest.raises(ValueError, match="positive"):
        replace(fit(), penalty=-1)
    model = replace(fit(), feature_names=["x"], means=[2], scales=[1], coefficients=[1])
    assert model.means == (2,)
    assert isinstance(model.feature_names, tuple)


@pytest.mark.parametrize(
    "rows", [[], None, [[1, 2]], [[True]], [[float("nan")]], [[1]] * (MAX_ROWS + 1)]
)
def test_prediction_validation(rows):
    with pytest.raises(ValueError):
        fit().predict(rows)


def test_numeric_limits_and_explicit_failures():
    # Mean computation does not overflow on a valid large constant column/target.
    assert (
        fit(rows=[[1e308], [1e308]], responses_log2=[1e308, 1e308]).intercept == 1e308
    )
    with pytest.raises(ValueError, match="centered feature"):
        fit(
            rows=[[-1.7e308], [1.7e308], [1.7e308]],
            responses_log2=[0, 0, 0],
            record_ids=["a", "b", "c"],
        )
    with pytest.raises(ValueError, match="centered response"):
        fit(
            rows=[[0], [0], [0]],
            responses_log2=[-1.7e308, 1.7e308, 1.7e308],
            record_ids=["a", "b", "c"],
        )
    with pytest.raises(ValueError, match="scale underflow"):
        fit(
            rows=[[0], [5e-324], [0], [0], [0]],
            responses_log2=[0] * 5,
            record_ids=list("abcde"),
        )
    with pytest.raises(ValueError, match="too small"):
        fit(rows=[[1, 1], [3, 3]], feature_names=["x", "y"], penalty=5e-324)
    with pytest.raises(ValueError, match="Cholesky pivot"):
        _solve([[1, 1], [1, 1]], [0, 0])
    with pytest.raises(ValueError, match="overflow"):
        fit(responses_log2=[-1.7e308, 1.7e308])
    # Summation overflow is explicit, including mixed signed overflow products.
    for terms in ([1.7e308, 1.7e308], [math.inf, -math.inf], [math.inf]):
        with pytest.raises(ValueError, match="overflow"):
            _sum(terms)
    # Synthetic linear systems isolate failure in each triangular solve stage.
    with pytest.raises(ValueError, match="Cholesky factor"):
        _solve([[5e-324, 0], [1e308, 1]], [0, 0])
    with pytest.raises(ValueError, match="forward solution"):
        _solve([[5e-324]], [1e308])
    with pytest.raises(ValueError, match="ridge coefficient"):
        _solve([[1e-300]], [1e100])


def test_prediction_overflow_and_training_scale_under_distribution_shift():
    with pytest.raises(ValueError, match="standardized prediction"):
        replace(fit(), means=(-1e308,)).predict([[1e308]])
    with pytest.raises(ValueError, match="standardized prediction"):
        replace(fit(), scales=(5e-324,)).predict([[3]])
    with pytest.raises(ValueError, match="prediction contribution"):
        replace(fit(), coefficients=(1e308,)).predict([[5]])
    with pytest.raises(ValueError, match="overflow"):
        replace(fit(), intercept=1.7e308, coefficients=(1.7e308,)).predict([[3]])
    assert fit().predict([[100], [102]]) == pytest.approx((102, 104))


def test_unrepresentable_feature_mean_keeps_intercept_unpenalized():
    # The exact mean 10**16 + 1 cannot be stored as a float. Population scale
    # remains 1; residual centering must be reflected in the fitted intercept.
    model = fit(rows=[[1e16], [1e16 + 2]])
    assert model.means == (1e16,)
    assert model.scales == (1,)
    assert model.intercept == pytest.approx(3)
    assert model.predict([[1e16], [1e16 + 2]]) == pytest.approx((3, 5))
    assert fit(rows=[[-1e308], [1e308]], responses_log2=[0, 0]).scales == (1e308,)


def test_rounded_target_mean_changes_the_exact_intercept():
    # Exact target mean = 10**16 + 1, rounded down; exact feature mean =
    # 10**16 + 3, rounded up. After centering, the exact ridge coefficient is
    # 1/2 and the intercept in stored coordinates is 10**16 + 3/2, rounding
    # to 10**16 + 2. Dropping target_offset instead rounds it to 10**16.
    model = fit(rows=[[1e16 + 2], [1e16 + 4]], responses_log2=[1e16, 1e16 + 2])
    assert model.means == (1e16 + 4,)
    assert model.scales == (1,)
    assert model.coefficients == (0.5,)
    assert model.intercept == 1e16 + 2
    assert model.predict([[1e16 + 4]]) == (1e16 + 2,)


def test_resource_boundaries_and_text_limits():
    rows = [[0.0] * MAX_FEATURES] * MAX_ROWS
    metadata = {"dataset_id": "d" * 1024, "split_id": "s"}
    metadata.update({str(i): "v" for i in range(30)})
    model = fit(
        rows=rows,
        responses_log2=[0] * MAX_ROWS,
        feature_names=[str(i) for i in range(MAX_FEATURES)],
        record_ids=[str(i) for i in range(MAX_ROWS)],
        provenance=metadata,
    )
    assert model.predict(rows) == (0,) * MAX_ROWS
    assert model.coefficients == (0,) * MAX_FEATURES
    assert RidgeModel.from_dict(model.to_dict()) == model
    assert fit(
        feature_names=["x" * 256], record_ids=["a" * 256, "b"]
    ).feature_names == ("x" * 256,)
