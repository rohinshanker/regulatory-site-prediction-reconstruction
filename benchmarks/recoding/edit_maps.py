"""Small independent per-base oracle for synthetic recoding comparisons.

This benchmark does not align sequences, predict regulatory sites or import any
runtime engine. Its explicit edit convention is current-recoded-validation.md.
"""

import hashlib
import json
import sys

MAX_BASES = 10000


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Coordinate must be an integer within its declared bounds")
    return value


def _dna(value, empty=False):
    if (
        not isinstance(value, str)
        or len(value) > MAX_BASES
        or (not value and not empty)
        or set(value) - set("ACGT")
    ):
        raise ValueError("Expected bounded uppercase ACGT DNA")
    return value


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Object keys do not match the explicit edit contract")


def _name(value):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError("Expected a nonempty identity of at most 128 characters")


def digest(value):
    """SHA256 of exact UTF-8 text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_map(document):
    """Validate both sequences and return an invertible partial base map.

    Equal-length replacement bases correspond by declared position. Unequal
    replacement bases have no inferred correspondence on either side.
    """
    _keys(
        document,
        ("schema_version", "pair_id", "topology", "current", "recoded", "edits"),
    )
    if document["schema_version"] != "paired-edit-input-1":
        raise ValueError("Unsupported paired input schema")
    _name(document["pair_id"])
    if document["topology"] not in ("linear", "circular"):
        raise ValueError("Topology must be linear or circular")
    for side in ("current", "recoded"):
        _keys(document[side], ("id", "sequence"))
        _name(document[side]["id"])
        _dna(document[side]["sequence"])
    current = document["current"]["sequence"]
    recoded = document["recoded"]["sequence"]
    edits = document["edits"]
    if not isinstance(edits, list) or len(edits) > MAX_BASES:
        raise ValueError("Edits must be a bounded explicit list")
    previous_end, previous_start = 0, -1
    seen = set()
    assembled = []
    forward = [None] * len(current)
    reverse = []
    edited = [False] * len(current)
    offset = 0
    for edit in edits:
        _keys(edit, ("id", "start", "end", "replacement"))
        _name(edit["id"])
        if edit["id"] in seen:
            raise ValueError("Duplicate edit identity")
        seen.add(edit["id"])
        start = _integer(edit["start"], 0, len(current))
        end = _integer(edit["end"], start, len(current))
        replacement = _dna(edit["replacement"], empty=True)
        if start < previous_end or start <= previous_start:
            raise ValueError("Edits overlap, share a start, or are not sorted")
        if start == end and not replacement:
            raise ValueError("An empty-to-empty edit has no declared operation")
        unchanged = current[previous_end:start]
        assembled.extend((unchanged, replacement))
        for old in range(previous_end, start):
            forward[old] = offset
            reverse.append(old)
            offset += 1
        for old in range(start, end):
            edited[old] = True
        if end - start == len(replacement):
            for old in range(start, end):
                forward[old] = offset
                reverse.append(old)
                offset += 1
        else:
            reverse.extend([None] * len(replacement))
            offset += len(replacement)
        previous_start, previous_end = start, end
    assembled.append(current[previous_end:])
    for old in range(previous_end, len(current)):
        forward[old] = offset
        reverse.append(old)
        offset += 1
    if "".join(assembled) != recoded:
        raise ValueError(
            "Explicit edits do not reproduce the supplied recoded sequence"
        )
    edits_bytes = json.dumps(
        edits, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return {
        "schema_version": "paired-edit-map-1",
        "pair_id": document["pair_id"],
        "topology": document["topology"],
        "current_sha256": digest(current),
        "recoded_sha256": digest(recoded),
        "edits_sha256": hashlib.sha256(edits_bytes).hexdigest(),
        "current_to_recoded": forward,
        "recoded_to_current": reverse,
        "current_declared_edited": edited,
        "current_unmatched": [i for i, other in enumerate(forward) if other is None],
        "recoded_unmatched": [i for i, other in enumerate(reverse) if other is None],
    }


def map_interval(mapping, side, start, end, strand):
    """Enumerate a half-open interval then retain nulls and ordered mapped runs.

    Circular ends may be unrolled, with at most one complete traversal. Runs are
    ascending intervals in transcription order, split at nulls, indels or origins.
    """
    if side not in ("current", "recoded") or strand not in ("+", "-"):
        raise ValueError("Explicit side and strand are required")
    key = "current_to_recoded" if side == "current" else "recoded_to_current"
    inverse = "recoded_to_current" if side == "current" else "current_to_recoded"
    source, target = mapping[key], mapping[inverse]
    length = len(source)
    circular = mapping["topology"] == "circular"
    start = _integer(start, 0, length - 1 if circular else length)
    end = _integer(end, start, start + length if circular else length)
    points = [i % length for i in range(start, end)]
    if strand == "-":
        points.reverse()
    mapped = [source[i] for i in points]
    step = 1 if strand == "+" else -1
    runs = []
    run = []
    previous = None
    contiguous = True
    for point in mapped:
        if point is None:
            contiguous = False
        if previous is not None and point is not None:
            adjacent = point == previous + step
            wraps = circular and point == (previous + step) % len(target)
            contiguous = contiguous and (adjacent or wraps)
        else:
            adjacent = False
        if run and (point is None or not adjacent):
            runs.append([min(run), max(run) + 1])
            run = []
        if point is not None:
            run.append(point)
        previous = point
    if run:
        runs.append([min(run), max(run) + 1])
    return {
        "source_bases": points,
        "mapped_bases": mapped,
        "mapped_runs": runs,
        "unmatched_bases": sum(point is None for point in mapped),
        "complete_base_mapping": all(point is not None for point in mapped),
        "contiguous_target_path": contiguous,
    }


def project_base(projection, local_base, local_strand, sequence_length):
    """Independently compose a local base and strand with an explicit projection."""
    _keys(
        projection,
        (
            "contig",
            "contig_length",
            "origin",
            "sequence_strand",
            "topology",
            "origin_crossing",
        ),
    )
    _name(projection["contig"])
    size = _integer(projection["contig_length"], 1, 10**9)
    _integer(sequence_length, 1, size)
    origin = _integer(projection["origin"], 0, size - 1)
    _integer(local_base, 0, sequence_length - 1)
    if projection["sequence_strand"] not in ("+", "-") or local_strand not in (
        "+",
        "-",
    ):
        raise ValueError("Invalid projection/site strand")
    if projection["topology"] not in ("linear", "circular"):
        raise ValueError("Invalid projection topology")
    direction = 1 if projection["sequence_strand"] == "+" else -1
    last = origin + direction * (sequence_length - 1)
    crossing = not 0 <= last < size
    if (
        type(projection["origin_crossing"]) is not bool
        or projection["origin_crossing"] != crossing
    ):
        raise ValueError("Projection crossing declaration disagrees")
    if crossing and projection["topology"] == "linear":
        raise ValueError("Linear projection leaves the contig")
    return {
        "contig": projection["contig"],
        "base": (origin + direction * local_base) % size,
        "strand": "+" if local_strand == projection["sequence_strand"] else "-",
    }


def _identity(value):
    _keys(
        value,
        ("model_sha256", "settings_sha256", "backend_sha256", "calibration_sha256"),
    )
    for item in value.values():
        if (
            not isinstance(item, str)
            or len(item) != 64
            or set(item) - set("0123456789abcdef")
        ):
            raise ValueError(
                "Comparison identities require complete lowercase SHA256 values"
            )


def _candidates(rows, length):
    if not isinstance(rows, list) or len(rows) > 2 * MAX_BASES:
        raise ValueError("Candidate roster must be a bounded list")
    ids, coordinates = set(), set()
    for row in rows:
        _keys(row, ("id", "base", "strand", "status", "score"))
        _name(row["id"])
        _integer(row["base"], 0, length - 1)
        if row["strand"] not in ("+", "-"):
            raise ValueError("Candidate strand is required")
        coordinate = (row["base"], row["strand"])
        if row["id"] in ids or coordinate in coordinates:
            raise ValueError("Duplicate candidate ID or anchor/strand")
        ids.add(row["id"])
        coordinates.add(coordinate)
        status, score = row["status"], row["score"]
        if status not in ("ok", "failed", "unsupported", "not_run", "no_candidate"):
            raise ValueError("Unknown candidate status")
        if status == "ok":
            if (
                type(score) not in (int, float)
                or not -sys.float_info.max <= score <= sys.float_info.max
            ):
                raise ValueError("Successful candidate needs a finite scalar score")
        elif score is not None:
            raise ValueError("Unsuccessful candidate must retain a null score")


def pair_candidates(mapping, current, recoded, current_identity, recoded_identity):
    """Pair supplied synthetic rosters; never infer biological gained/lost sites.

    Mapping must be the in-memory result of build_map. Identity hashes cover the
    model/parameters, settings, backend and calibration, separately from inputs.
    """
    for identity in (current_identity, recoded_identity):
        _identity(identity)
    forward, reverse = mapping["current_to_recoded"], mapping["recoded_to_current"]
    _candidates(current, len(forward))
    _candidates(recoded, len(reverse))
    compatible = current_identity == recoded_identity
    lookup = {(row["base"], row["strand"]): row for row in recoded}
    matched = set()
    result = []
    for before in current:
        target = forward[before["base"]]
        after = lookup.get((target, before["strand"]))
        entry = {
            "current_id": before["id"],
            "recoded_id": None,
            "status": "unmatched_current",
            "reason": "deleted_coordinate"
            if target is None
            else "mapped_anchor_absent",
            "delta": None,
        }
        if after is not None:
            matched.add(after["id"])
            entry.update(recoded_id=after["id"], status="paired", reason=None)
            if not compatible:
                entry.update(
                    status="incomparable", reason="model_settings_identity_mismatch"
                )
            elif before["status"] != "ok" or after["status"] != "ok":
                entry.update(status="incomplete", reason="unsuccessful_candidate")
            else:
                delta = after["score"] - before["score"]
                if -sys.float_info.max <= delta <= sys.float_info.max:
                    entry["delta"] = delta
                else:
                    entry.update(status="incomplete", reason="nonfinite_delta")
        entry["current_status"] = before["status"]
        entry["recoded_status"] = None if after is None else after["status"]
        result.append(entry)
    for after in recoded:
        if after["id"] not in matched:
            result.append(
                {
                    "current_id": None,
                    "recoded_id": after["id"],
                    "status": "unmatched_recoded",
                    "reason": "inserted_coordinate"
                    if reverse[after["base"]] is None
                    else "mapped_anchor_absent",
                    "delta": None,
                    "current_status": None,
                    "recoded_status": after["status"],
                }
            )
    return {
        "schema_version": "paired-prediction-audit-1",
        "pair_id": mapping["pair_id"],
        "current_identity": current_identity,
        "recoded_identity": recoded_identity,
        "current_count": len(current),
        "recoded_count": len(recoded),
        "matched_pairs": len(matched),
        "unmatched_current": len(current) - len(matched),
        "unmatched_recoded": len(recoded) - len(matched),
        "comparable_successful_pairs": sum(row["status"] == "paired" for row in result),
        "results": result,
        "biological_gain_loss_evaluated": False,
    }
