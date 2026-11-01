"""Hand-computed and brute-force checks of frozen input-only label groups."""

import contextlib
import copy
import hashlib
import io
import itertools
import json
import os
import random
import runpy
import sys
import tempfile
import unittest
import warnings
from fractions import Fraction
from pathlib import Path
from unittest import mock

from benchmarks.promoter import native_groups as g
from benchmarks.promoter import native_inputs as n
from benchmarks.promoter import native_metrics as m

COMPLEMENT = {"A": "T", "C": "G", "G": "C", "T": "A"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def revcomp(text):
    return "".join(COMPLEMENT[base] for base in reversed(text))


def random_dna(length, seed):
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(length))


def genome(sequence, topology="linear"):
    return {
        "sequence": sequence,
        "sequence_sha256": sha(sequence),
        "accession": "synthetic",
        "assembly": "synthetic-v1",
        "annotation": "synthetic-annotation-v1",
        "topology": topology,
    }


def label(genome_id, strand, point, query_id=None, tags=()):
    rows = [{"id": f"r{i}", "source_locus_tag": tag} for i, tag in enumerate(tags)]
    return {
        "label_id": f"tss:{genome_id}:{strand}:{point}",
        "genome_id": genome_id,
        "strand": strand,
        "tss_zero_based": point,
        "query_id": query_id,
        "local_index": None,
        "source_rows": rows or [{"id": "r0", "source_locus_tag": None}],
    }


def query(query_id, genome_id, *spans):
    return {
        "query_id": query_id,
        "genome_id": genome_id,
        "segments": [{"genomic": list(span)} for span in spans],
    }


def components(groups):
    result = {}
    for label_id, component in groups.items():
        result.setdefault(component, set()).add(label_id)
    return result


def reference_context(sequence, topology, strand, point):
    """Independent base-by-base context walk in transcript orientation."""
    length = len(sequence)
    step = 1 if strand == "+" else -1
    if topology == "circular":
        down = min(19, length - 1)
        up = min(67, length - 1 - down)
    else:
        up = min(67, point if strand == "+" else length - 1 - point)
        down = min(19, length - 1 - point if strand == "+" else point)
    bases = []
    for offset in range(-up, down + 1):
        base = sequence[(point + step * offset) % length]
        bases.append(base if strand == "+" else COMPLEMENT[base])
    return "".join(bases)


def reference_groups(genomes, queries, labels):
    """O(n^2) graph and breadth-first components, independent of the tool."""
    nodes = [("label", x["label_id"]) for x in labels] + [
        ("query", q["query_id"]) for q in queries
    ]
    adjacent = {node: set() for node in nodes}

    def connect(a, b):
        adjacent[a].add(b)
        adjacent[b].add(a)

    for x in labels:
        if x["query_id"] is not None:
            connect(("label", x["label_id"]), ("query", x["query_id"]))
    for qa, qb in itertools.combinations(queries, 2):
        if qa["genome_id"] != qb["genome_id"]:
            continue
        info = genomes[qa["genome_id"]]
        length = len(info["sequence"])
        bases_a = {i % length for s in qa["segments"] for i in range(*s["genomic"])}
        bases_b = {i % length for s in qb["segments"] for i in range(*s["genomic"])}
        # Touching means some base of one is adjacent to or equal to a base of
        # the other; adjacency wraps only on circular replicons.
        near = set()
        for i in bases_a:
            for j in (i - 1, i, i + 1):
                if info["topology"] == "circular":
                    near.add(j % length)
                elif 0 <= j < length:
                    near.add(j)
        if near & bases_b:
            connect(("query", qa["query_id"]), ("query", qb["query_id"]))
    kmers = {}
    for x in labels:
        info = genomes[x["genome_id"]]
        dna = reference_context(
            info["sequence"], info["topology"], x["strand"], x["tss_zero_based"]
        )
        if len(dna) >= 15:
            kmers[x["label_id"]] = {
                min(dna[i : i + 15], revcomp(dna[i : i + 15]))
                for i in range(len(dna) - 14)
            }
    for xa, xb in itertools.combinations(labels, 2):
        a, b = ("label", xa["label_id"]), ("label", xb["label_id"])
        if xa["genome_id"] == xb["genome_id"]:
            info = genomes[xa["genome_id"]]
            gap = abs(xa["tss_zero_based"] - xb["tss_zero_based"])
            if info["topology"] == "circular":
                gap = min(gap, len(info["sequence"]) - gap)
            tags_a = {r["source_locus_tag"] for r in xa["source_rows"]} - {None, ""}
            tags_b = {r["source_locus_tag"] for r in xb["source_rows"]} - {None, ""}
            if gap <= 86 or tags_a & tags_b:
                connect(a, b)
        ka, kb = kmers.get(xa["label_id"]), kmers.get(xb["label_id"])
        if ka and kb and Fraction(len(ka & kb), len(ka | kb)) >= Fraction(1, 2):
            connect(a, b)
    seen, groups = set(), {}
    for start in nodes:
        if start in seen:
            continue
        stack, members = [start], []
        seen.add(start)
        while stack:
            node = stack.pop()
            members.append(node)
            for other in adjacent[node] - seen:
                seen.add(other)
                stack.append(other)
        ids = sorted(identity for kind, identity in members if kind == "label")
        for identity in ids:
            groups[identity] = ids[0]
    return groups


