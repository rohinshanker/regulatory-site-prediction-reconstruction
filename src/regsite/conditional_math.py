"""Independent S4–S26 scalar algebra, with explicit binary64 failure semantics.

Inputs to these internal functions have already passed the public raw-document
validator. No fitted coefficients or experimental measurements are embedded.
"""

import math
import time
from decimal import ROUND_CEILING, ROUND_FLOOR, Context, Decimal, localcontext
from fractions import Fraction

GAS_CONSTANT = 8.31446261815324 / 4184
TOLERANCE = 1e-12
SIGN_PRECISIONS = (80, 160)


class ConditionalError(ValueError):
    """A stable refusal code and its public result status."""

    def __init__(self, code: str, message: str, status: str = "failed") -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def check_deadline(deadline: float) -> None:
    """Refuse work after the request's monotonic deadline."""
    if time.monotonic() >= deadline:
        raise ConditionalError("deadline_exceeded", "Request deadline exhausted")


def represent(value: Fraction) -> float:
    """Round exact elementary arithmetic once, detecting range loss."""
    try:
        result = float(value)
    except OverflowError as exc:
        raise ConditionalError("numerical_range", "Value exceeds binary64") from exc
    if value and result == 0:
        raise ConditionalError("numerical_range", "Nonzero value underflows binary64")
    return result


def difference(on: float, off: float) -> float:
    """Subtract without spurious intermediate range loss."""
    return represent(Fraction(on) - Fraction(off))


def log_ratio(numerator: float, denominator: float) -> float:
    """Preserve affinity changes near an arbitrarily large/small standard."""
    a, b = Fraction(numerator), Fraction(denominator)
    if b / 2 <= a <= 2 * b:
        return math.log1p(float((a - b) / b))
    return math.log(numerator) - math.log(denominator)


def exponential(log_value: float) -> float:
    """A positive ratio never silently becomes zero or infinity."""
    try:
        result = math.exp(log_value)
    except OverflowError as exc:
        raise ConditionalError("numerical_range", "Ratio exceeds binary64") from exc
    if result == 0:
        raise ConditionalError("numerical_range", "Positive ratio underflows binary64")
    return result


def mixture(log_ratio: float, log_fraction: float | None) -> float:
    """Compute (1-f)+f*exp(log_ratio), retaining tiny-f/large-ratio products."""
    if log_fraction is None:
        return 1.0
    if log_fraction == 0:
        return exponential(log_ratio)
    # log(1-exp(x)) has cancellation near x=0; expm1 preserves that tail.
    other = math.log(-math.expm1(log_fraction))
    weighted = represent(Fraction(log_fraction) + Fraction(log_ratio))
    larger, smaller = max(other, weighted), min(other, weighted)
    return exponential(larger + math.log1p(math.exp(smaller - larger)))


def empty_occupancy(mode: str) -> dict:
    """Return the complete public occupancy shape before any computation."""
    return dict(
        mode=mode,
        status="failed",
        fraction=None,
        concentrations=None,
        volume_fractions=None,
        solver=None,
    )


def log_bounds(ratio: Fraction, precision: int) -> tuple[Fraction, Fraction]:
    """Enclose ln(exact rational) using directed division and rounded Decimal ln.

    Decimal ln is correctly rounded to nearest/even. One adjacent representable
    value on each side encloses that rounding. ln(1) is exactly zero, avoiding
    Decimal's enormous subnormal neighbor at zero. No caller context is used.
    """
    with localcontext(Context(prec=precision)) as context:
        context.rounding = ROUND_FLOOR
        lower = Decimal(ratio.numerator) / Decimal(ratio.denominator)
        context.rounding = ROUND_CEILING
        upper = Decimal(ratio.numerator) / Decimal(ratio.denominator)
        low_log = Decimal(0) if lower == 1 else lower.ln().next_minus()
        high_log = Decimal(0) if upper == 1 else upper.ln().next_plus()
        return Fraction(low_log), Fraction(high_log)


