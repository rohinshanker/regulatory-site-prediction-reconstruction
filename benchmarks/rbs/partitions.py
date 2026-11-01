"""Outcome-blind native homology/context partitions with explicit component hashes."""

import argparse
import gzip
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.karlsen import annotation_index, genomic_context
from benchmarks.rbs.metrics import edit_distance, finite_number
from benchmarks.rbs.native import checked_source, gff_features

SEED = "native-wave2-20261017-v1"


def normalized_edit_similarity(left, right):
    """Unit-cost edit similarity used by the existing benchmark overlap contract."""
    if not left or not right:
        raise ValueError("Sequence contexts must be nonempty")
    return 1 - edit_distance(left, right) / max(len(left), len(right))


def homology_edges(text):
    """Validate the declared MMseqs output and retain qualifying undirected edges."""
    edges = set()
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) != 7 or not fields[0] or not fields[1]:
            raise ValueError("Expected seven nonempty MMseqs result fields")
        identity, qcov, tcov, evalue, length = map(float, fields[2:])
        if (
            not all(finite_number(x) for x in (identity, qcov, tcov, evalue, length))
            or not 0 <= identity <= 100
            or not 0 <= qcov <= 1
            or not 0 <= tcov <= 1
            or evalue < 0
            or length < 1
        ):
            raise ValueError("Invalid MMseqs alignment values")
        if (
            fields[0] != fields[1]
            and identity >= 30
            and min(qcov, tcov) >= 0.8
            and evalue <= 1e-5
        ):
            edges.add(tuple(sorted(fields[:2])))
    return sorted(edges)


