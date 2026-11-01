"""Original-source pilot parity checker: frozen-fixture success and every failure.

The independent success anchor is the pre-runtime homopolymer fixture: every
41-start curve of a 128-nt poly(A) window has the fixture's minimum state. Other
reports are built from the core itself to exercise plumbing, never as evidence.
"""

import copy
import dataclasses
import hashlib
import json
import math
import random
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.promoter import pilot_parity as pp
from regsite import promoter as p
from regsite import promoter_io

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "benchmarks/promoter/reference-fixtures.json"
FIXTURES_SHA256 = "8ba1cafe98736b723c7ee2148dbf24a345d0c12ec5f5bb233ecbfb808b6aef44"
LOCALIZATION = pp.LOCALIZATION_KEYS
PARAMS = p.load_parameters()
CALIBRATION = p.resolve_calibration("ecoli_mg1655", {"name": p.NATIVE_HOST})


def _homopolymer_state():
    raw = FIXTURES.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURES_SHA256
    case = next(c for c in json.loads(raw)["cases"] if c["id"] == "A200")
    best = min(case["expected_states"], key=lambda s: s["terms"]["dG_total"])
    return best["terms"]["dG_total"], best["Tx_rate"]


A_DG, A_RATE = _homopolymer_state()


def fixture_curve(_sequence):
    return [
        {"offset_nt": o, "dG_total": A_DG, "ecoli_model_Tx_rate": A_RATE}
        for o in pp.OFFSETS
    ]


def core_curve(sequence):
    rows = []
    for offset in pp.OFFSETS:
        site = p.score_site(
            sequence, "+", 87 + offset, PARAMS, CALIBRATION, keep_states=False
        )
        scored = site.selected.to_dict(128, "+", CALIBRATION, elements=False)
        rows.append(
            {
                "offset_nt": offset,
                "dG_total": site.selected.terms["total"],
                "ecoli_model_Tx_rate": scored["relative_transcription_score"],
            }
        )
    return rows


def arm(curve):
    return {
        "score_curve": curve,
        **pp.localization([row["dG_total"] for row in curve]),
    }


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make_case(name, replicon, strand, position, sequence, control, curve=core_curve):
    positions = pp.native_positions(replicon, strand, position)
    native = arm(curve(sequence))
    return {
        "id": name,
        "replicon": replicon,
        "strand": strand,
        "position": position,
        "locus": f"locus-{name}",
        "sequence": sequence,
        "native_positions": positions,
        "sequence_sha256": sha(sequence),
        "native": native,
        "best_native_tss_positions": [
            positions[87 + o] for o in native["best_offsets_nt"]
        ],
        "control": {
            "sequence": control,
            "sequence_sha256": sha(control),
            "kind": pp.CONTROL_KIND,
            "identical_to_native": control == sequence,
            **arm(curve(control)),
        },
    }


def refresh(report):
    """Recompute source-side summaries after a deliberate curve edit."""
    for case in report["results"]:
        for name in pp.ARMS:
            case[name].update(arm(case[name]["score_curve"]))
        case["best_native_tss_positions"] = [
            case["native_positions"][87 + o] for o in case["native"]["best_offsets_nt"]
        ]
    report["summary"] = pp.aggregate(
        report["results"],
        [{a: c[a] for a in pp.ARMS} for c in report["results"]],
    )
    return report


def make_report(cases, max_sites, excluded):
    report = {
        "schema_version": 1,
        "scope": pp.SCOPE,
        "model_host": p.NATIVE_HOST,
        "limitations": ["E. coli calibration is not UTEX calibration"],
        "inputs": copy.deepcopy(pp.SOURCE_INPUTS),
        "runtime": {
            "python": "3.12.0",
            "producer_sha256": pp.PRODUCER_SHA256,
            "numpy": "2",
            "sklearn": "1.5",
            "scipy": "1",
            "Bio": "1.85",
        },
        "parameters": {
            **copy.deepcopy(pp.FIXED_PARAMETERS),
            "max_sites": max_sites,
            "seed": 2973,
        },
        "cohort": {
            "input_anchors": len(cases) + sum(excluded.values()),
            "excluded": dict(excluded),
        },
        "results": copy.deepcopy(cases),
    }
    return refresh(report)


def random_dna(seed):
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(128))


def shuffled(sequence, seed):
    bases = list(sequence)
    random.Random(seed).shuffle(bases)
    return "".join(bases)


HOMOPOLYMER = make_case(
    "A", "NZ_CP006471.1", "+", 5000, "A" * 128, "A" * 128, fixture_curve
)
MIXED = [
    make_case(
        f"m{i}",
        replicon,
        strand,
        position,
        random_dna(i),
        shuffled(random_dna(i), i),
    )
    for i, (replicon, strand, position) in enumerate(
        [
            ("NZ_CP006471.1", "+", 1000),
            ("NZ_CP006472.1", "-", 30),
            ("NZ_CP006473.1", "+", 7830),
        ]
    )
]
SYNTHETIC = make_report([HOMOPOLYMER, *MIXED], 2475, {"same_locus": 2})


def synthetic():
    """Four-case self-consistent report; always a bounded population."""
    return copy.deepcopy(SYNTHETIC)


def run(tmp_path, document, **kwargs):
    raw = document if isinstance(document, bytes) else json.dumps(document).encode()
    path = tmp_path / "reference.json"
    path.write_bytes(raw)
    return pp.check(path, hashlib.sha256(raw).hexdigest(), **kwargs)


