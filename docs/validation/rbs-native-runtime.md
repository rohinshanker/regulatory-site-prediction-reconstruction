# Native transcript-context runtime

- Purpose: Define portable extraction, scoring, missingness and genomic export.
- Scope: The native evidence adapter and its local CLI/library boundary.
- Last verified: 2026-10-17

The adapter consumes the [source-neutral evidence contract](rbs-native-input-contract.md)
and preserves the full source record beside each prediction. It does not infer
which TSS or historical/current CDS annotation is correct. Alternate scenarios
must have distinct IDs; transcript counts are never treated as translation labels.
The versioned [input](../../schemas/native-rbs-evidence-1.schema.json) and
[result](../../schemas/native-rbs-result-1.schema.json) schemas define the boundary.

## Execution

After [installing the package and backend](rbs-runtime.md):

```sh
regsite-native benchmarks/rbs/native-input-example.json > native.json
regsite-native benchmarks/rbs/native-input-example.json --format gff3 > native.gff3
regsite-native benchmarks/rbs/native-input-example.json --mode conditional_scan
```

The included seven-case fixture is synthetic coordinate validation, not evidence
of native-host accuracy. `context2017` is the default; `--profile historical` and
`--profile footprint2017` explicitly select the other mechanisms. The Python API
is `regsite.native.predict_native(value, backend, profile=..., mode=...)`.

`supplied_start` scores the declared CDS start. `conditional_scan` searches
AUG/GUG/UUG only inside that same extracted context and ranks successful scores;
it is neither transcript discovery nor genome-wide start-site detection. Scores
remain relative initiation predictions with the selected model's limitations.
Host, temperature and nine-base anti-SD sequence are explicit inputs. An annotated
16S tail used as a host scenario does not establish mature-rRNA processing or
experimental host calibration.

## Coordinates and missingness

Genome sequences are normalized ACGT DNA, pinned by SHA256, accession, assembly,
annotation and topology. Contexts are RNA in transcript orientation, with
zero-based starts and half-open intervals. Negative-strand coordinates use reverse
complements. A `GenomicPath.first` is the first transcribed genomic nucleotide,
not the leftmost interval endpoint. Exported reference segments are ascending
within each interval and ordered along transcription; an origin-spanning interval
has two segments. Sequence hashes are explicitly DNA for the genome and RNA for
the extracted context.

A known TSS clips the upstream context. A missing TSS permits a clearly warned
genomic-flank scenario. Negative leaders from internal TSSs are unsupported and
never wrap into chromosome-sized leaders. Circular topology alone does not grant
permission to cross the origin: the record must set `origin_crossing`. Linear or
undeclared-origin contexts clip at contig boundaries. Contexts never traverse a
replicon twice. The adapter does not infer downstream transcript ends or operon
coupling. Leaderless and insufficient-context cases retain the core model's
explicit unsupported result.

Invalid or unsupported records remain in the output; one bad record/genome does
not discard unrelated records. Duplicate record IDs are invalid on their second
occurrence. A setup error raises `InputError`; the CLI exits 2. Completed batches
exit 1 if any row failed or is invalid, otherwise 0, including scientifically
unsupported rows. Inspect statuses, reasons and coverage rather than treating a
zero exit code as complete biological coverage. Missing values are null, never
zero-energy or zero-score substitutes.

The JSON output is authoritative for evidence, structures and failures. GFF3 uses
one-based inclusive intervals; circular features have an unwrapped end greater
than the replicon length, following the
[GFF3 specification](https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md).
Start codons are anchors, and binding/standby/footprint spans are model features,
not experimentally observed regulatory boundaries. Empty intervals emit no
feature. Score and phase columns are `.`; relative TIR is an explicit attribute,
not a significance score. Unsupported rows remain GFF comments. Structure-pair
coordinates retain their embedded core-result semantics and are not silently
converted to genomic pair indices.

## Bounds and verification

Defaults: 60 seconds per record, 300 seconds per batch; maximums 120 and 3600.
Batch exhaustion retains later records as failed, with their prepared context.
Each context is at most 100 upstream plus 100 downstream nucleotides. Inputs are
limited to 10,000 records, 100 genomes, 20 million total genome bases and 40 million
encoded JSON bytes. Duplicate JSON keys and nonfinite numbers are rejected.
The batch identity includes the full input, model/backend, implementation version,
mode and time budgets. Elapsed wall time is not part of that identity.

Required checks include B's independent seven-case coordinate fixtures, exhaustive
small-genome path/interval reconstruction on both strands and topologies, real
backend single/batch execution, GFF origin/strand conversion, schema checks,
invalid inputs, missing starts/TSSs, source-identity mismatches and both timeouts.
Run the full [runtime gates](rbs-runtime.md), including fresh-wheel examples.
