# Native RBS evidence input contract

- Owner: Session B (`9677689a-1792176763`); Session A owns the runtime adapter.
- Version: `native-rbs-evidence-1`; planning baseline `fc78dee42f934417f2bf905ae71b582903b7a949`.
- Scope: Source-specific records and independent coordinate fixtures, without translation outcomes.
- Last verified: 2026-10-17

## Record boundary

Each record identifies one source TSS-to-locus association or one supplied CDS
context. Alternate TSSs remain separate. A source association is not an
experimentally verified translation start.

The batch envelope is `{"schema_version": "native-rbs-evidence-1", "genomes":
{GENOME_ID: GENOME}, "records": [...]}`. Each genome carries `sequence` (normalized
ACGT, supplied once), `sequence_sha256`, `accession`, `assembly`, `annotation` and
`topology` (`linear` or `circular`). Records select it by `genome_id`. An outcome-free
[example batch](../../benchmarks/rbs/native-input-example.json) makes this boundary
concrete. The fixture's window lengths are illustrative; real batches declare
`upstream_limit_nt` and `downstream_length_nt`, initially 100 each.

| Field | Meaning |
| --- | --- |
| `id`, `study`, `source_file_sha256`, `source_sheet`, `source_row` | Stable identity; spreadsheet row is one-based. |
| `host`, `assembly`, `annotation`, `replicon`, `genome_sha256` | Strain, assembly/annotation revision, versioned accession and normalized whole-replicon hash. |
| `strand` | `+` or `-` in reference-genome coordinates. |
| `tss_zero_based` | First transcribed nucleotide, or null for an unmeasured transcript boundary. |
| `cds_start_zero_based` | First translated nucleotide in transcript orientation; highest start-codon coordinate on minus strand. Null for an unresolved join. |
| `transcript_start_evidence`, `translation_start_evidence` | Separate evidence types. Tan supplies `dRNA-seq TSS` and `annotation`, never measured TIS. |
| `source_start_zero_based`, `source_start_distance_nt` | Historical start inferred from the explicitly reported gTSS distance; not a current-annotation repair. |
| `leader_length_nt`, `source_current_start_delta_nt` | Signed distances in transcription direction. A negative current leader length marks an internal TSS, not an origin-spanning leader invented by modulo arithmetic. |
| `conditions` | Source-defined conditions/replicate metadata, including source conflicts. TSS counts are neither TE labels nor validated isoform weights. |
| `mapping_status`, `warnings`, `source_flags` | Exact join result, disagreements, S2 proposals and unsupported cases. Missingness never becomes a zero score. |

For Tan, only an exact current locus tag on the explicitly mapped replicon and
strand admits a current CDS association. Multiple distinct current models,
compound/slippage CDSs, unmatched IDs and ambiguous associations remain explicit.
Source/current start differences are retained even when both starts address
canonical codons. S2's homology-based proposals do not replace current starts or
become experimental TIS labels. The pipeline needs no consumer checkout.

## Runtime adapter and comparator windows

A takes the pinned genome plus these records and owns transcript-aware window
extraction, scoring and genomic export. B's fixture expectations are independent
of A's implementation. Intervals are zero-based half-open and ascending within
each reference segment; segment lists follow transcript order. Convert one-based
point coordinates by subtracting one exactly once.

For supplied-start strength comparisons, the initial common sequence contract
is up to 100 nt upstream and 100 nt from the start into the CDS. Clip upstream
sequence at a measured TSS. Without TSS evidence, label the 100-nt genomic flank
as an **unmeasured transcript-context assumption**, not a measured UTR. Preserve
full-context and model-preprocessed sequence hashes. A fixed-width SD comparator
gets its declared subwindow and retains its domain limitation. Model scores
never choose which transcript to retain.

Circular extraction requires an explicit origin-crossing context. An internal
TSS must not wrap around the whole chromosome to create a leader. Leaderless
and short-leader cases remain in coverage denominators even when unsupported.
The explicit aSD is in its own 5′→3′ orientation and is not reverse-complemented
with minus-strand mRNA; host labels alone do not select or calibrate it. Native
aSD admission needs its own sequence provenance.

## Fixtures and label separation

[Coordinate fixtures](../../benchmarks/rbs/native-coordinate-fixtures.json)
cover both strands, clipping, explicit origin spans and an internal TSS. The
small genomes and expected strings are hand-checkable; no scoring outputs are
included. [The native source ledger](../../benchmarks/rbs/native-sources.json)
pins the primary inputs.

The 136 public 2014 development records remain available unchanged. Karlsen TE
and Thiel reporter outcomes are withheld from A until eligibility, repeated-gene/
reporter-family groups and final partitions are frozen. The 2017 holdout remains
untouched. Native inputs contain no final outcomes, target-dependent filtering,
hidden-true-start-centered candidate windows or final per-case errors. Public
download alone does not establish training permission.

The initial backend recommendation remains separately installed, pinned
RNAstructure 6.6. Optional comparators retain their upstream algorithms and
environments; ViennaRNA's known redistribution restriction does not enter the
required open runtime. Learned code, weights and training rights each require
the comparator audit before adoption.
