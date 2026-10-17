"""Published standby costs with a declared, finite structural reconstruction.

Espah Borujeni et al. (2014), doi:10.1093/nar/gkt1139, equations 3/5 and
Supplementary Figure S3. See docs/validation/rbs-standby.md for choices not
specified by the paper. Energies come from a caller-supplied fixed-state oracle;
this module neither folds sequences nor fits experimental observations.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import product

from regsite.structures import BackendError, Structure, to_ct

MAX_STATES = 512
COEFFICIENTS = (0.038, -1.629, 17.359)
ZERO_AREA = (1.629 - math.sqrt(1.629**2 - 4 * 0.038 * 17.359)) / (2 * 0.038)
PARAMETERS = {
    "source_doi": "10.1093/nar/gkt1139",
    "source_xml_sha256": (
        "3410c14d94f74845fe5ffa8d879bd33144909c0fc72e439bc91e9ca032333a39"
    ),
    "supplement_pdf_sha256": (
        "a36ae7d252442865f4dc813ceb34022e2c0e01899c02fca61012d97c6558ffaf"
    ),
    "distortion_coefficients": list(COEFFICIENTS),
    "surface_area_offset_nt": 15,
    "accessibility_height_cap_nt": 15,
    "sliding_kcal_mol_per_nt": 0.2,
    "distortion_zero_area_nt": ZERO_AREA,
    "distortion_continuation": "zero at and above first quadratic root",
    "height_rule": "mean contour sides; recursive base-only/individual branch average",
    "opening_search": "ancestor-closed pair removals within one original module",
    "maximum_unique_states": MAX_STATES,
    "energy_rule": "nonnegative fixed whole-complex energy difference",
    "tie_rule": "cost, opened pair count, original module order, remaining core order",
    "binding_candidate_rule": "historical cofold-plus-spacing selection before standby",
}


class StandbySearchLimit(BackendError):
    """This structure is outside the declared exhaustive opening-search bound."""


@dataclass(frozen=True)
class Hairpin:
    """One paired root and its immediately nested paired roots."""

    start: int
    end: int  # Exclusive, including the closing base.
    children: tuple["Hairpin", ...]

    @property
    def height(self) -> float:
        unpaired = (
            self.end
            - self.start
            - 2
            - sum(child.end - child.start for child in self.children)
        )
        if not self.children:
            return 1 + unpaired / 2
        if len(self.children) == 1:
            return 1 + unpaired / 2 + self.children[0].height
        return (
            1
            + (unpaired + len(self.children)) / 2
            + sum(child.height - 0.5 for child in self.children)
            / (len(self.children) + 1)
        )


@dataclass(frozen=True)
class Module:
    """Transcript-oriented prefix coordinates; shared gaps belong to both neighbors."""

    distal: tuple[int, int]
    hairpin: tuple[int, int] | None
    proximal: tuple[int, int]
    height: float
    downstream: tuple[tuple[int, int, float], ...]

    @property
    def downstream_height(self) -> float:
        return sum(height for _, _, height in self.downstream)

    @property
    def area(self) -> float:
        return (
            15
            + self.distal[1]
            - self.distal[0]
            + self.proximal[1]
            - self.proximal[0]
            - min(15, self.height)
        )


@dataclass(frozen=True)
class Choice:
    """One module in one completely specified fixed secondary structure."""

    module: Module
    original_hairpin: tuple[int, int] | None
    pairs: tuple[int, ...]
    opened_pairs: tuple[tuple[int, int], ...]
    unfolding_raw: float
    unfolding: float
    distortion: float
    sliding: float

    @property
    def total(self) -> float:
        return self.unfolding + self.distortion + self.sliding


@dataclass(frozen=True)
class StandbyResult:
    """Selected state, finite search coverage and independently minimized ablations."""

    selected: Choice
    evaluated_states: int
    original_modules: int
    ablations: dict[str, float]
    negative_unfolding_seen: bool


def distortion(area: float) -> float:
    """Monotone nonnegative continuation of the published rounded quadratic."""
    if not math.isfinite(area) or area < 0:
        raise BackendError("standby surface area must be finite and nonnegative")
    if area >= ZERO_AREA:
        return 0.0
    a, b, c = COEFFICIENTS
    return max(0.0, a * area * area + b * area + c)


def _forest(pairs: tuple[int, ...], start: int, end: int) -> tuple[Hairpin, ...]:
    roots = []
    while start < end:
        partner = pairs[start]
        if partner >= 0:
            roots.append(
                Hairpin(start, partner + 1, _forest(pairs, start + 1, partner))
            )
            start = partner + 1
        else:
            start += 1
    return tuple(roots)


def _modules(roots: tuple[Hairpin, ...], length: int) -> tuple[Module, ...]:
    if not roots:
        return (Module((0, 0), None, (0, length), 0, ()),)
    return tuple(
        Module(
            (roots[i - 1].end if i else 0, root.start),
            (root.start, root.end),
            (root.end, roots[i + 1].start if i + 1 < len(roots) else length),
            root.height,
            tuple((other.start, other.end, other.height) for other in roots[i + 1 :]),
        )
        for i, root in enumerate(roots)
    )


def modules(structure: Structure) -> tuple[Module, ...]:
    """Validate and decompose at most 100 prefix bases into top-level modules."""
    if len(structure.sequence) > 100:
        raise BackendError("standby prefix exceeds 100 nucleotides")
    to_ct(structure.sequence, structure.pairs)
    return _modules(
        _forest(structure.pairs, 0, len(structure.pairs)), len(structure.pairs)
    )


def _state_count(root: Hairpin) -> int:
    """Count in O(n), saturating above the cap before enumerating any states."""
    return min(MAX_STATES + 1, 1 + math.prod(_state_count(c) for c in root.children))


def _openings(root: Hairpin) -> tuple[tuple[tuple[int, int], ...], ...]:
    """All ancestor-closed removals, after the caller has checked the total count."""
    states: list[tuple[tuple[int, int], ...]] = [()]
    children = [_openings(child) for child in root.children]
    for combination in product(*children):
        states.append(
            ((root.start, root.end - 1),)
            + tuple(pair for child_state in combination for pair in child_state)
        )
    return tuple(states)


def optimize(
    prefix: Structure,
    baseline_energy: float,
    evaluate: Callable[[tuple[int, ...]], float],
) -> StandbyResult:
    """Minimize distortion + unfolding + sliding over a declared complete state set.

    Only one original top-level hairpin may open. Removing a pair requires that
    all its ancestors have opened; descendants may independently remain paired.
    At a branch split each remaining daughter is eligible. Complete dissolution
    creates an unstructured module spanning the gap between neighboring roots.
    No new pairs form. Over-limit searches fail, never return a partial minimum.
    evaluate receives the full prefix pairing array and returns the energy of
    the corresponding full bound complex, preserving all other structures.
    """
    original_modules = modules(prefix)
    if not math.isfinite(baseline_energy):
        raise BackendError("nonfinite standby baseline energy")
    roots = _forest(prefix.pairs, 0, len(prefix.pairs))
    count = 1 + sum(_state_count(root) - 1 for root in roots)
    if count > MAX_STATES:
        raise StandbySearchLimit("standby opening search exceeds 512 states")
    searches = [(root, _openings(root)) for root in roots]
    choices = [
        Choice(
            module,
            module.hairpin,
            prefix.pairs,
            (),
            0,
            0,
            distortion(module.area),
            0.2 * module.downstream_height,
        )
        for module in original_modules
    ]
    negative = False
    for root, openings in searches:
        for removed in openings[1:]:
            pairs = list(prefix.pairs)
            for left, right in removed:
                pairs[left] = pairs[right] = -1
            updated = tuple(pairs)
            energy = evaluate(updated)
            if not math.isfinite(energy):
                raise BackendError("nonfinite standby state energy")
            raw = energy - baseline_energy
            negative |= raw < -1e-9
            remaining = _forest(updated, 0, len(updated))
            candidates = [
                module
                for module in _modules(remaining, len(updated))
                if module.hairpin is not None
                and root.start <= module.hairpin[0] < root.end
            ]
            if not candidates:
                left = max((r.end for r in remaining if r.end <= root.start), default=0)
                right = min(
                    (r.start for r in remaining if r.start >= root.end),
                    default=len(updated),
                )
                candidates = [
                    Module(
                        (left, left),
                        None,
                        (left, right),
                        0,
                        tuple(
                            (r.start, r.end, r.height)
                            for r in remaining
                            if r.start >= right
                        ),
                    )
                ]
            choices.extend(
                Choice(
                    module,
                    (root.start, root.end),
                    updated,
                    removed,
                    raw,
                    max(0.0, raw),
                    distortion(module.area),
                    0.2 * module.downstream_height,
                )
                for module in candidates
            )
    selected = min(
        choices,
        key=lambda choice: (
            choice.total,
            len(choice.opened_pairs),
            choice.original_hairpin or (-1, -1),
            choice.module.hairpin or (-1, -1),
        ),
    )
    return StandbyResult(
        selected,
        count,
        len(original_modules),
        {
            "no_opening": min(c.total for c in choices if not c.opened_pairs),
            "no_sliding": min(c.unfolding + c.distortion for c in choices),
            "no_distortion": min(c.unfolding + c.sliding for c in choices),
        },
        negative,
    )
