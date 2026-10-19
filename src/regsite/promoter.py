"""Pure historical La Fleur 2022 Promoter scoring and coordinate arithmetic.

Scores are learned regression contributions in source-dG units, not physical
free energies or calibrated probabilities. Host metadata never changes equations.
Parameter tables/weights derive from SalisLabCode 46da913, GPL-3.0-or-later;
see data/promoter-ORIGINAL-NOTICE.txt. No upstream Python is executed at runtime.

The core accepts normalized DNA; normalize_dna is the explicit text boundary.
Dataclass serializers return JSON-ready dictionaries without request-dependent
IDs. The I/O layer owns IDs, record validation, scan planning and deadlines.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Any

MODEL_ID = "promoter-lafleur2022-historical-1"
SOURCE_COMMIT = "46da9132740bce30bccd107f02808adf2215e2f0"
PARAMETER_JSON_SHA256 = (
    "e2957d4687a5d5a2a20bcce231b4ea1446f269b383bbae94eed72860efa360dc"
)
COEFFICIENT_ARRAY_SHA256 = (
    "fddf16b38bf29799481e8a45890b669111e16cf2e3448e99d1934d19a8f0b8e9"
)
INTERCEPT_ARRAY_SHA256 = (
    "f7c66a8d838da71a6b2ab17936cd6ff2564e446af8c0676fba95de2116e99a7b"
)
NATIVE_HOST = "Escherichia coli str. K-12 substr. MG1655"
TERMS_UNIT = "source_dG_units"
TERMS_SEMANTICS = (
    "learned regression score contributions; "
    "not independently established free energies"
)
TERM_SOURCE_NAMES = {
    "hex10": "dG_10",
    "hex35": "dG_35",
    "discriminator": "dG_disc",
    "extended10": "dG_ext10",
    "itr": "dG_ITR",
    "up": "dG_UP",
    "spacer": "dG_spacer",
    "intercept": "intercept",
    "total": "dG_total",
    "binding": "dG_bind",
    "source_apparent": "dG_apparent",
}
LOG_MIN = math.log(sys.float_info.min)
LOG_MAX = math.log(sys.float_info.max)
_TABLES = ("groove_access", "persistence", "DNA_DNA_hybrids", "RNA_DNA_hybrids")
_ASCII_SPACE = " \t\n\v\f\r"
_COMPLEMENT = str.maketrans("ACGT", "TGCA")
Interval = tuple[int, int]


class ParameterError(ValueError):
    """Installed model data is missing, malformed or fails its pinned identity."""


class InputError(ValueError):
    """Invalid pure-function input, with machine-readable source location."""

    def __init__(
        self,
        code: str,
        field: str,
        index: int | None = None,
        character: str | None = None,
    ) -> None:
        self.code = code
        self.field = field
        self.index = index
        self.character = character
        super().__init__(f"{code}: {field}")


@dataclass(frozen=True)
class PromoterParameters:
    """Immutable admitted coefficients and tables, including unused indices."""

    coefficients: tuple[float, ...]
    intercept: float
    normalizers: tuple[float, ...]
    tables: Mapping[str, Mapping[str, float]]
    array_sha256: Mapping[str, str]
    parameter_json_sha256: str
    source_commit: str
    license: str
    unused_indices: tuple[int, ...] = (336, 337, 338)


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _parse_parameters(data: Any) -> PromoterParameters:
    """Validate shape/values before verifying the complete canonical identity."""
    expected = {
        "array_sha256",
        "coefficients",
        "intercept",
        "license",
        "normalizers",
        "source_commit",
        "tables",
    }
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("Parameter object fields")
    coefficients, normalizers = data["coefficients"], data["normalizers"]
    for values, count in ((coefficients, 343), (normalizers, 4)):
        if not isinstance(values, list) or len(values) != count:
            raise ValueError("Parameter entry count")
        if not all(_finite_number(v) for v in values):
            raise ValueError("Nonfinite parameter")
    if not _finite_number(data["intercept"]) or any(v <= 0 for v in normalizers):
        raise ValueError("Invalid intercept/normalizers")
    tables = data["tables"]
    dimers = {"".join(k) for k in itertools.product("ACGT", repeat=2)}
    if not isinstance(tables, dict) or set(tables) != set(_TABLES):
        raise ValueError("Utility table names")
    for table in tables.values():
        if not isinstance(table, dict) or set(table) != dimers:
            raise ValueError("Utility table dimers")
        if not all(_finite_number(v) for v in table.values()):
            raise ValueError("Nonfinite utility table")
    if data["array_sha256"] != {
        "coefficients": COEFFICIENT_ARRAY_SHA256,
        "intercept": INTERCEPT_ARRAY_SHA256,
    }:
        raise ValueError("Array identity mismatch")
    if (
        data["source_commit"] != SOURCE_COMMIT
        or data["license"] != "GPL-3.0-or-later; see NOTICE and COPYING"
    ):
        raise ValueError("Source/licence identity mismatch")
    canonical = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != PARAMETER_JSON_SHA256:
        raise ValueError("Canonical parameter hash mismatch")
    return PromoterParameters(
        tuple(coefficients),
        data["intercept"],
        tuple(normalizers),
        MappingProxyType({k: MappingProxyType(v) for k, v in tables.items()}),
        MappingProxyType(data["array_sha256"]),
        PARAMETER_JSON_SHA256,
        SOURCE_COMMIT,
        data["license"],
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate parameter key")
        result[key] = value
    return result


def load_parameters() -> PromoterParameters:
    """Load hash-checked package data; failures are setup errors, never scores."""
    try:
        raw = (
            files("regsite")
            .joinpath("data/promoter-parameters-1.json")
            .read_text(encoding="utf-8")
        )
        return _parse_parameters(json.loads(raw, object_pairs_hook=_unique_object))
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise ParameterError(
            f"Cannot load admitted Promoter parameters: {exc}"
        ) from exc


def _integer(value: object, field: str, minimum: int = 0) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise InputError("invalid_integer", field)
    if isinstance(value, float) and not math.isfinite(value):
        raise InputError("invalid_integer", field)
    integer = int(value)
    if value != integer or integer < minimum:
        raise InputError("invalid_integer", field)
    return integer


def normalize_dna(value: object, *, max_length: int) -> str:
    """Normalize ASCII DNA/RNA; error indices refer to the original raw text."""
    _integer(max_length, "max_length")
    if not isinstance(value, str):
        raise InputError("invalid_sequence", "sequence")
    bases = []
    alphabet = set()
    for index, character in enumerate(value):
        if character in _ASCII_SPACE:
            continue
        base = character.upper()
        if not character.isascii() or base not in "ACGTU":
            code = (
                "ambiguous_base"
                if character.isascii() and base in "RYSWKMBDHVN"
                else "invalid_character"
            )
            raise InputError(code, "sequence", index, character)
        alphabet.add(base)
        if "T" in alphabet and "U" in alphabet:
            raise InputError("mixed_dna_rna", "sequence", index, character)
        bases.append("T" if base == "U" else base)
    if not bases:
        raise InputError("empty_sequence", "sequence")
    if len(bases) > max_length:
        raise InputError("limit_exceeded", "sequence")
    return "".join(bases)


def _strand(strand: str) -> None:
    if strand not in ("+", "-"):
        raise InputError("invalid_strand", "strand")


def _dna(local: str) -> None:
    if not isinstance(local, str) or not local or local.strip("ACGT"):
        raise InputError("invalid_sequence", "sequence")


def orient(local: str, strand: str) -> str:
    """Return local '+' unchanged, or its reverse complement for local '-'."""
    _strand(strand)
    _dna(local)
    return local if strand == "+" else local.translate(_COMPLEMENT)[::-1]


def state_windows(t: int, d: int, s: int) -> dict[str, Interval]:
    """Return oriented model windows, including the one-base gap and extended10."""
    t, d, s = _integer(t, "t"), _integer(d, "d"), _integer(s, "s")
    if not 6 <= d <= 10 or not 15 <= s <= 20:
        raise InputError("invalid_state", "state")
    disc = t - d
    h10 = disc - 6
    spacer = h10 - s
    h35 = spacer - 6
    return {
        "UP": (h35 - 25, h35 - 1),
        "gap": (h35 - 1, h35),
        "hex35": (h35, spacer),
        "spacer": (spacer, h10),
        "extended10": (h10 - 3, h10 - 1),
        "hex10": (h10, disc),
        "discriminator": (disc, t),
        "itr": (t, t + 20),
    }


def eligible_states(length: int, t: int) -> tuple[tuple[int, int], ...]:
    """Complete coordinate states in discriminator-major historical visit order."""
    length, t = _integer(length, "length"), _integer(t, "t")
    return tuple(
        (d, s)
        for d in range(6, 11)
        for s in range(15, 21)
        if t >= d + s + 37 and t + 20 <= length
    )


def _interval(length: int, interval: Interval) -> Interval:
    length = _integer(length, "length")
    a, b = interval
    a, b = _integer(a, "interval.start"), _integer(b, "interval.end")
    if a > b or b > length:
        raise InputError("invalid_interval", "interval")
    return a, b


def oriented_to_local_interval(
    length: int, strand: str, interval: Interval
) -> Interval:
    """Map an oriented half-open interval to ascending local-reference bounds."""
    _strand(strand)
    a, b = _interval(length, interval)
    return (a, b) if strand == "+" else (length - b, length - a)


def oriented_to_local_base(length: int, strand: str, oriented_t: int) -> int:
    """Map a base index; a reverse source dictionary key is never a base."""
    _strand(strand)
    length, t = _integer(length, "length"), _integer(oriented_t, "tss")
    if t >= length:
        raise InputError("position_out_of_range", "tss")
    return t if strand == "+" else length - 1 - t


def legacy_source_key(length: int, strand: str, oriented_t: int) -> int:
    """Return diagnostic-only upstream key (L-t for reverse), not coordinates."""
    base = oriented_to_local_base(length, strand, oriented_t)
    return base if strand == "+" else base + 1


def check_projection(projection: Mapping[str, Any], length: int) -> dict[str, Any]:
    """Validate/resolve a supplied reference map, without inventing context."""
    length = _integer(length, "length", 1)
    allowed = {
        "contig",
        "origin",
        "contig_length",
        "sequence_strand",
        "topology",
        "origin_crossing",
    }
    if not isinstance(projection, Mapping) or set(projection) - allowed:
        raise InputError("invalid_projection", "projection")
    contig = projection.get("contig")
    strand = projection.get("sequence_strand", "+")
    topology = projection.get("topology")
    crossing = projection.get("origin_crossing", False)
    if (
        not isinstance(contig, str)
        or not 1 <= len(contig) <= 128
        or strand not in ("+", "-")
        or topology not in ("linear", "circular")
        or type(crossing) is not bool
    ):
        raise InputError("invalid_projection", "projection")
    try:
        size = _integer(projection.get("contig_length"), "projection.contig_length", 1)
        origin = _integer(projection.get("origin"), "projection.origin")
    except InputError as exc:
        raise InputError("invalid_projection", "projection") from exc
    if origin >= size or length > size:
        raise InputError("invalid_projection", "projection")
    crosses = origin + length > size if strand == "+" else origin - (length - 1) < 0
    if topology == "linear" and (crosses or crossing):
        raise InputError("invalid_projection", "projection")
    if crosses != crossing:
        code = "undeclared_origin_crossing" if crosses else "origin_crossing_mismatch"
        raise InputError(code, "projection.origin_crossing")
    return {
        "contig": contig,
        "origin": origin,
        "contig_length": size,
        "sequence_strand": strand,
        "topology": topology,
        "origin_crossing": crossing,
    }


def project_base(projection: Mapping[str, Any], local_base: int) -> int:
    """Map a nonnegative local point through a previously checked projection."""
    base = _integer(local_base, "local_base")
    direction = 1 if projection.get("sequence_strand", "+") == "+" else -1
    return (projection["origin"] + direction * base) % projection["contig_length"]


def project_interval(
    projection: Mapping[str, Any],
    site_strand: str,
    interval: Interval,
) -> tuple[str, list[Interval]]:
    """Map a local interval; runs are ascending individually, in transcript order.

    Projection must first pass check_projection against the complete local length.
    Empty intervals map to one empty run; model windows are always nonempty.
    """
    _strand(site_strand)
    size = projection["contig_length"]
    a, b = _interval(size, interval)
    sequence_strand = projection.get("sequence_strand", "+")
    strand = "+" if site_strand == sequence_strand else "-"
    start = (
        projection["origin"] + a
        if sequence_strand == "+"
        else projection["origin"] - b + 1
    )
    p = start % size
    q = p + b - a
    runs = [(p, q)] if q <= size else [(p, size), (0, q - size)]
    if strand == "-":
        runs.reverse()
    return strand, runs


@dataclass(frozen=True)
class Calibration:
    """Explicit score scale; host and warnings describe applicability only."""

    profile: str
    K: int
    beta: float
    native_host: str | None
    host: dict[str, Any] | None
    host_status: str
    warnings: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return resolved public calibration fields; warnings remain separate."""
        return {
            "profile": self.profile,
            "K": self.K,
            "beta": self.beta,
            "native_host": self.native_host,
            "host": None if self.host is None else dict(self.host),
            "host_status": self.host_status,
        }


