"""Offline structural contract tests; no runtime imports, scoring or folding.

Schema acceptance cannot establish relational organization, strict JSON transport,
genuine integer wire types, projection fit or successful prediction.
"""

import copy
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
SCHEMA = json.loads(
    (SCHEMAS / "supplied-transcript-request-1.schema.json").read_text("utf-8")
)
SIBLINGS = ("promoter-request-1.0.schema.json", "rbs-request-1.0.schema.json")


def no_retrieval(uri):
    """Never use network or filesystem fallback for unresolved references."""
    raise NoSuchResource(ref=uri)


REGISTRY = Registry(retrieve=no_retrieval).with_resources(
    (name, Resource.from_contents(json.loads((SCHEMAS / name).read_text("utf-8"))))
    for name in SIBLINGS
)
VALIDATOR = Draft202012Validator(SCHEMA, registry=REGISTRY)
PROFILES = (
    "historical",
    "salis-v1-rnastructure-6.6-reconstruction-1",
    "footprint2017",
    "footprint2017-rnastructure-6.6-reconstruction-1",
    "context2017",
    "context2017-rnastructure-6.6-reconstruction-1",
    "standby2014",
    "standby2014-rnastructure-6.6-reconstruction-1",
    "joint_standby",
    "joint-standby-rnastructure-6.6-reconstruction-1",
)
OBJECT_FIELDS = (
    ((), "schema_version id sequence transcript cds rbs promoter projection settings"),
    (("transcript",), "id range provenance"),
    (("transcript", "provenance"), "kind reference"),
    (("cds", 0), "id range provenance"),
    (("cds", 0, "provenance"), "kind reference"),
    (("rbs",), "profile anti_sd temperature_c host"),
    (("promoter",), "calibration host scan"),
    (("promoter", "host"), "name"),
    (("promoter", "scan"), "mode positions"),
    (("promoter", "scan", "positions", 0), "strand tss"),
    (
        ("projection",),
        "contig origin contig_length sequence_strand topology origin_crossing",
    ),
    (("settings",), "seconds_per_rbs_record seconds_per_promoter_record seconds_total"),
)
ID_PATHS = (("id",), ("transcript", "id"), ("cds", 0, "id"))
REFERENCE_PATHS = (
    ("transcript", "provenance", "reference"),
    ("cds", 0, "provenance", "reference"),
)
INTEGER_PATHS = (
    ("transcript", "range", 0),
    ("transcript", "range", 1),
    ("cds", 0, "range", 0),
    ("cds", 0, "range", 1),
    ("promoter", "scan", "positions", 0, "tss"),
    ("projection", "origin"),
    ("projection", "contig_length"),
    ("promoter", "host", "taxon_id"),
)
NUMBER_PATHS = (
    ("rbs", "temperature_c"),
    ("settings", "seconds_per_rbs_record"),
    ("settings", "seconds_per_promoter_record"),
    ("settings", "seconds_total"),
)


def at(document, path):
    for key in path:
        document = document[key]
    return document


def request():
    """Populate every object variant without scientific or runtime assumptions."""
    document = json.loads(
        (ROOT / "examples/supplied-transcript-incompatible.json").read_text("utf-8")
    )
    document["promoter"]["host"] = {"name": "Example host", "taxon_id": 562}
    document["rbs"]["host"] = "Example host (configuration only)"
    return document


def changed(path, value):
    document = request()
    at(document, path[:-1])[path[-1]] = value
    return document


def positions(count):
    return {
        "mode": "positions",
        "positions": [{"strand": "+", "tss": index} for index in range(count)],
    }


def scan_range():
    return {"mode": "scan", "range": [0, 2], "strands": ["+", "-"]}


def test_schema_dialect_and_all_references_are_local():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def check(node):
        if isinstance(node, dict):
            if "$ref" in node:
                assert node["$ref"].split("#")[0] in ("", *SIBLINGS)
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(SCHEMA)


@pytest.mark.parametrize("name", ["single", "two-cds", "incompatible"])
def test_supported_examples(name):
    document = json.loads(
        (ROOT / f"examples/supplied-transcript-{name}.json").read_text("utf-8")
    )
    VALIDATOR.validate(document)


