# Intrinsic-termination adapter contract

- Purpose: Specify the optional external-engine interface and reproducible offline verification.
- Scope: Independently reviewed optional TransTermHP fragment adapter with accepted 0.12 development-package and Linux/macOS integration gates.
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
The POSIX runtime requires an executable temporary filesystem for its private
binary copy. A noexec temporary filesystem produces a typed launch failure.
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
The accepted development package registers `regsite-termination`; its engine
remains an explicitly supplied external dependency.

One fragment runs per process with a private temporary working directory and
fixed filenames/identifier: `input.fasta`, `input.coords`, `expterm.dat`,
`fragment`, `boundary_left`, `boundary_right`. Copy verified table bytes into the
working directory. Copy the verified executable bytes there with mode 0700 and
execute that private copy; concurrent replacement in the installation cannot
change the bytes selected for this record. The exact arguments are `-p expterm.dat --all-context -c 0 -S
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
parallel native execution inside one request. The public native API is supported
from a single-threaded Python process: child stack setup uses POSIX `preexec_fn`,
which is unsafe in processes with running threads. Use separate worker processes
for concurrency; the internal lock does not make threaded use supported.

The 100000-base input bound is an admission limit, not a guarantee that every
fragment completes within output, candidate or time limits. More than 1000
retained candidates produces `native_candidate_limit`, with null candidates;
no partial roster is returned. The parser still checks every remaining row,
trailer and context count before reporting overflow, so later corruption remains
`native_output_invalid`. Retained candidate storage stays capped at1000.
The candidate limit can apply below the length bound, depending on sequence.
Long-fragment completeness and candidate-density estimates are unverified.

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
retains its geometry/costs but has null `confidence` and null
`native.printed_confidence`, with a boundary-ambiguity status. Its native context
and raw-output byte identity remain available; the ambiguous numeric score is
not exported in the structured candidate. Every other admitted confidence is an integer background
candidate score, never a probability. Do not restore pruned mirror candidates.

`termination-result-1` binds the complete canonical request, fixed model profile,
backend identity, settings, roster, coverage and warnings. Each record separates
input/domain validation, backend invocation, successful parsing and candidate
count. `attempted` means the adapter's `run` method was called; it does not assert
that a native process started. Lock, artifact, stack or setup failures can have
`attempted: true` and null `execution`. Capture-helper failures retain diagnostics
when available; null `returncode` does not assert a launched native process. Null candidates mean unsupported, failed or unevaluated; an empty list is
reserved for a successful native search with no retained candidates. Batch status
is complete only when every record succeeds. Wall-clock timing and temporary
paths are execution details and must not change prediction identity. `prediction_sha256` hashes the complete result after removing each record's
`execution` capture and the hash fields. Native stderr contains elapsed wall-clock
text, so its raw byte identity must not influence prediction identity.
`result_sha256` separately hashes every result field, including the complete raw
capture identities and `prediction_sha256`, excluding only `result_sha256` itself.
Thus execution receipts remain bound even when harmless timing bytes vary.

Strict schemas, failure-path tests and real native fixture replay form the
implementation gate. Independent exact-patch review and common packaging remain
separate requirements. Schema validation checks structure and fixed state
constraints, including boundary confidence, strand/context and strict string
patterns. It does not prove cross-field arithmetic, candidate-tail adjacency,
coverage totals or hash equality; those are checked by producer logic and tests.
The [native smoke receipt](../../benchmarks/termination/native-smoke-manifest.json)
is executable evidence for original artificial inputs, not biological validation.

## Offline use and validation

The Python runtime ships no native engine or background table. With the exact
source ZIP and Debian patch already available, run the repository builder:

```sh
PYTHONPATH=src python tools/build_termination_backend.py \
  --archive /external/transterm_hp_v2.09.zip \
  --patch /external/0002-read_seq-return-NULL-instead-of-false.patch \
  --compiler /existing/compiler/clang++ --output /external/new-backend
```

For the verified Mac build, also pass `--arch arm64`, `--sysroot` with the existing
MacOSX26.5 SDK, `--cxx-include` with its `usr/include/c++/v1`, and
`--standard-library libc++`. The builder restricts paths passed through Make's
shell recipes, forbids extra scientific flags, and records explicit SDK options
in the external build receipt. It writes the backend manifest last; failed builds
cannot produce a successful receipt. Keep the separate source/notices and build
receipt with the executable. No download, installation or privilege is implicit.

```sh
PYTHONPATH=src python -m regsite.termination_cli \
  examples/termination-single.json --backend-manifest /external/new-backend/backend.json
PYTHONPATH=src python -m regsite.termination_cli \
  examples/termination-batch.json --backend-manifest /external/new-backend/backend.json
