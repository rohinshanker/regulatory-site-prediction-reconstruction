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

For real UTEX 2973 context, first reproduce `tan-contexts.json` with B's pinned
[Tan extraction commands](rbs-native-validation.md). The full input preserves all
4,808 source rows. This small demonstration selects eight records from source
annotation categories, without using translation measurements or score errors:

```sh
.venv/bin/python - <<'PY'
import hashlib, json
from pathlib import Path
source = Path.home() / '.cache/reg-site-wave2/tan-contexts.json'
raw = source.read_bytes()
selection = json.loads(Path('examples/rbs-native-tan-ids.json').read_text())
assert hashlib.sha256(raw).hexdigest() == selection['source_sha256']
batch = json.loads(raw)
by_id = {row['id']: row for row in batch['records']}
batch['records'] = [by_id[key] for key in selection['record_ids']]
Path('.cache').mkdir(exist_ok=True)
Path('.cache/tan-example.json').write_text(json.dumps(batch))
PY
regsite-native .cache/tan-example.json > .cache/tan-example-results.json
regsite-native .cache/tan-example.json --format gff3 > .cache/tan-example.gff3
```

The selection is a runtime example, not a representative accuracy or coverage
benchmark. Whole-input admission counts and whole-input prediction coverage must
be reported separately. Once source files and the backend are installed, these
commands need no network or credentials.

`supplied_start` scores the declared CDS start. `conditional_scan` searches
AUG/GUG/UUG only inside that same extracted context and ranks successful scores;
equal scores receive consecutive ranks ordered by upstream transcript position.
It is neither transcript discovery nor genome-wide start-site detection. Scores
remain relative initiation predictions with the selected model's limitations.
Host, temperature and nine-base anti-SD sequence are explicit inputs. An annotated
16S tail used as a host scenario does not establish mature-rRNA processing or
experimental host calibration.
When temperature is absent, the adapter explicitly warns that its default 37°C
scenario is not native-condition calibration. Tan's multiple-condition metadata
is preserved; one default-temperature prediction is not an estimate for every
measured condition.
The source alias `temperature_celsius` is accepted explicitly; if both temperature
fields are supplied they must agree and both must be valid. This preserves the
frozen Karlsen envelope's 30°C setting without rewriting its evidence hash.

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
replicon twice. Negative leaders remain unsupported even when their coordinates
cross the origin. A declared positive origin-spanning circular leader longer than half the
replicon is conservatively unsupported (`ambiguous_long_circular_leader`), rather
than interpreting a nearby internal TSS as a chromosome-sized leader. This is an
admission rule, not a biological maximum; such transcripts need a richer evidence
contract. A crossing declaration must correspond to the source TSS-to-start path
or the extracted downstream/flank context. The adapter does not infer downstream transcript ends or operon
coupling. Leaderless and insufficient-context cases retain the core model's
explicit unsupported result.

Invalid or unsupported records remain in the output; one bad record/genome does
not discard unrelated records. Duplicate record IDs are invalid on their second
occurrence. A setup error raises `InputError`; the CLI exits 2. Completed batches
exit 1 if any row failed or is invalid, otherwise 0, including scientifically
unsupported rows. Inspect statuses, reasons and coverage rather than treating a
zero exit code as complete biological coverage. Missing values are null, never
zero-energy or zero-score substitutes.
When the source explicitly sets `cds_start_zero_based` to null and cannot assign
a replicon, `genome_id`/strand may be absent or null. The adapter validates the
common metadata/settings and retains an unsupported unresolved-start/replicon
row with its complete source evidence; it never guesses a genomic association.

The JSON output is authoritative for evidence, structures and failures. GFF3 uses
one-based inclusive intervals; circular features have an unwrapped end greater
than the replicon length, following the
[GFF3 specification](https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md).
GFF `seqid` is the input `genome_id`, avoiding collisions when versioned genomes
share an accession. Each represented genome has a `sequence-region` directive and
landmark `region` with explicit `Is_circular`, original accession, annotation and
sequence hash. Genome IDs and attributes use the specification's escaping rules.
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
Core prediction IDs use the declared per-record budget; the enclosing batch's
remaining deadline separately limits execution. Repeated runs can differ in
timeout coverage, but elapsed scheduling time does not change the identity of
the requested calculation.

Required checks include B's independent seven-case coordinate fixtures, exhaustive
small-genome path/interval reconstruction on both strands and topologies, real
backend single/batch execution, GFF origin/strand conversion, schema checks,
invalid inputs, missing starts/TSSs, source-identity mismatches and both timeouts.
Run the full [runtime gates](rbs-runtime.md), including fresh-wheel examples.

## Whole-source coverage example

The pinned Tan envelope SHA256 is
`c442baf07480ddece0956a9ac10aefd5884472ec63ed0c62166e2ad7ef8a03d5`.
A full `context2017` run at implementation commit
`a77897df3b92f2b9e74631ebf332d0d73c236c4b`, 60 seconds per record and
3,600 seconds per batch, retained every row:

| Outcome | Rows |
| --- | ---: |
| Successful score | 2,212 |
| Unsupported before scoring: unresolved start | 2,375 |
| Unsupported before scoring: internal TSS | 16 |
| Unsupported during scoring: leaderless / other start codon | 42 / 4 |
| No interstrand candidate in bounded search | 62 |
| Failed backend structure/output | 97 |

The 97 failures comprise 85 nonreciprocal CTs, three crossing/inconsistent CTs,
and nine missing/unreadable outputs. Rejecting these is intentional; silently
repairing or discarding an unknown fold could change the selected structure.
The full result SHA256 is
`4f17041c17cebc0a8cca37e6c76581ed5b73217b914d285801da7d22c0a9af92`.
Later adapter changes improve stable identities and row-level reasons; this run
predates those changes and is not presented as a full final-tree rerun. Final
coordinate/input preparation and fresh-wheel subsets are checked separately.
These counts establish execution coverage on transcript-context scenarios, not
translation accuracy. Tan supplies no translation-strength labels for this test.
