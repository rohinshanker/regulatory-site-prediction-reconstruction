"""Complete-output parsing with constructed text, never biological evidence."""

import re

import pytest

from regsite import termination_output as output
from regsite.termination_backend import TerminationBackendError

SEQUENCE = "AC" + "ACGT" * 49 + "AC"


def text_output(sequence=SEQUENCE, rows=None, *, gene_terms=0, forward_terms=None):
    """Construct a bounded process double in the documented native grammar."""
    rows = [] if rows is None else rows
    if forward_terms is None:
        forward_terms = sum("+ F" in row for row in rows)
    boundary = sequence[:2] + sequence[-2:]
    interior = sequence[2:-2]
    lines = [
        "TransTermHP v2.08 (built on Oct 21 2026)",
        output._SETTINGS[0],
        "--pval-conf=expterm.dat",
        *output._SETTINGS[1:],
        f"Genes: {sum(c in 'AT' for c in boundary) / 4:.6g} %AT, "
        f"4 nt, {gene_terms} terms.",
        f"Intergenic: {sum(c in 'AT' for c in interior) / len(interior):.6g} %AT, "
        f"H2T: {len(interior)} nt, {forward_terms} terms; "
        "T2T: 0 nt, 0 terms; H2H: 0 nt, 0 terms.",
        *output._MAP_HEADER,
        f"SEQUENCE fragment  (length {len(sequence)})",
        "boundary_left 1 - 2 + |",
        *rows,
        f"boundary_right {len(sequence) - 1} - {len(sequence)} + |",
    ]
    return ("\n\n".join(lines) + "\n").encode()


def term(
    index=1,
    start=81,
    end=96,
    strand="+",
    context="F",
    confidence=80,
    hp="-11.8",
    tail="-3.87583",
    notes="",
):
    return (
        f"TERM {index} {start} - {end} {strand} {context} "
        f"{confidence} {hp} {tail} | {notes}"
    )


def invalid(raw, sequence=SEQUENCE):
    with pytest.raises(TerminationBackendError) as error:
        output.parse_output(raw, sequence)
    assert error.value.code == "native_output_invalid"


def test_complete_sorted_roster_and_printed_cutoff():
    rows = [
        term(start=85, end=72, strand="-", context="f", notes="opp_overlap 81"),
        term(index=2, hp="-2", notes="gap 1, opp_overlap 72, overlap 90 91"),
    ]
    result = output.parse_output(text_output(rows=rows), SEQUENCE)
    assert result[0]["hairpin"] == {"start": 71, "end": 85}
    assert result[0]["tail"] == {"start": 56, "end": 71}
    assert result[1]["tail"] == {"start": 96, "end": 111}
    assert [c["candidate_id"] for c in result] == ["candidate-0001", "candidate-0002"]
    assert result[1]["hairpin_score"] == "-2"
    assert result[0]["native"]["id"] == "TERM 1"
    assert output.parse_output(text_output(), SEQUENCE) == []


@pytest.mark.parametrize("context", ["F", "G"])
def test_boundary_ambiguity(context):
    row = term(start=2, end=60, context=context)
    raw = text_output(rows=[row], gene_terms=context == "G")
    # bool formatting is deliberately avoided in real counts.
    raw = raw.replace(b"True terms", b"1 terms").replace(b"False terms", b"0 terms")
    if context == "G":
        lines = raw.decode().splitlines()
        left = lines.index("boundary_left 1 - 2 + |")
        hit = next(i for i, line in enumerate(lines) if line.startswith("TERM"))
        lines[left], lines[hit] = lines[hit], lines[left]
        raw = ("\n".join(lines) + "\n").encode()
    result = output.parse_output(raw, SEQUENCE)
    assert result[0]["status"] == "boundary_ambiguous"
    assert result[0]["confidence"] is None
    assert result[0]["native"]["printed_confidence"] is None