def certified_stationary(
    bound: float,
    m: float,
    ligand: float,
    solvent: float,
    vm: float,
    vl: float,
    energy: Fraction,
    deadline: float,
) -> tuple[int, float, bool]:
    """Certify D's sign and residual bound, or refuse unresolved cancellation.

    Every argument to ln and every weighted interval operation is exact rational
    arithmetic. The two fixed Decimal precisions bound certification work. A
    float residual is diagnostic only; it never decides which root interval lives.
    """
    b, fm, fl = Fraction(bound), Fraction(m), Fraction(ligand)
    rna_ratio = b / (fm - b)
    ligand_ratio = Fraction(vl) * (fl - b) / Fraction(solvent)
    scale = max(Fraction(1), Fraction(vm), Fraction(vl), abs(energy))
    for precision in SIGN_PRECISIONS:
        check_deadline(deadline)
        rna_low, rna_high = log_bounds(rna_ratio, precision)
        ligand_low, ligand_high = log_bounds(ligand_ratio, precision)
        low = (Fraction(vm) * rna_low - Fraction(vl) * ligand_high + energy) / scale
        high = (Fraction(vm) * rna_high - Fraction(vl) * ligand_low + energy) / scale
        if low == high == 0:
            return 0, 0.0, True
        if low > 0 or high < 0:
            return (
                1 if low > 0 else -1,
                represent((low + high) / 2),
                max(abs(low), abs(high)) <= Fraction(TOLERANCE),
            )
    raise ConditionalError(
        "numerical_range", "Stationary sign uncertifiable at bounded precision"
    )


def solve_occupancy(
    supplied: dict,
    beta: float,
    switching: float | Fraction,
    iterations: int,
    deadline: float,
    out: dict | None = None,
) -> dict:
    """Solve the strictly monotone literal volume stationary equation."""
    out = empty_occupancy(supplied["mode"]) if out is None else out
    if supplied["mode"] == "supplied_fraction":
        out.update(status="ok", fraction=supplied["fraction"])
        return out
    m, ligand = supplied["mrna_total_molar"], supplied["ligand_total_molar"]
    solvent = supplied["solvent_molar"]
    vm, vl = supplied["mrna_relative_volume"], supplied["ligand_relative_volume"]
    bound, low, high, count, residual = 0.0, 0.0, min(m, ligand), 0, None
    out["solver"] = dict(iterations=0, bracket_molar=[low, high], scaled_residual=None)
    if m > 0 and ligand > 0:
        # Preserve the exact combined energy, including below a rounded RNA cost.
        energy = Fraction(beta) * Fraction(switching)
        for step in range(1, iterations + 1):
            count = step
            check_deadline(deadline)
            bound = low + (high - low) / 2
            if bound <= 0 or bound >= min(m, ligand) or bound in (low, high):
                raise ConditionalError(
                    "numerical_range", "No representable interior bracket"
                )
            sign, residual, residual_small = certified_stationary(
                bound, m, ligand, solvent, vm, vl, energy, deadline
            )
            if sign == 0:
                low = high = bound
            elif sign < 0:
                low = bound
            else:
                high = bound
            out["solver"] = dict(
                iterations=count, bracket_molar=[low, high], scaled_residual=residual
            )
            width_small = Fraction(high) - Fraction(low) <= (
                Fraction(TOLERANCE) * Fraction(min(m, ligand))
            )
            if width_small and residual_small:
                break
        else:
            raise ConditionalError(
                "nonconvergence", "Occupancy solver exhausted iterations"
            )
    check_deadline(deadline)
    free_m, free_l = m - bound, ligand - bound
    out.update(
        concentrations=dict(
            mrna_free_molar=free_m,
            ligand_free_molar=free_l,
            complex_molar=bound,
            mrna_balance_error_molar=math.fsum((free_m, bound, -m)),
            ligand_balance_error_molar=math.fsum((free_l, bound, -ligand)),
        ),
        solver=dict(
            iterations=count,
            bracket_molar=[low, high] if count else [0.0, 0.0],
            scaled_residual=residual,
        ),
    )
    out["fraction"] = None if m == 0 else represent(Fraction(bound) / Fraction(m))
    volumes = [
        represent(Fraction(v) * Fraction(c) / Fraction(solvent))
        for v, c in ((vm, free_m), (vl, free_l), (vm, bound))
    ]
    total = represent(sum((Fraction(v) for v in volumes), Fraction(0)))
    out.update(
        status="no_mrna" if m == 0 else "ok",
        volume_fractions=dict(
            mrna_free=volumes[0], ligand_free=volumes[1], complex=volumes[2], sum=total
        ),
    )
    return out


