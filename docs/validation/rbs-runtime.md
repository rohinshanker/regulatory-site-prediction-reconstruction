# RBS runtime and reconstruction profile

- Purpose: Reproduce the implemented RBS contract, installation and validation gates.
- Scope: `salis-v1-rnastructure-6.6-reconstruction-1`, schema 1.0; sequence-relative prediction.
- Last verified: 2026-10-16

## Identity and equations

This is a working reconstruction, with source equations from Salis v1 commit
`8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307`, not the original NUPACK implementation
or the hosted De Novo DNA model. See [source/licence evidence](rbs-source-decision.md)
and [NOTICE](../../NOTICE). `rbs.py` retains the upstream copyright and GPL notice.
No code is copied from iDOG's unresolved borrowed wrapper. RNAstructure 6.6 is a
separate GPL-2.0-only executable installation; no library is linked or bundled.

The result records the complete scalar parameter set, source commit, package
version, backend executable hashes, table-manifest hash and explicit settings.
The expected source-archive hash is an installation pin, not proof of a binary's
build ancestry. The documented installer checks it before compilation. A source
or parameter change requires a new model profile; an implementation change
requires a new package version before release.

For each supplied or scanned start at oriented position `s`:

1. Predict the minimum structure of `[max(0,s−35), min(n,s+35))` with
   `Fold --MFE`, then evaluate it with `efn2 --simple` for unbound mRNA energy.
2. Cofold the upstream portion and explicit 9-nt aSD, permitting intramolecular
   pairing. RNAstructure's 100 tracebacks, 100-percent energy window, zero
   diversity window and 30-nt internal-loop cap are fixed. Retain structures
   with interstrand pairs within 3 kcal/mol of the lowest **connected**
   reevaluated energy (1e-9 numerical tolerance). Disconnected structures lack
   the association energy term and must not define this connected-complex band. This is a bounded search,
   not NUPACK's exhaustive 3-kcal/mol suboptimal enumeration; it can miss states.
3. For interstrand pairs `(m,r)` in zero-based leader/aSD coordinates, choose
   the greatest paired `r`. Preserve the legacy strict boundary `m+1 < len(leader)`.
   Aligned spacing is `len(leader)−m−(r+1)`. Minimize cofold energy plus the
   unrounded Salis spacing penalty; ties take the first backend enumeration.
   rRNA-only pairing cannot become a binding site.
4. Re-fold the prefix before the most 5′ mRNA–aSD pair. Combine that prefix's
   pairs with interstrand pairs on the full window and evaluate with `efn2
   --simple`. The historical 1000-nt footprint prevents all downstream folding
   in this ≤70-nt window. No extra rRNA self-fold or downstream fold is added.
5. Re-fold the prefix ending four bases before the binding site, clamping to
   the window boundary. Reevaluate the combined structure. Signed standby energy
   is `min(0, complex_before − complex_after)`; subtract this signed value.
6. `dG_total = complex_before + spacing + start − unbound − standby_signed`.
   `tir = 2500 × exp(−dG_total / 2.222)`. No separate rRNA energy is subtracted,
   matching the executable upstream equation. The score is relative, not an
   absolute rate or probability. Nonfinite or underflowed scores fail explicitly.

The reconstructed structure after standby is returned even if the signed
correction was clamped to zero; both evaluated energies make this visible.
The plain dot-bracket strings represent individual strands of a joint structure:
interstrand parentheses are balanced only when the strings are concatenated.
Pair lists are the authoritative mapping. The artificial `III` linker never
appears in reported biological coordinates.

All predicted and constructed structures use `efn2 --simple` for scoring,
including candidate ranking and the 3-kcal/mol filter. RNAstructure's native
prediction energies are retained separately; differences trigger an explicit
warning. Even `--simple` can disagree with Fold/bifold's native objective, so
this does not prove global minimum selection under the evaluation function.
An absent CT energy remains null in native provenance and is explicitly
evaluated, never assumed zero. `Fold --MFE` avoids the extra positive-energy
traceback sometimes emitted by the combination `--maximum 1 --window 0`. Invalid/nonreciprocal CT
output remains a failed computation; it is not repaired into a guessed structure.
A known 6.6 diagnostic leader `UGGCUUGACGGCGUCAUUCCUAUUAUCAAAGCAAU`
with aSD `ACCUCCUUA` produced a nonreciprocal suboptimal CT during review.
Rejecting that entire search is intentional: silently discarding an unknown
candidate could change the band reference or selected state. This backend
limitation remains visible in failure/coverage denominators for ticket 06.

