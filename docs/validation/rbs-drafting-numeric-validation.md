# Independent artificial drafting numerical validation

- Purpose: Freeze original artificial expectations and check explicitly supplied external results against the public drafting interface.
- Scope: Supplied-rate stationary arithmetic and software contracts only; no predictor execution, biological outcomes, fitting or accuracy claim.
- Last verified: 2026-10-21

The [checker](../../benchmarks/rbs/drafting_numeric.py) and
[frozen panel](../../benchmarks/rbs/drafting-numeric-fixtures.json) implement the
[public v1 contract](rbs-drafting-contract.md) using the already admitted
[source mathematics](rbs-kinetics-source-admission.md). The fixture SHA-256 is
`54ff3c58945f43cd636ac42474c8ede4f39fe25fe49a62aa32327952973a69b6`
(513,526 bytes, below 512 KiB). The checker authenticates these exact bytes and
the four recorded source/contract identities before checking any result. Those
source bytes were separately verified at preparation baseline
`1897fc53d32f0e07bf27540f74acdb5cd5a78b10`. They are historical references;
the checker does not reopen mutable integrated documents or claim to verify
their current bytes. It cannot
replace expectations or pins from candidate data. Keep the fixture and protocol
commit frozen before any separately authorized candidate execution.

## Independent derivation and numerical rules

Normalize JSON rates to finite binary64 first, then use `Fraction.from_float`.
Original decimal text is not the mathematical input after that normalization.
For a cycle beginning when the occupied site clears, the mean residence times are

```text
U: 1/(a+f)
F: [f/(a+f)]/b
B: 1/e
```

Normalize these three exact residence times for occupancies; invert their sum
for throughput. No direct products of floating-point rates are needed. A separate
exact Gaussian elimination of two stationary balances plus normalization checks
this construction. The six admitted rational controls also check throughput,
finite-clearance fast-fold limits and their ratios. Source fixtures remain
unchanged. This is an independent derivation from public mathematics, without
reading or importing predictor source, tests, package internals or outputs.

Before constructing expectations, Decimal precision was fixed at **120 decimal
digits**. Divide the exact numerator by denominator and take `Decimal.ln` at
that precision, then round the log to binary64. Positive arithmetic avoids
cancellation in the residence calculation. The precision comfortably exceeds
binary64 precision and the absolute log tolerance, including extreme-rate logs;
logs extremely close to zero need only the declared absolute accuracy. Finite
logs are retained even when an occupancy rounds to zero.

The fixed comparisons are:

- Ordinary positive linear quantities: `abs(candidate - q) <= q/10**11`, with
  `q` the exact rational expectation and the candidate converted to an exact
  rational for this comparison.
- Natural logarithms: absolute difference at most `1e-10`; null, booleans and
  nonfinite values fail.
- For exact `0 < q < min_normal`, first form the exact interval
  `[q*(1-1e-11), q*(1+1e-11)]`, then round each endpoint to binary64, nearest
  with ties to even. Accept a finite positive candidate in that inclusive
  quantized interval. This expresses the ordinary tolerance at subnormal
  resolution, rather than imposing impossible relative precision on an already
  rounded float. Values at or above `min_normal` use the ordinary rule.
- Representation is independently fixed by rounding **q itself**: `finite` if
  that is positive; `underflow` with null linear value if it is zero. Only
  folded occupancy with `f=0` is `exact_zero`, with linear zero and null log.
  A tolerance interval crossing zero does not permit switching representations.
  Occupancies cannot exceed one, and their non-null logs cannot exceed zero;
  numerical tolerance does not relax either schema bound. Signed zero folding
  input must echo as +0.

