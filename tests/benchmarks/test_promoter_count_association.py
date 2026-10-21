"""Portable, synthetic source/admission failures and independent rank arithmetic."""

import copy
import csv
import gzip
import io
import math
import random
import runpy
import statistics
import sys

import pytest

from benchmarks.promoter import count_association as ca

ERRORS = (ValueError, KeyError, TypeError, IndexError)
REPLICON = "NZ_CP006471.1"


def tsv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def source_row(identity, locus, position, strand="+", count=1):
    return {
        "tss_id": identity,
        "replicon": "CP006471",
        "type": "gTSS",
        "strand": strand,
        "position": str(position),
        "locus_tag": locus,
        **{f"{c}_{i}": str(count + i - 1) for c in ca.CONDITIONS for i in (1, 2)},
    }


def synthetic(tmp_path):
    """Seven tiny public-schema files; no external dataset or model dependency."""
    protocol, manifest = copy.deepcopy(ca.freezes())
    sequence = "".join(random.Random(912).choices("ACGT", k=2400))
    protocol["selection"].update(
        source_rows=4, max_sites=4, replicon_lengths={REPLICON: len(sequence)}
    )
    # Full 2000 draws remain the default synthetic evaluate check.
    rows = [
        source_row("a", "old-A", 300, count=0),
        source_row("c", "C", 1100, count=2),
        source_row("d", "D", 1500, "-", count=3),
        source_row("e", "E", 1900, count=5),
    ]
    loci, genes, crosswalk = [], {}, []
    memberships = {"A": ["tu1"], "B": ["tu1", "tu2"], "C": ["tu2"], "D": [], "E": None}
    for index, (locus, ids) in enumerate(memberships.items()):
        strand = "-" if locus == "D" else "+"
        biotype = "ncRNA" if locus == "D" else "protein_coding"
        state = (
            "no-source-data"
            if ids is None
            else "membership-observed"
            if ids
            else "source-membership-empty"
        )
        loci.append(
            {
                "locusTag": locus,
                "seqid": REPLICON,
                "featureType": "gene",
                "geneBiotype": biotype,
                "state": state,
                "tuIds": ids,
                "sourceFrames": [locus] if ids is not None else [],
                "candidateSourceFrames": [locus] if ids is not None else [],
            }
        )
        partial = locus in ("B", "C")
        overlap = {
            "coverage": {
                "status": "partial" if partial else "complete",
                "coveredNt": 50 if partial else 100,
                "totalNt": 100,
            },
            "sameStrandCallIds": ["native:site"] if locus == "B" else [],
            "oppositeStrandCallIds": [],
            "observedSourceCallCount": 1 if locus == "B" else 0,
            "completeSourceCallCount": None if partial else 0,
        }
        genes[locus] = {
            "replicon": REPLICON,
            "strand": strand,
            "biotype": biotype,
            "featureType": "gene",
            "cdsSegments": []
            if locus == "D"
            else [[1 + index * 100, 100 + index * 100]],
            "cdsOverlap": None if locus == "D" else overlap,
        }
        crosswalk.append(
            {
                "subject_locus_tag": locus,
                "relationship": "current_locus_tag",
                "object_namespace": "RefSeq_locus_tag",
                "object_id": locus,
                "seqid": REPLICON,
                "strand": strand,
            }
        )
    crosswalk.append(
        {
            **crosswalk[0],
            "relationship": "old_locus_tag",
            "object_namespace": "legacy_locus_tag",
            "object_id": "old-A",
        }
    )
    # A donor alias must never be accepted as native context.
    crosswalk.append(
        {
            **crosswalk[0],
            "relationship": "pcc7942_ortholog",
            "object_namespace": "PCC7942_RefSeq_locus_tag",
            "object_id": "donor",
        }
    )
    data = {
        "fasta": gzip.compress(
            f">{REPLICON} description\n{sequence}\n".encode(), mtime=0
        ),
        "tss": tsv(rows),
        "crosswalk": tsv(crosswalk),
    }
    pins = manifest["inputs"]
    for name, raw in data.items():
        pins[name] = {
            "path": f"{name}.dat",
            "bytes": len(raw),
            "sha256": ca.digest(raw),
        }
    tu = {
        "schema": "biocyc-utex-tu-membership-1",
        "basis": "inferred",
        "scope": "non-positional-source-membership",
        "localRelease": ca.RELEASE,
        "inputs": [pins["crosswalk"]],
        "loci": loci,
        "groups": [
            {"tuId": "tu1", "linkedLoci": ["A", "B"]},
            {"tuId": "tu2", "linkedLoci": ["B", "C"]},
            {"tuId": "unresolved-only", "linkedLoci": []},
        ],
    }
    builder = {"path": "opaque/never-open.py", "sha256": "0" * 64}
    term = {
        "schemaVersion": 1,
        "annotationReleaseId": ca.RELEASE,
        "assembly": ca.ASSEMBLY,
        "method": "TransTermHP",
        "recordOrigin": "computed",
        "evidenceBasis": "proxy",
        "datasetId": "utex2973-transtermhp-retained-pilot-v1",
        "genes": genes,
        "sites": [{"id": "native:site", "replicon": REPLICON, "strand": "+"}],
        "replicons": {REPLICON: {"length": len(sequence), "circular": True}},
        "conversion": {"builder": builder},
        "verifiedInputs": {
            "fasta.dat": {
                "byteSize": pins["fasta"]["bytes"],
                "sha256": pins["fasta"]["sha256"],
            }
        },
        "runs": [
            {
                "name": "native",
                "sequenceSha256ByReplicon": {REPLICON: ca.digest(sequence)},
            }
        ],
    }
    data.update(tu=ca.canonical(tu), terminators=ca.canonical(term))
    for name in ("tu", "terminators"):
        pins[name] = {
            "path": f"{name}.json",
            "bytes": len(data[name]),
            "sha256": ca.digest(data[name]),
        }
        tu_kind = name == "tu"
        receipt = {
            "schema": "biocyc-utex-tu-membership-release-1"
            if tu_kind
            else "regulatory-transterm-release-1",
            "contract": "biocyc-utex-tu-membership-1"
            if tu_kind
            else "regulatory-transterm-payload-1",
            "scope": "non-positional-source-membership"
            if tu_kind
            else "native-intrinsic-terminator-coordinate-predictions",
            "status": "accepted-for-runtime-integration",
            "payload": pins[name],
            "reviewedImplementation": "a" * 40,
            "reviews": [
                {"id": role, "result": "accepted", "role": role}
                for role in ("source-contract", "exact-patch")
            ]
            if tu_kind
            else [
                {
                    "id": "review",
                    "result": "accepted",
                    "coverage": ["source-contract", "exact-patch"],
                }
            ],
        }
        if not tu_kind:
            receipt.update(
                builder=builder,
                dataset={
                    "annotationReleaseId": ca.RELEASE,
                    "assembly": ca.ASSEMBLY,
                    "datasetId": term["datasetId"],
                    "schemaVersion": 1,
                },
            )
        raw = ca.canonical(receipt)
        data[f"{name}_release"] = raw
        pins[f"{name}_release"] = {
            "path": f"{name}_release.json",
            "bytes": len(raw),
            "sha256": ca.digest(raw),
        }
    for name, raw in data.items():
        (tmp_path / pins[name]["path"]).write_bytes(raw)
    return protocol, manifest, data


