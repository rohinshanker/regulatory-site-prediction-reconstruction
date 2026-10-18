"""Independent high-precision oracle for supplied conditional-state scalars.

These are synthetic benchmark calculations, not sequence inference or measured
effects. Equations and conventions are pinned in ``conditional-fixtures.json``.
Inputs must be exact dictionaries of finite ASCII decimal strings, at most 128
characters each. Nonzero inputs must have adjusted exponents in [-1000, 1000].
Arithmetic uses an isolated 80-digit, round-half-even Decimal context; unsafe
intermediates (including subnormals) raise ValueError rather than returning zeros
or infinities. The context's exponent limits are -9999 and 9999.

Partition convergence requires bracket width / min(total mRNA, total ligand)
<= 1e-50 AND abs(D) / max(Vm, Vl, abs(beta * switching)) <= 1e-50.
Thus the bracket bounds the absolute bound-fraction error by at most 1e-50.
Finite precision and the 256-iteration cap can refuse extreme interior roots.
No solvent species, packing constraint, Hill law, or Kd-to-occupancy conversion
is added. beta is an independent empirical coefficient, not 1/(R*T).
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import (
    ROUND_HALF_EVEN,
    Clamped,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    Subnormal,
    Underflow,
    localcontext,
)

_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_TOLERANCE = Decimal("1e-50")
_BETA = "beta_mol_per_kcal"
_COST = "rna_structural_cost_kcal_mol"
_RESPONSE_FIELDS = (
    _BETA,
    _COST,
    "ligand_binding_kcal_mol",
    "ribosome_off_kcal_mol",
    "ribosome_on_kcal_mol",
    "bound_fraction",
)
_AFFINITY_FIELDS = ("kd_molar", "standard_molar", "temperature_kelvin")
_PARTITION_POSITIVE = (
    _BETA,
    "mrna_relative_volume",
    "ligand_relative_volume",
    "solvent_molar",
)
_PARTITION_TOTALS = ("mrna_total_molar", "ligand_total_molar")
_PARTITION_FIELDS = (
    *_PARTITION_POSITIVE,
    *_PARTITION_TOTALS,
    "switching_kcal_mol",
)


@contextmanager
def _arithmetic(operation: str) -> Iterator[None]:
    """Make results independent of the caller's precision, traps and flags."""
    context = Context(
        prec=80,
        rounding=ROUND_HALF_EVEN,
        Emin=-9999,
        Emax=9999,
        traps=[
            InvalidOperation,
            DivisionByZero,
            Overflow,
            Underflow,
            Subnormal,
            Clamped,
        ],
    )
    try:
        with localcontext(context):
            yield
    except DecimalException as exc:
        raise ValueError(
            f"{operation}: unsafe Decimal numeric range or domain"
        ) from exc


def _numbers(
    inputs: dict,
    fields: tuple[str, ...],
    *,
    positive: tuple[str, ...] = (),
    nonnegative: tuple[str, ...] = (),
) -> dict[str, Decimal]:
    """Validate the exact schema and numeric domain without changing inputs."""
    if type(inputs) is not dict or inputs.keys() != set(fields):
        raise ValueError("inputs must be a dictionary with exactly the required fields")
    result = {}
    for field in fields:
        text = inputs[field]
        if (
            type(text) is not str
            or not 1 <= len(text) <= 128
            or _DECIMAL.fullmatch(text) is None
        ):
            raise ValueError(
                f"{field}: expected a finite decimal string (1..128 chars)"
            )
        value = Decimal(text)
        if value != 0 and not -1000 <= value.adjusted() <= 1000:
            raise ValueError(f"{field}: adjusted exponent must be in [-1000, 1000]")
        if field in positive and value <= 0:
            raise ValueError(f"{field}: must be positive")
        if field in nonnegative and value < 0:
            raise ValueError(f"{field}: must be nonnegative")
        result[field] = value
    return result


def response(inputs: dict) -> dict:
    """Return Decimal response ratios and the strict-positive correction state.

    Exactly zero switching energy is uncorrected by the declared reconstruction
    policy; the source leaves that boundary unspecified. Repression is valid.
    """
    with _arithmetic("response"):
        values = _numbers(
            inputs, _RESPONSE_FIELDS, positive=(_BETA,), nonnegative=(_COST,)
        )
        beta, fraction = values[_BETA], values["bound_fraction"]
        if not 0 <= fraction <= 1:
            raise ValueError("bound_fraction: must be in [0, 1]")
        switching = values[_COST] + values["ligand_binding_kcal_mol"]
        log_maximum = -beta * (
            values["ribosome_on_kcal_mol"] - values["ribosome_off_kcal_mol"]
        )
        maximum = log_maximum.exp()
        concentration = (1 - fraction) + fraction * maximum
        applied = switching > 0
        factor = _ONE
        if applied:
            weight = (-beta * switching).exp()
            factor = weight / (1 + weight)
        # This equivalent convex sum preserves tiny positive repression ratios.
        actual = (1 - factor) + factor * concentration
        return {
            "maximum_ratio": maximum,
            "log_maximum_ratio": log_maximum,
            "concentration_ratio": concentration,
            "actual_ratio": actual,
            "switching_kcal_mol": switching,
            "metastability_factor": factor,
            "metastability_applied": applied,
        }


