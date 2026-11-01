"""Frozen input-only uncertainty groups for projected positive TSS labels.

Groups are connected components of a fixed graph over label and query nodes,
built only from the pinned envelope, its regenerated query document and its
regenerated label projection. No score, read count or outcome is consulted.
Coordinates are zero-based half-open.
"""

import argparse
import bisect
import json
import sys
from pathlib import Path

from benchmarks.promoter import native_inputs as inputs
from benchmarks.promoter.native_metrics import (
    GROUP_SCHEMA,
    MAX_LABEL_BYTES,
    MAX_QUERIES,
)
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.native import COMPLEMENT

CONTEXT_UPSTREAM_NT = inputs.UPSTREAM_NT
CONTEXT_DOWNSTREAM_NT = inputs.DOWNSTREAM_NT
CONTEXT_NT = CONTEXT_UPSTREAM_NT + 1 + CONTEXT_DOWNSTREAM_NT
MAX_LABEL_DISTANCE_NT = 86
KMER_NT = 15
# Jaccard |A & B| / |A | B| >= 1/2, in exact integers: 3 |A & B| >= |A| + |B|.
JACCARD_NUMERATOR, JACCARD_DENOMINATOR = 1, 2
MAX_GROUP_LABELS = 20_000
MAX_PAIRS_PER_RULE = 1_000_000
MAX_PAIR_OPERATIONS = 2_000_000
RULES = (
    "label_query_attachment",
    "query_interval_overlap_or_touch",
    "label_locus_tag",
    "label_distance",
    "label_context_kmer",
)


def tool_sha256():
    """Identity of this exact grouping implementation."""
    return digest(Path(__file__).read_bytes())


def group_settings():
    """Fixed grouping rule; nothing here is tunable from the command line."""
    return {
        "nodes": "projected labels and selected queries",
        "rules": {
            "label_query_attachment": "each in-window label joins its query",
            "query_interval_overlap_or_touch": (
                "padded genomic segments overlap or touch on one replicon, "
                "either strand; circular segments ending at L touch those at 0"
            ),
            "label_locus_tag": (
                "exact nonempty source_locus_tag shared on one replicon; "
                "no alias inference"
            ),
            "label_distance": (
                f"|a - b| <= {MAX_LABEL_DISTANCE_NT} nt on one replicon, either "
                "strand; minimum circular distance on circular replicons"
            ),
            "label_context_kmer": (
                "Jaccard of distinct canonical k-mer sets >= numerator/denominator; "
                "canonical k-mer is min(kmer, reverse complement)"
            ),
        },
        "context_upstream_nt": CONTEXT_UPSTREAM_NT,
        "context_downstream_nt": CONTEXT_DOWNSTREAM_NT,
        "context_policy": (
            "transcript-oriented; linear clips at ends; circular wraps the "
            "origin at most once without repeating a base, shortening upstream "
            "first; fewer than k bases is unavailable"
        ),
        "max_label_distance_nt": MAX_LABEL_DISTANCE_NT,
        "kmer_nt": KMER_NT,
        "jaccard_min": {
            "numerator": JACCARD_NUMERATOR,
            "denominator": JACCARD_DENOMINATOR,
        },
        "component_id": "lexicographically smallest member label_id",
        "limits": {
            "max_labels": MAX_GROUP_LABELS,
            "max_queries": MAX_QUERIES,
            "max_pairs_per_rule": MAX_PAIRS_PER_RULE,
            "max_pair_operations": MAX_PAIR_OPERATIONS,
        },
    }


