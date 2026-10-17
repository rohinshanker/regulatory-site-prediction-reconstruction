"""Outcome-independent stop-bounded queries and positive-only start evaluation."""

import statistics
from collections import Counter

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.native import COMPLEMENT

STARTS = {"ATG", "GTG", "TTG", "CTG"}
STOPS = {"TAA", "TAG", "TGA"}


def stop_query(sequence, stop, strand, cap=3000, flank=100):
    """Enumerate an in-frame stop-bounded universe without reading a true start.

    stop is the first translated base of the terminal stop, zero-based genomic.
    Input sequence is circular genomic DNA; output is already transcript-oriented.
    cap bounds upstream search, not distance around a hidden positive site.
    """
    if (
        not isinstance(sequence, str)
        or set(sequence) - set("ACGT")
        or type(stop) is not int
        or not 0 <= stop < len(sequence)
        or strand not in {"+", "-"}
        or type(cap) is not int
        or cap < 3
        or cap % 3
        or type(flank) is not int
        or flank < 0
        or cap + 2 * flank + 3 >= len(sequence)
    ):
        raise ValueError("Invalid circular stop-query reference or bounds")
    sign = 1 if strand == "+" else -1

    def bases(offset, length):
        value = "".join(
            sequence[(stop + sign * i) % len(sequence)]
            for i in range(offset, offset + length)
        )
        return value if strand == "+" else value.translate(COMPLEMENT)

    if bases(0, 3) not in STOPS:
        raise ValueError("Declared stop anchor is not an in-frame stop codon")
    upstream, found = cap, False
    for distance in range(3, cap + 1, 3):
        if bases(-distance, 3) in STOPS:
            upstream, found = distance - 3, True
            break
    context = bases(-upstream - flank, upstream + 2 * flank + 3)
    candidates = [
        flank + upstream + offset
        for offset in range(-upstream, 0, 3)
        if bases(offset, 3) in STARTS
    ]
    return {
        "sequence": context,
        "sequence_sha256": digest(context),
        "start_positions": candidates,
        "strand": "+",
        "genomic_strand": strand,
        "genomic_stop_first_zero_based": stop,
        "oriented_first_genomic_zero_based": (stop - sign * (upstream + flank))
        % len(sequence),
        "terminal_stop_position": upstream + flank,
        "upstream_search_nt": cap,
        "prior_stop_found": found,
        "flank_nt": flank,
        "candidate_universe": (
            "ATG/GTG/TTG/CTG in frame before supplied stop, after prior stop or cap"
        ),
        "context_boundary_evidence": (
            "assumed genomic flank; transcript boundaries unmeasured"
        ),
    }


def true_index(query, genomic_start, genome_length):
    """Project evaluator-only labels into an already frozen query, never recenter."""
    if type(genomic_start) is not int or not 0 <= genomic_start < genome_length:
        raise ValueError("Invalid private genomic label")
    sign = 1 if query["genomic_strand"] == "+" else -1
    return (
        sign * (genomic_start - query["oriented_first_genomic_zero_based"])
    ) % genome_length


def evaluate(queries, labels, predictions, tolerance=3):
    """Positive-only conditional ranking with conservative, explicit tie handling.

    Unlabelled queries never become negatives. Top1 requires every top-tied start
    to match; expected uniform-tie top1 and worst-tie reciprocal rank are separate.
    Incomplete candidate scoring gives zero top1/MRR in all-positive denominators.
    No precision/PR-AUC is valid without justified negatives.
    """
    universe = {row["id"]: row for row in queries}
    truth = {row["id"]: row for row in labels}
    inferred = {row["id"]: row for row in predictions}
    if (
        len(universe) != len(queries)
        or len(truth) != len(labels)
        or len(inferred) != len(predictions)
        or set(truth) - set(universe)
        or set(inferred) - set(universe)
        or any(not isinstance(key, str) or not key for key in universe)
    ):
        raise ValueError("Duplicate, unknown or invalid positional query identity")
    if type(tolerance) is not int or tolerance < 0:
        raise ValueError("Positional tolerance must be a nonnegative integer")
    totals = Counter()
    ranks, counts = [], []
    for identity, query in universe.items():
        candidates = query["start_positions"]
        if (
            not isinstance(candidates, list)
            or any(type(x) is not int or x < 0 for x in candidates)
            or len(candidates) != len(set(candidates))
        ):
            raise ValueError("Invalid independent candidate universe")
        output = inferred.get(identity, {}).get("candidates", [])
        positions = [row["start"] for row in output]
        if (
            len(positions) != len(set(positions))
            or set(positions) - set(candidates)
            or any(type(p) is not int for p in positions)
        ):
            raise ValueError("Predictions changed the observable candidate universe")
        scored = []
        for row in output:
            if row["status"] == "ok":
                if not finite_number(row["score"]):
                    raise ValueError("Successful positional score must be finite")
                scored.append(row)
            elif row["status"] not in {
                "failed",
                "unsupported",
                "no_candidate",
                "not_evaluated",
            }:
                raise ValueError("Unknown positional prediction status")
        label = truth.get(identity)
        if label is None or label["tier"] == "unlabelled":
            totals["unlabelled"] += 1
            continue
        if (
            label["tier"] != "positive"
            or not label["starts"]
            or any(type(x) is not int or x < 0 for x in label["starts"])
        ):
            raise ValueError("Only explicit positive labels are admitted")
        target = set(label["starts"])
        totals["positive"] += 1
        counts.append(len(candidates))
        totals["truth_in_universe"] += bool(target & set(candidates))
        totals["query_with_any_score"] += bool(scored)
        totals["all_candidates_scored"] += len(scored) == len(candidates) and bool(
            candidates
        )
        matched = [row for row in scored if row["start"] in target]
        totals["positive_scored"] += bool(matched)
        if not scored or len(scored) != len(candidates):
            ranks.append(0.0)
            continue
        top_score = max(row["score"] for row in scored)
        top = [row["start"] for row in scored if row["score"] == top_score]
        exact = sum(p in target for p in top)
        tolerant = sum(any(abs(p - t) <= tolerance for t in target) for p in top)
        totals["top1_exact"] += exact == len(top)
        totals["top1_tolerant"] += tolerant == len(top)
        totals["top1_uniform_tie_expected"] += exact / len(top)
        if matched:
            best_true = max(row["score"] for row in matched)
            worst_rank = (
                sum(row["score"] >= best_true for row in scored)
                - sum(row["score"] == best_true for row in matched)
                + 1
            )
            ranks.append(1 / worst_rank)
        else:
            ranks.append(0.0)
    n = totals["positive"]
    result = {
        "n_queries": len(queries),
        "n_positive": n,
        "n_unlabelled": totals["unlabelled"],
        "counts": dict(totals),
        "tolerance_nt": tolerance,
        "candidate_count_range": [min(counts), max(counts)] if counts else None,
        "mrr_worst_tie_all_positive": statistics.mean(ranks) if ranks else None,
        "precision": None,
        "pr_auc": None,
        "scope": (
            "conditional supplied-stop start selection; "
            "no genome-wide discovery or negative labels"
        ),
    }
    for metric in (
        "truth_in_universe",
        "query_with_any_score",
        "all_candidates_scored",
        "positive_scored",
        "top1_exact",
        "top1_tolerant",
        "top1_uniform_tie_expected",
    ):
        result[metric + "_fraction"] = totals[metric] / n if n else None
    return result
