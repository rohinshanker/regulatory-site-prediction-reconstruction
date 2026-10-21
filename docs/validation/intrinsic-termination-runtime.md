# Intrinsic-termination adapter contract

- Purpose: Freeze the optional external-engine interface before parallel implementation.
- Scope: Source-admitted bounded TransTermHP fragment adapter for #62; implementation and exact runtime verification in progress.
- Last verified: 2026-10-21

Read the [source boundary](intrinsic-termination-source.md) first. This interface
preserves retained native motif candidates and their background scores. It does
not estimate termination efficiency, readthrough or expression. Only the fixed
source/table/build profile is supported; no scientific parameter knobs, padding,
gene inference or automatic backend substitution are allowed.

## Input and limits

A `termination-request-1` envelope has exactly `schema_version`, `records` and
`settings`. Each record has exactly `id` and `sequence`; IDs are unique ASCII
`[A-Za-z0-9_.:-]` strings of1–128characters. Settings contain only `max_seconds`
(0.001–300) and `per_record_seconds` (0.001–60), finite numbers excluding booleans.
At most20records are accepted. Normalize explicit ASCII whitespace and uppercase
before requiring A/C/G/T, maximum100000bases. Do not translate U to T or accept
ambiguous bases. Preserve normalized sequence length and SHA256 without exporting
sequence unnecessarily. Reject malformed records individually; invalid envelopes
have no accepted roster. Every accepted roster position survives a deadline.

Transport is strict UTF8 JSON, unique keys, finite numbers, depth at most32,
and at most4MiB received bytes. The Python-object API has a separate24MiB
canonical-ASCII size cap; received Unicode bytes must not be measured by escaped
canonical size. Output is fully serialized before writing, maximum32MiB.

Lengths below75 are unsupported; length75 has zero search positions and remains
an explicit unsupported-domain record with null candidates, not a measured
negative. Length76 has one anchor per strand. Return both half-open anchor
intervals and their counts. Require mixed AT/GC in the interior `[2,N-2)` and the
four outer synthetic-boundary bases. Report counts, denominator, binary64 nearest
table, endpoint clamping and exact rational tie status separately for each group.

## External engine and process contract

The backend is supplied separately from the request, by an explicit local backend
manifest. Absence or invalidity is a typed backend failure; there is no network,
automatic discovery, installation or fallback. A valid manifest binds the source
archive, admitted patches, fixed compiler flags, binary bytes and required table.
The executable and table are local regular files; reject final symlinks, special
files, oversized or changing reads. Verify the table and executable hashes before
execution. This verifies the supplied build receipt and bytes; it cannot prove a
caller-authored compiler claim independently of the trusted build workflow.

The offline builder accepts only the pinned source archive and required patch,
an explicitly selected installed compiler and a new external output directory.
It checks archive/member hashes and safe paths, excludes bundled executables,
preserves source/notices separately and builds only `transterm` with `make -j1`.
No download, install, calibration or host configuration occurs. A completed backend
manifest is written only after the build succeeds and the executable is identified.
Common package configuration and console registration belong to A.

One fragment runs per process with a private temporary working directory and
fixed filenames/identifier: `input.fasta`, `input.coords`, `expterm.dat`,
`fragment`, `boundary_left`, `boundary_right`. Copy verified table bytes into the
working directory. The exact arguments are `-p expterm.dat --all-context -c 0 -S
input.fasta input.coords`. Keep default scientific settings. Raise only the owned child soft stack limit to at least8MiB before exec,
preserving its hard limit; fail closed if that limit or setup forbids it. The
adapter does not change parent/host limits or invoke a shell.

Bound stdout to262144bytes, stderr to65536bytes and retained candidates to1000.
A record uses the smaller of its per-record budget and remaining batch budget.
Timeout, output overflow, nonzero exit, launch/read failure and malformed output
are distinct typed failures with null candidates. Retain captured byte hashes,
byte counts and exit status when available; never mislabel a captured prefix as
a complete output. Kill/reap only an owned unreaped child; no stale process-group
signalling. All temporary resources are removed on every path. There is no
parallel native execution inside one request.

## Parsing and result identity

Validate the fixed version/header parameters, one fragment length, synthetic
boundary rows, region counts and consecutive native TERM numbers. Reject unknown
or malformed nonempty output lines, unexpected sequence output, invalid intervals,
strands, contexts, costs, confidence or notes. Costs remain their native printed
decimal strings. Printed hairpin `-2` can be valid and must not be rejected by
reapplying the strict internal cutoff. Preserve native notes as bounded source
bookkeeping; they are not biological annotations.

Convert TERM coordinates to ascending zero-based half-open hairpin intervals,
and derive the15-base tail interval on its strand. Preserve full native retained
rosters, including overlapping candidates. Canonically sort by start/end/strand;
numbered canonical candidate IDs do not reuse native TERM IDs. Preserve the
native ID/context/notes as provenance. A forward candidate starting at index1
retains its geometry/costs but has null admitted confidence and a boundary-
ambiguity status. Every other admitted confidence is an integer background
candidate score, never a probability. Do not restore pruned mirror candidates.

`termination-result-1` binds the complete canonical request, fixed model profile,
backend identity, settings, roster, coverage and warnings. Each record separates
input/domain validation, attempted execution, successful parsing and candidate
count. Null candidates mean unsupported, failed or unevaluated; an empty list is
reserved for a successful native search with no retained candidates. Batch status
is complete only when every record succeeds. Wall-clock timing and temporary
paths are execution details and must not change prediction identity. Hash the
complete result excluding only its own `prediction_sha256` field.

Implementation, strict schemas, every-path tests, real native fixture replay and
finite independent exact-patch review must verify this contract before completion.
The [native smoke receipt](../../benchmarks/termination/native-smoke-manifest.json)
is executable evidence for original artificial inputs, not biological validation.