@pytest.fixture
def inputs(tmp_path):
    protocol, manifest, data = synthetic(tmp_path)
    return tmp_path, protocol, manifest, data


def prepared(inputs):
    root, protocol, manifest, _ = inputs
    return ca.prepare(root, protocol, manifest)


def arm(rate, best_offset=0):
    # This fixture constructs summary values without calling production admission.
    curve = [
        {
            "offset_nt": i,
            "dG_total": float((i - best_offset) ** 2),
            "ecoli_model_Tx_rate": rate if i == 0 else rate + 0.25,
        }
        for i in range(-20, 21)
    ]
    energies = [row["dG_total"] for row in curve]
    anchor = best_offset**2
    return {
        "score_curve": curve,
        "best_offsets_nt": [best_offset],
        "anchor_energy_rank_best": 1 + sum(e < anchor for e in energies),
        "anchor_energy_rank_worst": sum(e <= anchor for e in energies),
        "best_distance_min_nt": abs(best_offset),
        "best_distance_max_nt": abs(best_offset),
    }


def original_report(p, protocol, manifest):
    results = []
    by_id = {row["id"]: row for row in p["rows"]}
    for identity in p["selected_ids"]:
        row = by_id[identity]
        rate = {"a": 1.0, "c": 2.0, "d": 3.0, "e": 4.0}[identity]
        shuffled = list(row["sequence"])
        random.Random(f"{protocol['selection']['seed']}:{identity}").shuffle(shuffled)
        shuffled = "".join(shuffled)
        native_arm, control_arm = arm(rate), arm(5.0 - rate, 2)
        results.append(
            {
                **{
                    k: row[k]
                    for k in (
                        "id",
                        "replicon",
                        "strand",
                        "position",
                        "locus",
                        "sequence",
                        "native_positions",
                        "sequence_sha256",
                    )
                },
                "native": native_arm,
                "control": {
                    **control_arm,
                    "sequence": shuffled,
                    "sequence_sha256": ca.digest(shuffled),
                    "kind": "mononucleotide shuffle; no native coordinates",
                    "identical_to_native": shuffled == row["sequence"],
                },
                "best_native_tss_positions": [row["position"]],
            }
        )
    summary = {
        "anchors": 4,
        "strands": {"+": 3, "-": 1},
        "replicons": {REPLICON: 4},
        "native": {
            "any_best_within_5nt": 4,
            "all_best_within_5nt": 4,
            "median_anchor_rank_best": 1.0,
            "median_anchor_rank_worst": 1.0,
        },
        "control": {
            "any_best_within_5nt": 4,
            "all_best_within_5nt": 4,
            "median_anchor_rank_best": 4.0,
            "median_anchor_rank_worst": 5.0,
        },
    }
    runner = protocol["runner"]
    return {
        "schema_version": 1,
        "scope": "Synthetic complete runner report",
        "model_host": runner["model_host"],
        "limitations": ["Synthetic only"],
        "inputs": {
            "fasta_sha256": manifest["inputs"]["fasta"]["sha256"],
            "tss_sha256": manifest["inputs"]["tss"]["sha256"],
            "upstream_commit": runner["upstream_commit"],
            "prepared_files_sha256": runner["prepared_files_sha256"],
        },
        "runtime": {
            "producer_sha256": runner["producer_sha256"],
            **{k: "synthetic" for k in ("python", "numpy", "scipy", "sklearn", "Bio")},
        },
        "parameters": ca.parameters(protocol["selection"]),
        "cohort": {"input_anchors": len(p["rows"]), "excluded": p["excluded"]},
        "summary": summary,
        "results": results,
    }