One deliberate boundary is `finite-panel`, record
index **5**, occupied occupancy has quantized interval `[0, min_subnormal]` but
its exact value lies just above half a minimum subnormal. It therefore rounds to
`min_subnormal` and requires `finite`. Its frozen
`zero_boundary_ambiguous: true` flags that a tolerance-scale perturbation crosses
zero; it does not widen acceptance. Before any candidate execution, A explicitly
confirmed this strict rule in contract clarification
[`c9ab1e9`](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/commit/c9ab1e9fbc34da188f4f9c2b0fb8027d82b75d3e),
whose `docs/validation/rbs-drafting-contract.md` is 8,188 bytes, SHA-256
`688222af1c2bd29caacb5c7ff0bb770ced30f7dd86bf1fe0d1b2d593a14bf220`.
That clarification resolves the question without changing the fixture or
tolerances. It is a separate historical reference, not a replacement source pin.

For this domain, throughput always rounds positive:
`J >= e*b/(e+b) > b/2 >= min_subnormal/2`. In particular the coordinator-supplied
artificial cross-check `a=b=min_subnormal, f=e=max_binary64` has occupied occupancy
rounding to zero while throughput rounds to `min_subnormal`, with finite log
approximately `-744.4400719213813`. Throughput-underflow payloads are software
mutations, never admitted biological examples.

## Panel and complete accounting

There are **30 frozen requests**, containing **305 record entries** in parseable
request rosters, including invalid envelopes. The accepted rosters contain
**198 records**: **48 expected successes**, **139 invalid records**, and
**11 unsupported-domain records**. There are **17 invalid-envelope/transport
cases**. All remain present in the panel and in reports; invalid envelopes
correctly have empty public result rosters and null coverage. Their original
rosters are retained in the frozen request text. No successful subset is a
replacement denominator.

Categories are explicit on every case. They cover all six admitted controls,
ordinary and extreme finite rates, equal binding, zero and negative-zero folding,
common scaling, finite clearance just above its strict bound, minimum subnormals,
maximum finite values, representation neighbors, singular/domain refusals,
malformed records/IDs/units/provenance/rates/envelopes, roster bounds, duplicate
keys/IDs, nonfinite JSON, request hash number forms, wire and canonical size limits.
The 100-record boundary case intentionally uses malformed records; its entire
accepted roster must still be evaluated and retained. No random selection,
sequence or empirical outcome appears in the panel.

Each case has exactly `id`, `category`, `wire`, `trailing_spaces`, `expected`.
The request bytes are exactly:

```python
case["wire"].encode("utf-8") + b" " * case["trailing_spaces"]
```

The bounded space recipe permits input-limit checks without storing a megabyte
of padding. The canonical-size rejection has compact UTF-8 below the input cap
and escaped canonical JSON above it. Input wire and canonical object caps are
independently 1,048,576 bytes. Rejected wire/JSON requests have null request hash;
canonicalizable invalid envelopes retain the original parsed-object hash when
within its cap. Transport rejection occurs before unsafe parsing. Parsed integer
`2` and float `2.0` have different request hashes; `2e0` and `2.0` parse to the
same float and have the same canonical hash. Echo normalization alone uses floats.

## Frozen candidate identity receipt

An external UTF-8 JSON receipt is mandatory. Its exact top-level keys are
`schema_version`, `model`, `warnings`, `candidate`:

- `schema_version` is `drafting-candidate-identity-1`.
- `model` has exactly the six public model fields, including the installed
  `implementation_version`. A supplied `0.12.0rc1` as the current candidate
  version. Core model values must equal the frozen public contract.
- `warnings` is exactly the following ordered array, with no extra strings.
- `candidate` has exactly `source_commit` (40 lowercase hex digits),
  `wheel_sha256` and `settings_sha256` (each 64 lowercase hex digits). Freeze
  the exact execution settings externally and record their SHA-256 here.

```json
[
  "Rates and provenance are unverified caller inputs, not measurement evidence.",
  "Stationary memoryless states omit ribosome traffic and transcript turnover.",
  "Throughput is initiation-region passage, not completed protein production.",
  "Neither native-host accuracy nor hosted parity is established."
]
```