@pytest.mark.parametrize(
    "old,new",
    [
        (b"v2.08", b"v2.09"),
        (b"25 bins", b"24 bins"),
        (b"--pval-conf=expterm.dat", b"--pval-conf=x"),
        (b"--gap=6", b"--gap=7"),
        (b"Genes: 0.5", b"Genes: 50"),
        (b"H2T: 196 nt", b"H2T: 195 nt"),
        (b"Intergenic: 0.5", b"Intergenic: 50"),
        (b"T2T: 0 nt", b"T2T: 1 nt"),
        (b"Genes: 0.5 %AT, 4 nt, 0", b"Genes: 0.5 %AT, 4 nt, 1"),
        (b"196 nt, 0 terms", b"196 nt, 1 terms"),
        (b"Genes are interspersed", b"Gene are interspersed"),
        (b"length 200", b"length 201"),
        (b"boundary_left", b"left"),
        (b"boundary_right", b"right"),
        (b"1 - 2", b"1 - 3"),
    ],
)
def test_header_and_boundary_corruption(old, new):
    raw = text_output()
    assert old in raw
    invalid(raw.replace(old, new))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"index": 2},
        {"start": 0},
        {"start": 96, "end": 81},
        {"start": 1, "end": 60},
        {"start": 2, "end": 61},
        {"start": 100, "end": 160},
        {"end": 185},
        {"end": 201},
        {"strand": "-", "context": "f"},
        {"context": "G"},
        {"context": "f"},
        {"start": 100, "end": 90, "strand": "-", "context": "F"},
        {"start": 25, "end": 10, "strand": "-", "context": "f"},
        {"start": 170, "end": 155, "strand": "-", "context": "f"},
        {"confidence": 101},
        {"confidence": -1},
        {"hp": "NaN"},
        {"hp": "-1.999"},
        {"hp": "-" + "1" * 40},
        {"tail": "-2.4"},
        {"notes": "biology"},
        {"notes": "gap 0"},
        {"notes": "gap 60"},
        {"notes": "gap 1 2"},
        {"notes": "overlap 201"},
        {"notes": "overlap"},
        {"notes": "overlap 01"},
        {"notes": "overlap 1, gap 1"},
        {"notes": "gap 1, gap 1"},
        {"notes": "overlap  " + "1 " * 9000},
    ],
)
def test_term_corruption(kwargs):
    invalid(text_output(rows=[term(**kwargs)]))


def test_strict_stream_and_full_roster():
    raw = text_output(rows=[term()])
    for bad in (
        b"",
        b"a" * 262145,
        raw[:-1],
        raw + b"trailing\n",
        raw + b"\xff\n",
        raw.replace(b"TERM 1", b"TERM\t1"),
        raw.split(b"Each")[0],
        raw.replace(b"TERM 1", b"SEQUENCE fragment\nTERM 1"),
    ):
        invalid(bad)
    invalid(raw, "N" * 200)
    invalid(raw, "AC" * 20)
    invalid(raw, None)


def test_map_order_and_duplicates():
    raw = text_output()
    invalid(
        raw.replace(
            b"boundary_left 1 - 2 + |",
            b"boundary_left 1 - 2 + |\nboundary_left 1 - 2 + |",
        )
    )
    invalid(raw.replace(b"boundary_left 1 - 2 + |", b""))
    invalid(raw.replace(b"boundary_right 199 - 200 + |", b""))
    invalid(text_output(rows=[term()]).replace(b"boundary_left 1 - 2 + |\n\n", b""))
    invalid(raw + b"boundary_right 199 - 200 + |\n")
    raw = text_output(rows=[term()])
    left = b"boundary_left 1 - 2 + |"
    raw = raw.replace(left, b"").replace(b"boundary_right", left + b"\nboundary_right")
    invalid(raw)


def test_sort_plus_before_minus_for_shared_hairpin():
    rows = [term(start=96, end=81, strand="-", context="f"), term(index=2)]
    result = output.parse_output(text_output(rows=rows), SEQUENCE)
    assert [c["strand"] for c in result] == ["+", "-"]
    assert [c["native"]["id"] for c in result] == ["TERM 2", "TERM 1"]


def test_notes_and_scientific_notation():
    result = output.parse_output(
        text_output(rows=[term(hp="-2e+0", tail="-3e0")]), SEQUENCE
    )
    assert result[0]["hairpin_score"] == "-2e+0"
    assert re.fullmatch(r"candidate-0001", result[0]["candidate_id"])


@pytest.mark.parametrize("value", ["-1e99999", "-1e9999999999999999999999999"])
def test_unrepresentable_native_cost_is_typed(value):
    invalid(text_output(rows=[term(hp=value)]))


def test_candidate_limit_is_distinct_from_malformed_output(monkeypatch):
    monkeypatch.setattr(output, "MAX_CANDIDATES", 1)
    raw = text_output(rows=[term(), term(index=2), term(index=3)])
    with pytest.raises(TerminationBackendError) as error:
        output.parse_output(raw, SEQUENCE)
    assert error.value.code == "native_candidate_limit"
    invalid(raw.replace(b"TERM 2", b"BROKEN 2"))


@pytest.mark.parametrize(
    "old,new",
    [
        (b"boundary_right 199 - 200 + |", b""),
        (b"boundary_right", b"GARBAGE\nboundary_right"),
        (b"TERM 3", b"TERM 4"),
        (b"196 nt, 3 terms", b"196 nt, 2 terms"),
        (b"4 nt, 0 terms", b"4 nt, 1 terms"),
    ],
)
def test_candidate_overflow_validates_remaining_output(monkeypatch, old, new):
    monkeypatch.setattr(output, "MAX_CANDIDATES", 1)
    raw = text_output(rows=[term(), term(index=2), term(index=3)])
    assert old in raw
    invalid(raw.replace(old, new))


def test_gene_candidate_must_precede_left_boundary_end():
    invalid(text_output(rows=[term(start=2, end=60, context="G")], gene_terms=1))
