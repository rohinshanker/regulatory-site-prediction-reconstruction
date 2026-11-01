"""Synthetic, hand-checkable complete CDS geometry and input boundaries."""

import hashlib
from copy import deepcopy

import pytest

from regsite.coupling_geometry import CouplingGeometryError, validate_pair_geometry

SEQUENCE = "AUGAAAUAAAUGCCCUAG"
UPSTREAM = {"id": "up", "interval": [0, 9]}
DOWNSTREAM = {"id": "down", "interval": [9, 18]}


def mirror(sequence, upstream, downstream):
    """Build a minus-strand input independently of the runtime projector."""
    sequence = "".join(
        {"A": "U", "U": "A", "C": "G", "G": "C"}[b] for b in sequence[::-1]
    )
    length = len(sequence)
    return (
        sequence,
        [length - upstream[1], length - upstream[0]],
        [
            length - downstream[1],
            length - downstream[0],
        ],
    )


def assert_error(code, **changes):
    """Check the public exception type, classification and explanation."""
    request = dict(
        sequence=SEQUENCE,
        strand="+",
        upstream=deepcopy(UPSTREAM),
        downstream=deepcopy(DOWNSTREAM),
    )
    request.update(changes)
    with pytest.raises(CouplingGeometryError) as caught:
        validate_pair_geometry(**request)
    assert isinstance(caught.value, ValueError)
    assert caught.value.code == code
    assert str(caught.value)


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize(
    "sequence,up,down,distance",
    [
        (SEQUENCE, [0, 9], [9, 18], 0),
        ("CCAUGAAAUAAACCCAUGCCCUAGGG", [2, 11], [15, 24], 4),
        ("AUGUAA" + "C" * 26 + "GUGUGA", [0, 6], [32, 38], 26),
        ("AUGCCAUGAAAUAA", [0, 9], [5, 14], -4),
        ("AUGAAAAAUGAAAAAUAAAAAAUAA", [0, 18], [7, 25], -11),
    ],
)
def test_exact_geometry_and_mirrored_inputs(strand, sequence, up, down, distance):
    supplied, input_up, input_down = sequence, up, down
    if strand == "-":
        supplied, input_up, input_down = mirror(sequence, up, down)
    upstream = {"id": "up:1._-", "interval": input_up}
    downstream = {"id": "D" * 128, "interval": input_down}
    original = deepcopy((upstream, downstream))
    result = validate_pair_geometry(supplied, strand, upstream, downstream)
    assert result == {
        "sequence": supplied,
        "oriented_sequence": sequence,
        "sequence_sha256": hashlib.sha256(supplied.encode()).hexdigest(),
        "oriented_sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
        "strand": strand,
        "distance_nt": distance,
        "upstream": {
            "id": "up:1._-",
            "interval": input_up,
            "oriented_interval": up,
            "start_codon": sequence[up[0] : up[0] + 3],
            "stop_codon": sequence[up[1] - 3 : up[1]],
        },
        "downstream": {
            "id": "D" * 128,
            "interval": input_down,
            "oriented_interval": down,
            "start_codon": sequence[down[0] : down[0] + 3],
            "stop_codon": sequence[down[1] - 3 : down[1]],
        },
    }
    assert (upstream, downstream) == original
    result["upstream"]["interval"][0] = -1
    assert (upstream, downstream) == original


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("start", ["AUG", "GUG", "UUG"])
@pytest.mark.parametrize("stop", ["UAA", "UAG", "UGA"])
def test_all_known_codons_and_minimal_complete_cds(strand, start, stop):
    sequence = (start + stop) * 2
    up, down = [0, 6], [6, 12]
    if strand == "-":
        sequence, up, down = mirror(sequence, up, down)
    result = validate_pair_geometry(
        sequence, strand, {"id": "u", "interval": up}, {"id": "d", "interval": down}
    )
    for name in ("upstream", "downstream"):
        assert result[name]["start_codon"] == start
        assert result[name]["stop_codon"] == stop
    assert result["distance_nt"] == 0


@pytest.mark.parametrize("strand", ["+", "-"])
def test_shared_normalization_and_hashes_count_nucleotides(strand):
    supplied, up, down = SEQUENCE, [0, 9], [9, 18]
    if strand == "-":
        supplied, up, down = mirror(supplied, up, down)
    raw = " \n\t" + " \r\n".join(supplied.lower().replace("u", "t")) + "\u2003"
    normalized = validate_pair_geometry(
        raw, strand, {"id": "u", "interval": up}, {"id": "d", "interval": down}
    )
    assert normalized == validate_pair_geometry(
        supplied, strand, {"id": "u", "interval": up}, {"id": "d", "interval": down}
    )
    assert normalized["oriented_sequence"] == SEQUENCE
    assert (
        normalized["sequence_sha256"] == hashlib.sha256(supplied.encode()).hexdigest()
    )


