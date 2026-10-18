"""Exact partial coordinate correspondence for explicitly supplied DNA edits.

No alignment or sequence optimization is performed. Equal-length replacements
declare positional correspondence; unequal replacements deliberately do not.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import cast

MAX_BASES = 10_000
MAX_EDITS = 10_000


class EditError(ValueError):
    """A pair cannot establish the declared exact coordinate correspondence."""


def _object(value: object, keys: set[str], field: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise EditError(f"{field}: expected exactly {sorted(keys)}")
    return value


def _name(value: object, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise EditError(f"{field}: expected 1..128 characters")
    return value


def _integer(value: object, low: int, high: int, field: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise EditError(f"{field}: expected an integer in [{low}, {high}]")
    return value


def _dna(value: object, field: str, *, empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or not (0 if empty else 1) <= len(value) <= MAX_BASES
        or value.strip("ACGT")
    ):
        raise EditError(f"{field}: expected bounded uppercase ACGT DNA")
    return value


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EditMap:
    """Validated immutable partial bijection in the declared forward frame."""

    pair_id: str
    current_id: str
    recoded_id: str
    topology: str
    current: str
    recoded: str
    edits_sha256: str
    current_to_recoded: tuple[int | None, ...]
    recoded_to_current: tuple[int | None, ...]
    current_declared_edited: tuple[bool, ...]

    def to_dict(self) -> dict:
        """Serialize the shared paired-edit-map-1 contract without hidden settings."""
        return {
            "schema_version": "paired-edit-map-1",
            "pair_id": self.pair_id,
            "topology": self.topology,
            "current_sha256": _digest(self.current),
            "recoded_sha256": _digest(self.recoded),
            "edits_sha256": self.edits_sha256,
            "current_to_recoded": list(self.current_to_recoded),
            "recoded_to_current": list(self.recoded_to_current),
            "current_declared_edited": list(self.current_declared_edited),
            "current_unmatched": [
                i for i, v in enumerate(self.current_to_recoded) if v is None
            ],
            "recoded_unmatched": [
                i for i, v in enumerate(self.recoded_to_current) if v is None
            ],
        }

    def map_base(self, side: str, base: int) -> int | None:
        """Map a base, preserving null for a deliberately unmatched coordinate."""
        mapping = self._mapping(side)
        return mapping[_integer(base, 0, len(mapping) - 1, "base")]

    def _mapping(self, side: str) -> tuple[int | None, ...]:
        if side not in ("current", "recoded"):
            raise EditError("side: expected current or recoded")
        return self.current_to_recoded if side == "current" else self.recoded_to_current

    def map_interval(self, side: str, start: int, end: int, strand: str) -> dict:
        """Map every interval base; distinguish missing bases, gaps and wrapping.

        Intervals are ascending half-open in their source frame. Circular ends
        may be unrolled by at most one traversal. Runs remain ascending but are
        listed along transcription; origin splits can still form a contiguous path.
        """
        mapping = self._mapping(side)
        if strand not in ("+", "-"):
            raise EditError("strand: expected + or -")
        circular = self.topology == "circular"
        length = len(mapping)
        start = _integer(start, 0, length - int(circular), "interval.start")
        end = _integer(
            end, start, start + length if circular else length, "interval.end"
        )
        indices = range(start, end) if strand == "+" else range(end - 1, start - 1, -1)
        source = [index % length for index in indices]
        target = [mapping[index] for index in source]
        step = 1 if strand == "+" else -1
        target_length = len(self.recoded if side == "current" else self.current)
        complete = all(value is not None for value in target)
        mapped = cast(list[int], target)  # Used only after complete is true below.
        contiguous = complete and all(
            b == ((a + step) % target_length if circular else a + step)
            for a, b in zip(mapped, mapped[1:], strict=False)
        )
        runs: list[list[int]] = []
        previous: int | None = None
        for value in target:
            if value is not None:
                if previous is not None and value == previous + step:
                    if step == 1:
                        runs[-1][1] = value + 1
                    else:
                        runs[-1][0] = value
                else:
                    runs.append([value, value + 1])
            previous = value
        return {
            "source_bases": source,
            "mapped_bases": target,
            "mapped_runs": runs,
            "unmatched_bases": target.count(None),
            "complete_base_mapping": complete,
            "contiguous_target_path": contiguous,
        }


def build_edit_map(document: object) -> EditMap:
    """Verify paired-edit-input-1 and construct its exact partial coordinate map.

    Edits are applied in the current forward frame. Distinct starts and explicit
    order make boundary insertions unambiguous. A no-change replacement remains
    declared edited even when its sequence happens to be identical.
    """
    value = _object(
        document,
        {"schema_version", "pair_id", "topology", "current", "recoded", "edits"},
        "pair",
    )
    if value["schema_version"] != "paired-edit-input-1":
        raise EditError("schema_version: expected paired-edit-input-1")
    pair_id = _name(value["pair_id"], "pair_id")
    topology = value["topology"]
    if topology not in ("linear", "circular"):
        raise EditError("topology: expected linear or circular")
    sequences: dict[str, str] = {}
    identifiers: dict[str, str] = {}
    for side in ("current", "recoded"):
        source = _object(value[side], {"id", "sequence"}, side)
        identifiers[side] = _name(source["id"], f"{side}.id")
        sequences[side] = _dna(source["sequence"], f"{side}.sequence")
    current, recoded = sequences["current"], sequences["recoded"]
    edits = value["edits"]
    if not isinstance(edits, list) or len(edits) > MAX_EDITS:
        raise EditError("edits: expected a bounded list")
    chunks: list[str] = []
    # Each aligned segment is (old start, old end, target start). An unequal
    # replacement contributes no aligned segment, so no guessed alignment enters.
    aligned: list[tuple[int, int, int]] = []
    edited = [False] * len(current)
    current_cursor = recoded_cursor = 0
    last_start = -1
    seen_ids: set[str] = set()
    for index, raw in enumerate(edits):
        field = f"edits[{index}]"
        edit = _object(raw, {"id", "start", "end", "replacement"}, field)
        name = _name(edit["id"], field + ".id")
        if name in seen_ids:
            raise EditError(f"{field}.id: duplicate edit identity")
        seen_ids.add(name)
        start = _integer(edit["start"], 0, len(current), field + ".start")
        end = _integer(edit["end"], start, len(current), field + ".end")
        replacement = _dna(edit["replacement"], field + ".replacement", empty=True)
        if start < current_cursor or start <= last_start:
            raise EditError(
                f"{field}: edits must be sorted, distinct and nonoverlapping"
            )
        if start == end and not replacement:
            raise EditError(f"{field}: empty-to-empty edit")
        unchanged = current[current_cursor:start]
        chunks.extend((unchanged, replacement))
        aligned.append((current_cursor, start, recoded_cursor))
        recoded_cursor += len(unchanged)
        edited[start:end] = [True] * (end - start)
        if end - start == len(replacement):
            aligned.append((start, end, recoded_cursor))
        recoded_cursor += len(replacement)
        current_cursor, last_start = end, start
        if recoded_cursor > MAX_BASES:
            raise EditError("edits: reconstructed sequence exceeds maximum length")
    chunks.append(current[current_cursor:])
    aligned.append((current_cursor, len(current), recoded_cursor))
    if "".join(chunks) != recoded:
        raise EditError("edits: do not reproduce the exact supplied recoded sequence")
    forward: list[int | None] = [None] * len(current)
    reverse: list[int | None] = [None] * len(recoded)
    for first, stop, destination in aligned:
        forward[first:stop] = range(destination, destination + stop - first)
        reverse[destination : destination + stop - first] = range(first, stop)
    edits_bytes = json.dumps(
        edits, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return EditMap(
        pair_id,
        identifiers["current"],
        identifiers["recoded"],
        topology,
        current,
        recoded,
        hashlib.sha256(edits_bytes).hexdigest(),
        tuple(forward),
        tuple(reverse),
        tuple(edited),
    )