def evaluate_response(
    data: dict, settings: dict, deadline: float
) -> tuple[dict, float | None, list]:
    """Evaluate independent components, retaining valid fields after range failures."""
    response: dict = dict.fromkeys(
        (
            "ligand_binding_kcal_mol",
            "switching_kcal_mol",
            "log_ar_max",
            "ar_max",
            "ar_conc",
            "ar_actual",
            "metastability_factor",
            "metastability_applied",
        )
    )
    response["occupancy"] = empty_occupancy(data["occupancy"]["mode"])
    errors: list[ConditionalError] = []

    def attempt(function):
        try:
            check_deadline(deadline)
            return function()
        except ConditionalError as exc:
            errors.append(exc)
            return None

    energies, beta, affinity = (
        data["energies"],
        data["beta_mol_per_kcal"],
        data["affinity"],
    )
    exact_cost = Fraction(energies["rna_on_kcal_mol"]) - Fraction(
        energies["rna_off_kcal_mol"]
    )
    cost = attempt(lambda: represent(exact_cost))
    if affinity["mode"] == "delta_g":
        binding = affinity["delta_g_kcal_mol"]
    else:
        binding = attempt(
            lambda: represent(
                Fraction(GAS_CONSTANT)
                * Fraction(data["temperature_kelvin"])
                * Fraction(log_ratio(affinity["kd_molar"], affinity["standard_molar"]))
            )
        )
    response["ligand_binding_kcal_mol"] = binding
    log_ar = attempt(
        lambda: represent(
            -Fraction(beta)
            * (
                Fraction(energies["ribosome_on_kcal_mol"])
                - Fraction(energies["ribosome_off_kcal_mol"])
            )
        )
    )
    response["log_ar_max"] = log_ar
    if log_ar is not None:
        response["ar_max"] = attempt(lambda: exponential(log_ar))
    if binding is not None:
        exact_switching = exact_cost + Fraction(binding)
        switching = attempt(lambda: represent(exact_switching))
        response["switching_kcal_mol"] = switching
        if switching is not None:
            applied = exact_switching > 0
            response["metastability_applied"] = applied
            log_q: float | None = 0.0
            if applied:
                product = attempt(lambda: represent(Fraction(beta) * exact_switching))
                log_q = (
                    None
                    if product is None
                    else -product - math.log1p(math.exp(-product))
                )
            if log_q is not None:
                response["metastability_factor"] = attempt(lambda: exponential(log_q))
            occupancy = attempt(
                lambda: solve_occupancy(
                    data["occupancy"],
                    beta,
                    exact_switching,
                    settings["max_iterations"],
                    deadline,
                    response["occupancy"],
                )
            )
            occupancy = response["occupancy"] if occupancy is None else occupancy
            f = occupancy["fraction"]
            if f is not None and log_ar is not None:
                log_f = None if f == 0 else math.log(f)
                response["ar_conc"] = attempt(lambda: mixture(log_ar, log_f))
                if log_q is not None:
                    actual_f = None if log_f is None else log_f + log_q
                    response["ar_actual"] = attempt(lambda: mixture(log_ar, actual_f))
    return response, cost, errors
