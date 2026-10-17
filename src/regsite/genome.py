"""Source-independent, strand-aware paths through linear or circular contigs."""

from dataclasses import dataclass

from regsite.sequence import InputError, Interval, reverse_complement


@dataclass(frozen=True)
class GenomicPath:
    """A transcript-oriented contiguous path, traversing a contig at most once.

    `first` is the zero-based genomic nucleotide transcribed first, on either
    strand. This is a point, not an ascending interval's left boundary.
    Projected intervals have ascending, half-open bounds in transcript order.
    """

    contig_length: int
    first: int
    length: int
    strand: str
    circular: bool

    def __post_init__(self) -> None:
        if any(
            type(x) is not int for x in (self.contig_length, self.first, self.length)
        ):
            raise InputError("genomic path lengths and first position must be integers")
        if not 1 <= self.length <= self.contig_length <= 20_000_000:
            raise InputError(
                "genomic path must span 1..contig_length, at most 20M bases"
            )
        if not 0 <= self.first < self.contig_length:
            raise InputError("genomic first nucleotide lies outside the contig")
        if self.strand not in ("+", "-") or type(self.circular) is not bool:
            raise InputError("genomic path requires strand +/- and boolean circular")
        last = self.first + (self.length - 1) * (1 if self.strand == "+" else -1)
        if not self.circular and not 0 <= last < self.contig_length:
            raise InputError("linear genomic path crosses the contig boundary")

    def point(self, offset: int) -> int:
        """Map a transcript nucleotide index to a zero-based genomic point."""
        if type(offset) is not int or not 0 <= offset < self.length:
            raise InputError("transcript nucleotide offset is outside its path")
        step = 1 if self.strand == "+" else -1
        return (self.first + step * offset) % self.contig_length

    def project(self, start: int, end: int) -> tuple[Interval, ...]:
        """Map an interval, splitting at the origin; empty intervals stay empty."""
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start <= end <= self.length
        ):
            raise InputError(
                "transcript interval must satisfy 0 <= start <= end <= length"
            )
        if start == end:
            return ()
        first = self.point(start)
        length = end - start
        if self.strand == "+":
            stop = first + length
            if stop <= self.contig_length:
                return (Interval(first, stop, "+"),)
            return (
                Interval(first, self.contig_length, "+"),
                Interval(0, stop - self.contig_length, "+"),
            )
        begin = first - length + 1
        if begin >= 0:
            return (Interval(begin, first + 1, "-"),)
        return (
            Interval(0, first + 1, "-"),
            Interval(self.contig_length + begin, self.contig_length, "-"),
        )

    def extract(self, normalized_rna: str) -> str:
        """Extract from a prevalidated ACGU contig; no topology is inferred.

        Full-contig normalization/validation belongs to the manifest loader and
        occurs once, not for every transcript in a batch.
        """
        if (
            not isinstance(normalized_rna, str)
            or len(normalized_rna) != self.contig_length
        ):
            raise InputError("contig sequence length disagrees with genomic path")
        parts = [normalized_rna[p.start : p.end] for p in self.project(0, self.length)]
        if self.strand == "-":
            parts = [reverse_complement(part) for part in parts]
        return "".join(parts)