def test_nested_sibling_references_resolve_without_retrieval():
    document = request()
    VALIDATOR.validate(document)
    document["promoter"]["scan"] = scan_range()
    VALIDATOR.validate(document)
    with pytest.raises(Unresolvable):
        Draft202012Validator(SCHEMA, registry=Registry(retrieve=no_retrieval)).validate(
            document
        )


@pytest.mark.parametrize(
    "path,field",
    [(path, field) for path, fields in OBJECT_FIELDS for field in fields.split()],
)
def test_every_required_object_key(path, field):
    document = request()
    del at(document, path)[field]
    assert not VALIDATOR.is_valid(document)


@pytest.mark.parametrize("field", ["mode", "range", "strands"])
def test_scan_variant_requires_every_key(field):
    scan = scan_range()
    del scan[field]
    assert not VALIDATOR.is_valid(changed(("promoter", "scan"), scan))


@pytest.mark.parametrize("path,fields", OBJECT_FIELDS)
def test_every_object_rejects_extra_fields(path, fields):
    document = request()
    at(document, path)["unexpected"] = True
    assert not VALIDATOR.is_valid(document)


def test_scan_variant_rejects_extra_fields():
    assert not VALIDATOR.is_valid(
        changed(("promoter", "scan"), {**scan_range(), "positions": []})
    )


@pytest.mark.parametrize("path,fields", OBJECT_FIELDS)
@pytest.mark.parametrize("value", [False, 0, 1.5, "object", []])
def test_object_types(path, fields, value):
    document = changed(path, value) if path else value
    assert not VALIDATOR.is_valid(document)


@pytest.mark.parametrize("path,fields", OBJECT_FIELDS)
def test_only_host_and_projection_objects_may_be_null(path, fields):
    document = changed(path, None) if path else None
    assert VALIDATOR.is_valid(document) == (
        path in (("projection",), ("promoter", "host"))
    )


@pytest.mark.parametrize("path", ID_PATHS + REFERENCE_PATHS)
@pytest.mark.parametrize(
    "value", [None, True, 1, [], {}, "", "bad\n", "\x00bad", "x\x7f", "x\x85"]
)
def test_identifiers_and_provenance_reject_invalid_text(path, value):
    assert not VALIDATOR.is_valid(changed(path, value))


@pytest.mark.parametrize(
    "path,limit",
    [(path, 128) for path in ID_PATHS] + [(path, 1024) for path in REFERENCE_PATHS],
)
def test_text_length_boundaries_and_unicode(path, limit):
    for value in ("a", "é" * limit, "spaces and punctuation / : .", "x\u2028y"):
        VALIDATOR.validate(changed(path, value))
    assert not VALIDATOR.is_valid(changed(path, "a" * (limit + 1)))


@pytest.mark.parametrize("parent", [("transcript",), ("cds", 0)])
@pytest.mark.parametrize(
    "kind", ["user_supplied", "annotation", "measured", "synthetic"]
)
def test_provenance_variants(parent, kind):
    VALIDATOR.validate(changed((*parent, "provenance", "kind"), kind))


@pytest.mark.parametrize("parent", [("transcript",), ("cds", 0)])
@pytest.mark.parametrize("kind", [None, True, 1, [], {}, "", "unknown", "Synthetic"])
def test_unknown_provenance_kinds(parent, kind):
    assert not VALIDATOR.is_valid(changed((*parent, "provenance", "kind"), kind))


@pytest.mark.parametrize("value", ["A", "ACGT", "T" * 5000])
def test_sequence_boundaries(value):
    VALIDATOR.validate(changed(("sequence",), value))


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        [],
        {},
        "",
        "A" * 5001,
        "acgt",
        "ACGU",
        "ACGN",
        " ACGT",
        "ACGT\n",
        "AC\tGT",
        "ＡＣＧＴ",
    ],
)
def test_sequence_is_strict_uppercase_dna(value):
    assert not VALIDATOR.is_valid(changed(("sequence",), value))