def categories(report):
    return {k: v for k, v in report["comparison"]["failures_by_category"].items() if v}


def test_frozen_source_pins():
    assert pp.SOURCE_INPUTS["fasta_sha256"] == (
        "22a2b07881c1099c32454778de0e90b1c40f74f44c0f59e000507106c0deb567"
    )
    assert pp.SOURCE_INPUTS["tss_sha256"] == (
        "d06524cf492aa8f009bf004c596a5d305ac54acbe7537ec98bbc7992ce164bff"
    )
    assert len(pp.SOURCE_INPUTS["prepared_files_sha256"]) == 6
    assert pp.PRODUCER_SHA256 == (
        "7d3440ad5239f216ec072dbaac49b430bbaa17d7b28674e18effadcc131f4766"
    )
    assert pp.REPLICON_LENGTHS == {
        "NZ_CP006471.1": 2690418,
        "NZ_CP006472.1": 46366,
        "NZ_CP006473.1": 7842,
    }
    assert (pp.LENGTH, pp.OFFSETS[0], pp.OFFSETS[-1], pp.LAYOUTS) == (128, -20, 20, 30)
    assert (pp.REL_TOL, pp.ABS_TOL, pp.TIE_ABS_TOL) == (1e-12, 1e-12, 1e-12)


def test_independent_homopolymer_fixture_passes_with_real_core(tmp_path):
    report = run(tmp_path, make_report([HOMOPOLYMER], 1, {}))
    assert report["status"] == "pass"
    assert report["cohort"]["completeness"] == "bounded_sample"
    comparison = report["comparison"]
    assert comparison["failures"] == []
    assert comparison["denominators"] == {
        "cases": 1,
        "arms": 2,
        "positions": 82,
        "numeric_comparisons": 164,
    }
    assert comparison["evaluated"] == {
        "positions": 82,
        "numeric_comparisons": 164,
        "arms_with_reconstructed_localization": 2,
        "reconstructed_cohort_summary": True,
    }
    for field in pp.FIELDS:
        assert comparison["maxima"][field]["abs_diff"] <= 1e-12
        assert comparison["maxima"][field]["rel_diff"] <= 1e-12
    # Hand-derived: all 41 starts tie, so anchor ranks span 1..41.
    native = HOMOPOLYMER["native"]
    assert native["best_offsets_nt"] == list(range(-20, 21))
    assert (native["anchor_energy_rank_best"], native["anchor_energy_rank_worst"]) == (
        1,
        41,
    )
    assert (native["best_distance_min_nt"], native["best_distance_max_nt"]) == (0, 20)


def test_synthetic_report_identities_stay_bounded(tmp_path):
    report = run(tmp_path, synthetic())
    assert report["status"] == "pass"
    assert report["schema"] == "regsite-promoter-pilot-parity-1"
    assert "not biological accuracy" in report["claim"]
    assert report["cohort"] == {
        "completeness": "bounded_sample",
        "max_sites": 2475,
        "seed": 2973,
        "input_anchors": 6,
        "selected": 4,
        "excluded": {"same_locus": 2},
        "strands": {"+": 3, "-": 1},
        "replicons": {"NZ_CP006471.1": 2, "NZ_CP006472.1": 1, "NZ_CP006473.1": 1},
        "ordered_selected_ids_sha256": pp.ordered_ids_sha256(["A", "m0", "m1", "m2"]),
    }
    assert report["comparison"]["denominators"]["positions"] == 328
    assert report["comparison"]["evaluated"]["positions"] == 328
    module = Path(pp.__file__)
    assert report["tool"]["sha256"] == hashlib.sha256(module.read_bytes()).hexdigest()
    reconstruction = report["reconstruction"]
    assert reconstruction["model_identity"] == promoter_io.model_identity(PARAMS)[0]
    assert reconstruction["calibration"]["host_status"] == "calibration_native"
    core = Path(p.__file__)
    assert reconstruction["core_files_sha256"]["regsite/promoter.py"] == (
        hashlib.sha256(core.read_bytes()).hexdigest()
    )
    assert (
        reconstruction["core_files_sha256"]["regsite/data/promoter-parameters-1.json"]
        == hashlib.sha256(
            (core.parent / "data/promoter-parameters-1.json").read_bytes()
        ).hexdigest()
    )
    assert report["reference"]["source_inputs"] == pp.SOURCE_INPUTS
    assert report["reference"]["declared_runtime"]["producer_sha256"] == (
        pp.PRODUCER_SHA256
    )
    assert report["input"]["bytes"] > 0
    assert report["integrity_failure"] is None
    pp.report_bytes(report)  # Finite and serializable.


def test_localization_ties_ranks_and_distances():
    energies = [5.0] * 41
    energies[20] = 1.0  # anchor
    energies[0] = 1.0 + 5e-13  # tied within absolute 1e-12
    energies[40] = 1.0 + 2e-12  # outside the tie tolerance, worse than anchor
    energies[35] = 0.5  # strict best
    assert pp.localization(energies) == {
        "best_offsets_nt": [15],
        "anchor_energy_rank_best": 2,
        "anchor_energy_rank_worst": 3,
        "best_distance_min_nt": 15,
        "best_distance_max_nt": 15,
    }
    energies[35] = 5.0
    assert pp.localization(energies) == {
        "best_offsets_nt": [-20, 0],
        "anchor_energy_rank_best": 1,
        "anchor_energy_rank_worst": 2,
        "best_distance_min_nt": 0,
        "best_distance_max_nt": 20,
    }


