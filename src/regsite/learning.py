"""Deterministic stdlib ridge regression for caller-supplied log2 responses.

``fit_ridge`` minimizes sum of squared log2 residuals + penalty * sum(beta**2)
on columns standardized with training population statistics. The intercept is
unpenalized. A zero scale explicitly marks a constant training column: it always
contributes zero, including on new rows. Coefficients refer to standardized
columns; predictions are log2 translation scores, never energies/probabilities.

Only lists/tuples of finite Python ints/floats are accepted (booleans excluded).
There are 1..10,000 rows and 1..64 features. Binary64 rounding applies; overflow,
collapsed nonconstant scales and nonpositive Cholesky pivots raise ValueError.
Penalties lost when added to a Gram diagonal are rejected explicitly.
Cholesky also rejects a pivot/original-diagonal ratio below 2**-33. This
feature-order-dependent heuristic screens severe local dependence; it is not a
full-system condition-number estimate or a guarantee of coefficient accuracy.
Provenance is caller-supplied nonsecret text, including dataset_id and split_id.
No data access, target transformation, tuning or scientific evaluation occurs.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import fsum, isfinite, sqrt
from statistics import mean, pstdev
from types import MappingProxyType
from typing import ClassVar

MAX_ROWS = 10_000
MAX_FEATURES = 64
VERSION = "ridge-log2-assay-v1"
_MIN_RELATIVE_PIVOT = 2.0**-33


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number, not a boolean")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} is outside finite float range") from exc
    if not isfinite(result):
        raise ValueError(f"{label} must be finite (numerical overflow)")
    return result


def _items(value: object, label: str, limit: int) -> list | tuple:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= limit:
        raise ValueError(f"{label} must be a list/tuple with 1..{limit} entries")
    return value


def _text(value: object, label: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text of at most {limit} characters")
    return value


def _names(value: object, label: str, limit: int) -> tuple[str, ...]:
    names = tuple(_text(item, label) for item in _items(value, label, limit))
    if len(set(names)) != len(names):
        raise ValueError(f"{label} must be unique")
    return names


def _numbers(value: object, label: str, length: int) -> tuple[float, ...]:
    items = _items(value, label, length)
    if len(items) != length:
        raise ValueError(f"{label} must have exactly {length} entries")
    return tuple(_number(item, label) for item in items)


def _rows(value: object, width: int) -> tuple[tuple[float, ...], ...]:
    return tuple(_numbers(row, "row", width) for row in _items(value, "rows", MAX_ROWS))


def _provenance(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or not 2 <= len(value) <= 32:
        raise ValueError("provenance must be a mapping with 2..32 text entries")
    copied = {
        _text(key, "provenance key"): _text(item, "provenance value", 1024)
        for key, item in value.items()
    }
    if not {"dataset_id", "split_id"} <= copied.keys():
        raise ValueError("provenance requires dataset_id and split_id")
    return MappingProxyType(copied)


def _digest(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _sum(values: list[float]) -> float:
    try:
        result = fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError("numerical overflow while summing") from exc
    return _number(result, "computed sum")


@dataclass(frozen=True, slots=True)
class RidgeModel:
    """Immutable training statistics and standardized weights; use fit_ridge.

    to_dict/from_dict exchange strict JSON objects. The artifact checksum detects
    accidental changes, not malicious rewriting; it is not an authenticity proof.
    The input fingerprint covers ordered rows, log2 responses, IDs, feature names,
    penalty, version and provenance after numeric validation/conversion to float.
    Returned JSON dictionaries and the original metadata cannot mutate the model.
    Models are unhashable. JSON via to_dict/from_dict is the supported portability
    boundary; pickle and deepcopy are unsupported.
    """

    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    intercept: float
    coefficients: tuple[float, ...]
    penalty: float
    training_sha256: str
    provenance: Mapping[str, str]
    version: str = VERSION
    score_scale: ClassVar[str] = "log2_assay_response"
    __hash__: ClassVar[None] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.version != VERSION:
            raise ValueError("unsupported ridge model version")
        names = _names(self.feature_names, "feature_names", MAX_FEATURES)
        object.__setattr__(self, "feature_names", names)
        for field in ("means", "scales", "coefficients"):
            object.__setattr__(
                self, field, _numbers(getattr(self, field), field, len(names))
            )
        object.__setattr__(self, "intercept", _number(self.intercept, "intercept"))
        object.__setattr__(self, "penalty", _number(self.penalty, "penalty"))
        if self.penalty <= 0:
            raise ValueError("penalty must be positive")
        for scale, coefficient in zip(self.scales, self.coefficients, strict=True):
            if scale < 0 or (scale == 0 and coefficient != 0):
                raise ValueError(
                    "scales must be nonnegative; constant weights must be zero"
                )
        if not isinstance(self.training_sha256, str) or not re.fullmatch(
            "[0-9a-f]{64}", self.training_sha256
        ):
            raise ValueError("training_sha256 must be a lowercase SHA-256 hex digest")
        object.__setattr__(self, "provenance", _provenance(self.provenance))

    def _payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "score_scale": self.score_scale,
            "feature_names": list(self.feature_names),
            "means": list(self.means),
            "scales": list(self.scales),
            "intercept": self.intercept,
            "coefficients": list(self.coefficients),
            "penalty": self.penalty,
            "training_sha256": self.training_sha256,
            "provenance": dict(self.provenance),
        }

    def to_dict(self) -> dict[str, object]:
        """Return an independent JSON object, including its content checksum."""
        payload = self._payload()
        return {**payload, "artifact_sha256": _digest(payload)}

    @classmethod
    def from_dict(cls, value: object) -> "RidgeModel":
        """Validate a JSON object and checksum; reject missing/unknown fields."""
        fields = {
            "version",
            "score_scale",
            "feature_names",
            "means",
            "scales",
            "intercept",
            "coefficients",
            "penalty",
            "training_sha256",
            "provenance",
            "artifact_sha256",
        }
        if not isinstance(value, dict) or value.keys() != fields:
            raise ValueError("ridge artifact has missing or unknown fields")
        if value["score_scale"] != cls.score_scale:
            raise ValueError("ridge score_scale must be log2_assay_response")
        model = cls(
            feature_names=value["feature_names"],
            means=value["means"],
            scales=value["scales"],
            intercept=value["intercept"],
            coefficients=value["coefficients"],
            penalty=value["penalty"],
            training_sha256=value["training_sha256"],
            provenance=value["provenance"],
            version=value["version"],
        )
        if value["artifact_sha256"] != _digest(model._payload()):
            raise ValueError("ridge artifact checksum mismatch")
        return model

    def predict(self, rows: object) -> tuple[float, ...]:
        """Score 1..10,000 rows in feature_names order using training scaling."""
        numeric_rows = _rows(rows, len(self.feature_names))
        return tuple(
            _sum(
                [
                    self.intercept,
                    *[
                        _number(
                            _number((value - mean) / scale, "standardized prediction")
                            * coefficient,
                            "prediction contribution",
                        )
                        for value, mean, scale, coefficient in zip(
                            row, self.means, self.scales, self.coefficients, strict=True
                        )
                        if scale != 0
                    ],
                ]
            )
            for row in numeric_rows
        )


def _solve(gram: list[list[float]], rhs: list[float]) -> tuple[float, ...]:
    """Solve a symmetric positive definite system by Cholesky factorization."""
    size = len(rhs)
    lower = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1):
            residual = _sum(
                [gram[i][j], -_sum([lower[i][k] * lower[j][k] for k in range(j)])]
            )
            if i == j:
                if residual <= 0:
                    raise ValueError(
                        "nonpositive Cholesky pivot; increase ridge penalty"
                    )
                if residual / gram[i][i] < _MIN_RELATIVE_PIVOT:
                    raise ValueError(
                        "ill-conditioned Cholesky pivot; increase ridge penalty "
                        "or remove dependent features"
                    )
                lower[i][j] = sqrt(residual)
            else:
                lower[i][j] = _number(residual / lower[j][j], "Cholesky factor")
    forward = [0.0] * size
    for i in range(size):
        forward[i] = _number(
            _sum([rhs[i], -_sum([lower[i][j] * forward[j] for j in range(i)])])
            / lower[i][i],
            "forward solution",
        )
    weights = [0.0] * size
    for i in reversed(range(size)):
        weights[i] = _number(
            _sum(
                [
                    forward[i],
                    -_sum([lower[j][i] * weights[j] for j in range(i + 1, size)]),
                ]
            )
            / lower[i][i],
            "ridge coefficient",
        )
    return tuple(weights)


def fit_ridge(
    rows: object,
    responses_log2: object,
    *,
    feature_names: object,
    record_ids: object,
    penalty: object,
    provenance: object,
) -> RidgeModel:
    """Fit standardized ridge to already-log2 responses, without data access.

    IDs are nonempty unique strings in row order; names define column order.
    Provenance requires nonsecret dataset_id/split_id strings (up to 32 entries,
    256-character keys and 1024-character values). IDs/names allow 256 characters.
    Penalty must be finite and strictly positive; its objective uses a sum,
    rather than a mean, of squared residuals. Row order is part of the fingerprint.
    """
    names = _names(feature_names, "feature_names", MAX_FEATURES)
    matrix = _rows(rows, len(names))
    targets = _numbers(responses_log2, "responses_log2", len(matrix))
    ids = _names(record_ids, "record_ids", MAX_ROWS)
    if len(ids) != len(matrix):
        raise ValueError("record_ids must match the number of rows")
    ridge = _number(penalty, "penalty")
    if ridge <= 0:
        raise ValueError("penalty must be positive")
    metadata = _provenance(provenance)
    columns = tuple(zip(*matrix, strict=True))
    # statistics uses exact ratios internally, avoiding sum/square overflow.
    means = tuple(mean(column) for column in columns)
    scales = []
    standardized = []
    for column, center in zip(columns, means, strict=True):
        centered = tuple(
            _number(value - center, "centered feature") for value in column
        )
        if max(column) == min(column):
            scale = 0.0
            values = [0.0] * len(matrix)
        else:
            scale = pstdev(column)
            if scale == 0:
                raise ValueError("nonconstant feature scale underflow")
            values = [
                _number(value / scale, "standardized feature") for value in centered
            ]
        scales.append(scale)
        standardized.append(values)
    intercept = mean(targets)
    centered_targets = [
        _number(value - intercept, "centered response") for value in targets
    ]
    # Rounded stored means may leave a nonzero standardized mean (e.g. a
    # midpoint between adjacent floats). Recenter for the solve, then adjust
    # the unpenalized intercept back to the stored prediction coordinates.
    offsets = [mean(column) for column in standardized]
    standardized = [
        [value - offset for value in column]
        for column, offset in zip(standardized, offsets, strict=True)
    ]
    target_offset = mean(centered_targets)
    centered_targets = [
        _number(value - target_offset, "recentered response")
        for value in centered_targets
    ]
    gram = []
    for i, left in enumerate(standardized):
        entries = []
        for j, right in enumerate(standardized):
            product = _sum([a * b for a, b in zip(left, right, strict=True)])
            if i == j:
                diagonal = _sum([product, ridge])
                if diagonal == product:
                    raise ValueError("penalty is too small at working precision")
                product = diagonal
            entries.append(product)
        gram.append(entries)
    rhs = [
        _sum([a * b for a, b in zip(column, centered_targets, strict=True)])
        for column in standardized
    ]
    weights = _solve(gram, rhs)
    intercept = _sum(
        [
            intercept,
            target_offset,
            -_sum([a * b for a, b in zip(offsets, weights, strict=True)]),
        ]
    )
    fingerprint = _digest(
        {
            "version": VERSION,
            "rows": matrix,
            "responses_log2": targets,
            "feature_names": names,
            "record_ids": ids,
            "penalty": ridge,
            "provenance": dict(metadata),
        }
    )
    return RidgeModel(
        names, means, tuple(scales), intercept, weights, ridge, fingerprint, metadata
    )