def evaluated(p, report, protocol, manifest):
    pr, rr = ca.canonical(p), ca.canonical(report)
    return ca.evaluate(pr, ca.digest(pr), rr, ca.digest(rr), protocol, manifest)


def change_file(inputs, name, mutate):
    """Rehash a synthetic changed input; catches semantic failures beyond hashes."""
    root, _, manifest, data = inputs
    value = ca.parse_json(data[name])
    mutate(value)
    raw = ca.canonical(value)
    data[name] = raw
    manifest["inputs"][name].update(bytes=len(raw), sha256=ca.digest(raw))
    (root / manifest["inputs"][name]["path"]).write_bytes(raw)
    if name in ("tu", "terminators"):
        receipt_name = f"{name}_release"
        receipt = ca.parse_json(data[receipt_name])
        receipt["payload"] = manifest["inputs"][name]
        raw = ca.canonical(receipt)
        data[receipt_name] = raw
        manifest["inputs"][receipt_name].update(bytes=len(raw), sha256=ca.digest(raw))
        (root / manifest["inputs"][receipt_name]["path"]).write_bytes(raw)


def test_complete_prepare_evaluate(inputs):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    assert len(p["selected_ids"]) == 4 and not p["excluded"]
    by_id = {row["id"]: row for row in p["rows"]}
    assert by_id["a"]["group"] == by_id["c"]["group"]  # bridge B has no TSS
    assert by_id["a"]["counts"]["control"] == [0.0, 1.0]
    assert by_id["a"]["mapping_status"] == "unique"
    assert by_id["e"]["tu_state"] == "no-source-data"
    result = evaluated(p, original_report(p, protocol, manifest), protocol, manifest)
    primary = result["primary"]
    assert primary["native"]["value"] == 1.0
    assert primary["shuffled"]["value"] == -1.0
    assert primary["native_minus_shuffled"]["value"] == 2.0
    assert primary["n"] == primary["eligible"] == 4
    assert primary["groups"] == 3
    assert result["independent_source_reproduction_established"] is False
    for family in result["strata"].values():
        assert sum(v["n"] for v in family.values()) == 4
        assert sum(v["eligible"] for v in family.values()) == 4
    assert result["source_accounting"]["input_rows"] == 4
    assert ca.digest(ca.canonical(protocol)) == p["trust"]["protocol_sha256"]


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":{"a":0,"a":1}}',
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"1e999",
        b"{",
        b"\xff",
        b"[" * 1500 + b"0" + b"]" * 1500,
    ],
)
def test_strict_json(raw):
    with pytest.raises(ValueError):
        ca.parse_json(raw)


@pytest.mark.parametrize(
    "token,expected",
    [("", None), ("NA", None), ("0", 0.0), ("12.5", 12.5), ("1e2", 100.0), (".5", 0.5)],
)
def test_decimal_missing_counts(token, expected):
    assert ca.count_token(token) == expected


@pytest.mark.parametrize(
    "token", [None, True, 1, "-1", "NaN", "inf", "1e999", " 1", "na"]
)
def test_invalid_counts(token):
    with pytest.raises(ValueError):
        ca.count_token(token)


@pytest.mark.parametrize("value", [True, None, -1, float("inf"), "1"])
def test_numbers(value):
    with pytest.raises(ValueError):
        ca.number(value)


def test_rank_arithmetic():
    assert ca.ranks([10, 0, 10, 20]) == [2.5, 1.0, 2.5, 4.0]
    # x=[1.5,1.5,3], y=[1,2,3]; covariance=1.5, norms=sqrt(1.5*2).
    assert ca.spearman([0, 0, 2], [0, 1, 2])["value"] == pytest.approx(math.sqrt(3) / 2)
    assert ca.spearman([1, 2, 3], [1, 3, 2])["value"] == 0.5
    assert ca.spearman([1, 2], [2, 1])["reason"] == "fewer-than-minimum-pairs"
    assert ca.spearman([0, 0, 0], [1, 2, 3])["reason"] == "constant-ranks"
    assert ca.spearman([1, 2, 3], [0, 0, 0])["reason"] == "constant-ranks"
    with pytest.raises(ValueError):
        ca.spearman([], [1])
    assert ca.quantile([3, 0, 1, 2], 0.25) == 0.75
    assert ca.quantile([3], 0.975) == 3
    assert ca.mean_pair([None, 5]) is None
    assert ca.mean_pair([0, 3]) == 1.5
    assert ca.mean_pair([1e308, 1e308]) == 1e308


def analysis_rows():
    return [
        {
            "id": str(i),
            "group": group,
            "native_rate": float(i + 1),
            "shuffled_rate": float(4 - i),
            "counts": {c: [float(i), float(i)] for c in ca.CONDITIONS},
            "mapping_status": "unique",
            "tu_state": "membership-observed",
            "terminator": "observed",
        }
        for i, group in enumerate(("a", "a", "b", "b"))
    ]