def test_native_positions_circular_both_strands():
    plus = pp.native_positions("NZ_CP006473.1", "+", 1)
    assert (plus[0], plus[86], plus[87], plus[88], plus[-1]) == (7756, 7842, 1, 2, 41)
    minus = pp.native_positions("NZ_CP006473.1", "-", 1)
    assert (minus[0], minus[86], minus[87], minus[88], minus[-1]) == (
        88,
        2,
        1,
        7842,
        7803,
    )
    assert len(plus) == len(minus) == 128


def test_aggregate_counts_medians_and_tallies():
    rows = [
        {
            a: {
                "best_distance_min_nt": dmin,
                "best_distance_max_nt": dmax,
                "anchor_energy_rank_best": rank,
                "anchor_energy_rank_worst": rank + 1,
            }
            for a in pp.ARMS
        }
        for dmin, dmax, rank in ((0, 5, 1), (5, 6, 4))
    ]
    cases = [
        {"strand": "+", "replicon": "NZ_CP006471.1"},
        {"strand": "-", "replicon": "NZ_CP006471.1"},
    ]
    summary = pp.aggregate(cases, rows)
    assert summary["anchors"] == 2
    assert summary["strands"] == {"+": 1, "-": 1}
    assert summary["replicons"] == {"NZ_CP006471.1": 2}
    assert summary["native"] == {
        "any_best_within_5nt": 2,
        "all_best_within_5nt": 1,
        "median_anchor_rank_best": 2.5,
        "median_anchor_rank_worst": 3.5,
    }


def test_equal_compares_numbers_by_value_only():
    assert pp._equal(2, 2.0)
    assert not pp._equal(True, 1)
    assert not pp._equal({"+": 1}, {"+": 1.0})
    assert pp._equal({"a": 1, "b": 2}, {"b": 2, "a": 1})


def _set(path, value):
    def mutate(report):
        target = report
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


def _delete(path):
    def mutate(report):
        target = report
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return mutate


def _curve(index, arm_name, transform):
    def mutate(report):
        curve = report["results"][index][arm_name]["score_curve"]
        report["results"][index][arm_name]["score_curve"] = transform(curve)

    return mutate


def _control_sequence(sequence):
    def mutate(report):
        control = report["results"][1]["control"]
        control["sequence"] = sequence
        control["sequence_sha256"] = sha(sequence)

    return mutate


def _recase(index, **changes):
    def mutate(report):
        report["results"][index].update(changes)

    return mutate


def _add_case(case):
    def mutate(report):
        report["results"].append(copy.deepcopy(case))

    return mutate