class ContextTest(unittest.TestCase):
    def test_hand_checked_contexts(self):
        sequence = random_dna(300, 1)
        context = g.label_context
        self.assertEqual(
            context(sequence, "linear", "+", 100),
            (sequence[33:120], "complete", None),
        )
        self.assertEqual(
            context(sequence, "linear", "-", 100),
            (revcomp(sequence[81:168]), "complete", None),
        )
        self.assertEqual(
            context(sequence, "linear", "+", 10),
            (sequence[0:30], "clipped", "linear_edge"),
        )
        self.assertEqual(
            context(sequence, "linear", "-", 290),
            (revcomp(sequence[271:300]), "clipped", "linear_edge"),
        )
        self.assertEqual(
            context(sequence, "circular", "+", 5),
            (sequence[238:] + sequence[:25], "complete", None),
        )
        self.assertEqual(
            context(sequence, "circular", "-", 295),
            (revcomp(sequence[276:] + sequence[:63]), "complete", None),
        )
        # A circular replicon shorter than 87 nt yields each base once.
        small = random_dna(50, 2)
        dna, status, reason = context(small, "circular", "+", 0)
        self.assertEqual(
            (dna, status, reason),
            (small[20:] + small[:20], "clipped", "circular_no_repeat_limit"),
        )
        self.assertEqual(
            context(small[:14], "circular", "-", 3)[1:],
            ("unavailable", "circular_no_repeat_limit"),
        )
        self.assertEqual(
            context(small[:14], "linear", "+", 13)[1:], ("unavailable", "linear_edge")
        )
        self.assertEqual(context(small[:15], "linear", "+", 0)[1], "clipped")

    def test_contexts_match_reference_walk(self):
        for topology, length in (("linear", 200), ("circular", 200), ("circular", 60)):
            sequence = random_dna(length, length)
            for strand in "+-":
                for point in range(length):
                    self.assertEqual(
                        g.label_context(sequence, topology, strand, point)[0],
                        reference_context(sequence, topology, strand, point),
                    )

    def test_canonical_kmers(self):
        self.assertEqual(g.canonical_kmers("A" * 16 + "T"), {"A" * 15, "A" * 14 + "T"})
        self.assertEqual(g.canonical_kmers("A" * 14), set())
        dna = random_dna(87, 3)
        self.assertEqual(g.canonical_kmers(dna), g.canonical_kmers(revcomp(dna)))
        self.assertEqual(len(g.canonical_kmers(dna)), 73)

    def test_jaccard_boundary(self):
        self.assertTrue(g.jaccard_connects(2, 3, 3))  # 2/4
        self.assertTrue(g.jaccard_connects(1, 1, 2))  # 1/2
        self.assertTrue(g.jaccard_connects(48, 73, 71))  # 48/96
        self.assertFalse(g.jaccard_connects(47, 73, 70))  # 47/96
        self.assertFalse(g.jaccard_connects(2, 3, 4))  # 2/5
        self.assertFalse(g.jaccard_connects(0, 5, 5))
        self.assertTrue(g.jaccard_connects(5, 5, 5))