def sequence_edges(sequences, similarity=normalized_edit_similarity, threshold=0.85):
    """Enumerate every near-identical context pair without using measured outcomes."""
    if not finite_number(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Sequence similarity threshold must be within [0, 1]")
    return [
        (a, b)
        for a, b in combinations(sorted(sequences), 2)
        if similarity(sequences[a], sequences[b]) >= threshold
    ]


def components(nodes, edges):
    """Connected components keep every declared related pair on one side of a split."""
    nodes = list(nodes)
    if len(set(nodes)) != len(nodes) or any(
        not isinstance(node, str) or not node for node in nodes
    ):
        raise ValueError("Partition nodes must be unique nonempty identifiers")
    parents = {node: node for node in nodes}

    def root(node):
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    for first, second in edges:
        if first not in parents or second not in parents:
            raise ValueError("Edge endpoint absent from the frozen universe")
        a, b = root(first), root(second)
        if a != b:
            parents[max(a, b)] = min(a, b)
    grouped = defaultdict(list)
    for node in sorted(nodes):
        grouped[root(node)].append(node)
    return sorted(grouped.values())


def partition_components(groups):
    """Hash full component membership into 60/20/20 train/validation/final buckets."""
    assignments, records = {}, []
    for group in groups:
        identity = digest("\n".join(group))
        bucket = int(digest(SEED + ":" + identity), 16) % 100
        split = (
            "development_train"
            if bucket < 60
            else "development_validation"
            if bucket < 80
            else "final"
        )
        records.append({"id": identity, "members": group, "partition": split})
        for member in group:
            assignments[member] = {"group": identity, "partition": split}
    return assignments, records


def freeze(envelope, features, homology_text, similarity=normalized_edit_similarity):
    """Freeze the entire annotation universe so later study joins do not move genes."""
    _, cds = annotation_index(features)
    sequences = {key: row["sequence"] for key, row in envelope["genomes"].items()}
    contexts = {}
    for locus, matches in cds.items():
        if len(matches) == 1:
            feature = matches[0]
            contexts[locus] = genomic_context(
                sequences[feature["replicon"]],
                feature["start_zero_based"],
                feature["strand"],
            )
    edges = homology_edges(homology_text)
    near_full = sequence_edges(contexts, similarity)
    near_regulatory = sequence_edges(
        {k: v[65:170] for k, v in contexts.items()}, similarity
    )
    near_utr = sequence_edges({k: v[70:100] for k, v in contexts.items()}, similarity)
    near = sorted(set(near_full + near_regulatory + near_utr))
    ids = [row["id"] for row in envelope["records"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source input identity")
    input_nodes = {
        row["id"]: row["current_locus_tag"] or "unmapped:" + row["id"]
        for row in envelope["records"]
    }
    nodes = set(cds) | set(input_nodes.values())
    assignments, groups = partition_components(components(sorted(nodes), edges + near))
    records = [
        {
            "id": row["id"],
            "source_orf": row["source_orf"],
            "current_locus_tag": row["current_locus_tag"],
            "sequence_sha256": row["sequence_sha256"],
            "mapping_status": row["mapping_status"],
            "primary_eligible": row["primary_eligible"],
            **assignments[input_nodes[row["id"]]],
        }
        for row in sorted(envelope["records"], key=lambda r: r["id"])
    ]
    return {
        "schema_version": "native-rbs-splits-1",
        "seed": SEED,
        "strategy": (
            "Connected components of full-annotation protein homology and >=0.85 "
            "normalized edit similarity of 200nt(-100,+100),105nt(-35,+70),"
            "or30nt(-30,0) contexts; all conditions of a source gene remain together"
        ),
        "homology_method": (
            "MMseqs2 18-8cc5c; min identity0.30, coverage0.80 both, E<=1e-5, "
            "sensitivity7.5, max-seqs10000, threads1; heuristic homology proxy, "
            "not verified orthology"
        ),
        "homology_input_sha256": digest(homology_text),
        "n_annotation_loci": len(cds),
        "n_contexts_compared": len(contexts),
        "n_homology_edges": len(edges),
        "n_near_context_edges": len(near),
        "near_context_edges_by_window": {
            "200nt": len(near_full),
            "105nt": len(near_regulatory),
            "30nt": len(near_utr),
        },
        "context_edges_sha256": digest(json.dumps(near, separators=(",", ":"))),
        "n_groups": len(groups),
        "groups": groups,
        "records": records,
        "partition_counts": dict(Counter(r["partition"] for r in records)),
        "primary_partition_counts": dict(
            Counter(r["partition"] for r in records if r["primary_eligible"])
        ),
        "primary_group_counts": dict(
            sorted(
                Counter(
                    split
                    for split, group in {
                        (r["partition"], r["group"])
                        for r in records
                        if r["primary_eligible"]
                    }
                ).items()
            )
        ),
        "no_outcome_values_read": True,
        "limits": [
            "Single-host PCC6803 partitions; not native UTEX calibration",
            "Protein search is heuristic; distant homologs may remain",
            "Genomic flanks are not measured transcript boundaries",
            "Unmapped source identifiers remain unjoined and ineligible",
        ],
    }


def main(argv=None):
    """Freeze inputs, optionally accelerating exact edit distances with RapidFuzz."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("homology", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rapidfuzz", action="store_true")
    args = parser.parse_args(argv)
    similarity = normalized_edit_similarity
    if args.rapidfuzz:
        from rapidfuzz.distance.Levenshtein import normalized_similarity

        similarity = normalized_similarity
    envelope = json.loads(args.inputs.read_text())
    sequences = {key: row["sequence"] for key, row in envelope["genomes"].items()}
    features = gff_features(
        gzip.decompress(checked_source(args.root, "pcc6803-genomic.gff.gz")).decode(),
        sequences,
    )
    result = freeze(envelope, features, args.homology.read_text(), similarity)
    result["input_envelope_sha256"] = digest(args.inputs.read_bytes())
    write_json(args.output, result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "n_groups",
                    "n_homology_edges",
                    "n_near_context_edges",
                    "partition_counts",
                    "primary_partition_counts",
                    "primary_group_counts",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