Coordinator B supplied this public schema constant from source commit
`356abc2d40198a95f807967a38126a14b0f3d0c9`, path
`schemas/drafting-result-1.schema.json`, SHA-256
`0b5dc941cac51ff8cbe7d70e63a0a6633a3a9bffe1f6991625ab2dc018b62371`.
The implementer received this identity from B, who verified the public schema
bytes directly. Neither read candidate internals. The fixture records the
implementer's supplied-evidence distinction. Warning identity is explicit; no keyword
or semantic inference is used. Tests simulate separate warning identities using
clearly artificial strings and also test this supplied public constant.

B/A must supply and freeze the complete receipt and its byte SHA-256 **before
execution**. A missing receipt is a setup error, never a passing check. The checker
binds all result model fields and warnings to the receipt. It does not read a
source checkout, wheel or execution settings, so those receipt hashes remain
claims; matching them does not independently verify candidate bytes or settings.

## Later execution protocol

Preparation and review do not authorize execution. After A accepts the immutable
fixture/protocol commit and explicitly authorizes the candidate run, freeze an
external settings file and identity receipt. The current proposed package is
0.12.0rc1, source `356abc2d40198a95f807967a38126a14b0f3d0c9`, wheel SHA-256
`a95abeeca03360e94b2d79a469520c62cfb8d45ff505dc6395032d9aa2f6c11b`
(189,790 bytes), supplied by A. Preserve that original candidate even if a later
package exists. Verify the actual wheel and installed-file receipt before running;
the result checker cannot establish those identities by itself.

Use all 30 cases in fixture order, once each, with no retries or outcome-dependent
selection. Materialize request bytes using the frozen recipe above into exclusive
external files and record their SHA-256 and byte counts. From an external working
directory, the command for each case is:

```text
ABSOLUTE_CANDIDATE_PYTHON -I -B -m regsite.drafting_cli ABSOLUTE_REQUEST_FILE
```

Freeze the resolved interpreter/installed candidate, exact argument arrays,
environment, fixture/protocol/checker identities and the following execution
limits in the settings receipt before starting: one serial process, ten seconds
per request, stdout bounded at 4,194,305 bytes (one byte beyond the result cap),
stderr at 65,536 bytes, and no network/backend/folding process. Retain explicit
exit/timeout/overflow status, byte counts and hashes in the execution receipt;
store complete outputs within those limits. A timeout, overflow, identity change
or unexpected exit stops subsequent execution and requires a finding disposition,
not an automatic rerun. Unstarted cases remain missing in the full denominator.
An ordinary checked numerical mismatch does not change inputs or tolerances.
`-I` isolates import configuration; `-B` prevents bytecode writes into the
externally owned installed candidate.

Expected CLI exits are 0 for complete envelopes, 1 for partial envelopes and 2
for invalid envelopes/transport. Check these against the execution receipt
separately. Also require complete received stdout to equal the prescribed
authoritative JSON serialization byte-for-byte, including its final newline.
The JSON checker accepts other JSON whitespace that meets both byte caps and
does not attest exact CLI formatting. It receives only result files and does not
verify process exit codes, environment, elapsed time, stderr or installed code. Preserve
those evidence limits in any combined conclusion. Candidate outputs and execution
receipts stay external; only a compact public numerical summary may later be
added within a separately agreed path. No current candidate result has been read.

## Offline checker invocation and outputs

From the repository root, with Python 3.11 or later:

```sh
python -m benchmarks.rbs.drafting_numeric --help
python -m benchmarks.rbs.drafting_numeric \
  --identity /absolute/external/frozen-identity.json \
  --identity-sha256 "$FROZEN_IDENTITY_SHA256" \
  --result control-equal_binding_rates=/absolute/external/control-equal_binding_rates.json \
  --output /absolute/external/new-report.json
```

That second command is complete syntax but deliberately supplies only one case:
it reports the other 29 as missing and exits 1. Supply one repeated
`--result CASE=PATH` for **every** frozen case ID for a possible all-pass result.
There is no subset mode. Unknown/duplicate case IDs and malformed path mappings
are invocation errors. There is no globbing, recursive search, subprocess,
predictor, network call or automatic result discovery. Paths are local explicit
regular files; final symlinks, devices, FIFOs and oversized files are refused.
Only the first `=` separates the case ID and path.

