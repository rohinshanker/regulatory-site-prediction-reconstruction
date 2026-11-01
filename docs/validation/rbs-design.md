# Bounded RBS design

- Purpose: Enumerate a small, explicitly allowed leader substitution neighborhood and rank it using an existing named RBS profile.
- Scope: Original local design algorithm, not recovered hosted optimization or biological validation.
- Last verified: 2026-10-31
- State: Implemented and independently accepted; local, fresh-install and platform gates pass in the [0.14.0rc1 engineering package](engineering-0.14-candidate.md). Publication and scientific validation remain separate.

## Source and scientific meaning

The pinned Salis v1 repository includes a GPL-3.0-or-later historical Monte Carlo
designer. Its `RBS_MC_Design.py` at commit
`8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307` has SHA256
`6077524e90fccffa9636ef935b58ec294ff51f5339c36de0393a7c8e6e3b7d3a`
and Git blob `7c0b2799881859f39d06501772e85813a0f4ff81`. Inspection confirms
Python 2 constructs, the historical scorer dependency and an unconstrained
random search. That scorer depends on the excluded required NUPACK runtime;
see [source admission](rbs-source-decision.md). No designer code or its heuristic
constraints are copied into this new deterministic, fixed-length algorithm.

The objective is absolute natural-log distance from the requested **model TIR**.
Scores have the chosen profile's arbitrary relative units. A smaller objective
is not demonstrated expression improvement, calibrated cyanobacterial behavior,
recoding-effect validation or production design equivalence. Existing predictor
limitations/warnings and full native identities remain visible.

## Request and search

`rbs-design-request-1` has exactly `schema_version`, `rbs`, `profile`, `target_tir`,
`editable_positions`, `max_changes` and `limits`. `rbs` uses the existing 1.0
request with exactly one explicit start, canonical uppercase ACGT DNA of at most
1,000 bases and either strand. Only ATG/GTG/TTG starts in transcript orientation
are admitted, with at least one upstream base. Host/aSD/temperature are preserved.
`profile` is a short name in the existing profile registry, not a model-ID alias.

Editable positions are distinct integer indices into the supplied DNA, sorted
canonically. Every position must lie upstream of the selected start within the
profile's scoring window. Minus-strand input index i maps to oriented index
`length-1-i`. The start codon, all coding bases and every unlisted base are fixed.
This first mode does not edit coding sequence, insert/delete bases or discover starts.

`max_changes` is an integer from zero through min(2, editable-position count).
Enumerate seed first, then increasing edit count, lexicographic combinations of
sorted input positions, and A/C/G/T replacement products excluding the original
base. There is no RNG or sampling. Search size is
`sum(comb(n,k)*3**k for k in range(max_changes+1))`.
The whole space must fit `limits.max_candidates` (integer 1–256); otherwise refuse
before scoring. There is no hidden truncation to a preferred prefix.

Limits are exactly `max_candidates`, `seconds_per_score` (>0, ≤120) and
`seconds_total` (>0, ≤3,600), all finite; booleans are not numbers. The total
clock starts before enumeration/scoring. A call's execution budget is the smaller
of declared score seconds and remaining total time. Declared score seconds define
native prediction identity. File/setup/serialization operations use cooperative
checks; no OS-wide resource or strict end-to-end wall-time guarantee is implied.
No retries or resume. Every planned candidate remains represented if time expires.

## Results and selection

`rbs-design-result-1` binds the complete request, algorithm/version, profile,
backend and native model identities. Each row retains canonical DNA, exact input
and oriented edits, native outcome and score or explicit null. Full admitted
native records are retained, with an independent canonical hash. All native
identity/model/backend inconsistencies, including record ID and profile schema,
stop further scoring; they are not scores.
A rejected non-object response keeps its canonical hash with a null payload.
Each embedded native record has a 128 KiB pretty-JSON allocation cap; oversized
records remain explicit failures with their hash and no retained native payload.
The full authoritative pretty JSON plus newline is capped at 64 MiB before stdout.
Malformed/oversized output produces a small typed refusal, never a selected prefix.

Only successful singleton native scores with finite positive TIR/finite log TIR
are ranked. Order is absolute log error, edit count, then canonical input DNA.
The lowest-ranked observed success is a proposal. It is scored again in a fresh
predictor call with the same declared identity, and constraints are checked again.
Selection requires exact complete native-record hash agreement. A failed,
changed or unstarted confirmation yields no verified selected sequence. No
alternate candidate is tried after failed confirmation.

Complete means every candidate scored successfully and confirmation matched.
Partial means some candidate or confirmation failed/unstarted; a verified best
among successful candidates may still be returned with explicit incomplete
coverage. No-candidate means no successful candidate was observed. Invalid input
has no admitted roster or selected sequence. A verified selected sequence is
never called the global optimum when any candidate is missing or failed.
CLI exits: 0 complete, 1 partial/no-candidate, 2 invalid/setup/transport error.
The request and result structural schemas are
[`rbs-design-request-1`](../../schemas/rbs-design-request-1.schema.json) and
[`rbs-design-result-1`](../../schemas/rbs-design-result-1.schema.json). Runtime
checks enforce the additional sequence, roster, identity and count relationships.
A native record rejected for its identity/shape may be retained as opaque failure
evidence; its presence is not admission. The CLI reads binary stdin or a regular
file without following its final symlink; directory/FIFO inputs are refused.

JSON is the default and sole initial transport; raw records stay in external
files for real runs. No browser/consumer or existing job-runner change is included.

## Verification

Required checks: independent combinatorial roster/strand invariants and ranking;
all request boundaries and unknown fields; ordinary native failures and nulls;
time exhaustion before/during scoring and confirmation; identity changes and
confirmation mismatch; byte caps and transport errors; exact result hashes;
real tiny artificial offline search with a pinned backend; fresh install and
existing regression gates. Artificial controls verify software behavior, not
biological accuracy. Scientific endpoints require a separate frozen protocol.

## Identity and reproducible invocation

All canonical hashes use SHA256 over `json.dumps(value, sort_keys=True,
separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")`.
`request_sha256` binds the admitted request as supplied; input number spelling
normalized by the JSON parser is not retained. `design_id` hashes the object
with exactly `request`, `algorithm` (the algorithm ID string),
`implementation_version` and `backend`. `result_sha256` hashes the whole result
excluding only that field. It includes elapsed time, so repeat runs can have
stable design IDs and different result hashes. Native record hashes bind their
entire retained values. Native prediction IDs retain the predictor's declared
float score budget; an enclosing shorter execution allowance never changes it.
DNA hashes use the supplied canonical uppercase DNA bytes; oriented edits are
reported separately. No additional genomic assembly or transcript binding is inferred.

Use the existing development environment and explicit separate backend:

```sh
python -m regsite.design_cli examples/rbs-design-single.json --backend-root /absolute/path/to/RNAstructure
python -m pytest tests/test_design.py tests/test_design_io.py tests/test_design_cli.py tests/test_design_schema.py
REGSITE_RNASTRUCTURE=/absolute/path/to/RNAstructure python -m pytest tests/test_design_native.py
```

The small committed example searches four candidates and makes one fresh
confirmation call. A complete result can still be far from its requested target:
`absolute_log_error` is the distance that was actually achieved, not a pass gate
or a biological validation statistic. The target may be unreachable within the
caller-selected edits. Full candidate results make that limitation inspectable.