RESULT = ("results", 2)  # m1: NZ_CP006472.1, minus strand, position 30.
REVERSE = MIXED[0]["sequence"].translate(str.maketrans("ACGT", "TGCA"))[::-1]
INTEGRITY = [
    ("extra top key", _set(("extra",), 1), "object_keys"),
    ("schema bool", _set(("schema_version",), True), "schema_version"),
    ("schema text", _set(("schema_version",), "1"), "schema_version"),
    ("scope", _set(("scope",), "other"), "scope"),
    ("host", _set(("model_host",), "Synechococcus"), "model_host"),
    ("no limitations", _set(("limitations",), []), "limitations"),
    ("limitations type", _set(("limitations",), "x"), "limitations"),
    ("blank limitation", _set(("limitations",), [""]), "invalid_text"),
    ("fasta pin", _set(("inputs", "fasta_sha256"), "0" * 64), "source_pins"),
    (
        "prepared pin",
        _set(("inputs", "prepared_files_sha256", "util.py"), "0" * 64),
        "source_pins",
    ),
    ("runtime keys", _delete(("runtime", "Bio")), "object_keys"),
    ("runtime blank", _set(("runtime", "numpy"), ""), "invalid_text"),
    ("producer", _set(("runtime", "producer_sha256"), "0" * 64), "producer_sha256"),
    (
        "tie tolerance",
        _set(("parameters", "energy_tie_absolute_tolerance"), 1e-11),
        "protocol_parameter",
    ),
    (
        "offset types",
        _set(("parameters", "candidate_offset_range_inclusive"), [-20.0, 20]),
        "protocol_parameter",
    ),
    ("upstream", _set(("parameters", "upstream_nt"), 86), "protocol_parameter"),
    (
        "layouts",
        _set(("parameters", "layouts_per_candidate"), 29),
        "protocol_parameter",
    ),
    ("parameter keys", _delete(("parameters", "seed")), "object_keys"),
    ("max sites zero", _set(("parameters", "max_sites"), 0), "invalid_integer"),
    ("max sites high", _set(("parameters", "max_sites"), 2476), "invalid_integer"),
    ("max sites bool", _set(("parameters", "max_sites"), True), "invalid_integer"),
    ("seed negative", _set(("parameters", "seed"), -1), "invalid_integer"),
    ("cohort keys", _delete(("cohort", "excluded")), "object_keys"),
    ("anchors zero", _set(("cohort", "input_anchors"), 0), "invalid_integer"),
    ("exclusion type", _set(("cohort", "excluded"), []), "exclusion_reasons"),
    ("exclusion name", _set(("cohort", "excluded"), {"other": 2}), "exclusion_reasons"),
    (
        "exclusion zero",
        _set(("cohort", "excluded"), {"same_locus": 0}),
        "invalid_integer",
    ),
    ("cohort total", _set(("cohort", "input_anchors"), 7), "cohort_total"),
    ("results type", _set(("results",), {}), "empty_results"),
    ("summary keys", _delete(("summary", "replicons")), "object_keys"),
    (
        "summary arm keys",
        _delete(("summary", "control", "all_best_within_5nt")),
        "object_keys",
    ),
    ("case extra key", _set((*RESULT, "gene"), "x"), "object_keys"),
    ("case not object", _set(RESULT, []), "object_keys"),
    ("blank id", _set((*RESULT, "id"), ""), "invalid_text"),
    ("locus type", _set((*RESULT, "locus"), 5), "invalid_text"),
    ("replicon", _set((*RESULT, "replicon"), "NZ_CP006474.1"), "unknown_replicon"),
    ("replicon type", _set((*RESULT, "replicon"), []), "unknown_replicon"),
    ("strand", _set((*RESULT, "strand"), "."), "invalid_strand"),
    ("position zero", _set((*RESULT, "position"), 0), "invalid_integer"),
    ("position beyond", _set((*RESULT, "position"), 46367), "invalid_integer"),
    ("position float", _set((*RESULT, "position"), 30.0), "invalid_integer"),
    ("short sequence", _set((*RESULT, "sequence"), "A" * 127), "invalid_sequence"),
    ("lowercase", _set((*RESULT, "sequence"), "a" * 128), "invalid_sequence"),
    ("ambiguous", _set((*RESULT, "sequence"), "N" * 128), "invalid_sequence"),
    (
        "sequence hash",
        _set((*RESULT, "sequence_sha256"), "0" * 64),
        "sequence_hash_mismatch",
    ),
    (
        "native positions",
        lambda r: r["results"][1]["native_positions"].__setitem__(87, 31),
        "native_positions_mismatch",
    ),
    (
        "position shift",
        _set((*RESULT, "position"), 31),
        "native_positions_mismatch",
    ),
    ("strand flip", _set((*RESULT, "strand"), "+"), "native_positions_mismatch"),
    (
        "best native type",
        _set((*RESULT, "best_native_tss_positions"), 1),
        "invalid_best_native",
    ),
    (
        "best native zero",
        _set((*RESULT, "best_native_tss_positions"), [0]),
        "invalid_integer",
    ),
    (
        "best native beyond",
        _set((*RESULT, "best_native_tss_positions"), [46367]),
        "invalid_integer",
    ),
    ("arm keys", _delete((*RESULT, "native", "best_distance_max_nt")), "object_keys"),
    ("curve type", _set((*RESULT, "native", "score_curve"), {}), "invalid_curve"),
    (
        "row keys",
        _curve(1, "native", lambda c: [{**c[0], "extra": 1}, *c[1:]]),
        "object_keys",
    ),
    (
        "duplicate offset",
        _curve(1, "native", lambda c: [c[0], c[0], *c[2:]]),
        "curve_offsets",
    ),
    ("omitted offset", _curve(1, "native", lambda c: c[1:]), "curve_offsets"),
    (
        "extra offset",
        _curve(1, "native", lambda c: [*c, {**c[-1], "offset_nt": 21}]),
        "curve_offsets",
    ),
    ("reordered", _curve(1, "native", lambda c: [c[1], c[0], *c[2:]]), "curve_offsets"),
    (
        "offset float",
        _curve(1, "native", lambda c: [{**c[0], "offset_nt": -20.0}, *c[1:]]),
        "curve_offsets",
    ),
    (
        "energy text",
        _curve(1, "control", lambda c: [{**c[0], "dG_total": "1"}, *c[1:]]),
        "invalid_number",
    ),
    (
        "energy bool",
        _curve(1, "native", lambda c: [{**c[0], "dG_total": False}, *c[1:]]),
        "invalid_number",
    ),
    (
        "energy beyond float",
        _curve(1, "native", lambda c: [{**c[0], "dG_total": 10**400}, *c[1:]]),
        "invalid_number",
    ),
    (
        "rate zero",
        _curve(1, "native", lambda c: [{**c[0], "ecoli_model_Tx_rate": 0}, *c[1:]]),
        "invalid_rate",
    ),
    ("best empty", _set((*RESULT, "native", "best_offsets_nt"), []), "invalid_best"),
    ("best type", _set((*RESULT, "native", "best_offsets_nt"), 0), "invalid_best"),
    (
        "best range",
        _set((*RESULT, "native", "best_offsets_nt"), [21]),
        "invalid_integer",
    ),
    (
        "rank negative",
        _set((*RESULT, "control", "anchor_energy_rank_best"), -1),
        "invalid_integer",
    ),
    (
        "control coordinates",
        _set((*RESULT, "control", "native_positions"), [1]),
        "object_keys",
    ),
    ("control length", _control_sequence("A" * 127), "invalid_sequence"),
    ("control composition", _control_sequence("A" * 128), "control_composition"),
    (
        "control hash",
        _set((*RESULT, "control", "sequence_sha256"), "0" * 64),
        "sequence_hash_mismatch",
    ),
    (
        "control kind",
        _set((*RESULT, "control", "kind"), "dinucleotide"),
        "control_kind",
    ),
    (
        "control flag",
        _set((*RESULT, "control", "identical_to_native"), True),
        "control_identity_flag",
    ),
    (
        "control flag int",
        _set(("results", 0, "control", "identical_to_native"), 1),
        "control_identity_flag",
    ),
    ("duplicate id", _recase(2, id="m0"), "duplicate_id"),
    ("duplicate site", _add_case({**MIXED[0], "id": "dup"}), "duplicate_site"),
    ("duplicate locus", _recase(2, locus="locus-m0"), "duplicate_locus"),
    (
        "reverse-complement window",
        _add_case(
            make_case("rc", "NZ_CP006471.1", "-", 200000, REVERSE, shuffled(REVERSE, 9))
        ),
        "duplicate_window_sequence",
    ),
    (
        "overlapping window",
        _add_case(
            make_case(
                "near",
                "NZ_CP006471.1",
                "-",
                1050,
                random_dna(99),
                shuffled(random_dna(99), 99),
            )
        ),
        "overlapping_window",
    ),
    ("over max sites", _set(("parameters", "max_sites"), 3), "sample_limit"),
    (
        "sample limit short",
        lambda r: r.update(
            parameters={**r["parameters"], "max_sites": 5},
            cohort={"input_anchors": 5, "excluded": {"sample_limit": 1}},
        ),
        "sample_limit",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [case[1:] for case in INTEGRITY],
    ids=[case[0] for case in INTEGRITY],
)
def test_integrity_failures_are_explicit(tmp_path, mutate, code):
    document = synthetic()
    mutate(document)
    report = run(tmp_path, document)
    assert report["status"] == "input_integrity_failure"
    assert report["integrity_failure"]["code"] == code
    assert report["comparison"] is None and report["cohort"] is None
    assert report["input"]["sha256"] is not None


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"a": 1, "a": 2}', "duplicate_key"),
        (b'{"a": NaN}', "nonfinite_number"),
        (b'{"a": -Infinity}', "nonfinite_number"),
        (b'{"a": 1e999}', "nonfinite_number"),
        (b"\xff", "invalid_json"),
        (b"{", "invalid_json"),
        (b"[" * 200000, "invalid_json"),
        (b"[]", "object_keys"),
    ],
)
def test_parse_failures(tmp_path, raw, code):
    report = run(tmp_path, raw)
    assert report["integrity_failure"]["code"] == code