@pytest.mark.parametrize("profile", PROFILES)
def test_supported_rbs_profiles_and_model_ids(profile):
    VALIDATOR.validate(changed(("rbs", "profile"), profile))


@pytest.mark.parametrize(
    "profile", [None, False, 1, [], {}, "", "HISTORICAL", "learned", "unknown"]
)
def test_unsupported_rbs_profiles(profile):
    assert not VALIDATOR.is_valid(changed(("rbs", "profile"), profile))


@pytest.mark.parametrize("value", ["A" * 9, "U" * 9, "ACCUCCUUA"])
def test_anti_sd_is_nine_uppercase_rna_bases(value):
    VALIDATOR.validate(changed(("rbs", "anti_sd"), value))


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        [],
        {},
        "",
        "A" * 8,
        "A" * 10,
        "accuccuua",
        "ACCTCCTTA",
        "ACCUCCUUN",
        "ACCUCCUU\n",
        "ACCUCCUUA\n",
    ],
)
def test_anti_sd_has_no_normalization(value):
    assert not VALIDATOR.is_valid(changed(("rbs", "anti_sd"), value))


@pytest.mark.parametrize("value", [None, "x", "x" * 128])
def test_rbs_host_variants(value):
    VALIDATOR.validate(changed(("rbs", "host"), value))


@pytest.mark.parametrize("value", [True, 1, [], {}, "", "x" * 129])
def test_rbs_host_rejections(value):
    assert not VALIDATOR.is_valid(changed(("rbs", "host"), value))


@pytest.mark.parametrize(
    "value", [None, {"name": "x"}, {"name": "x" * 200, "taxon_id": 1}]
)
def test_promoter_host_variants(value):
    VALIDATOR.validate(changed(("promoter", "host"), value))


@pytest.mark.parametrize(
    "value",
    [
        "host",
        {},
        {"taxon_id": 1},
        {"name": ""},
        {"name": "x" * 201},
        {"name": None},
        {"name": False},
        {"name": []},
        {"name": {}},
        {"name": "x", "taxon_id": None},
        {"name": "x", "taxon_id": 0},
        {"name": "x", "extra": 1},
    ],
)
def test_promoter_host_taxon_is_omitted_rather_than_null(value):
    assert not VALIDATOR.is_valid(changed(("promoter", "host"), value))


@pytest.mark.parametrize("path", INTEGER_PATHS)
@pytest.mark.parametrize(
    "value", [None, True, False, -1, 1.5, "1", [], {}, math.inf, -math.inf]
)
def test_coordinates_and_taxon_require_nonnegative_integers(path, value):
    assert not VALIDATOR.is_valid(changed(path, value))


@pytest.mark.parametrize(
    "path", [("projection", "contig_length"), ("promoter", "host", "taxon_id")]
)
def test_lengths_and_taxon_require_positive_integers(path):
    assert not VALIDATOR.is_valid(changed(path, 0))
    VALIDATOR.validate(changed(path, 1))


@pytest.mark.parametrize("path", NUMBER_PATHS)
@pytest.mark.parametrize(
    "value", [None, True, False, "1", [], {}, -1, math.inf, -math.inf]
)
def test_budgets_and_temperature_require_bounded_numbers(path, value):
    assert not VALIDATOR.is_valid(changed(path, value))


@pytest.mark.parametrize(
    "path,ceiling",
    [
        (NUMBER_PATHS[0], 100),
        (NUMBER_PATHS[1], 120),
        (NUMBER_PATHS[2], 120),
        (NUMBER_PATHS[3], 240),
    ],
)
def test_numeric_endpoints(path, ceiling):
    for value in (0.001, 1, 1.0, ceiling, float(ceiling)):
        VALIDATOR.validate(changed(path, value))
    assert VALIDATOR.is_valid(changed(path, 0)) == (path == NUMBER_PATHS[0])
    assert not VALIDATOR.is_valid(changed(path, ceiling + 0.001))


@pytest.mark.parametrize("path", NUMBER_PATHS)
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_tokens_require_strict_json_transport(path, value):
    document = changed(path, value)
    with pytest.raises(ValueError):
        json.dumps(document, allow_nan=False)
    if not math.isnan(value):
        assert not VALIDATOR.is_valid(document)