@pytest.mark.parametrize("strand", ["+", "-"])
def test_out_of_frame_and_outside_stops_do_not_truncate_cds(strand):
    sequence = "UAAAUGCUAACCUAAGUGCCCUAGUGA"
    up, down = [3, 15], [15, 24]
    if strand == "-":
        sequence, up, down = mirror(sequence, up, down)
    result = validate_pair_geometry(
        sequence, strand, {"id": "u", "interval": up}, {"id": "d", "interval": down}
    )
    assert result["upstream"]["oriented_interval"] == [3, 15]
    assert result["downstream"]["oriented_interval"] == [15, 24]
    assert result["distance_nt"] == 0


@pytest.mark.parametrize("size", [100000, 100001])
def test_normalized_sequence_length_limit(size):
    sequence = SEQUENCE + "A" * (size - len(SEQUENCE))
    if size > 100000:
        assert_error("invalid_input", sequence=sequence)
    else:
        result = validate_pair_geometry(sequence, "+", UPSTREAM, DOWNSTREAM)
        assert len(result["sequence"]) == size


def test_raw_text_limit_inherited_from_normalizer():
    sequence = SEQUENCE + " " * (1000000 - len(SEQUENCE))
    result = validate_pair_geometry(sequence, "+", UPSTREAM, DOWNSTREAM)
    assert result["sequence"] == SEQUENCE
    assert_error("invalid_input", sequence=sequence + " ")


@pytest.mark.parametrize(
    "sequence", [None, 123, True, b"AUG", [], {}, "", " \n", "AUGN", ">id\nAUG", "A-UG"]
)
def test_invalid_sequences(sequence):
    assert_error("invalid_input", sequence=sequence)


@pytest.mark.parametrize(
    "strand", [None, True, 1, [], {}, "", "forward", "+-", " +", "−"]
)
def test_invalid_strand(strand):
    assert_error("invalid_input", strand=strand)


@pytest.mark.parametrize("side", ["upstream", "downstream"])
@pytest.mark.parametrize(
    "cds",
    [
        None,
        [],
        "cds",
        {},
        {"id": "a"},
        {"interval": [0, 9]},
        {"id": "a", "interval": [0, 9], "extra": 1},
    ],
)
def test_exact_cds_object_keys(side, cds):
    assert_error("invalid_input", **{side: cds})


@pytest.mark.parametrize("side", ["upstream", "downstream"])
@pytest.mark.parametrize(
    "cds_id", [None, True, 1, [], "", "a" * 129, "a b", "é", "a/1", "a\n", "ａ"]
)
def test_invalid_ids(side, cds_id):
    assert_error("invalid_input", **{side: {"id": cds_id, "interval": [0, 9]}})


def test_duplicate_ids():
    assert_error("invalid_input", downstream={"id": "up", "interval": [9, 18]})


@pytest.mark.parametrize("side", ["upstream", "downstream"])
@pytest.mark.parametrize(
    "interval",
    [
        None,
        "0,9",
        {},
        (0, 9),
        [],
        [0],
        [0, 9, 12],
        [False, 9],
        [0, True],
        [0.0, 9],
        [0, 9.0],
        ["0", 9],
        [0, None],
        [-1, 9],
        [0, 19],
        [9, 0],
        [9, 9],
        [18, 19],
    ],
)
def test_invalid_interval_types_and_ranges(side, interval):
    assert_error("invalid_input", **{side: {"id": "other", "interval": interval}})


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize(
    "up,down",
    [
        ([9, 18], [0, 9]),  # Reversed annotation order; circular inference forbidden.
        ([0, 18], [4, 10]),  # Out-of-frame nested CDS.
        ([4, 10], [0, 18]),  # Enclosing downstream annotation.
        ([0, 9], [0, 18]),  # Shared start.
        ([0, 18], [4, 18]),  # Shared end.
        ([0, 12], [3, 18]),  # Same-frame overlap.
    ],
)
def test_unsupported_pair_order_nesting_and_frame(strand, up, down):
    sequence = SEQUENCE
    if strand == "-":
        sequence, up, down = mirror(sequence, up, down)
    assert_error(
        "unsupported_geometry",
        sequence=sequence,
        strand=strand,
        upstream={"id": "u", "interval": up},
        downstream={"id": "d", "interval": down},
    )


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("side", ["upstream", "downstream"])
@pytest.mark.parametrize(
    "coding",
    [
        "AUG",  # Too short to include a distinct stop.
        "AUGAUAA",  # Incomplete reading frame.
        "CUGAAAUAA",  # Unsupported initiation codon.
        "AUGAAAAAA",  # Missing terminal stop.
        "AUGUAAAAAUAA",  # Internal UAA.
        "AUGUAGAAAUAA",  # Internal UAG.
        "AUGUGAAAAUAA",  # Internal UGA.
    ],
)
def test_unsupported_complete_cds_requirements(strand, side, coding):
    up_coding = coding if side == "upstream" else "AUGAAAUAA"
    down_coding = coding if side == "downstream" else "GUGCCCUAG"
    sequence = up_coding + down_coding
    up, down = [0, len(up_coding)], [len(up_coding), len(sequence)]
    if strand == "-":
        sequence, up, down = mirror(sequence, up, down)
    assert_error(
        "unsupported_geometry",
        sequence=sequence,
        strand=strand,
        upstream={"id": "u", "interval": up},
        downstream={"id": "d", "interval": down},
    )