def test_bootstrap_hand_example():
    rows = analysis_rows()
    settings = {
        "seed": 2973,
        "replicates": 2000,
        "minimum_groups": 2,
        "interval": [0.025, 0.975],
    }
    result = ca.bootstrap(rows, settings)
    # Each group has two differently ranked observations. Even aa/bb draws have
    # four pairs with repeated ties: native=1, shuffled=-1, delta=2 in every draw.
    for name, expected in (
        ("native", 1.0),
        ("shuffled", -1.0),
        ("native_minus_shuffled", 2.0),
    ):
        assert result[name] == {
            "requested": 2000,
            "valid": 2000,
            "undefined": 0,
            "interval": [expected, expected],
            "reason": None,
        }
    rows[2]["counts"]["control"] = [None, 2]
    rows[3]["counts"]["control"] = [None, None]
    result = ca.bootstrap(rows, settings)
    # Draws aa are valid; ab, ba and bb have fewer than 3 measured pairs.
    rng = random.Random(2973)
    valid = sum(
        [rng.choice(["a", "b"]) for _ in range(2)] == ["a", "a"] for _ in range(2000)
    )
    assert result["native"]["valid"] == valid
    assert result["native"]["interval"] is None
    assert result["native"]["reason"] == "fewer-than-90-percent-valid"
    assert result == ca.bootstrap(rows, settings)
    assert ca.bootstrap(rows[:2], settings)["native"]["reason"] == "too-few-groups"
    assert ca.bootstrap([], settings)["native"]["undefined"] == 2000


def test_nontrivial_bootstrap_quantiles():
    # Enumerate the seeded four-row group samples independently. Compute Pearson
    # on explicitly ranked integer vectors rather than calling ca.spearman.
    rows = analysis_rows()
    rows[0]["shuffled_rate"], rows[1]["shuffled_rate"] = 1.0, 4.0
    settings = {
        "seed": 7,
        "replicates": 2000,
        "minimum_groups": 2,
        "interval": [0.025, 0.975],
    }
    rng = random.Random(7)
    observed = []
    for _ in range(2000):
        groups = [rng.choice(["a", "b"]) for _ in range(2)]
        indices = [i for group in groups for i in range(4) if rows[i]["group"] == group]
        vectors = [
            [rows[i][key] for i in indices] for key in ("native_rate", "shuffled_rate")
        ]
        vectors.append([rows[i]["counts"]["control"][0] for i in indices])
        ranked = []
        for vector in vectors:
            ranked.append(
                [
                    1
                    + sum(v < x for v in vector)
                    + (sum(v == x for v in vector) - 1) / 2
                    for x in vector
                ]
            )
        correlations = []
        for arm_ranks in ranked[:2]:
            correlations.append(statistics.correlation(arm_ranks, ranked[2]))
        observed.append(correlations[0] - correlations[1])
    observed.sort()
    expected = []
    for p in (0.025, 0.975):
        loc = 1999 * p
        a, b = math.floor(loc), math.ceil(loc)
        expected.append(observed[a] * (b - loc) + observed[b] * (loc - a))
    assert ca.bootstrap(rows, settings)["native_minus_shuffled"][
        "interval"
    ] == pytest.approx(expected)


def test_missing_endpoints_and_strata():
    rows = analysis_rows()
    rows[0]["counts"]["dark"] = [None, 0]
    rows[1]["counts"]["dark"] = [None, None]
    protocol = ca.freezes()[0]
    result = ca.analyze(rows, protocol)
    dark = result["conditions"]["dark"]
    assert dark["replicate_1"]["eligible"] == 2
    assert dark["replicate_2"]["eligible"] == 3
    assert dark["mean"]["eligible"] == 2
    assert dark["replicate_agreement"]["missing"] == 2
    assert dark["mean"]["native_minus_shuffled"]["reason"] == "undefined-arm"
    assert dark["replicate_1"]["eligible_groups"] == 1


def test_windows():
    sequence = "ACGTTGCA"
    settings = {"upstream_nt": 2, "downstream_nt": 1}
    assert ca.window({"position": 1, "strand": "+"}, sequence, settings) == (
        "CAAC",
        [7, 8, 1, 2],
    )
    assert ca.window({"position": 1, "strand": "-"}, sequence, settings) == (
        "CGTT",
        [3, 2, 1, 8],
    )
    with pytest.raises(ValueError):
        ca.window({"position": 1, "strand": "+"}, "A", settings)


def test_all_exclusion_reasons(inputs):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    rows = copy.deepcopy(p["source_rows"])
    rows += [
        source_row("extra-same", "old-A", 700),
        source_row("extra-overlap", "unknown", 301),
    ]
    protocol["selection"].update(source_rows=6, max_sites=1)
    # Pick an explicit seed ordering a first, followed by same locus and overlap.
    for seed in range(1000):
        order = sorted(
            [r["tss_id"] for r in rows], key=lambda x: ca.digest(f"{seed}:{x}")
        )
        if order[0] == "a":
            break
    protocol["selection"]["seed"] = seed
    p = ca.build_prepared(protocol, manifest, p["genomes"], rows, p["context"])
    assert p["excluded"] == {
        "same_locus": 1,
        "overlapping_window": 1,
        "sample_limit": 3,
    }
    assert sum(p["excluded"].values()) + len(p["selected_ids"]) == 6
    # A distant reverse-complement copy is rejected as a duplicate window.
    protocol["selection"].update(source_rows=2, max_sites=2)
    rows = [source_row("a", "old-A", 300), source_row("other", "other", 1000)]
    genome = list(p["genomes"][REPLICON])
    first = next(row for row in p["rows"] if row["id"] == "a")["sequence"]
    genome[1000 - 88 : 1000 + 40] = first.translate(ca.COMPLEMENT)[::-1]
    p = ca.build_prepared(
        protocol, manifest, {REPLICON: "".join(genome)}, rows, p["context"]
    )
    assert p["excluded"] == {"identical_or_reverse_complement_window": 1}