def resolve_calibration(
    profile: str, host: Mapping[str, Any] | None = None
) -> Calibration:
    """Resolve one of two fixed profiles and exact NFC host registry matches.

    None represents omitted host here. The request parser rejects explicit null.
    """
    if profile not in ("ecoli_mg1655", "in_vitro"):
        raise InputError("invalid_calibration", "calibration")
    resolved_host = None
    if host is not None:
        if not isinstance(host, Mapping) or set(host) - {"name", "taxon_id"}:
            raise InputError("invalid_host", "host")
        name = host.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 200:
            raise InputError("invalid_host", "host.name")
        taxon = None
        if "taxon_id" in host:
            try:
                taxon = _integer(host["taxon_id"], "host.taxon_id", 1)
            except InputError as exc:
                raise InputError("invalid_host", "host.taxon_id") from exc
        resolved_host = {"name": unicodedata.normalize("NFC", name), "taxon_id": taxon}
    native = NATIVE_HOST if profile == "ecoli_mg1655" else None
    name = None if resolved_host is None else resolved_host["name"]
    warnings: tuple[dict[str, str], ...] = ()
    if profile == "ecoli_mg1655" and name == native:
        status = "calibration_native"
    elif profile == "in_vitro" and name in (None, "in vitro"):
        status = "in_vitro_reference"
    elif name is None:
        status = "unspecified"
        warnings = (
            {"code": "host_unspecified", "message": "No target host supplied."},
        )
    else:
        status = "extrapolated"
        warnings = (
            {
                "code": "host_extrapolation",
                "message": (
                    "Profile applied to a host without host-specific calibration "
                    "or native "
                    "validation; host metadata does not change the model."
                ),
            },
        )
    return Calibration(
        profile,
        42,
        1.636217004872062 if native else 0.81632623,
        native,
        resolved_host,
        status,
        warnings,
    )