Strict UTF-8 JSON rejects BOM, duplicate keys and nonfinite tokens or converted
floats. Each result wire read is bounded before parsing at **4,194,304 bytes**;
the independently reconstructed authoritative result serialization must also fit
that cap. Authoritative formatting is sorted, indented by two, ASCII escaped,
finite-only JSON plus one newline. Compact canonical hashes use sorted keys,
compact separators, ASCII escaping and no newline. Unknown fields fail exact key
checks; they are never silently dropped to make a prediction hash match.

Checks include exact public key sets, supported schemas, whole-model identity,
exact warnings, original request hash, full prediction hash, roster order,
index/ID/status, normalized input echo, provenance/units, reasons, coverage,
refusal nulls, and all four quantities. The contract leaves concise reason-code
text unspecified, so refusals require a nonblank string; successes require null.
A `numerical_failure` in place of an expected success fails. Tests rehash semantic
mutations so arithmetic and structure checks are exercised beyond hash rejection.

Reports use fixed fixture order and deterministic serialization. They retain the
full expected denominators and every case, including missing or unreadable
results. Each row states its expected record count, failures and credited record
count. Each successfully read result also records its exact received byte count
and SHA-256, including malformed JSON; missing, unreadable or over-limit files
have null byte identities. CLI reports bind the identity receipt and checker
source bytes by SHA-256. This is a byte identity, not an attestation against
concurrent modification of the local process or files. A case earns credit for
all its expected records only when every check
passes; otherwise it earns zero. Credit is contract agreement, not biological
accuracy. Supplied unreadable/oversized files produce explicit transport failures
while retaining all-case accounting. Invocation/trust errors emit an explicit
stderr diagnostic and do not emit a partial-looking report.

Exit codes are **0** for all cases passing, **1** for checked failures or missing
case paths, and **2** for invocation/trust/setup errors or supplied-file transport
failures. Without `--output`, the report goes to stdout. File output uses a private
0600 temporary file and an atomic exclusive hard link in the destination parent;
it refuses existing files/symlinks and protected fixture/checker/source/identity/result
paths. It never overwrites a report or input. The existing destination parent
must permit creating and linking regular files.
Parent-directory path swaps are outside this local-file threat model; use an
exclusive task directory and preserve source, identity and result files during
checking. No directory tree is traversed or recursively authenticated.

## Isolated verification

The [tests](../../tests/benchmarks/test_drafting_numeric.py) import only this tool
and standard/test libraries. The root test conftest imports the predictor and
must be excluded. No environment installation or shared settings edit is needed.
Use the pre-existing permitted interpreter and an exclusive external scratch:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
COVERAGE_FILE=/tmp/drafting-numeric-evidence-20261021/worker/.coverage \
/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-wave4-runtime/.venv/bin/python \
  -m pytest -p pytest_cov --confcutdir=tests/benchmarks \
  tests/benchmarks/test_drafting_numeric.py \
  --cov=benchmarks.rbs.drafting_numeric --cov-branch --cov-report=term-missing \
  -o cache_dir=/tmp/drafting-numeric-evidence-20261021/worker/pytest-cache \
  --basetemp=/tmp/drafting-numeric-evidence-20261021/worker/pytest-tmp
```

Require full statement and branch coverage of the tool, focused Ruff checks and
format checks of both new Python files, and mypy of the tool only. Keep their
caches in the same exclusive scratch. Do not run the runtime suite, load backend
plugins, import a predictor or execute a candidate. Check local links, ticket
fields/indexes and `git diff --check`. Independent exact-patch review belongs to
B after the committed handoff; candidate collection requires its separate freeze
and authorization. Neither arithmetic nor coverage establishes host accuracy,
sequence-to-rate inference, experimental calibration or hosted equivalence.
