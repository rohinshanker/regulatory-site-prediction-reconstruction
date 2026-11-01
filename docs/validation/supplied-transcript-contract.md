# Supplied-transcript component contract

- Purpose: Analyze declared transcript/CDS organization with admitted RBS and Promoter components for portable current/recoded consumer use.
- Scope: A #47 / B #45 under parent #8; no integrated Operon, coupling or abundance claim.
- Last verified: 2026-10-18

This is orchestration of the existing predictors, with no new scientific parameters.
The [source admission](operon-riboswitch-source-admission.md) names the missing
Operon submodels. Separate isoforms require separate requests. Transcript and CDS
annotations remain caller-supplied evidence, not inferred truth. Genomic projection
relabels bases; it does not add RNA context, wrap a transcript, or establish gene
identity. No score product estimates protein abundance.

## Request version 1

The object has exactly `schema_version`, `id`, `sequence`, `transcript`, `cds`,
`rbs`, `promoter`, `projection`, `settings`. `schema_version` is
`supplied-transcript-request-1`. IDs contain 1–128 characters without controls.
`sequence` is 1–5,000 uppercase ACGT bases in the transcript-oriented construct
frame; no implicit normalization. Coordinates are genuine zero-based integers;
intervals are ascending half-open. JSON must be finite, duplicate-free and valid
UTF-8, with no unknown fields. Received and compact canonical input are each
at most 1,000,000 bytes, depth at most 16 and at most 20,000 nodes.

`transcript` is exactly `{id,range,provenance}`. Its nonempty range `[u,v)` is
inside the construct. `provenance` is exactly `{kind,reference}`: kind is one of
`user_supplied`, `annotation`, `measured`, `synthetic`; reference is a nonempty
string of at most 1,024 characters without controls. These labels make no
independent evidence or licence assertion.

`cds` is a list of 1–10 objects, each exactly `{id,range,provenance}`. IDs and
start coordinates are unique; entries are ordered strictly by start. Ranges
span at least three bases and lie inside the construct; overlaps are allowed.
The CDS annotation is preserved in full, without ORF/stop/protein validation.
Only its first three bases `[s,s+3)` must fit inside `[u,v)` for RBS eligibility.
An incompatible annotation remains in the result with signed offset `s-u`,
original coordinates and incompatible status. Eligibility reasons, in order,
are `start_before_transcript` for `s<u`, `start_after_transcript` for `s>=v`,
and `start_codon_after_transcript` for `s<v<s+3`; no RBS start is clipped or invented. If its start fits but CDS end exceeds `v`, retain it with
`downstream_clipped` warning. Other eligible annotations can still run.

`rbs` is exactly `{profile,anti_sd,temperature_c,host}`. Profile must be one of
the existing admitted mechanistic profiles; no implicit model choice. `anti_sd`
is exactly nine uppercase ACGU bases; temperature is finite in [0,100] degrees C;
host is null or the existing RBS host string. Build one RBS request on exactly
`sequence[u:v]`, strand `+`, with all and only eligible offsets `s-u`. All starts
share one explicit RBS record budget. Its observed structures/scores remain
relative to this RNA segment until an explicit coordinate offset/projection.

`promoter` is exactly `{calibration,host,scan}`. Calibration is `ecoli_mg1655` or
`in_vitro`; host is null or the existing Promoter host object (omit absent taxon
ID in the native request). `scan` uses the existing explicit scan-range/strand
or listed-position contract on the full construct. Both local strands are
allowed; no candidate determines or changes the supplied RNA transcript. Cap the
candidate roster at 512, preserve empty rosters, and fix native output settings
to `{states:"selected",legacy_keys:false,elements:true}`. No metadata/defaults,
legacy positions, all-state output or implicit calibration is accepted here.

`projection` is null or the exact six fields `{contig,origin,contig_length,
sequence_strand,topology,origin_crossing}` under the existing public Promoter
projection contract, checked against the full construct. For a construct base
`i`, genomic point is `(origin + direction*i) mod contig_length`, direction +1
or -1. Linear crossings are invalid; circular crossings must be declared and
span at most one traversal. Reverse projections preserve transcript order in
split genomic runs. The RNA segment itself is linear regardless of this map.

`settings` is exactly `{seconds_per_rbs_record,seconds_per_promoter_record,
seconds_total}`. Every value is finite and positive, component budgets at most
120 seconds and total at most 240. Emit resolved floats and complete effective
wrapper/native limits. Backend verification precedes prediction; no new folding
process begins after the execution deadline. Deadline behavior is cooperative
between component operations as documented by the native contracts.

## Execution and result requirements

Run RBS first, then Promoter, serially. Shorten each execution budget to remaining
whole-request time without silently changing the requested scientific settings.
No retries or batching that changes the RNA context. If no CDS is eligible,
retain every incompatible annotation and mark the RBS component not applicable;
a backend is not required solely to invent a missing score. Every unstarted
component is `not_evaluated` with `deadline_exceeded`; preserve its declared
request/roster and a null native result. An empty declared Promoter scan is not
evidence that a deadline-skipped component ran.

Atomic malformed organization/settings produce an explicit input error before
scoring. Valid native failures and unsupported codons remain in the result,
including successful sibling sites. Whole-result setup/integrity/export failures
must not emit a misleading complete JSON result. Retain requested/returned/scored
counts, incompatible and not-evaluated counts separately. A list of unsupported
capabilities names coupling, elongation, decay/stability, termination, native
operon discovery and joint protein abundance; none supplies a numerical value.

Retain complete native component results, model/source/parameter/backend/settings
identities, original supplied organization/provenance, transcript/construct/genomic
coordinates and a per-CDS correspondence into the RBS site roster. Do not duplicate
large native payloads per CDS. Features whose semantics are established by the
native result may be projected; preserve null/empty intervals honestly. Missing
sites, unsupported codons and failed calculations never become zero scores.
A single comparative/export row binds the complete JSON identity.

The wrapper result schema is `supplied-transcript-result-1`. A request SHA-256
hashes the original parsed request using sorted compact ASCII-escaped finite JSON
without newline. A prediction SHA-256 hashes the complete result with the
`prediction_sha256` field omitted, using the same serialization. Full output uses
`json.dumps(sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)` plus one
newline, ASCII bytes, capped initially at 33,554,432 bytes. Successful deterministic
runs have stable identities; deadline-dependent missingness may change a result.
The exact emitted nested field schema will be frozen with the reviewed runtime
before B collection; this document does not claim implementation or resources
have passed yet.

## Acceptance and consumer limits

Use actual local RBS and Promoter calls, independent B organization fixtures,
100% new statement/branch tests, exact-patch review, fresh offline CLI installation
and finite synthetic resource measurements. Include internal/overlapping CDSs,
leaderless/short leaders, before-TSS and near-end starts, clipped CDS ends,
reverse/circular projection, empty scans, partial failures and all deadlines.
The consumer can apply the same contract to each supplied recode and preserve
its explicit edit-map identities. This wrapper does not propose edits or claim
that a score change is a regulatory effect. Parent #8 stays open.