def test_size_limit_and_hash_pin(tmp_path):
    raw = json.dumps(synthetic()).encode()
    oversized = run(tmp_path, raw, max_bytes=len(raw) - 1)
    assert oversized["integrity_failure"] == {"code": "input_too_large", "path": "$"}
    assert oversized["input"]["bytes"] is None and oversized["input"]["sha256"] is None
    assert run(tmp_path, raw, max_bytes=len(raw))["status"] == "pass"
    path = tmp_path / "reference.json"
    report = pp.check(path, "0" * 64)
    assert report["integrity_failure"]["code"] == "input_sha256_mismatch"
    assert report["input"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["input"]["bytes"] == len(raw)


def test_bounded_sample_limit_is_labelled(tmp_path):
    document = make_report([HOMOPOLYMER, *MIXED], 4, {"sample_limit": 3})
    report = run(tmp_path, document)
    assert report["status"] == "pass"
    assert report["cohort"]["completeness"] == "bounded_sample"


def test_numeric_mismatch_is_indexed(tmp_path):
    document = synthetic()
    row = document["results"][2]["control"]["score_curve"][7]
    expected = row["dG_total"] + 1e-9
    row["dG_total"] = expected
    rate = document["results"][3]["native"]["score_curve"][40]
    rate["ecoli_model_Tx_rate"] *= 1 + 1e-9
    report = run(tmp_path, refresh(document))
    assert report["status"] == "parity_failure"
    numeric = [
        f
        for f in report["comparison"]["failures"]
        if f["category"] == "numeric_mismatch"
    ]
    assert [
        (f["source_id"], f["arm"], f["offset_nt"], f["field"]) for f in numeric
    ] == [
        ("m1", "control", -13, "dG_total"),
        ("m2", "native", 20, "ecoli_model_Tx_rate"),
    ]
    assert numeric[0]["reference"] == expected
    assert math.isclose(
        report["comparison"]["maxima"]["dG_total"]["abs_diff"], 1e-9, rel_tol=1e-6
    )
    assert report["comparison"]["evaluated"]["positions"] == 328


def test_within_tolerance_near_tie_stays_visible(tmp_path):
    document = synthetic()
    # |dG| 1.34 gives numeric tolerance 1.34e-12; a 1.2e-12 shift passes
    # numerically but leaves the source tie class at abs 1e-12.
    document["results"][0]["native"]["score_curve"][30]["dG_total"] += 1.2e-12
    report = run(tmp_path, refresh(document))
    assert report["status"] == "parity_failure"
    assert categories(report) == {"reconstructed_summary_mismatch": 3}
    fields = [f["field"] for f in report["comparison"]["failures"]]
    assert fields == [
        "best_offsets_nt",
        "anchor_energy_rank_worst",
        "best_native_tss_positions",
    ]
    first = report["comparison"]["failures"][0]
    assert 10 not in first["reference"] and 10 in first["observed"]


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (
            ("results", 1, "native", "anchor_energy_rank_best"),
            99,
            "anchor_energy_rank_best",
        ),
        (
            ("results", 1, "control", "best_offsets_nt"),
            list(range(-20, 21)),
            "best_offsets_nt",
        ),
        (("results", 1, "native", "best_distance_min_nt"), 21, "best_distance_min_nt"),
        (("results", 1, "best_native_tss_positions"), [1], "best_native_tss_positions"),
    ],
)
def test_case_summary_mutations_fail_both_sides(tmp_path, path, value, field):
    document = synthetic()
    _set(path, value)(document)
    report = run(tmp_path, document)
    failures = report["comparison"]["failures"]
    assert [(f["category"], f["field"], f["source_id"]) for f in failures] == [
        ("source_summary_mismatch", field, "m0"),
        ("reconstructed_summary_mismatch", field, "m0"),
    ]


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (("summary", "anchors"), 5, "summary.anchors"),
        (("summary", "strands"), {"+": 4}, "summary.strands"),
        (("summary", "replicons"), {}, "summary.replicons"),
        (
            ("summary", "native", "any_best_within_5nt"),
            0,
            "summary.any_best_within_5nt",
        ),
        (
            ("summary", "control", "median_anchor_rank_best"),
            1.5,
            "summary.median_anchor_rank_best",
        ),
        (
            ("summary", "native", "all_best_within_5nt"),
            True,
            "summary.all_best_within_5nt",
        ),
    ],
)
def test_cohort_summary_mutations_fail_both_sides(tmp_path, path, value, field):
    document = synthetic()
    _set(path, value)(document)
    report = run(tmp_path, document)
    assert [(f["category"], f["field"]) for f in report["comparison"]["failures"]] == [
        ("source_summary_mismatch", field),
        ("reconstructed_summary_mismatch", field),
    ]


