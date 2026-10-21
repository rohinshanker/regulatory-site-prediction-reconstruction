"""Parse the complete fixed-profile TransTermHP map without losing candidates."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from regsite.termination_backend import STDOUT_LIMIT, TerminationBackendError

MAX_CANDIDATES = 1000
_SETTINGS = [
    "25 bins; sample size is 20000000",
    "--gc=-2.3 --au=-0.9 --gu=1.3 --mm=3.5 --gap=6",
    "--max-len=59 --min-stem=4 --max-loop=13 --min-loop=3",
    "--uwin-length=6 --uwin-require=3 --max-hp-score=-2 --max-tail-score=-2.5",
    "--loop-penalty=1,2,3,4,5,6,7,8,9,10,11",
    "--start-cut=0 --end-cut=25",
]
_MAP_HEADER = [
    "Each terminator entry starts in column 3 and is of the form:",
    "term #       start - end      +/-  regionconf   hp     tail | notes",
    "Followed by the sequence of the 5' tail, 5' stem, loop, 3' stem, and 3' tail.",
    "Genes are interspersed, and start the first column.",
]
_DECIMAL = r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?"
_TERM = re.compile(
    rf"TERM ([1-9][0-9]{{0,3}})\s+([1-9][0-9]{{0,5}}) - ([1-9][0-9]{{0,5}})\s+"
    rf"([+-]) ([FfG])\s+([0-9]{{1,3}})\s+({_DECIMAL})\s+({_DECIMAL}) \| ?(.*)"
)


def _require(condition: bool) -> None:
    if not condition:
        raise TerminationBackendError(
            "Invalid complete native termination output.", code="native_output_invalid"
        )


def _cost(value: str, cutoff: Decimal) -> str:
    _require(len(value) <= 32)
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise TerminationBackendError(
            "Invalid complete native termination output.", code="native_output_invalid"
        ) from exc
    _require(number.is_finite() and math.isfinite(float(value)) and number <= cutoff)
    return value


def _notes(value: str, length: int) -> str:
    """Check native bookkeeping grammar without assigning biological meaning."""
    _require(len(value) <= 16384)
    last = -1
    if value:
        for note in value.split(", "):
            fields = note.split(" ")
            kind = fields[0]
            _require(kind in ("gap", "opp_overlap", "overlap"))
            order = ("gap", "opp_overlap", "overlap").index(kind)
            _require(order > last and len(fields) > 1)
            last = order
            for coordinate in fields[1:]:
                _require(re.fullmatch(r"[1-9][0-9]{0,5}", coordinate) is not None)
                _require(int(coordinate) <= (59 if kind == "gap" else length))
            _require(kind != "gap" or len(fields) == 2)
    return value


def _candidate(line: str, sequence: str, expected_id: int) -> dict[str, Any]:
    match = _TERM.fullmatch(line)
    _require(match is not None)
    assert match is not None
    native_id, first, second, strand, context, printed, hp, tail, notes = match.groups()
    first_i, second_i, confidence = int(first), int(second), int(printed)
    _require(int(native_id) == expected_id and 0 <= confidence <= 100)
    start, end = min(first_i, second_i) - 1, max(first_i, second_i)
    length = len(sequence)
    _require(0 <= start < end <= length and 2 <= end - start <= 59)
    if strand == "+":
        _require(first_i < second_i and 59 <= end - 1 < length - 16)
        _require(context == "F" or (context == "G" and start == 1))
        tail_start, tail_end = end, end + 15
    else:
        _require(first_i > second_i and 16 <= start < length - 59 and context == "f")
        tail_start, tail_end = start - 15, start
    _require(0 <= tail_start < tail_end <= length)
    ambiguous = strand == "+" and start == 1
    return {
        "candidate_id": "",
        "strand": strand,
        "hairpin": {"start": start, "end": end},
        "tail": {"start": tail_start, "end": tail_end},
        "status": "boundary_ambiguous" if ambiguous else "ok",
        "confidence": None if ambiguous else confidence,
        "hairpin_score": _cost(hp, Decimal("-2")),
        "tail_score": _cost(tail, Decimal("-2.5")),
        "native": {
            "id": f"TERM {native_id}",
            "context": context,
            "printed_confidence": None if ambiguous else confidence,
            "notes": _notes(notes, length),
        },
    }


def parse_output(stdout: bytes, sequence: str) -> list[dict[str, Any]]:
    """Validate the entire output before returning a canonically ordered roster."""
    _require(isinstance(stdout, bytes) and 0 < len(stdout) <= STDOUT_LIMIT)
    _require(
        isinstance(sequence, str)
        and 75 <= len(sequence) <= 100000
        and re.fullmatch(r"[ACGT]+", sequence) is not None
    )
    try:
        text = stdout.decode("ascii")
    except UnicodeError as exc:
        raise TerminationBackendError(
            "Invalid complete native termination output.", code="native_output_invalid"
        ) from exc
    _require(
        text.endswith("\n") and all(c == "\n" or 32 <= ord(c) <= 126 for c in text)
    )
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    _require(len(lines) >= 16)
    _require(
        re.fullmatch(
            r"TransTermHP v2\.08 \(built on [A-Z][a-z]{2} [ 0-9][0-9] [0-9]{4}\)",
            lines[0],
        )
        is not None
    )
    _require(lines[1] == _SETTINGS[0])
    _require(
        len(lines[2]) <= 4096
        and re.fullmatch(r"--pval-conf=\S*expterm\.dat", lines[2]) is not None
    )
    _require(lines[3:8] == _SETTINGS[1:])
    genes = re.fullmatch(
        rf"Genes: ({_DECIMAL}) %AT, 4 nt, ([0-9]{{1,4}}) terms\.", lines[8]
    )
    intergenic = re.fullmatch(
        rf"Intergenic: ({_DECIMAL}) %AT, H2T: ([0-9]{{1,6}}) nt, ([0-9]{{1,4}}) terms; "
        r"T2T: 0 nt, 0 terms; H2H: 0 nt, 0 terms\.",
        lines[9],
    )
    _require(genes is not None and intergenic is not None)
    assert genes is not None and intergenic is not None
    boundary = sequence[:2] + sequence[-2:]
    interior = sequence[2:-2]
    _require(genes[1] == format(sum(c in "AT" for c in boundary) / 4, ".6g"))
    _require(
        intergenic[1] == format(sum(c in "AT" for c in interior) / len(interior), ".6g")
    )
    _require(int(intergenic[2]) == len(interior) and lines[10:14] == _MAP_HEADER)
    _require(lines[14] == f"SEQUENCE fragment  (length {len(sequence)})")
    left = re.compile(r"boundary_left\s+1 - 2\s+\+ \|")
    right = re.compile(
        rf"boundary_right\s+{len(sequence) - 1} - {len(sequence)}\s+\+ \|"
    )
    candidates: list[dict[str, Any]] = []
    candidate_count = 0
    gene_count = 0
    forward_count = 0
    seen_left = False
    seen_right = False
    for line in lines[15:]:
        _require(not seen_right)
        if left.fullmatch(line):
            _require(not seen_left and gene_count == candidate_count)
            seen_left = True
        elif right.fullmatch(line):
            _require(seen_left)
            seen_right = True
        else:
            candidate = _candidate(line, sequence, candidate_count + 1)
            _require(seen_left != (candidate["native"]["context"] == "G"))
            candidate_count += 1
            gene_count += candidate["native"]["context"] == "G"
            forward_count += candidate["native"]["context"] == "F"
            if candidate_count <= MAX_CANDIDATES:
                candidates.append(candidate)
    _require(seen_left and seen_right)
    _require(int(genes[2]) == gene_count and int(intergenic[3]) == forward_count)
    if candidate_count > MAX_CANDIDATES:
        raise TerminationBackendError(
            "Native termination candidate limit exceeded.",
            code="native_candidate_limit",
        )
    candidates.sort(
        key=lambda c: (c["hairpin"]["start"], c["hairpin"]["end"], c["strand"])
    )
    for index, candidate in enumerate(candidates, 1):
        candidate["candidate_id"] = f"candidate-{index:04d}"
    return candidates