class RuleTest(unittest.TestCase):
    def test_query_intervals(self):
        genomes = {
            "l": genome("A" * 300),
            "c": genome("A" * 300, "circular"),
        }
        queries = [
            query("touch-a", "l", (0, 10)),
            query("touch-b", "l", (10, 20)),
            query("gap", "l", (21, 30)),
            query("edge", "l", (290, 300)),
            query("seam-end", "c", (290, 300)),
            query("seam-start", "c", (0, 5)),
            query("wrapped", "c", (280, 300), (0, 2)),
            query("inside", "c", (100, 200)),
            query("overlap", "c", (150, 160)),
        ]
        pairs = {
            tuple(sorted((queries[a]["query_id"], queries[b]["query_id"])))
            for a, b in g.query_interval_pairs(queries, genomes)
        }
        self.assertEqual(
            pairs,
            {
                ("touch-a", "touch-b"),
                ("seam-end", "seam-start"),
                ("seam-end", "wrapped"),
                ("seam-start", "wrapped"),
                ("inside", "overlap"),
            },
        )
        # The linear "edge" query never touches "touch-a" across the ends.
        self.assertNotIn(("edge", "touch-a"), pairs)

    def test_label_distance(self):
        genomes = {
            "l": genome("A" * 1000),
            "c": genome("A" * 300, "circular"),
        }
        labels = [
            label("l", "+", 100),
            label("l", "-", 186),  # 86 from 100
            label("l", "+", 273),  # 87 from 186
            label("l", "-", 100),  # same point, other strand
            label("l", "+", 5),
            label("l", "+", 999),  # linear: no wrap to 5
            label("c", "+", 5),
            label("c", "-", 219),  # circular 86 via the origin
            label("c", "+", 218),  # circular 87
        ]
        found = {
            (labels[a]["label_id"], labels[b]["label_id"])
            for a, b in g.label_distance_pairs(labels, genomes)
        }
        self.assertEqual(
            found,
            {
                ("tss:l:+:100", "tss:l:-:186"),
                ("tss:l:+:100", "tss:l:-:100"),
                ("tss:l:-:186", "tss:l:-:100"),
                ("tss:c:+:5", "tss:c:-:219"),
                ("tss:c:-:219", "tss:c:+:218"),
            },
        )

    def test_locus_tags(self):
        labels = [
            label("l", "+", 1, tags=("T1", "T1")),  # repeated conditions
            label("l", "-", 900, tags=("T1", "T2")),
            label("l", "+", 500, tags=("T2",)),
            label("c", "+", 1, tags=("T1",)),  # same tag, other replicon
            label("l", "+", 700, tags=("", None)),
            label("l", "+", 800, tags=("t1",)),  # exact, case-sensitive
        ]
        self.assertEqual(g.locus_tags(labels[4]), set())
        self.assertEqual(g.locus_tag_pairs(labels), {(0, 1), (1, 2)})

    def test_kmer_pairs(self):
        sets = {
            0: {"a", "b", "c"},
            1: {"b", "c", "d"},  # 2/4 with 0
            2: {"b", "c", "d", "e"},  # 2/5 with 0, 3/4 with 1
            3: {"x"},
        }
        self.assertEqual(g.kmer_pairs(sets), {(0, 1), (1, 2)})
        self.assertEqual(g.kmer_pairs({}), set())

    def test_union_find(self):
        forest = g.UnionFind(5)
        forest.union(0, 1)
        forest.union(3, 4)
        forest.union(1, 4)
        forest.union(4, 0)
        roots = {forest.find(i) for i in (0, 1, 3, 4)}
        self.assertEqual(len(roots), 1)
        self.assertNotEqual(forest.find(2), forest.find(0))
        self.assertEqual(forest.size[forest.find(0)], 4)

    def test_pair_limits(self):
        genomes = {"l": genome("A" * 300)}
        labels = [label("l", "+", p, tags=("T",)) for p in (1, 2, 3)]
        with mock.patch.object(g, "MAX_PAIRS_PER_RULE", 2):
            with self.assertRaisesRegex(ValueError, "label_distance edges exceed 2"):
                g.label_distance_pairs(labels, genomes)
            with self.assertRaisesRegex(ValueError, "label_locus_tag edges"):
                g.locus_tag_pairs(labels)
            with self.assertRaisesRegex(ValueError, "query_interval"):
                g.query_interval_pairs(
                    [query(str(i), "l", (0, 10)) for i in range(3)], genomes
                )
            with self.assertRaisesRegex(ValueError, "label_context_kmer edges"):
                g.kmer_pairs({i: {"a"} for i in range(3)})
        with mock.patch.object(g, "MAX_PAIR_OPERATIONS", 2):
            with self.assertRaisesRegex(ValueError, "label_locus_tag pair operations"):
                g.locus_tag_pairs(labels)
            with self.assertRaisesRegex(ValueError, "kmer pair operations exceed 2"):
                g.kmer_pairs({i: {"a"} for i in range(3)})
        with mock.patch.object(g, "MAX_PAIR_OPERATIONS", 3):
            self.assertEqual(len(g.kmer_pairs({i: {"a"} for i in range(3)})), 3)


