"""Independent three-base geometry accounting for supplied RBS rosters.

This oracle neither discovers candidates nor evaluates scores or biological
gain/loss. Circular topology does not permit paths outside the supplied string.
"""

from benchmarks.recoding.edit_maps import build_map

MAX_CANDIDATES = 20000


def _paths(rows, mapping):
    """Validate a roster and retain each complete local and mapped codon path."""
    if not isinstance(rows, list) or len(rows) > MAX_CANDIDATES:
        raise ValueError("Candidate roster must be a list of at most 20000 rows")
    ids, coordinates = set(), set()
    paths = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "base", "strand"}:
            raise ValueError("Candidate requires exactly id, base and strand")
        name, base, strand = row["id"], row["base"], row["strand"]
        if not isinstance(name, str) or not name or len(name) > 128:
            raise ValueError("Candidate ID must contain 1 to 128 characters")
        if type(base) is not int or not 0 <= base < len(mapping):
            raise ValueError("Candidate base must be an integer inside the sequence")
        if strand not in ("+", "-"):
            raise ValueError("Candidate strand must be + or -")
        step = 1 if strand == "+" else -1
        bases = [base + step * offset for offset in range(3)]
        if not 0 <= bases[-1] < len(mapping):
            raise ValueError("All three codon bases must fit inside the sequence")
        coordinate = (base, strand)
        if name in ids or coordinate in coordinates:
            raise ValueError("Duplicate candidate ID or anchor/strand")
        ids.add(name)
        coordinates.add(coordinate)
        paths.append(
            {"id": name, "bases": bases, "mapped_bases": [mapping[b] for b in bases]}
        )
    return paths


def match_rbs_candidates(document, current, recoded):
    """Partition supplied candidates by exact, strand-preserving codon mapping.

    Args:
        document: A paired-edit-input-1 document validated through build_map.
        current: Ordered list of exactly {id, base, strand} current candidates.
        recoded: Independently supplied list with the same shape for recoded DNA.

    Returns:
        An rbs-codon-correspondence-1 dictionary retaining all paths and candidates.
        An absent same-strand anchor takes precedence over internal disruption.

    Raises:
        ValueError: If the edit document or either candidate roster is invalid.
    """
    mapping = build_map(document)
    current_paths = _paths(current, mapping["current_to_recoded"])
    recoded_paths = _paths(recoded, mapping["recoded_to_current"])
    lookup = {
        (row["base"], row["strand"]): path
        for row, path in zip(recoded, recoded_paths, strict=True)
    }
    pairs, unmatched_current, unmatched_recoded = [], [], []
    matched, interrupted = set(), set()
    for row, path in zip(current, current_paths, strict=True):
        anchor = path["mapped_bases"][0]
        after = lookup.get((anchor, row["strand"]))
        if anchor is None:
            reason = "deleted_coordinate"
        elif after is None:
            reason = "mapped_anchor_absent"
        elif path["mapped_bases"] != after["bases"]:
            reason = "interrupted_codon"
            interrupted.add(after["id"])
        else:
            pairs.append({"current_id": row["id"], "recoded_id": after["id"]})
            matched.add(after["id"])
            continue
        unmatched_current.append({"id": row["id"], "reason": reason})
    for row, path in zip(recoded, recoded_paths, strict=True):
        if row["id"] in matched:
            continue
        if row["id"] in interrupted:
            reason = "interrupted_codon"
        elif path["mapped_bases"][0] is None:
            reason = "inserted_coordinate"
        else:
            reason = "mapped_anchor_absent"
        unmatched_recoded.append({"id": row["id"], "reason": reason})
    return {
        "schema_version": "rbs-codon-correspondence-1",
        "pair_id": mapping["pair_id"],
        "current_count": len(current),
        "recoded_count": len(recoded),
        "matched_pairs": len(pairs),
        "pairs": pairs,
        "unmatched_current": unmatched_current,
        "unmatched_recoded": unmatched_recoded,
        "current_paths": current_paths,
        "recoded_paths": recoded_paths,
        "biological_gain_loss_evaluated": False,
    }
