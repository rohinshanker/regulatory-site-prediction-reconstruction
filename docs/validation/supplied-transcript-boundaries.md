# Supplied-transcript component boundary

- Purpose: Preserve declared transcript/CDS organization and independently check component coordinates and missingness.
- Scope: Session B #45 under parent #8; preparation for A's supplied-transcript runtime, not a complete Operon Calculator.
- Last verified: 2026-10-19

The admitted [component inventory](operon-riboswitch-source-admission.md) supports
explicit Promoter and uncoupled RBS calculations. It does not supply coupling,
elongation, pausing, RNA stability, termination/readthrough, transcript discovery
or a combined RNA/protein abundance model. Supplied organization is evidence
from the caller. Adjacent genes or predicted promoter peaks do not establish an
operon, transcript boundary or isoform mixture.

## Input and coordinate semantics

A request has one already transcript-oriented DNA construct, one explicit
half-open transcript range `[u,v)` with provenance, and 1–10 named CDS annotation
ranges in construct coordinates. Canonical fixture DNA is uppercase ACGT.
Any public text normalization belongs in A's request contract, before sequence
hashing and coordinate validation. The transcript is always the exact substring
`construct[u:v]`, interpreted in the local forward direction; no reverse
complement is applied a second time. RNA folding replaces T by U without changing
length or positions. Distinct isoforms require distinct requests.

CDS ranges have unique IDs and starts, are ordered by increasing start, and may
overlap. A range `[s,e)` is a supplied annotation, including whatever end the
caller declares. The wrapper neither infers a stop codon nor validates a protein
sequence, reading frame or functional ORF. Ranges must span at least three bases
and be contained in the construct. Shorter ranges are invalid organization,
even if three construct bases happen to follow their start. Negative-strand CDSs on this transcript require a separate
request; they cannot silently become cistrons of the same molecule.

For an annotation, preserve signed start offset `s-u`. Only a complete start
codon inside the supplied transcript, `u <= s` and `s+3 <= v`, can become an RBS
request. Eligible starts are `s-u` on `construct[u:v]`, with local strand `+`.
They are never clipped to zero, moved to an internal codon, or rescued with DNA
upstream of `u`. The supplied CDS end may extend beyond `v`; preserve its original
range and an explicit downstream-annotation-clipped warning. This does not imply
a complete protein or a valid translation-termination prediction.

An out-of-construct or malformed range is an invalid organization. A well-formed
annotation incompatible with the transcript remains in the result with no RBS
request/prediction, its signed offset and a precise reason:

| Condition, in precedence order | Independent fixture reason |
| --- | --- |
| `s < u` | `start_before_transcript` |
| `s >= v` | `start_after_transcript` |
| `s < v < s+3` | `start_codon_after_transcript` |

Other eligible CDSs can still run. A noncanonical start triplet is left to the
admitted RBS component's explicit unsupported/no-candidate semantics; the
organization layer must not invent a score or remove it. Leaderless and short
leaders are valid organizations even when an RBS profile cannot score them.

One explicit RBS profile/settings object applies to the declared starts: host
metadata, anti-SD, temperature and deadlines retain the component contract.
The wrapper must preserve every CDS/start/result correspondence, including a
multi-start component's requested entries. These are uncoupled model estimates.
No preceding cistron occupancy, drafting, translational reinitiation or inferred
RNA protection can alter them without a separately admitted model.

The Promoter request explicitly names positions or a scan on the complete
construct, its calibration, requested strands and output settings. Its normalized
sequence must equal the supplied construct. Promoter results never redefine
`[u,v)`, create another RNA isoform, or weight RBS scores. Opposite-strand
promoter candidates remain explicitly opposite-strand features. Version 1 has
no optional terminator or other part fields; unknown fields are rejected.

## Genomic mapping

Optional full-construct projection uses the established explicit contig length,
topology, first-base `origin` and `sequence_strand`. For construct base `f`,
`g = origin + direction*f`, where direction is +1 or -1. Apply modulo contig
length only for a declared circular contig; linear coordinates must remain
in bounds. The construct cannot traverse a contig twice.