def scenario(shared_nt=62):
    """Hand-designed genomes; returns (genomes, queries, labels, expected)."""
    base = list(random_dna(3000, 10))
    # S (g:+:600) context g[533:620]; T (g:-:1000) context revcomp(g[981:1068]).
    # Make T's context identical to S's: Jaccard 1 across strands.
    base[981:1068] = revcomp("".join(base[533:620]))
    # U (g:+:65) is clipped to g[0:85] (71 k-mers); A (g:+:1700) has 73 k-mers.
    # Sharing `shared_nt` aligned bases gives shared_nt - 14 common k-mers;
    # 62 nt gives 48/96 = exactly 1/2, 61 nt gives 47/97.
    base[10 : 10 + shared_nt] = base[1640 : 1640 + shared_nt]
    sequence = "".join(base)
    genomes = {
        "g": genome(sequence),
        "c": genome(random_dna(1000, 11), "circular"),
        "d": genome(random_dna(1000, 12), "circular"),
        "t": genome(random_dna(10, 13)),
    }
    queries = [
        query("Q1", "g", (100, 300)),
        query("Q2", "g", (300, 500)),  # touches Q1 across strands
        query("Q3", "g", (2700, 2800)),  # unlabelled-only
        query("Q4", "c", (900, 1000)),
        query("Q5", "c", (0, 50)),  # touches Q4 at the circular seam
        query("Q6", "c", (500, 600)),
    ]
    labels = [
        label("g", "+", 250, "Q1"),
        label("g", "-", 450, "Q2"),
        label("g", "+", 1500, tags=("L1",)),
        label("g", "-", 2500, tags=("L1", "L1")),
        label("g", "+", 2000),
        label("g", "-", 2086),
        label("g", "+", 2173),
        label("g", "+", 600),
        label("g", "-", 1000),
        label("g", "+", 65),
        label("g", "+", 1700),
        label("c", "+", 920, "Q4"),
        label("c", "-", 10, "Q5"),
        label("c", "+", 550, "Q6"),
        label("d", "+", 980),
        label("d", "-", 60),
        label("d", "+", 500),
        label("t", "+", 5),
    ]
    expected = [
        {"tss:g:+:250", "tss:g:-:450"},
        {"tss:g:+:1500", "tss:g:-:2500"},
        {"tss:g:+:2000", "tss:g:-:2086"},
        {"tss:g:+:2173"},
        {"tss:g:+:600", "tss:g:-:1000"},
        {"tss:c:+:920", "tss:c:-:10"},
        {"tss:c:+:550"},
        {"tss:d:+:980", "tss:d:-:60"},
        {"tss:d:+:500"},
        {"tss:t:+:5"},
    ]
    pair = {"tss:g:+:65", "tss:g:+:1700"}
    expected += [pair] if shared_nt >= 62 else [{x} for x in sorted(pair)]
    return genomes, queries, labels, expected