def relative_score(log_score: float) -> tuple[float | None, str]:
    """Convert a finite log score, retaining null for overflow and underflow."""
    if not math.isfinite(log_score):
        raise ArithmeticError("nonfinite_arithmetic")
    if log_score > LOG_MAX:
        return None, "overflow"
    if log_score < LOG_MIN:
        return None, "underflow"
    return math.exp(log_score), "ok"


def _kmer_index(sequence: str) -> int:
    index = 0
    for base in sequence:
        index = index * 4 + "ACGT".index(base)
    return index


def _dimer_sum(sequence: str, table: Mapping[str, float]) -> float:
    return math.fsum(table[sequence[i : i + 2]] for i in range(0, len(sequence), 2))


@dataclass(frozen=True)
class StateScore:
    """Calibration-free terms and oriented windows/elements for one state."""

    discriminator_length: int
    spacer_length: int
    terms: Mapping[str, float]
    oriented_intervals: Mapping[str, Interval]
    elements: Mapping[str, str]

    def to_dict(
        self,
        length: int,
        strand: str,
        calibration: Calibration,
        *,
        elements: bool = True,
        projection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Serialize coordinates and scores; request-dependent IDs are caller-owned."""
        log_score = math.log(calibration.K) - calibration.beta * self.terms["total"]
        relative, status = relative_score(log_score)
        intervals = {
            k: oriented_to_local_interval(length, strand, v)
            for k, v in self.oriented_intervals.items()
        }
        result: dict[str, Any] = {
            "discriminator_length": self.discriminator_length,
            "spacer_length": self.spacer_length,
            "terms": dict(self.terms),
            "log_relative_transcription_score": log_score,
            "relative_transcription_score": relative,
            "score_status": status,
            "intervals": {k: list(v) for k, v in intervals.items()},
            "oriented_intervals": {
                k: list(v) for k, v in self.oriented_intervals.items()
            },
        }
        if elements:
            result["elements"] = dict(self.elements)
        if projection is not None:
            result["genomic_intervals"] = {
                k: [list(run) for run in project_interval(projection, strand, v)[1]]
                for k, v in intervals.items()
            }
        return result


def score_state(
    oriented: str, t: int, d: int, s: int, params: PromoterParameters
) -> StateScore:
    """Evaluate one complete state using basic float operations and accurate sums."""
    _dna(oriented)
    return _score_validated_state(oriented, t, d, s, params)


def _score_validated_state(
    oriented: str, t: int, d: int, s: int, params: PromoterParameters
) -> StateScore:
    """Score a state on nonempty uppercase ACGT DNA already checked by _dna.

    Only whole-sequence validation is omitted; state and context checks remain.
    """
    windows = state_windows(t, d, s)
    if windows["UP"][0] < 0 or windows["itr"][1] > len(oriented):
        raise InputError("insufficient_context", "state")
    elements = {
        name: oriented[a:b]
        for name, (a, b) in windows.items()
        if name not in ("gap", "extended10")
    }
    c, tables = params.coefficients, params.tables
    up, h35, spacer = elements["UP"], elements["hex35"], elements["spacer"]
    h10, disc, itr = elements["hex10"], elements["discriminator"], elements["itr"]
    d, s = len(disc), len(spacer)
    raw = (
        _dimer_sum(up[:12], tables["groove_access"]),
        _dimer_sum(up[12:], tables["groove_access"]),
        _dimer_sum(itr[:14], tables["DNA_DNA_hybrids"])
        - _dimer_sum(itr[:14], tables["RNA_DNA_hybrids"]),
        _dimer_sum(up + h35 + spacer[:14], tables["persistence"]) / 44,
    )
    numeric = tuple(raw[i] / params.normalizers[i] * c[339 + i] for i in range(4))
    terms = {
        "hex10": c[_kmer_index(h10[:3])] + c[64 + _kmer_index(h10[3:])],
        "hex35": c[128 + _kmer_index(h35[:3])] + c[192 + _kmer_index(h35[3:])],
        "discriminator": c[256 + _kmer_index(disc[:3])],
        "extended10": c[320 + _kmer_index(spacer[-3:-1])],
        "itr": numeric[2],
        "up": math.fsum((numeric[0], numeric[1], numeric[3])),
        "spacer": 0.1463 * s**2 - 4.9113 * s + 41.119,
        "intercept": params.intercept,
    }
    terms["total"] = math.fsum(terms.values())
    terms["binding"] = math.fsum(
        terms[k] for k in ("hex10", "hex35", "extended10", "up", "spacer")
    )
    terms["source_apparent"] = (terms["total"] + 2.80271176) / 0.81632623
    if not all(math.isfinite(v) for v in terms.values()):
        raise ArithmeticError("nonfinite_arithmetic")
    return StateScore(
        d,
        s,
        MappingProxyType(terms),
        MappingProxyType(windows),
        MappingProxyType(elements),
    )


@dataclass(frozen=True)
class SiteResult:
    """One attempted local site, with eligibility independent of score success."""

    strand: str
    local_base: int
    oriented_base: int
    length: int
    status: str
    reason: str | None
    state_count: int
    tie_count: int | None
    selected: StateScore | None
    states: tuple[StateScore, ...] | None
    calibration: Calibration

    def to_dict(
        self,
        *,
        elements: bool = True,
        projection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return contract-shaped fields except IDs and opt-in legacy diagnostics."""
        result: dict[str, Any] = {
            "strand": self.strand,
            "tss": {
                "forward_base": self.local_base,
                "oriented_base": self.oriented_base,
            },
            "genomic": None,
            "status": self.status,
            "reason": self.reason,
            "context": {
                "required_upstream": 67,
                "required_downstream": 19,
                "available_upstream": self.oriented_base,
                "available_downstream": self.length - 1 - self.oriented_base,
            },
            "state_count": self.state_count,
            "complete_state_set": self.state_count == 30,
            "attempted": True,
            "tie_count": self.tie_count,
            "selected": None
            if self.selected is None
            else self.selected.to_dict(
                self.length,
                self.strand,
                self.calibration,
                elements=elements,
                projection=projection,
            ),
        }
        if self.states is not None:
            result["states"] = [
                dict(
                    state.to_dict(
                        self.length,
                        self.strand,
                        self.calibration,
                        elements=False,
                        projection=projection,
                    ),
                    selected=state is self.selected,
                )
                for state in self.states
            ]
        if projection is not None:
            sequence_strand = projection.get("sequence_strand", "+")
            result["genomic"] = {
                "contig": projection["contig"],
                "base": project_base(projection, self.local_base),
                "strand": "+" if self.strand == sequence_strand else "-",
                "sequence_strand": sequence_strand,
            }
        return result


def score_site(
    local: str,
    strand: str,
    local_base: int,
    params: PromoterParameters,
    calibration: Calibration,
    *,
    keep_states: bool,
) -> SiteResult:
    """Score complete states, keeping the first strict minimum and exact tie count."""
    oriented = orient(local, strand)
    t = oriented_to_local_base(len(local), strand, local_base)
    candidates = eligible_states(len(local), t)
    selected = None
    states = []
    ties: int | None = None
    status = "no_candidate"
    reason: str | None = "insufficient_context"
    try:
        for d, s in candidates:
            state = _score_validated_state(oriented, t, d, s, params)
            # Validate log arithmetic even when the caller does not serialize states.
            relative_score(
                math.log(calibration.K) - calibration.beta * state.terms["total"]
            )
            if selected is None or state.terms["total"] < selected.terms["total"]:
                selected, ties = state, 1
            elif state.terms["total"] == selected.terms["total"]:
                assert ties is not None
                ties += 1
            if keep_states:
                states.append(state)
        if selected is not None:
            status, reason = "ok", None
    except ArithmeticError:
        status, reason = "failed", "nonfinite_arithmetic"
        selected, ties, states = None, None, []
    return SiteResult(
        strand,
        local_base,
        t,
        len(local),
        status,
        reason,
        len(candidates),
        ties,
        selected,
        tuple(states) if keep_states else None,
        calibration,
    )