def test_context_mapping_and_repeated_loci(inputs):
    p = prepared(inputs)
    context = copy.deepcopy(p["context"])
    context["aliases"] += [["ambiguous", "A"], ["ambiguous", "C"]]
    anchors = [
        dict(p["rows"][0], id="donor", locus="donor"),
        dict(p["rows"][0], id="ambiguous", locus="ambiguous"),
        dict(p["rows"][0], id="conflict", locus="D"),
        dict(p["rows"][0], id="first", locus="missing"),
        dict(p["rows"][0], id="second", locus="missing"),
        dict(p["rows"][0], id="current", locus="A"),
    ]
    result = ca.project_rows(anchors, context)
    assert [row["mapping_status"] for row in result] == [
        "unmatched",
        "ambiguous",
        "identity_conflict",
        "unmatched",
        "unmatched",
        "unique",
    ]
    assert result[3]["group"] == result[4]["group"]
    assert result[0]["group"] != result[3]["group"]
    assert result[1]["current_locus"] is None
    assert result[1]["tu_state"] == result[2]["terminator"] == "mapping-unavailable"
    # An exact legacy alias duplicated in current/legacy rows is one candidate.
    context["aliases"].append(["old-A", "A"])
    assert ca.project_rows([p["rows"][0]], context)[0]["mapping_status"] == "unique"
    a = ca.Components()
    a.union("z", "y")
    a.union("y", "x")
    assert a.root("z") == "x"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(schema="other"),
        lambda p: p["trust"].update(protocol_sha256="0" * 64),
        lambda p: p["rows"][0]["counts"]["control"].__setitem__(0, 99),
        lambda p: p["rows"][0].update(group="invented"),
        lambda p: p["rows"][0].update(exclusion="same_locus"),
        lambda p: p["selected_ids"].reverse(),
        lambda p: p["groups"].clear(),
        lambda p: p["context"]["loci"]["E"].update(tu_ids=[]),
        lambda p: p["context"]["aliases"].append(["oops", "unknown"]),
        lambda p: p["genomes"].update(extra="ACGT"),
        lambda p: p["source_rows"].append(p["source_rows"][0]),
    ],
)
def test_prepared_rehash_still_rejects_mismatches(inputs, mutation):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    report = original_report(p, protocol, manifest)
    mutation(p)
    with pytest.raises(ERRORS):
        evaluated(p, report, protocol, manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(schema_version=True),
        lambda r: r.update(model_host="native UTEX"),
        lambda r: r["inputs"].update(upstream_commit="0" * 40),
        lambda r: r["runtime"].update(producer_sha256="0" * 64),
        lambda r: r["runtime"].update(numpy=None),
        lambda r: r["parameters"].update(max_sites=1),
        lambda r: r["cohort"].update(excluded={"same_locus": 1}),
        lambda r: r["summary"].update(anchors=3),
        lambda r: r["results"].pop(),
        lambda r: r["results"].append(r["results"][0]),
        lambda r: r["results"].reverse(),
        lambda r: r.update(results=[]),
        lambda r: r["results"][0].update(sequence="A" * 128),
        lambda r: r["results"][0]["native_positions"].__setitem__(0, 1),
        lambda r: r["results"][0]["best_native_tss_positions"].__setitem__(0, 1),
        lambda r: r["results"][0]["control"].update(sequence="A" * 128),
        lambda r: r["results"][0]["control"].update(kind="native"),
        lambda r: r["results"][0]["control"].update(identical_to_native=True),
        lambda r: r["results"][0]["control"]["score_curve"].pop(),
        lambda r: r["results"][0]["native"]["score_curve"].__setitem__(
            1, r["results"][0]["native"]["score_curve"][0]
        ),
        lambda r: r["results"][0]["native"]["score_curve"][0].update(offset_nt=-19),
        lambda r: r["results"][0]["native"]["score_curve"][0].update(
            ecoli_model_Tx_rate=0
        ),
        lambda r: r["results"][0]["native"]["score_curve"][0].update(
            ecoli_model_Tx_rate=True
        ),
        lambda r: r["results"][0]["native"]["score_curve"][0].update(dG_total=True),
        lambda r: r["results"][0]["native"].update(best_offsets_nt=[1]),
        lambda r: r["results"][0]["native"].update(anchor_energy_rank_worst=2),
        lambda r: r["results"][0]["control"].update(native_positions=[]),
    ],
)
def test_report_mutations_rehashed(inputs, mutation):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    report = original_report(p, protocol, manifest)
    mutation(report)
    with pytest.raises(ERRORS):
        evaluated(p, report, protocol, manifest)