class GroupLabelsTest(unittest.TestCase):
    def test_hand_computed_components(self):
        genomes, queries, labels, expected = scenario()
        groups, counts = g.group_labels(genomes, queries, labels)
        self.assertEqual(components(groups), {min(ids): ids for ids in expected})
        self.assertEqual(groups, reference_groups(genomes, queries, labels))
        self.assertEqual(
            counts,
            {
                "n_labels": 18,
                "n_labels_in_window": 5,
                "n_labels_out_of_window": 13,
                "n_labels_with_locus_tag": 2,
                "n_queries": 6,
                "n_queries_with_labels": 5,
                "edges": {
                    "label_query_attachment": 5,
                    "query_interval_overlap_or_touch": 2,
                    "label_locus_tag": 1,
                    "label_distance": 2,
                    "label_context_kmer": 2,
                },
                "context_status": {"complete": 16, "clipped": 1, "unavailable": 1},
                "context_limit_reason": {
                    "linear_edge": 2,
                    "circular_no_repeat_limit": 0,
                },
                "n_groups": 11,
                "group_size_counts": [[1, 4], [2, 7]],
                "max_group_size": 2,
                "n_unlabelled_query_components": 1,
                "n_queries_in_unlabelled_components": 1,
            },
        )

    def test_jaccard_just_below_half_does_not_connect(self):
        genomes, queries, labels, expected = scenario(shared_nt=61)
        groups, counts = g.group_labels(genomes, queries, labels)
        self.assertEqual(components(groups), {min(ids): ids for ids in expected})
        self.assertEqual(counts["edges"]["label_context_kmer"], 1)
        self.assertEqual(groups, reference_groups(genomes, queries, labels))

    def test_transitive_chain_and_lexicographic_identity(self):
        genomes = {"g": genome(random_dna(2000, 20))}
        # 9 -> 90 -> 170 by distance; 1000 joins through a shared locus tag;
        # string order makes "tss:g:+:1000" the identity, not the query ID.
        labels = [
            label("g", "+", 9, "Q-z"),
            label("g", "-", 90),
            label("g", "+", 170, tags=("X",)),
            label("g", "+", 1000, tags=("X",)),
        ]
        queries = [query("Q-z", "g", (0, 50))]
        groups, counts = g.group_labels(genomes, queries, labels)
        self.assertEqual(set(groups.values()), {"tss:g:+:1000"})
        self.assertEqual(counts["n_groups"], 1)
        self.assertEqual(counts["group_size_counts"], [[4, 1]])

    def test_reorder_invariance_and_random_reference(self):
        rng = random.Random(7)
        for trial in range(8):
            base = list(random_dna(1500, 100 + trial))
            for _ in range(3):  # planted forward and reverse repeats
                source, target = rng.randrange(1400), rng.randrange(1400)
                piece = "".join(base[source : source + 80])
                base[target : target + 80] = (
                    piece if rng.random() < 0.5 else revcomp(piece)
                )
            genomes = {
                "a": genome("".join(base), rng.choice(("linear", "circular"))),
                "b": genome(random_dna(400, 200 + trial), "circular"),
            }
            queries = []
            for i in range(6):
                genome_id = rng.choice("ab")
                length = len(genomes[genome_id]["sequence"])
                start = rng.randrange(length)
                end = start + rng.randrange(1, 120)
                spans = (
                    [(start, end)]
                    if end <= length or genomes[genome_id]["topology"] == "linear"
                    else [(start, length), (0, end - length)]
                )
                spans = [(a, min(b, length)) for a, b in spans]
                queries.append(query(f"q{i}", genome_id, *spans))
            labels, seen = [], set()
            for _ in range(25):
                genome_id = rng.choice("ab")
                point = rng.randrange(len(genomes[genome_id]["sequence"]))
                strand = rng.choice("+-")
                if (genome_id, strand, point) in seen:
                    continue
                seen.add((genome_id, strand, point))
                attach = rng.choice([None] + [q["query_id"] for q in queries])
                tags = rng.choice([(), ("T1",), ("T2",), ("T1", "T2")])
                labels.append(label(genome_id, strand, point, attach, tags))
            expected = reference_groups(genomes, queries, labels)
            groups, counts = g.group_labels(genomes, queries, labels)
            self.assertEqual(groups, expected)
            shuffled_labels, shuffled_queries = labels[:], queries[:]
            rng.shuffle(shuffled_labels)
            rng.shuffle(shuffled_queries)
            self.assertEqual(
                g.group_labels(genomes, shuffled_queries, shuffled_labels),
                (groups, counts),
            )

    def test_limits(self):
        genomes, queries, labels, _ = scenario()
        with mock.patch.object(g, "MAX_GROUP_LABELS", 17):
            with self.assertRaisesRegex(ValueError, "at most 17 labels"):
                g.group_labels(genomes, queries, labels)
        with mock.patch.object(g, "MAX_QUERIES", 5):
            with self.assertRaisesRegex(ValueError, "5 queries"):
                g.group_labels(genomes, queries, labels)