@pytest.mark.parametrize("path", [("transcript", "range"), ("cds", 0, "range")])
@pytest.mark.parametrize("value", [None, True, 1, "0,1", {}, [], [0], [0, 1, 2]])
def test_annotation_range_shape(path, value):
    assert not VALIDATOR.is_valid(changed(path, value))


@pytest.mark.parametrize("count", [1, 10])
def test_cds_list_bounds_and_order_preserved(count):
    document = request()
    template = document["cds"][0]
    document["cds"] = [
        {**copy.deepcopy(template), "id": f"cds-{i}", "range": [i, i + 3]}
        for i in range(count)
    ]
    original = copy.deepcopy(document)
    VALIDATOR.validate(document)
    assert document == original


@pytest.mark.parametrize("value", [None, True, 1, "cds", {}, [], [None], [{}]])
def test_cds_list_type_and_minimum(value):
    assert not VALIDATOR.is_valid(changed(("cds",), value))


def test_eleven_cds_annotations_are_rejected():
    assert not VALIDATOR.is_valid(changed(("cds",), request()["cds"][:1] * 11))


@pytest.mark.parametrize("calibration", ["ecoli_mg1655", "in_vitro"])
def test_promoter_calibrations(calibration):
    VALIDATOR.validate(changed(("promoter", "calibration"), calibration))


@pytest.mark.parametrize("calibration", [None, True, 1, [], {}, "", "unknown"])
def test_promoter_requires_supported_calibration(calibration):
    assert not VALIDATOR.is_valid(changed(("promoter", "calibration"), calibration))


@pytest.mark.parametrize("count", [0, 1, 512])
def test_explicit_scan_cap_and_empty_roster(count):
    VALIDATOR.validate(changed(("promoter", "scan"), positions(count)))


def test_wrapper_scan_cap_narrows_the_native_schema():
    scan = positions(513)
    native = json.loads((SCHEMAS / SIBLINGS[0]).read_text("utf-8"))
    Draft202012Validator(native).validate(
        {"id": "native", "sequence": "A" * 1000, "scan": scan}
    )
    assert not VALIDATOR.is_valid(changed(("promoter", "scan"), scan))


@pytest.mark.parametrize(
    "scan",
    [
        scan_range(),
        {"mode": "scan", "range": [0, 0], "strands": ["-"]},
        {
            "mode": "positions",
            "positions": [{"strand": "-", "tss": 0}, {"strand": "+", "tss": 0}],
        },
    ],
)
def test_scan_variants_and_both_strands(scan):
    VALIDATOR.validate(changed(("promoter", "scan"), scan))