@pytest.mark.parametrize(
    "name,mutation",
    [
        ("tu", lambda x: x.update(schema="wrong")),
        ("tu", lambda x: x.update(localRelease="wrong")),
        ("tu", lambda x: x["inputs"].clear()),
        ("tu", lambda x: x["loci"].append(x["loci"][0])),
        ("tu", lambda x: x["loci"][0].update(seqid="other")),
        ("tu", lambda x: x["loci"][0].update(state="source-membership-empty")),
        ("tu", lambda x: x["loci"][4].update(tuIds=[])),
        ("tu", lambda x: x["groups"][0].update(linkedLoci=["A"])),
        ("tu", lambda x: x["groups"].append(x["groups"][0])),
        ("terminators", lambda x: x.update(assembly="other")),
        ("terminators", lambda x: x["genes"]["A"].update(featureType="other")),
        ("terminators", lambda x: x["genes"]["A"].update(biotype="other")),
        ("terminators", lambda x: x["genes"].pop("A")),
        ("terminators", lambda x: x["sites"].append(x["sites"][0])),
        ("terminators", lambda x: x["sites"][0].update(id="control:site")),
        (
            "terminators",
            lambda x: x["genes"]["B"]["cdsOverlap"].update(
                sameStrandCallIds=["missing"]
            ),
        ),
        (
            "terminators",
            lambda x: x["genes"]["A"]["cdsOverlap"].update(observedSourceCallCount=1),
        ),
        (
            "terminators",
            lambda x: x["genes"]["C"]["cdsOverlap"].update(completeSourceCallCount=0),
        ),
        ("terminators", lambda x: x["genes"]["D"].update(cdsOverlap={})),
        ("terminators", lambda x: x["genes"]["A"].update(cdsOverlap=None)),
        (
            "terminators",
            lambda x: x["genes"]["B"]["cdsOverlap"].update(
                oppositeStrandCallIds=["native:site"]
            ),
        ),
        ("terminators", lambda x: x["sites"][0].update(strand="-")),
        ("terminators", lambda x: x["sites"][0].update(replicon="other")),
        ("terminators", lambda x: x["verifiedInputs"]["fasta.dat"].update(byteSize=2)),
        (
            "terminators",
            lambda x: x["runs"][0]["sequenceSha256ByReplicon"].update(other="0" * 64),
        ),
        ("terminators", lambda x: x["replicons"][REPLICON].update(length=1)),
        ("terminators", lambda x: x["conversion"]["builder"].update(sha256="1" * 64)),
        ("tu_release", lambda x: x.update(status="pending")),
        ("tu_release", lambda x: x.update(reviews=[])),
        ("tu_release", lambda x: x.update(reviewedImplementation="bad")),
        ("terminators_release", lambda x: x["dataset"].update(schemaVersion=2)),
        ("terminators_release", lambda x: x["payload"].update(bytes=1)),
    ],
)
def test_input_schema_crossfile_failures_after_rehash(inputs, name, mutation):
    root, protocol, manifest, _ = inputs
    change_file(inputs, name, mutation)
    with pytest.raises(ERRORS):
        ca.prepare(root, protocol, manifest)


def test_other_context_states(inputs):
    root, protocol, manifest, data = inputs
    tu = ca.parse_json(data["tu"])
    term = ca.parse_json(data["terminators"])
    tu["loci"][4]["state"] = "unresolved-source-link"
    term["genes"]["C"]["cdsOverlap"]["coverage"] = {
        "status": "none",
        "coveredNt": 0,
        "totalNt": 100,
    }
    context = ca.input_context(tu, term, ca.table(data["crosswalk"], []), manifest)
    assert context["loci"]["E"]["tu_state"] == "unresolved-source-link"
    assert context["loci"]["B"]["terminator"] == "observed"  # despite partial
    assert context["loci"]["C"]["terminator"] == "coverage-incomplete"
    assert context["loci"]["D"]["terminator"] == "not-applicable"
    # Opposite strand calls never create an observed same-strand stratum.
    term["sites"][0]["strand"] = "-"
    term["genes"]["B"]["cdsOverlap"].update(
        sameStrandCallIds=[], oppositeStrandCallIds=["native:site"]
    )
    context = ca.input_context(tu, term, ca.table(data["crosswalk"], []), manifest)
    assert context["loci"]["B"]["terminator"] == "coverage-incomplete"
    # No CDS geometry, even with a protein label, is not an inferred complete zero.
    gene = {"biotype": "protein_coding", "cdsSegments": [], "cdsOverlap": None}
    assert ca.terminator_state(gene, {}) == "not-applicable"
    assert ca.prepare(root, protocol, manifest)["schema"] == ca.PREPARED


@pytest.mark.parametrize("value", [None, ["x", "x"], ["z", "a"], [1], [""]])
def test_unique_strings(value):
    with pytest.raises(ValueError):
        ca.unique_strings(value)


@pytest.mark.parametrize(
    "change",
    [
        {"coveredNt": 101},
        {"totalNt": 0},
        {"status": "none"},
        {"coveredNt": True},
    ],
)
def test_bad_coverage(change):
    with pytest.raises(ValueError):
        ca.coverage({"status": "complete", "coveredNt": 100, "totalNt": 100, **change})


@pytest.mark.parametrize(
    "raw", [b"\tfoo\na\tb\n", b"x\tx\n1\t2\n", b"x\n", b"x\ty\n1\n", b"x\n1\t2\n"]
)
def test_bad_tsv(raw):
    with pytest.raises(ValueError):
        ca.table(raw, ["x"])