def pipeline(records, width=100, cap=128, sequence=None):
    sequence = sequence or random_dna(600, 30)
    value = {
        "schema_version": n.ENVELOPE_SCHEMA,
        "genomes": {"g": genome(sequence, "circular")},
        "records": records,
    }
    raw = json.dumps(value).encode()
    digest = hashlib.sha256(raw).hexdigest()
    envelope = n.load_envelope(raw, digest)
    queries = n.build_queries(envelope, digest, n.grid_settings(width, cap, "grp"))
    labels = n.project_labels(envelope, digest, queries)
    return raw, digest, envelope, queries, labels


RECORDS = [
    {
        "id": "a",
        "genome_id": "g",
        "strand": "+",
        "tss_zero_based": 120,
        "source_locus_tag": "loc1",
    },
    {
        "id": "b",
        "genome_id": "g",
        "strand": "+",
        "tss_zero_based": 120,
        "source_locus_tag": "loc1",
        "conditions": {"dark": [1, 2]},
    },
    {"id": "c", "genome_id": "g", "strand": "-", "tss_zero_based": 420},
    {"id": "d", "genome_id": "g", "strand": "+", "tss_zero_based": None},
]


class BuildGroupsTest(unittest.TestCase):
    def test_document_and_metrics_compatibility(self):
        _, digest, envelope, queries, labels = pipeline(RECORDS, cap=2)
        document = g.build_groups(envelope, digest, queries, labels)
        self.assertEqual(document["schema_version"], m.GROUP_SCHEMA)
        self.assertEqual(document["labels_document_sha256"], n.document_sha256(labels))
        self.assertEqual(
            document["inputs"],
            {
                "envelope_file_sha256": digest,
                "query_document_sha256": n.document_sha256(queries),
                "labels_document_sha256": n.document_sha256(labels),
            },
        )
        self.assertEqual(document["settings"], g.group_settings())
        self.assertEqual(
            document["settings_sha256"], n.document_sha256(g.group_settings())
        )
        self.assertEqual(document["tool_sha256"], g.tool_sha256())
        self.assertEqual(
            document["tool_sha256"],
            hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),
        )
        self.assertEqual(
            document["dependency_tool_sha256"], {"native_inputs": n.tool_sha256()}
        )
        self.assertEqual(set(document["groups"]), {"tss:g:+:120", "tss:g:-:420"})
        self.assertEqual(document["counts"]["n_labels"], labels["counts"]["n_labels"])
        # The metrics evaluator accepts the mapping unchanged.
        scores = {
            "schema_version": m.SCORE_SCHEMA,
            "query_document_sha256": n.document_sha256(queries),
            "results": [
                {
                    "request_id": f"r{i}",
                    "query_id": q["query_id"],
                    "status": "not_run",
                    "candidates": [],
                }
                for i, q in enumerate(queries["queries"])
            ],
        }
        metrics = m.evaluate(queries, scores, labels, document, m.metric_settings(True))
        self.assertEqual(
            metrics["inputs"]["groups_sha256"], n.document_sha256(document)
        )
        self.assertEqual(metrics["n_groups"], document["counts"]["n_groups"])

    def test_all_tiles_connect_into_one_window_group(self):
        _, digest, envelope, queries, labels = pipeline(RECORDS)
        document = g.build_groups(envelope, digest, queries, labels)
        self.assertEqual(set(document["groups"].values()), {"tss:g:+:120"})
        self.assertEqual(document["counts"]["edges"]["label_query_attachment"], 2)
        self.assertEqual(document["counts"]["n_unlabelled_query_components"], 0)

    def test_record_order_does_not_change_groups(self):
        _, digest, envelope, queries, labels = pipeline(RECORDS, cap=2)
        first = g.build_groups(envelope, digest, queries, labels)
        _, digest2, envelope2, queries2, labels2 = pipeline(
            list(reversed(RECORDS)), cap=2
        )
        second = g.build_groups(envelope2, digest2, queries2, labels2)
        self.assertEqual(first["groups"], second["groups"])
        self.assertEqual(first["counts"], second["counts"])

    def test_tampered_inputs(self):
        _, digest, envelope, queries, labels = pipeline(RECORDS, cap=2)
        tampered = copy.deepcopy(labels)
        tampered["labels"][0]["source_rows"][0]["source_locus_tag"] = "other"
        with self.assertRaisesRegex(ValueError, "not reproduced"):
            g.build_groups(envelope, digest, queries, tampered)
        moved = copy.deepcopy(queries)
        moved["queries"][0]["segments"][0]["genomic"][0] += 1
        with self.assertRaisesRegex(ValueError, "Query document is not reproduced"):
            g.build_groups(envelope, digest, moved, labels)
        for bad in ({"labels": "x"}, {}):
            with self.assertRaisesRegex(ValueError, "Labels must be a list"):
                g.build_groups(envelope, digest, queries, bad)
        with mock.patch.object(g, "MAX_GROUP_LABELS", 1):
            with self.assertRaisesRegex(ValueError, "at most 1"):
                g.build_groups(envelope, digest, queries, labels)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        raw, self.digest, _, queries, labels = pipeline(RECORDS, cap=2)
        (self.path / "env.json").write_bytes(raw)
        (self.path / "queries.json").write_bytes(n.canonical_bytes(queries))
        (self.path / "labels.json").write_bytes(n.canonical_bytes(labels))

    def argv(self, output="groups.json", digest=None, labels="labels.json"):
        return [
            str(self.path / "env.json"),
            str(self.path / "queries.json"),
            str(self.path / labels),
            str(self.path / output),
            "--source-sha256",
            digest or self.digest,
        ]

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = g.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_success_and_no_overwrite(self):
        code, out, _ = self.run_main(self.argv())
        self.assertEqual(code, 0)
        output = self.path / "groups.json"
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        raw = output.read_bytes()
        summary = json.loads(out)
        self.assertEqual(summary["output_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(summary["n_groups"], json.loads(raw)["counts"]["n_groups"])
        self.assertEqual(n.canonical_bytes(json.loads(raw)), raw)
        code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error:", err)
        self.assertEqual(output.read_bytes(), raw)

    def test_failures(self):
        code, out, err = self.run_main(self.argv(digest="0" * 64))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Envelope file SHA-256 mismatch", err)
        labels = json.loads((self.path / "labels.json").read_bytes())
        (self.path / "pretty.json").write_text(json.dumps(labels, indent=1))
        code, _, err = self.run_main(self.argv(labels="pretty.json"))
        self.assertEqual(code, 1)
        self.assertIn("not canonical", err)
        (self.path / "list.json").write_bytes(n.canonical_bytes([]))
        code, _, err = self.run_main(self.argv(labels="list.json"))
        self.assertEqual(code, 1)
        code, _, err = self.run_main(self.argv(labels="missing.json"))
        self.assertEqual(code, 1)
        self.assertFalse((self.path / "groups.json").exists())

    def test_module_entry_point(self):
        with (
            mock.patch.object(
                sys, "argv", ["native_groups", *self.argv(digest="0" * 64)]
            ),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "benchmarks.promoter.native_groups", run_name="__main__"
                )
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