def affinity(inputs: dict) -> Decimal:
    """Return binding kcal/mol as R*T*(ln(Kd_molar) - ln(standard_molar))."""
    with _arithmetic("affinity"):
        values = _numbers(inputs, _AFFINITY_FIELDS, positive=_AFFINITY_FIELDS)
        gas_constant = Decimal("8.31446261815324") / Decimal("4184")
        return (
            gas_constant
            * values["temperature_kelvin"]
            * (values["kd_molar"].ln() - values["standard_molar"].ln())
        )


def _solve(
    mrna: Decimal,
    ligand: Decimal,
    mrna_volume: Decimal,
    ligand_volume: Decimal,
    solvent: Decimal,
    energy: Decimal,
    max_iterations: int,
) -> tuple[Decimal, tuple[Decimal, Decimal], Decimal, int, Decimal]:
    """Bisect the strictly increasing source derivative on its feasible domain."""
    lower, upper = _ZERO, min(mrna, ligand)
    initial_width = upper
    scale = max(mrna_volume, ligand_volume, abs(energy))
    for iteration in range(1, max_iterations + 1):
        bound = (lower + upper) / 2
        residual = (
            mrna_volume * (bound / (mrna - bound)).ln()
            - ligand_volume * (ligand_volume * (ligand - bound) / solvent).ln()
            + energy
        )
        if residual < 0:
            lower = bound
        else:
            upper = bound
        if (upper - lower) / initial_width <= _TOLERANCE and abs(
            residual
        ) / scale <= _TOLERANCE:
            return bound, (lower, upper), residual, iteration, scale
    raise ValueError(
        "partition: convergence not reached within max_iterations; "
        "interior root may exceed numeric resolution"
    )


def partition(inputs: dict, *, max_iterations: int = 256) -> dict:
    """Return mass-balanced species, occupancy, volume fractions and solver data.

    All concentrations are molar. Complex volume equals free-mRNA volume and
    free-ligand energy is zero. ``solver_bracket_molar`` encloses the root;
    ``solver_residual`` is D at the returned complex concentration. Boundary
    cases have bracket (0, 0), zero iterations, and no residual or residual scale.
    Missing mRNA gives ``bound_fraction=None`` and ``status='no_mrna'``.
    Volume sums above one are reported and flagged without changing the solution.
    """
    if type(max_iterations) is not int or not 1 <= max_iterations <= 256:
        raise ValueError("max_iterations: must be an integer in [1, 256]")
    with _arithmetic("partition"):
        values = _numbers(
            inputs,
            _PARTITION_FIELDS,
            positive=_PARTITION_POSITIVE,
            nonnegative=_PARTITION_TOTALS,
        )
        mrna, ligand = (values[field] for field in _PARTITION_TOTALS)
        mrna_volume = values["mrna_relative_volume"]
        ligand_volume = values["ligand_relative_volume"]
        solvent = values["solvent_molar"]
        bound, bracket, residual, iterations, scale = (
            _ZERO,
            (_ZERO, _ZERO),
            None,
            0,
            None,
        )
        if mrna > 0 and ligand > 0:
            bound, bracket, residual, iterations, scale = _solve(
                mrna,
                ligand,
                mrna_volume,
                ligand_volume,
                solvent,
                values[_BETA] * values["switching_kcal_mol"],
                max_iterations,
            )
        mrna_free, ligand_free = mrna - bound, ligand - bound
        volumes = {
            "mrna_free_volume_fraction": mrna_volume * mrna_free / solvent,
            "ligand_free_volume_fraction": ligand_volume * ligand_free / solvent,
            "complex_volume_fraction": mrna_volume * bound / solvent,
        }
        volume_sum = sum(volumes.values(), _ZERO)
        return {
            "status": "ok" if mrna > 0 else "no_mrna",
            "bound_fraction": bound / mrna if mrna > 0 else None,
            "complex_molar": bound,
            "mrna_free_molar": mrna_free,
            "ligand_free_molar": ligand_free,
            **volumes,
            "volume_fraction_sum": volume_sum,
            "volume_fraction_sum_exceeds_one": volume_sum > 1,
            "solver_bracket_molar": bracket,
            "solver_residual": residual,
            "solver_residual_scale": scale,
            "solver_iterations": iterations,
            "solver_tolerance": _TOLERANCE,
        }