@pytest.mark.parametrize(
    "decoded",
    [b"ACGT\n", b">x\nACGN\n", b">x\nACGT\n>x\nACGT\n", b">x\n\n", b">x\nACGT\n"],
)
def test_bad_fasta(decoded):
    with pytest.raises(ValueError):
        ca.fasta(gzip.compress(decoded), {"x": 8})


def test_fasta_bound(monkeypatch):
    monkeypatch.setattr(ca, "MAX_FASTA", 4)
    with pytest.raises(ValueError, match="Decoded"):
        ca.fasta(gzip.compress(b">x\nAAAAA"), {"x": 5})
    with pytest.raises((EOFError, OSError)):
        ca.fasta(b"not gzip", {})


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r[0].update(type="aTSS"),
        lambda r: r[0].update(strand="?"),
        lambda r: r[0].update(position="0"),
        lambda r: r[0].update(position="no"),
        lambda r: r[0].update(locus_tag=""),
        lambda r: r[0].update(replicon="other"),
        lambda r: r[0].update(control_1="-1"),
        lambda r: r[0].update(control_2=True),
        lambda r: r[1].update(tss_id=r[0]["tss_id"]),
        lambda r: r[1].update(position=r[0]["position"]),
    ],
)
def test_source_failures(inputs, mutate):
    p = prepared(inputs)
    rows = p["source_rows"]
    mutate(rows)
    with pytest.raises(ERRORS):
        ca.source_anchors(rows, {REPLICON: 2400}, 4)


def test_read_pins_paths_atomic_and_cleanup(inputs, monkeypatch, capsys):
    root, protocol, manifest, _ = inputs
    path = root / "plain"
    path.write_bytes(b"abc")
    assert ca.read_bytes(path) == b"abc"
    with pytest.raises(ValueError, match="byte limit"):
        ca.read_bytes(path, 2)
    with pytest.raises(ValueError, match="identity"):
        ca.pinned_bytes(path, {"bytes": 3, "sha256": "0" * 64})
    link = root / "link"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        ca.read_bytes(link)
    with pytest.raises(ValueError):
        ca.read_bytes(root)
    out = root / "output.json"
    ca.publish(out, {"z": 1, "a": "é"})
    assert out.read_bytes() == b'{\n  "a": "\\u00e9",\n  "z": 1\n}\n'
    for existing in (out, link):
        with pytest.raises(FileExistsError):
            ca.publish(existing, {})
    assert path.read_bytes() == b"abc"
    assert not list(root.glob(".count-association-*"))
    with pytest.raises(ValueError):
        ca.publish(root / "invalid.json", {"bad": float("inf")})
    assert not (root / "invalid.json").exists()

    def failed_link(*args):
        raise OSError("simulated publication error")

    monkeypatch.setattr(ca.os, "link", failed_link)
    with pytest.raises(OSError):
        ca.publish(root / "failure.json", {})
    assert not list(root.glob(".count-association-*"))
    assert not (root / "failure.json").exists()
    manifest["inputs"]["fasta"]["path"] = "../outside"
    with pytest.raises(ValueError, match="Disallowed"):
        ca.prepare(root, protocol, manifest)
    manifest["inputs"]["fasta"]["path"] = str(path)
    with pytest.raises(ValueError, match="Disallowed"):
        ca.prepare(root, protocol, manifest)
    monkeypatch.setattr(ca, "freezes", lambda: (protocol, manifest))
    assert (
        ca.main(["prepare", "--input-root", str(root), "--output", str(root / "bad")])
        == 2
    )
    assert "Disallowed" in capsys.readouterr().err


def test_cli_success_and_hash_failure(inputs, monkeypatch, capsys):
    root, protocol, manifest, _ = inputs
    monkeypatch.setattr(ca, "freezes", lambda: (protocol, manifest))
    prep = root / "prepared.json"
    assert ca.main(["prepare", "--input-root", str(root), "--output", str(prep)]) == 0
    p = ca.parse_json(prep.read_bytes())
    report = root / "report.json"
    report.write_bytes(ca.canonical(original_report(p, protocol, manifest)))
    output = root / "evaluation.json"
    argv = [
        "evaluate",
        "--prepared",
        str(prep),
        "--prepared-sha256",
        ca.digest(prep.read_bytes()),
        "--report",
        str(report),
        "--report-sha256",
        ca.digest(report.read_bytes()),
        "--output",
        str(output),
    ]
    assert ca.main(argv) == 0
    assert ca.parse_json(output.read_bytes())["primary"]["native"]["value"] == 1.0
    assert ca.main(argv) == 2  # collision preserves bytes
    assert not list(root.glob(".count-association-*"))
    argv[argv.index("--prepared-sha256") + 1] = "0" * 64
    assert ca.main(argv) == 2
    assert "Prepared file hash" in capsys.readouterr().err
    argv[argv.index("--prepared-sha256") + 1] = ca.digest(prep.read_bytes())
    argv[argv.index("--report-sha256") + 1] = "bad"
    assert ca.main(argv) == 2
    assert "Expected lowercase" in capsys.readouterr().err
    argv[argv.index("--report-sha256") + 1] = "0" * 64
    assert ca.main(argv) == 2
    assert "Report file hash" in capsys.readouterr().err