def test_integer_median_equals_float_median(tmp_path):
    document = synthetic()
    summary = document["summary"]["native"]
    summary["median_anchor_rank_best"] = float(summary["median_anchor_rank_best"])
    assert run(tmp_path, document)["status"] == "pass"


def _failing_scorer(failures):
    """Wrap the real kernel; fail only the declared (sequence prefix, start)s."""

    def scorer(sequence, strand, start, params, calibration, *, keep_states):
        site = p.score_site(
            sequence, strand, start, params, calibration, keep_states=keep_states
        )
        kind = failures.get((sequence[:12], start - 87))
        if kind == "raise":
            raise RuntimeError("kernel crashed")
        if kind == "coverage":
            return dataclasses.replace(site, state_count=29)
        if kind == "status":
            return dataclasses.replace(
                site, status="failed", reason="nonfinite_arithmetic", selected=None
            )
        if kind == "overflow":
            terms = {**site.selected.terms, "total": -1e6}
            return dataclasses.replace(
                site, selected=dataclasses.replace(site.selected, terms=terms)
            )
        return site

    return scorer


def test_kernel_failures_are_retained_not_dropped(tmp_path):
    native = MIXED[0]["sequence"][:12]
    control = MIXED[1]["control"]["sequence"][:12]
    scorer = _failing_scorer(
        {
            (native, -20): "raise",
            (native, 0): "coverage",
            (native, 20): "status",
            (control, 5): "overflow",
        }
    )
    report = run(tmp_path, synthetic(), scorer=scorer)
    comparison = report["comparison"]
    assert report["status"] == "parity_failure"
    assert categories(report) == {"calculation_failure": 4}
    assert [
        (f["source_id"], f["arm"], f["offset_nt"], f["detail"])
        for f in comparison["failures"]
    ] == [
        ("m0", "native", -20, "kernel_exception:RuntimeError"),
        ("m0", "native", 0, "state_coverage:29"),
        ("m0", "native", 20, "kernel_status:failed:nonfinite_arithmetic"),
        ("m1", "control", 5, "score_status:overflow"),
    ]
    assert comparison["denominators"]["positions"] == 328
    assert comparison["evaluated"] == {
        "positions": 324,
        "numeric_comparisons": 648,
        "arms_with_reconstructed_localization": 6,
        "reconstructed_cohort_summary": False,
    }


def test_zero_reference_energy_has_no_relative_difference(tmp_path):
    def zero(sequence, strand, start, params, calibration, *, keep_states):
        site = p.score_site(
            sequence, strand, start, params, calibration, keep_states=keep_states
        )
        terms = {**site.selected.terms, "total": 0.0}
        return dataclasses.replace(
            site, selected=dataclasses.replace(site.selected, terms=terms)
        )

    def flat(_sequence):
        return [
            {"offset_nt": o, "dG_total": 0.0, "ecoli_model_Tx_rate": 42.0}
            for o in pp.OFFSETS
        ]

    case = make_case(
        "z", "NZ_CP006471.1", "+", 9000, random_dna(5), random_dna(5), flat
    )
    report = run(tmp_path, make_report([case], 1, {}), scorer=zero)
    assert report["status"] == "pass"
    maxima = report["comparison"]["maxima"]
    assert maxima["dG_total"] == {
        "abs_diff": 0.0,
        "rel_diff": None,
        "abs_diff_overflow": 0,
        "rel_diff_overflow": 0,
        "rel_diff_zero_reference": 82,
    }
    assert maxima["ecoli_model_Tx_rate"]["rel_diff"] <= 1e-15


def test_cli_pass_is_deterministic_and_never_overwrites(tmp_path, capsys):
    raw = json.dumps(synthetic()).encode()
    reference = tmp_path / "reference.json"
    reference.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for output in (first, second):
        argv = [
            "--reference",
            str(reference),
            "--sha256",
            digest,
            "--output",
            str(output),
            "--allow-bounded-cohort",
        ]
        assert pp.main(argv) == 0
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_bytes())["status"] == "pass"
    assert json.loads(capsys.readouterr().out.splitlines()[0])["status"] == "pass"
    before = first.read_bytes()
    argv = ["--reference", str(reference), "--sha256", digest, "--output", str(first)]
    assert pp.main(argv) == 2
    assert first.read_bytes() == before
    argv[-1] = str(reference)
    assert pp.main(argv) == 2
    assert reference.read_bytes() == raw
    dangling = tmp_path / "dangling.json"
    dangling.symlink_to(tmp_path / "missing-target.json")
    argv[-1] = str(dangling)
    assert pp.main(argv) == 2
    assert not (tmp_path / "missing-target.json").exists()