Transcript base `t` maps through construct base `u+t`. A CDS start codon maps its
three consecutive transcript-order bases individually. Half-open intervals are
mapped separately as ordered segments; a negative-strand segment has ascending
endpoints but is traversed from its upper end. Never treat an interval endpoint
as a base or sort origin-crossing segments into genomic order. Genomic strand is
the product of local strand and projection direction. Null projection means no
genomic coordinate can be supplied.

Circular genomic projection does not make the supplied RNA circular. Folding
uses only the finite transcript substring. The upstream end of that substring
cannot wrap to its downstream end. Likewise, annotation overlap is retained as
geometry and does not prove translational coupling.

## Execution and results

A freezes the exact request/result schemas, measured caps and public component
ordering before independent runtime validation. Initial organization bounds are
5,000 construct bases and 1–10 CDSs; component candidate/state/output limits may
narrow those bounds. Explicit per-component and whole-request deadlines must
retain unstarted work. Organization validation and the complete component roster
precede model execution. Deterministic execution order and stop rules are part
of the settings receipt, not scheduler-dependent behavior.

The [public request contract at `3b146dc`](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/3b146dcc4d947c36c5259d9ba02637e2124b0c66/docs/validation/supplied-transcript-contract.md)
agrees with these geometry rules. It makes organization validation atomic,
runs RBS before Promoter, and fixes explicit component settings and complete
candidate rosters. The fixture input is a geometry oracle rather than a wire
request: its `transcript_range` maps to `transcript.range`; fixture projection
`length` maps to `contig_length`, with explicit contig and origin-crossing
declarations added by the request builder. Supplied provenance and predictor
settings must also be explicit. The fixture flag
`downstream_annotation_clipped` corresponds to the runtime warning
`downstream_clipped`; no scientific meaning is changed by that spelling.

Retain original Promoter and RBS results, complete model/settings/backend
identities, each CDS annotation and start correspondence, transcript-to-construct
mapping, and genomic projection where supplied. Keep all statuses and nulls:
failed is not an empty candidate universe; not-run is not a completed failure;
an incompatible CDS is not a missing CDS. Partial component results are marked
incomplete and do not supply an all-components-success endpoint. An actual empty
Promoter request can have the component's valid no-candidate result.

Report named capabilities for unimplemented submodels, with explicit unsupported
status and null quantities. Do not multiply Promoter and RBS scores into protein
expression, compare their units as one scale, infer expression changes from
annotation-only parts, or present this wrapper as the complete production Operon
Calculator. Current/recoded comparisons use separately supplied organizations and
edit maps; a changed candidate universe alone is not biological site gain/loss.

## Independent fixtures

[`organization-fixtures.json`](../../benchmarks/operon/organization-fixtures.json)
is an original synthetic geometry panel under GPL-3.0-or-later, SHA256
`cb9fd2eeb8a1927c5d8bba41bd8ed63fb9c5d44398e65571c8a350b3cbd14e10`.
It contains 12 literal cases and four artificial three-component status rosters.
No experimental sequence, output, model equation or learned threshold is used.
The repeated ACGT constructs test bookkeeping, not initiation strength.

Cases cover monocistronic and overlapping annotations, leaderless/short leaders,
a TSS inside an annotated CDS, incomplete or last-complete boundary codons,
a CDS annotation beyond the transcript, an alternative transcript, negative
linear projection, and both orientations across a circular genomic origin.
For example, origin 990 on a 1,000-base positive-strand contig maps construct
start 8 to codon bases `[998,999,0]`; origin 5 on the negative strand maps start
4 to `[1,0,999]`. Both constructs remain linear RNA substrates.

The tests independently enumerate transcript positions and genomic base walks,
reconstruct ordered half-open segments, reconcile every start and status, and
verify the immutable fixture hash:

```sh
python -m pytest --confcutdir=tests/benchmarks -q \
  tests/benchmarks/test_operon_organization_fixtures.py
```

All 12 cases satisfy the public minimum CDS span and retain their original
fixture hash. These checks establish input expectations only. They execute no predictor and
cannot establish runtime deadline handling or biological accuracy. A's immutable
runtime candidate and execution receipt remain prerequisites for the subsequent
independent component/result comparison. Parent #8 stays open for missing models.