def test_freezes_and_executable_entrypoint(monkeypatch, capsys):
    protocol, manifest = ca.freezes()
    assert ca.digest(ca.canonical(protocol)) == ca.PROTOCOL_SHA256
    assert ca.digest(ca.canonical(manifest)) == ca.MANIFEST_SHA256
    monkeypatch.setattr(sys, "argv", ["count_association.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(ca.__file__, run_name="__main__")
    assert exc.value.code == 0
    assert "prepare" in capsys.readouterr().out
    original = ca.read_bytes
    monkeypatch.setattr(
        ca,
        "read_bytes",
        lambda path: b"{}" if path.name.endswith("protocol.json") else original(path),
    )
    with pytest.raises(ValueError, match="Protocol freeze"):
        ca.freezes()


def test_atomic_open_failure(tmp_path, monkeypatch):
    def no_temp(**kwargs):
        raise OSError("simulated temp creation failure")

    monkeypatch.setattr(ca.tempfile, "NamedTemporaryFile", no_temp)
    with pytest.raises(OSError):
        ca.publish(tmp_path / "absent", {})
    assert list(tmp_path.iterdir()) == []


def test_context_invalid_structure(inputs):
    p = prepared(inputs)
    lengths = {REPLICON: 2400}
    for mutate in (
        lambda x: x["loci"]["A"].update(strand="?"),
        lambda x: x["loci"]["A"].update(tu_state="unknown"),
        lambda x: x["loci"]["A"].update(tu_ids=[]),
        lambda x: x["aliases"].append(["A"]),
        lambda x: x["aliases"].append(["A", "A"]),
        lambda x: x["aliases"].pop(0),
    ):
        context = copy.deepcopy(p["context"])
        mutate(context)
        with pytest.raises(ERRORS):
            ca.validate_context(context, lengths)


def test_negative_energies_all_ties_and_tolerance():
    value = arm(3.0)
    for state in value["score_curve"]:
        state["dG_total"] = -5.0
    value.update(
        best_offsets_nt=list(range(-20, 21)),
        anchor_energy_rank_best=1,
        anchor_energy_rank_worst=41,
        best_distance_min_nt=0,
        best_distance_max_nt=20,
    )
    assert ca.admit_arm(value) == 3.0
    # Source tolerance is absolute, not relative or a best-offset endpoint.
    value["score_curve"][0]["dG_total"] = -5.0 - 5e-13
    assert ca.admit_arm(value) == 3.0
    value["score_curve"][0]["dG_total"] = -5.0 - 2e-12
    with pytest.raises(ValueError, match="best_offsets"):
        ca.admit_arm(value)


def test_zero_count_levels_are_explicit():
    result = ca.analyze([], ca.freezes()[0])
    assert result["strata"]["mapping_status"]["ambiguous"]["n"] == 0
    assert len(result["strata"]["tu_state"]) == 5
    assert len(result["strata"]["terminator"]) == 5
    assert result["primary"]["native"]["reason"] == "fewer-than-minimum-pairs"


def test_write_failure_cleans_temporary(tmp_path, monkeypatch):
    def failed_fsync(fd):
        raise OSError("simulated incomplete write")

    monkeypatch.setattr(ca.os, "fsync", failed_fsync)
    with pytest.raises(OSError):
        ca.publish(tmp_path / "absent.json", {"x": 1})
    assert list(tmp_path.iterdir()) == []


def test_no_clobber_dangling_symlink(tmp_path):
    output = tmp_path / "output"
    output.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        ca.publish(output, {})
    assert output.is_symlink()
    assert not (tmp_path / "absent").exists()
    assert len(list(tmp_path.iterdir())) == 1


def test_prepare_cannot_escape_explicit_root(inputs, tmp_path):
    root, protocol, manifest, _ = inputs
    outside = root.parent / f"{root.name}-outside"
    outside.write_bytes(b"out")
    (root / "escape").symlink_to(outside)
    manifest["inputs"]["fasta"]["path"] = "escape"
    with pytest.raises(ValueError, match="escapes"):
        ca.prepare(root, protocol, manifest)


def test_nonfinite_reports_and_rehashed_duplicate_json(inputs):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    report = original_report(p, protocol, manifest)
    raw = ca.canonical(report)
    prep = ca.canonical(p)
    for bad in (
        b'{"ignored":1,"ignored":2}',
        b'{"unused":NaN}',
        raw.replace(b'"dG_total": 400.0', b'"dG_total": 1e999', 1),
    ):
        with pytest.raises(ValueError, match="Invalid JSON"):
            ca.evaluate(prep, ca.digest(prep), bad, ca.digest(bad), protocol, manifest)


def test_all_synthetic_missing_source_tokens(inputs):
    _, protocol, manifest, _ = inputs
    p = prepared(inputs)
    p["source_rows"][0].update(control_1="NA", dark_2="", high_light_1="12.5")
    p = ca.build_prepared(
        protocol, manifest, p["genomes"], p["source_rows"], p["context"]
    )
    result = evaluated(p, original_report(p, protocol, manifest), protocol, manifest)
    assert result["primary"]["eligible"] == 3
    assert result["conditions"]["control"]["replicate_2"]["eligible"] == 4
    assert result["conditions"]["dark"]["mean"]["eligible"] == 3
    source = next(row for row in result["rows"] if row["id"] == "a")
    assert source["counts"]["high_light"][0] == 12.5