RNAstructure parameters, dangles/coaxial stacking, isolated-pair rules, loop
caps, traceback ordering and suboptimal enumeration differ from NUPACK rna1999.
The historical `start > 35` auto-dangle switch cannot be reproduced by this
interface; every result warns of this difference. The constant rate scale,
spacing and start energies remain historical at every requested temperature;
non-37°C predictions explicitly warn that these scalars were not recalibrated.

## Input, output and missingness

The [input schema](../../schemas/rbs-request-1.0.schema.json) and
[result schema](../../schemas/rbs-result-1.0.schema.json) are version 1.0.
`schema_version` defaults to `1.0` on input; other supplied versions fail.
Runtime validation additionally enforces normalized sequence and index bounds.

- Uppercase, remove whitespace, and map T to U. Reject ambiguous bases. Sequence
  coordinates count normalized nucleotides, not raw text characters. Record
  raw, normalized and oriented SHA-256 identities.
- Require a 9-nt `anti_sd` in its own 5′→3′ orientation. It is never reverse
  complemented when selecting the mRNA minus strand. Optional `host` is metadata,
  not a calibrated preset. ACCUCCUUA and ACCUCCUUU remain separate scenarios.
- `strand: "-"` scores the reverse complement of normalized supplied sequence.
  `start_positions` always indexes this oriented sequence. JSON integral numbers
  such as `20.0` normalize to integer indices; booleans and fractions fail. Omitted/null scans
  AUG/GUG/UUG; an empty list requests no starts. Explicit CUG is supported.
- Report intervals as zero-based, half-open, ascending bounds in the normalized
  **supplied** sequence, with strand. Report window-relative pair positions
  separately, and window bounds in transcript orientation. Binding spans are
  the first through last paired mRNA base, not an experimentally established SD
  motif. Standby spans are modeled unpaired prefixes, possibly shorter than 4 nt.
- Starts at position zero are unsupported leaderless initiation. Circular
  sequence wrapping, genome projection, kinetic/refined RBS models and design
  are not implemented. No fabricated feature intervals are emitted for them.

| Status | Meaning |
| --- | --- |
| `ok` | Every selected start was scored successfully. |
| `no_candidate` | No selected starts, or at least one selected start had no viable interstrand candidate in this bounded search; not proof of no biological initiation. |
| `unsupported` | At least one start/model configuration is unsupported. |
| `invalid_input` | This record failed validation. |
| `failed` | At least one site failed computation, or its request budget was invalid/exhausted. |

For mixed site outcomes, precedence is failed → unsupported → no_candidate → ok.
Successful sites remain in mixed results. Inspect site statuses, not just the
record status. Non-ok sites have null energies, structures and scores, never
zero sentinels. Malformed/oversized JSON or unavailable installation fails the
CLI as a whole (exit 2); individual invalid/failed records give exit 1 while
preserving valid batch results. Completed unsupported/no-candidate records give
exit 0. Standard output is JSON/CSV only; diagnostics go to standard error.

JSON is authoritative; CSV is a summary with a row even for missing results.
Prediction identity hashes request provenance, model/backend identities and
wall-time policy. Binary changes, orientation changes and raw input changes
can intentionally change that identity. Runtime timestamps and machine paths
are excluded. Output metadata is copied and cannot mutate model constants.

## Installation and reproducibility

Python ≥3.11; CI targets Python 3.11 and 3.14 on Ubuntu 24.04 and macOS 14.
Windows is unverified. The Python runtime has no third-party dependencies.
Build/test dependencies are version/hash locked in `requirements-dev.lock`.
Their installed metadata identifies MIT, BSD, Apache-2.0, MPL-2.0 or PSF-2.0
terms (the exact distributions/versions are in the lock); they are development
only and are not bundled with the runtime. Python itself is separately installed
under its PSF/component notices. Source-derived fixture compilation is GPL-3.0-or-later.
The lock generator uses pip 25.3 because pip-tools 7.5.3 imports an API removed
by the installed newer pip. Do not regenerate with an untested toolchain.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