def label_context(sequence, topology, strand, point):
    """Oriented 67+1+19 context of a TSS as (dna, status, limit_reason).

    Reuses the query builder's padding for a one-base tile, so linear ends clip
    and circular padding never repeats a base. Status is `complete`, `clipped`
    (at least k bases) or `unavailable` (fewer than k bases).
    """
    length = len(sequence)
    up, down = inputs.padding(length, topology, strand, point, point + 1)
    start, end = (
        (point - up, point + 1 + down)
        if strand == "+"
        else (point - down, point + 1 + up)
    )
    dna = inputs.oriented_sequence(
        sequence, strand, inputs.segments(length, strand, start, end)
    )
    if len(dna) == CONTEXT_NT:
        return dna, "complete", None
    reason = "linear_edge" if topology == "linear" else "circular_no_repeat_limit"
    return dna, "clipped" if len(dna) >= KMER_NT else "unavailable", reason


def canonical_kmers(dna):
    """Distinct k-mers, each canonicalized as min(kmer, reverse complement)."""
    result = set()
    for i in range(len(dna) - KMER_NT + 1):
        kmer = dna[i : i + KMER_NT]
        result.add(min(kmer, kmer.translate(COMPLEMENT)[::-1]))
    return result


def jaccard_connects(shared, size_a, size_b):
    """Exact integer test of shared / (a + b - shared) >= numerator/denominator."""
    union = size_a + size_b - shared
    return JACCARD_DENOMINATOR * shared >= JACCARD_NUMERATOR * union


def _add_pair(pairs, a, b, rule):
    if a != b:
        pairs.add((a, b) if a < b else (b, a))
        if len(pairs) > MAX_PAIRS_PER_RULE:
            raise ValueError(f"{rule} edges exceed {MAX_PAIRS_PER_RULE}")