def _cli(directory, document, *extra):
    directory.mkdir()
    raw = json.dumps(document).encode()
    reference = directory / "reference.json"
    reference.write_bytes(raw)
    output = directory / "report.json"
    code = pp.main(
        [
            "--reference",
            str(reference),
            "--sha256",
            hashlib.sha256(raw).hexdigest(),
            "--output",
            str(output),
            *extra,
        ]
    )
    return code, json.loads(output.read_bytes())


def test_cli_exit_codes(tmp_path, capsys):
    bounded = make_report([HOMOPOLYMER], 1, {})
    assert _cli(tmp_path / "a", bounded)[0] == 3
    assert "Bounded cohort" in capsys.readouterr().err
    assert _cli(tmp_path / "b", bounded, "--allow-bounded-cohort")[0] == 0
    mismatch = synthetic()
    mismatch["summary"]["anchors"] = 9
    assert _cli(tmp_path / "c", mismatch)[0] == 1
    broken = synthetic()
    broken["scope"] = "other"
    code, report = _cli(tmp_path / "d", broken)
    assert code == 2 and report["integrity_failure"]["code"] == "scope"


def test_cli_setup_errors(tmp_path, monkeypatch, capsys):
    output = tmp_path / "report.json"
    argv = [
        "--reference",
        str(tmp_path / "missing.json"),
        "--sha256",
        "0" * 64,
        "--output",
        str(output),
    ]
    assert pp.main(argv) == 2
    assert not output.exists()
    assert "failed to run" in capsys.readouterr().err

    def broken():
        raise p.ParameterError("tampered")

    monkeypatch.setattr(p, "load_parameters", broken)
    (tmp_path / "missing.json").write_text("{}")
    assert pp.main(argv) == 2
    assert not output.exists()
    with pytest.raises(SystemExit) as exc:
        pp.main([*argv[:3], "ABC", *argv[4:]])
    assert exc.value.code == 2


@pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")
def test_module_entry_point(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["pilot_parity", "--reference", str(tmp_path / "x"), "--sha256", "0" * 64]
        + ["--output", str(output)],
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("experiments.promoter.pilot_parity", run_name="__main__")
    assert exc.value.code == 2


# Synthetic roster identity; explicit expected hash of '["x", "y", "z"]'.
ROSTER = ["x", "y", "z"]
ROSTER_SHA256 = "567a648207b52b5108eb64cb246c1b20eb4347c1f39ba0752ece72883d1c2904"
ROSTER_COHORT = {
    "input_anchors": 5,
    "selected": 3,
    "excluded": {"same_locus": 2},
    "strands": {"+": 3},
    "replicons": {"NZ_CP006471.1": 3},
    "ordered_selected_ids_sha256": ROSTER_SHA256,
}


def roster_identity(ids, **changes):
    return {
        **ROSTER_COHORT,
        "selected": len(ids),
        "ordered_selected_ids_sha256": pp.ordered_ids_sha256(ids),
        **changes,
    }


def test_full_cohort_pin_is_the_input_only_receipt():
    assert pp.FULL_COHORT == {
        "input_anchors": 2475,
        "selected": 1597,
        "excluded": {
            "identical_or_reverse_complement_window": 1,
            "overlapping_window": 264,
            "same_locus": 613,
        },
        "strands": {"+": 823, "-": 774},
        "replicons": {"NZ_CP006471.1": 1580, "NZ_CP006472.1": 17},
        "ordered_selected_ids_sha256": (
            "da8dab4627396d7ffe75aa120a438a01925fb9447438f785cbf210015ebb1923"
        ),
    }
    assert 1597 + sum(pp.FULL_COHORT["excluded"].values()) == 2475


def test_ordered_id_serialization_is_exact():
    assert pp.ordered_ids_sha256(ROSTER) == ROSTER_SHA256
    assert pp.ordered_ids_sha256(["é"]) == (
        "d8f81e7a2fa1455720e881bd1d164699bdc9bd7dd91641754a2ead7107c1ea0a"
    )


def test_classify_exact_roster_as_full():
    identity = roster_identity(ROSTER)
    assert pp.classify_cohort(2475, identity, ROSTER_COHORT) == "full_eligible"


@pytest.mark.parametrize(
    "identity",
    [
        roster_identity(["x", "y"]),  # truncated
        roster_identity(["y", "x", "z"]),  # reordered
        roster_identity(["x", "y", "y"]),  # duplicated
        roster_identity(["x"], selected=3),  # roster replaced, count kept
        roster_identity(ROSTER, excluded={"same_locus": 1, "sample_limit": 1}),
        roster_identity(ROSTER, strands={"+": 2, "-": 1}),
        roster_identity(ROSTER, replicons={"NZ_CP006472.1": 3}),
    ],
    ids=[
        "truncated",
        "reordered",
        "duplicate",
        "replaced",
        "excluded",
        "strands",
        "replicons",
    ],
)
def test_complete_claim_with_other_roster_is_refused(identity):
    with pytest.raises(pp.IntegrityError) as exc:
        pp.classify_cohort(2475, identity, ROSTER_COHORT)
    assert exc.value.code == "full_cohort_identity"


def test_classify_without_complete_claim_is_bounded():
    exact = roster_identity(ROSTER)
    assert pp.classify_cohort(2474, exact, ROSTER_COHORT) == "bounded_sample"
    other_total = roster_identity(["x"], input_anchors=1)
    assert pp.classify_cohort(2475, other_total, ROSTER_COHORT) == "bounded_sample"


def test_one_case_report_cannot_pass_as_full_pilot(tmp_path, capsys):
    # Review probe: one internally valid case at the 2475-site ceiling.
    code, report = _cli(tmp_path / "small", make_report([HOMOPOLYMER], 2475, {}))
    assert code == 3
    assert report["status"] == "pass"
    assert report["cohort"]["completeness"] == "bounded_sample"
    assert "Bounded cohort" in capsys.readouterr().err
    # The same case claiming the complete 2475-anchor population is refused.
    claim = make_report([HOMOPOLYMER], 2475, {"same_locus": 2474})
    code, report = _cli(tmp_path / "claim", claim)
    assert code == 2
    assert report["integrity_failure"] == {
        "code": "full_cohort_identity",
        "path": "cohort",
    }


@pytest.mark.parametrize(
    ("observed", "expected", "result"),
    [
        (1.0, 1.0, (0.0, 0.0, None)),
        (0.5, 0.0, (0.5, None, "rel_diff_zero_reference")),
        (-1.0, 5e-324, (1.0, None, "rel_diff_overflow")),
        (-sys.float_info.max, sys.float_info.max, (None, None, "abs_diff_overflow")),
        (-1.0, -sys.float_info.max, (sys.float_info.max, 1.0, None)),
    ],
)
def test_difference_diagnostics_stay_finite(observed, expected, result):
    assert pp.differences(observed, expected) == result


@pytest.mark.parametrize("field", pp.FIELDS)
def test_cli_subnormal_reference_keeps_indexed_failure(tmp_path, field):
    document = make_report([HOMOPOLYMER], 1, {})
    document["results"][0]["native"]["score_curve"][0][field] = 5e-324
    code, report = _cli(tmp_path / field, refresh(document))
    assert code == 1
    assert report["status"] == "parity_failure"
    comparison = report["comparison"]
    numeric = [f for f in comparison["failures"] if f["category"] == "numeric_mismatch"]
    assert numeric == [
        {
            "category": "numeric_mismatch",
            "source_id": "A",
            "arm": "native",
            "offset_nt": -20,
            "field": field,
            "reference": 5e-324,
            "observed": numeric[0]["observed"],
            "detail": "rel_diff_overflow",
        }
    ]
    assert comparison["evaluated"]["positions"] == 82
    assert comparison["denominators"]["numeric_comparisons"] == 164
    assert comparison["maxima"][field]["rel_diff_overflow"] == 1
    assert comparison["maxima"][field]["rel_diff"] <= 1e-12


def test_serializer_failure_creates_no_output(tmp_path, monkeypatch, capsys):
    def broken(_report):
        raise ValueError("Out of range float values are not JSON compliant")

    monkeypatch.setattr(pp, "report_bytes", broken)
    raw = json.dumps(make_report([HOMOPOLYMER], 1, {})).encode()
    reference = tmp_path / "reference.json"
    reference.write_bytes(raw)
    output = tmp_path / "report.json"
    digest = hashlib.sha256(raw).hexdigest()
    argv = ["--reference", str(reference), "--sha256", digest]
    assert pp.main([*argv, "--output", str(output)]) == 2
    assert not output.exists()
    assert "failed to run" in capsys.readouterr().err


def test_cli_exact_frozen_identity_exits_full(tmp_path, monkeypatch):
    """Exit path only: the pin is replaced by this synthetic report's identity."""
    document = synthetic()
    cases = document["results"]
    identity = pp.cohort_identity(cases, 6, {"same_locus": 2})
    monkeypatch.setattr(pp, "FULL_COHORT", {**identity, "input_anchors": 6})
    code, report = _cli(tmp_path / "pinned", document)
    assert code == 0
    assert report["cohort"]["completeness"] == "full_eligible"


def test_absolute_difference_overflow_keeps_indexed_mismatch(tmp_path):
    """Deliberately mocked extreme kernel value against a finite extreme reference."""
    extreme = SimpleNamespace(
        state_count=30,
        status="ok",
        reason=None,
        selected=SimpleNamespace(
            terms={"total": -sys.float_info.max},
            to_dict=lambda *args, **kwargs: {
                "score_status": "ok",
                "relative_transcription_score": A_RATE,
            },
        ),
    )

    def scorer(sequence, strand, start, params, calibration, *, keep_states):
        if start == 87 - 20:
            return extreme
        return p.score_site(
            sequence, strand, start, params, calibration, keep_states=keep_states
        )

    document = make_report([HOMOPOLYMER], 1, {})
    for name in pp.ARMS:
        document["results"][0][name]["score_curve"][0]["dG_total"] = sys.float_info.max
    report = run(tmp_path, refresh(document), scorer=scorer)
    comparison = report["comparison"]
    numeric = [f for f in comparison["failures"] if f["category"] == "numeric_mismatch"]
    assert [(f["arm"], f["offset_nt"], f["detail"]) for f in numeric] == [
        ("native", -20, "abs_diff_overflow"),
        ("control", -20, "abs_diff_overflow"),
    ]
    assert comparison["maxima"]["dG_total"]["abs_diff_overflow"] == 2
    assert comparison["evaluated"]["positions"] == 82
    pp.report_bytes(report)  # Remains finite and serializable.