PYTHONPATH=src python -m regsite.termination_cli \
  examples/termination-unsupported.json --backend-manifest /external/new-backend/backend.json
```

The CLI writes one bounded JSON result. Exit0 means complete,1 means a retained
partial roster, and2 means an invalid envelope/transport failure. The unsupported
example deliberately exits1 with null candidates. Request files must be regular,
with final symlinks rejected; `-` reads stdin. There is no environment-based native
backend discovery. An absent or invalid explicitly supplied backend produces
per-record failure, never fallback predictions.

`max_seconds` is a scheduling budget starting at the public API call. Request
transport and backend loading precede it; final hashing/serialization follows
scoring. Synchronous filesystem/setup operations can finish after the deadline
before the next check reports a failure. A final deadline check prevents
launching a child when setup has already exhausted its budget. It is not a hard wall-time guarantee for
input/output or filesystem calls. Native capture itself has a deadline, and all
accepted roster positions survive expiry.

The [build receipt](../../benchmarks/termination/adapter-build-manifest.json)
binds the original builder output, compiler, native binary and CLI outputs.
The [post-repair runtime receipt](../../benchmarks/termination/adapter-runtime-validation.json)
preserves the original frozen evidence and binds four complete CLI outputs,
including the frozen boundary control. Independent DEM619 exact runtime review,
repair recheck and final overflow check admit code `6113b54a467af3f90a9a70b20a77c2247983a91c`;
all material findings are closed. The earlier receipts retain their actual
checkpoint identities and pending-review status rather than being relabelled. The source-built ARM64 binary passed370 focused tests with zero
skips and100% coverage of712 statements/188 branches, including every original
synthetic roster, automatic child stack setup, CLI invocation outside the checkout,
strict schema validation and missingness. One warning is deliberately produced by
the rejected duplicate-ZIP-member test. CI-scoped Ruff/format (184 files) and mypy (56 source files) also passed.
The builder took8.98seconds; its measured process had321,110,016bytes maximum
resident memory and310,592,232bytes peak footprint. These include reading the
selected compiler for identity and are not native scorer memory measurements.

Reproduce the focused gate with the separately built backend:

```sh
PYTHONPATH=src REGSITE_TERMINATION_TEST_BACKEND=/external/new-backend/backend.json \
  python -m pytest tests/test_termination*.py \
  --cov=regsite.termination --cov=regsite.termination_io \
  --cov=regsite.termination_cli --cov=regsite.termination_backend \
  --cov=regsite.termination_output --cov=tools.build_termination_backend \
  --cov-branch --cov-report=term-missing --cov-fail-under=100
```

Without that explicit test backend,17 native release checks are skipped and must
not be reported as verified. That local receipt establishes only its recorded ARM64 macOS build. The
separate package/platform acceptance below expands the software validation
boundary; genome-scale behavior and biological accuracy remain unverified.

## Accepted development-package and platform boundary

The [0.12 package guide](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/4eba1b6f197cdb843ac778b746fefed0676d6dab/docs/validation/drafting-0.12-candidate.md)
and its [immutable receipt](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/4eba1b6f197cdb843ac778b746fefed0676d6dab/models/drafting/0.12.0rc1/package.json)
bind frozen source `356abc2d40198a95f807967a38126a14b0f3d0c9`. All five
termination modules match reviewed code `6113b54a467af3f90a9a70b20a77c2247983a91c`
in that source, the wheel, the source archive and the tested CI source.

The wheel SHA256 is
`a95abeeca03360e94b2d79a469520c62cfb8d45ff505dc6395032d9aa2f6c11b`;
the source archive is
`2d9f42fe24419faf4ab9be16273af3aba5d275edd578bc4d0a40cc9813706954`.
All 54 installed runtime files match their source. The distribution contains no
native executable or background table. Independent package review and its focused
repair recheck accepted the integration with no open finding.

The combined local gate passed 6,972 tests with zero skips and full coverage of
17,506 statements and 6,514 branches. Thirty fresh offline build/install checks
include installed termination controls and complete identity checks.
[CI 39703039920](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39703039920)
passed all eight jobs at `efe90fcb3b7b788fcd0c2920b68f79eeccae3551`.
Each Linux/macOS and Python 3.11/3.14 runtime job built the native termination
engine and passed its installed controls. Each runtime suite passed 6,971 tests
with one declared exact-original conditional-backend skip unrelated to termination;
the local gate includes that backend. No termination check was skipped.

This completes the scoped intrinsic-termination candidate adapter. Preserve the
source, numerical and missingness contracts above for future changes. Full Operon
inference, sequence-to-stability reconstruction, empirical/native calibration,
consumer admission and publication retain their separate scopes.