@pytest.mark.parametrize(
    "scan",
    [
        {},
        {"mode": "unknown"},
        {"mode": "positions", "positions": None},
        {"mode": "positions", "positions": {}},
        {"mode": "positions", "positions": [1]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": 0}] * 2},
        {"mode": "positions", "positions": [{"strand": "?", "tss": 0}]},
        {"mode": "positions", "positions": [], "range": [0, 0]},
        *[
            {**scan_range(), "range": value}
            for value in (None, {}, [], [0], [0, 1, 2], [False, 1], [0, -1], [0, 1.5])
        ],
        *[
            {**scan_range(), "strands": value}
            for value in (None, "+", [], ["+", "+"], ["?"], [True], ["+", "-", "+"])
        ],
    ],
)
def test_invalid_scan_shapes_and_duplicate_points(scan):
    assert not VALIDATOR.is_valid(changed(("promoter", "scan"), scan))


@pytest.mark.parametrize(
    "topology,strand,crossing",
    [
        ("linear", "+", False),
        ("linear", "-", False),
        ("circular", "+", False),
        ("circular", "-", True),
    ],
)
def test_projection_variants(topology, strand, crossing):
    projection = request()["projection"]
    projection.update(
        topology=topology, sequence_strand=strand, origin_crossing=crossing
    )
    VALIDATOR.validate(changed(("projection",), projection))


@pytest.mark.parametrize(
    "field,value",
    [
        ("contig", ""),
        ("contig", "x" * 129),
        ("contig", None),
        ("contig", 1),
        ("contig", []),
        ("sequence_strand", "?"),
        ("sequence_strand", None),
        ("topology", "unknown"),
        ("topology", None),
        ("origin_crossing", 0),
        ("origin_crossing", "false"),
        ("origin_crossing", None),
    ],
)
def test_projection_field_types(field, value):
    assert not VALIDATOR.is_valid(changed(("projection", field), value))


def test_projection_contig_boundary_and_linear_crossing():
    VALIDATOR.validate(changed(("projection", "contig"), "x" * 128))
    assert not VALIDATOR.is_valid(changed(("projection", "topology"), "linear"))


@pytest.mark.parametrize(
    "path,field",
    [
        ((), "metadata"),
        ((), "defaults"),
        (("rbs",), "strand"),
        (("rbs",), "start_positions"),
        (("promoter",), "output"),
        (("promoter",), "metadata"),
        (("promoter",), "positions"),
        (("transcript",), "strand"),
        (("cds", 0), "sequence"),
    ],
)
def test_native_controls_cannot_override_wrapper_contract(path, field):
    document = request()
    at(document, path)[field] = {}
    assert not VALIDATOR.is_valid(document)


@pytest.mark.parametrize(
    "value", [None, True, 1, [], {}, "1", "supplied-transcript-request-2"]
)
def test_exact_schema_version(value):
    assert not VALIDATOR.is_valid(changed(("schema_version",), value))


@pytest.mark.parametrize(
    "path,value",
    [
        (("transcript", "range"), [100, 80]),
        (("transcript", "range"), [80, 80]),
        (("transcript", "range"), [0, 5001]),
        (("cds", 0, "range"), [95, 96]),
        (("cds", 0, "range"), [100, 90]),
        (("cds", 0, "range"), [5000, 5003]),
        (
            ("promoter", "scan"),
            {"mode": "scan", "range": [0, 257], "strands": ["+", "-"]},
        ),
        (("promoter", "scan"), {"mode": "scan", "range": [2, 1], "strands": ["+"]}),
        (("promoter", "scan"), {"mode": "scan", "range": [0, 5001], "strands": ["+"]}),
        (("promoter", "scan", "positions", 0, "tss"), 5001),
        (("projection", "origin"), 1000),
        (("projection", "contig_length"), 1),
        (("projection", "origin_crossing"), False),
        (("sequence",), "A"),
    ],
)
def test_relational_semantics_are_explicitly_runtime_authoritative(path, value):
    """Acceptance is not a claim that malformed geometry can be executed."""
    VALIDATOR.validate(changed(path, value))


def test_cds_identity_order_and_biological_meaning_require_runtime():
    document = request()
    document["cds"] = document["cds"] * 2
    VALIDATOR.validate(document)  # Duplicate IDs and starts are relational checks.
    document = request()
    document["cds"].reverse()
    VALIDATOR.validate(document)  # Ordering is not inferred or changed by schema.
    document["sequence"] = "A" * 5000
    VALIDATOR.validate(document)  # No codon/ORF, evidence or execution assertion.


@pytest.mark.parametrize("path", INTEGER_PATHS)
def test_integral_float_wire_type_is_a_documented_schema_limit(path):
    VALIDATOR.validate(changed(path, 1.0))


def test_received_bytes_and_duplicate_keys_require_strict_transport():
    document = request()
    # Leading JSON whitespace alone exceeds the received-byte cap without changing
    # the parsed object. Canonical bytes/depth/nodes also remain runtime checks.
    wire = " " * 1_000_001 + json.dumps(document, allow_nan=False)
    VALIDATOR.validate(json.loads(wire))
    # Duplicate keys are likewise invisible after ordinary parsing.
    wire = json.dumps(document)
    duplicate = '{"id":"discarded",' + wire[1:]
    VALIDATOR.validate(json.loads(duplicate))
    assert json.loads(duplicate)["id"] == document["id"]