Install RNAstructure separately from its pinned source archive, preserving its
source and licence. Choose a user-writable installation directory. Download
requires network; installed inference and fresh wheel installation do not.
The official URL is mutable: refuse a different hash rather than silently
upgrading. A retained matching archive can be used instead of downloading.

```sh
mkdir -p .cache
curl --fail --location https://rna.urmc.rochester.edu/Releases/current/RNAstructureSource.tgz -o .cache/RNAstructureSource.tgz
python3 -c 'import hashlib,pathlib; assert hashlib.sha256(pathlib.Path(".cache/RNAstructureSource.tgz").read_bytes()).hexdigest()=="1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3"'
tar -xzf .cache/RNAstructureSource.tgz -C .cache
make -C .cache/RNAstructure -j2 Fold bifold efn2
export REGSITE_RNASTRUCTURE="$PWD/.cache/RNAstructure"
```

On macOS with installed command-line developer tools, replace `make` with:

```sh
sdk="$(xcrun --show-sdk-path)"
make -C .cache/RNAstructure -j2 Fold bifold efn2 CXX="clang++ -isysroot $sdk -isystem $sdk/usr/include/c++/v1"
```

No administrator access is needed when a compiler/SDK already exists. If absent,
the user must install/approve developer tools separately. Always use the backend
root: macOS's `/usr/bin/fold` is an unrelated text utility. At startup all 45
pinned parameter files and all three executable version strings are checked;
actual executable hashes are included in the result. Runtime scratch files are
private temporary directories removed after each operation.

```sh
.venv/bin/regsite examples/rbs-single.json
.venv/bin/regsite examples/rbs-batch.json --format csv
```

## Validation gates and resources

Run these from the repository root with `REGSITE_RNASTRUCTURE` set. Missing this
variable skips real-engine fixtures, so that run cannot satisfy release gates.

```sh
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src/regsite
.venv/bin/python -m pytest --cov=regsite --cov-report=term-missing
.venv/bin/python -m build --no-isolation
.venv/bin/python -m venv .cache/fresh
.cache/fresh/bin/python -m pip install --no-index --no-deps dist/*.whl
.cache/fresh/bin/regsite examples/rbs-single.json
.cache/fresh/bin/regsite examples/rbs-batch.json
.cache/fresh/bin/regsite examples/rbs-batch.json --format csv
git diff --check
```

The test suite requires 100% runtime statement/branch coverage, checks the
independent scalar and engine fixtures, reverse-strand mappings, exact standby
algebra, partial failures, parser corruption, timeouts, schema missingness, and
real single/batch execution. CI runs the gates and fresh-wheel examples on all
four Python/platform combinations; its actual run status is authoritative.

Limits: 10,000 normalized bases, 1,000 selected starts, 100 batch records,
2,000,000 input/output text characters. One process handles at most 70 mRNA
bases plus 3 linker/9 aSD positions, ≤100 structures and one thread. Process
wall-time is capped at 15 s and total folding time at 60 s per record by default,
configurable up to 120 s. Input-size/window caps bound computational memory;
there is no operating-system memory quota. The shipped batch provides a reproducible smoke workload; measure wall time and
peak RSS with `/usr/bin/time` on the actual installation, since every predicted
structure is reevaluated and backend binaries/hosts differ.
Timeout failure is tested, not
silently converted to no binding. Large native-genome scans require a separately
validated adapter and budget policy.

Independent checks establish the unrounded spacing/rate/standby equations and
RNAstructure hairpin/duplex energies (−1.2/−11.6 kcal/mol). The synthetic RBS
example totals −12.794 and scores approximately 791687.32. These do **not**
establish historical whole-model, hosted or experimental accuracy. Benchmark
and hosted discrepancies belong to the separate evidence protocol; freeze them
before using outcomes for improvements. Native UTEX calibration remains absent.
