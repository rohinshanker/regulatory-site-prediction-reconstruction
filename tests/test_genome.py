"""Independent enumerated coordinate checks, including both circular directions."""

import pytest

from regsite.genome import GenomicPath
from regsite.sequence import InputError, Interval


def test_named_forward_reverse_and_origin_fixtures():
    assert GenomicPath(100, 80, 30, "+", True).project(0, 30) == (
        Interval(80, 100, "+"),
        Interval(0, 10, "+"),
    )
    reverse = GenomicPath(100, 10, 30, "-", True)
    assert reverse.project(0, 30) == (Interval(0, 11, "-"), Interval(81, 100, "-"))
    assert reverse.project(10, 13) == (Interval(0, 1, "-"), Interval(98, 100, "-"))
    assert reverse.point(0) == 10
    assert reverse.point(12) == 98
    assert GenomicPath(100, 80, 30, "-", False).project(3, 6) == (
        Interval(75, 78, "-"),
    )


def test_exhaustive_small_contig_projection_and_extraction():
    genome = "ACGUACG"
    complement = dict(zip("ACGU", "UGCA", strict=True))
    size = len(genome)
    for strand, step in (("+", 1), ("-", -1)):
        for first in range(size):
            for length in range(1, size + 1):
                expected = [(first + i * step) % size for i in range(length)]
                crosses = any(not 0 <= first + i * step < size for i in range(length))
                for circular in (True, False):
                    if crosses and not circular:
                        with pytest.raises(InputError, match="linear"):
                            GenomicPath(size, first, length, strand, circular)
                        continue
                    path = GenomicPath(size, first, length, strand, circular)
                    assert [path.point(i) for i in range(length)] == expected
                    sequence = "".join(
                        genome[i] if strand == "+" else complement[genome[i]]
                        for i in expected
                    )
                    assert path.extract(genome) == sequence
                    for a in range(length + 1):
                        for b in range(a, length + 1):
                            segments = path.project(a, b)
                            observed = []
                            for part in segments:
                                points = list(range(part.start, part.end))
                                observed.extend(
                                    points if strand == "+" else points[::-1]
                                )
                            assert observed == expected[a:b]


@pytest.mark.parametrize(
    "args",
    [
        (100.0, 0, 10, "+", False),
        (100, True, 10, "+", False),
        (100, 0, 1.5, "+", False),
        (0, 0, 1, "+", False),
        (100, 0, 0, "+", False),
        (100, 0, 101, "+", True),
        (20_000_001, 0, 1, "+", False),
        (100, -1, 10, "+", False),
        (100, 100, 10, "+", False),
        (100, 0, 10, "?", False),
        (100, 0, 10, "+", 1),
        (100, 0, 10, "-", False),
        (100, 99, 10, "+", False),
    ],
)
def test_invalid_paths_are_not_silently_wrapped(args):
    with pytest.raises(InputError):
        GenomicPath(*args)


def test_invalid_projections_and_sequence_lengths():
    path = GenomicPath(10, 8, 5, "+", True)
    for offset in (False, -1, 5, 1.0):
        with pytest.raises(InputError, match="offset"):
            path.point(offset)
    for start, end in ((False, 2), (0, 2.0), (-1, 1), (2, 1), (0, 6)):
        with pytest.raises(InputError, match="interval"):
            path.project(start, end)
    for sequence in (None, "ACGU", ["A"] * 10):
        with pytest.raises(InputError, match="length"):
            path.extract(sequence)