def _check_operations(buckets, rule):
    """Fail before allocating pairs when bucket pair work exceeds the cap."""
    total = sum(len(bucket) * (len(bucket) - 1) // 2 for bucket in buckets)
    if total > MAX_PAIR_OPERATIONS:
        raise ValueError(f"{rule} pair operations exceed {MAX_PAIR_OPERATIONS}")


def query_interval_pairs(queries, genomes):
    """Query index pairs whose padded genomic segments overlap or touch."""
    pairs, by_genome = set(), {}
    for index, query in enumerate(queries):
        for segment in query["segments"]:
            lower, upper = segment["genomic"]
            by_genome.setdefault(query["genome_id"], []).append((lower, upper, index))
    for genome_id, spans in by_genome.items():
        spans.sort()
        for i, (_, upper, a) in enumerate(spans):
            for j in range(i + 1, len(spans)):
                lower, _, b = spans[j]
                if lower > upper:
                    break
                _add_pair(pairs, a, b, RULES[1])
        genome = genomes[genome_id]
        if genome["topology"] == "circular":
            length = len(genome["sequence"])
            ends = [a for _, upper, a in spans if upper == length]
            starts = [b for lower, _, b in spans if lower == 0]
            for a in ends:
                for b in starts:
                    _add_pair(pairs, a, b, RULES[1])
    return pairs


def label_distance_pairs(labels, genomes):
    """Label index pairs within the fixed distance on one replicon."""
    pairs, by_genome = set(), {}
    for index, label in enumerate(labels):
        by_genome.setdefault(label["genome_id"], []).append(
            (label["tss_zero_based"], index)
        )
    for genome_id, points in by_genome.items():
        points.sort()
        values = [point for point, _ in points]
        genome = genomes[genome_id]
        length, circular = len(genome["sequence"]), genome["topology"] == "circular"
        for i, (point, a) in enumerate(points):
            last = bisect.bisect_right(values, point + MAX_LABEL_DISTANCE_NT)
            for _, b in points[i + 1 : last]:
                _add_pair(pairs, a, b, RULES[3])
            if circular:
                first = bisect.bisect_left(
                    values, point + length - MAX_LABEL_DISTANCE_NT
                )
                for _, b in points[max(first, i + 1) :]:
                    _add_pair(pairs, a, b, RULES[3])
    return pairs


def locus_tags(label):
    """Exact nonempty source locus tags of a label's preserved source rows."""
    return {
        row.get("source_locus_tag")
        for row in label["source_rows"]
        if isinstance(row.get("source_locus_tag"), str) and row["source_locus_tag"]
    }


def locus_tag_pairs(labels):
    """Label index pairs sharing an exact nonempty source locus tag."""
    buckets = {}
    for index, label in enumerate(labels):
        for tag in sorted(locus_tags(label)):
            buckets.setdefault((label["genome_id"], tag), []).append(index)
    _check_operations(buckets.values(), RULES[2])
    pairs = set()
    for bucket in buckets.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                _add_pair(pairs, a, b, RULES[2])
    return pairs


def kmer_pairs(kmer_sets):
    """Label index pairs whose canonical k-mer sets meet the Jaccard threshold.

    kmer_sets maps label index to a nonempty set. An inverted index counts exact
    intersections only for pairs sharing at least one k-mer; total posting-pair
    work is capped before the counter is allocated.
    """
    postings = {}
    for index in sorted(kmer_sets):
        for kmer in kmer_sets[index]:
            postings.setdefault(kmer, []).append(index)
    _check_operations(postings.values(), RULES[4])
    shared = {}
    for bucket in postings.values():
        for i, a in enumerate(bucket):
            for b in bucket[i + 1 :]:
                shared[(a, b)] = shared.get((a, b), 0) + 1
    pairs = set()
    for (a, b), count in shared.items():
        if jaccard_connects(count, len(kmer_sets[a]), len(kmer_sets[b])):
            _add_pair(pairs, a, b, RULES[4])
    return pairs


class UnionFind:
    """Disjoint sets with path halving and union by size."""

    def __init__(self, size):
        self.parent = list(range(size))
        self.size = [1] * size

    def find(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            if self.size[a] < self.size[b]:
                a, b = b, a
            self.parent[b] = a
            self.size[a] += self.size[b]


def group_labels(genomes, queries, labels):
    """Return ({label_id: component id}, aggregate counts) for the fixed graph.

    Nodes 0..n-1 are labels and n.. are queries. A component's identity is its
    lexicographically smallest label ID; label-free components are counted but
    produce no group. Results are independent of input list order.
    """
    if len(labels) > MAX_GROUP_LABELS or len(queries) > MAX_QUERIES:
        raise ValueError(
            f"Grouping needs at most {MAX_GROUP_LABELS} labels and "
            f"{MAX_QUERIES} queries"
        )
    labels = sorted(labels, key=lambda label: label["label_id"])
    queries = sorted(queries, key=lambda query: query["query_id"])
    n_labels = len(labels)
    query_node = {q["query_id"]: n_labels + i for i, q in enumerate(queries)}
    attachments = {
        (i, query_node[label["query_id"]])
        for i, label in enumerate(labels)
        if label["query_id"] is not None
    }
    contexts, kmer_sets, reasons = {}, {}, {}
    for i, label in enumerate(labels):
        genome = genomes[label["genome_id"]]
        dna, status, reason = label_context(
            genome["sequence"],
            genome["topology"],
            label["strand"],
            label["tss_zero_based"],
        )
        contexts[status] = contexts.get(status, 0) + 1
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        if status != "unavailable":
            kmer_sets[i] = canonical_kmers(dna)
    query_edges = query_interval_pairs(queries, genomes)
    edges = {
        RULES[0]: attachments,
        RULES[1]: {(n_labels + a, n_labels + b) for a, b in query_edges},
        RULES[2]: locus_tag_pairs(labels),
        RULES[3]: label_distance_pairs(labels, genomes),
        RULES[4]: kmer_pairs(kmer_sets),
    }
    forest = UnionFind(n_labels + len(queries))
    for rule in RULES:
        for a, b in edges[rule]:
            forest.union(a, b)
    members = {}
    for node in range(n_labels + len(queries)):
        members.setdefault(forest.find(node), []).append(node)
    groups, sizes = {}, {}
    unlabelled_components = unlabelled_queries = 0
    for nodes in members.values():
        label_nodes = [node for node in nodes if node < n_labels]
        if not label_nodes:
            unlabelled_components += 1
            unlabelled_queries += len(nodes)
            continue
        # Labels are sorted by ID, so the lowest label node holds the minimum ID.
        component = labels[label_nodes[0]]["label_id"]
        for node in label_nodes:
            groups[labels[node]["label_id"]] = component
        sizes[len(label_nodes)] = sizes.get(len(label_nodes), 0) + 1
    in_window = sum(label["query_id"] is not None for label in labels)
    counts = {
        "n_labels": n_labels,
        "n_labels_in_window": in_window,
        "n_labels_out_of_window": n_labels - in_window,
        "n_labels_with_locus_tag": sum(bool(locus_tags(label)) for label in labels),
        "n_queries": len(queries),
        "n_queries_with_labels": len({b for _, b in attachments}),
        "edges": {rule: len(edges[rule]) for rule in RULES},
        "context_status": {
            status: contexts.get(status, 0)
            for status in ("complete", "clipped", "unavailable")
        },
        "context_limit_reason": {
            reason: reasons.get(reason, 0)
            for reason in ("linear_edge", "circular_no_repeat_limit")
        },
        "n_groups": sum(sizes.values()),
        "group_size_counts": [[size, sizes[size]] for size in sorted(sizes)],
        "max_group_size": max(sizes, default=0),
        "n_unlabelled_query_components": unlabelled_components,
        "n_queries_in_unlabelled_components": unlabelled_queries,
    }
    return dict(sorted(groups.items())), counts


def build_groups(envelope, source_sha256, query_document, label_document):
    """Group labels after requiring exact regeneration of queries and labels."""
    labels = label_document.get("labels")
    if not isinstance(labels, list) or len(labels) > MAX_GROUP_LABELS:
        raise ValueError(f"Labels must be a list of at most {MAX_GROUP_LABELS}")
    if inputs.project_labels(envelope, source_sha256, query_document) != (
        label_document
    ):
        raise ValueError("Label document is not reproduced by this envelope/queries")
    groups, counts = group_labels(
        envelope["genomes"], query_document["queries"], labels
    )
    settings = group_settings()
    return {
        "schema_version": GROUP_SCHEMA,
        "scope": (
            "input-only uncertainty groups frozen before scoring; a fixed "
            "near-duplicate screen, not exhaustive homology detection"
        ),
        "labels_document_sha256": inputs.document_sha256(label_document),
        "inputs": {
            "envelope_file_sha256": source_sha256,
            "query_document_sha256": inputs.document_sha256(query_document),
            "labels_document_sha256": inputs.document_sha256(label_document),
        },
        "settings": settings,
        "settings_sha256": inputs.document_sha256(settings),
        "tool_sha256": tool_sha256(),
        "dependency_tool_sha256": {"native_inputs": inputs.tool_sha256()},
        "counts": counts,
        "groups": groups,
    }


def _canonical_document(path, limit):
    raw = inputs.read_bounded(path, limit)
    document = inputs.strict_json(raw)
    if inputs.canonical_bytes(document) != raw:
        raise ValueError(f"Document is not canonical tool output: {path}")
    return document


def main(argv=None):
    """Write a new 0600 group document; nonzero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("envelope", "queries", "labels", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        envelope = inputs.load_envelope(
            inputs.read_bounded(args.envelope, inputs.MAX_ENVELOPE_BYTES),
            args.source_sha256,
        )
        queries = _canonical_document(args.queries, inputs.MAX_QUERY_DOCUMENT_BYTES)
        labels = _canonical_document(args.labels, MAX_LABEL_BYTES)
        result = build_groups(envelope, args.source_sha256, queries, labels)
        inputs.write_exclusive(args.output, result, 0o600)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "n_groups": result["counts"]["n_groups"],
                "output_sha256": inputs.document_sha256(result),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
