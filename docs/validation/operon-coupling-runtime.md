# Supplied-energy reinitiation component

- Purpose: Define a bounded, opt-in adjacent-CDS calculation with explicit inputs and missingness.
- Scope: Implemented `coupling-request-1` / `coupling-result-1`; independent review, fresh package installation, combined local tests and exact-source CI verified; publication and consumer admission remain separate.
- Last verified: 2026-10-21

This component adds a historical reinitiation contribution to a supplied
independent downstream initiation score. The [source boundary](operon-coupling-source.md)
defines its admitted equations and unresolved unfolding correction. It neither
calculates energies from RNA nor reconstructs the complete Operon Calculator.

## Request

The JSON envelope has exactly `schema_version`, `records`, and `settings`.
Schema version is `coupling-request-1`; `records` contains 1–100 objects;
`settings` has exactly `seconds_total`, a finite number greater than zero and at
most 60. A one-record envelope is the single-input form. Received input is
limited to 1,048,576 bytes, not an advertised file size or the larger ASCII-escaped
hash representation. Transport JSON must be finite UTF-8 with no duplicate keys
and container nesting limited to 32 levels. Separately, the Python object API
refuses canonical ASCII representations above 6,291,456 bytes with
`api_object_byte_limit`. This larger guard accommodates Unicode escaping and
number serialization expansion without changing the received-byte limit or
deterministic hashes. All limits are engineering limits, not biological ones.

A record has exactly `id`, `sequence`, `strand`, `upstream`, `downstream` and
`energies`. IDs are 1–128 ASCII letters, digits or `_.:-`; record IDs are unique.
Sequence normalization follows `regsite.sequence.normalize_rna`: remove
whitespace, uppercase, convert T to U; other symbols are refused. Bounds refer to
this normalized sequence, which is limited to 100,000 bases. Strand is `+` or `-`.
The sequence explicitly represents the supplied transcript context, not an
inferred operon or an unlabelled chromosome window.

Each CDS has exactly `id` and `interval`. The interval is zero-based, half-open,
ascending on the normalized supplied sequence and includes the terminal stop
codon. On `-`, map `[a,b)` to `[N-b,N-a)` on the reverse complement before
checking order or distance. CDSs must have distinct IDs, at least two codons,
length divisible by three, an AUG/GUG/UUG start, a UAA/UAG/UGA stop and no internal
in-frame stop. Upstream start and end both precede the downstream start and end
in transcript orientation. Nested, reverse-ordered and same-frame overlapping
CDSs are unsupported; overlapping out-of-frame CDSs are retained. Geometry
validation itself imposes no model distance limits.

`energies` has exactly `upstream_total_kcal_mol`,
`downstream_independent_total_kcal_mol`, `beta_mol_per_kcal`, and `provenance`.
The two energies are finite numbers within [-1,000,000, 1,000,000]. Beta must
explicitly equal the historical value 0.45. Provenance is a nonempty string of
at most 1,000 characters that identifies the caller's common calculation and
energy convention. Supplying a provenance string does not verify that claim.
Both energies refer to these supplied CDSs and this exact RNA; no hidden upstream
score intercept, separate fluorescence scaling or pre-existing coupling term
may be included. The runtime never chooses or fetches an energy model.

## Result and execution

The result identifies the component `tian2015-reinitiation-only-1`, the package
version, source DOI, beta, `k_P`, coefficient domain, supplied-energy convention
and absence of an executed folding backend. Every requested record retains its
index, ID when valid, status and reason. Valid geometry retains original and
oriented intervals, codons, sequence length/hashes, strand and distance; exact
input and output are bound by canonical SHA-256 values. No RNA structure is
invented and full sequences need not be repeated in results.

For a supported record retain both supplied energies/provenance, independent
upstream/downstream log scores, reinitiation log score, total downstream log
score and corresponding finite linear values, as well as the fold change
relative to the independent downstream score. Linear overflow or underflow is
null with `numerical_range`, never infinity or a fabricated zero; valid log
values remain available. Add the two contributions in log space. All scores are
dimensionless and relative. No probability, absolute rate or abundance is
returned. The unimplemented unfolding correction is explicitly null.

Per-record statuses distinguish `ok`, `invalid_input`, `unsupported_geometry`,
`unsupported_distance`, `numerical_range`, and `not_evaluated`. A deadline is
checked before each record and after its calculation; expired work is explicitly
`not_evaluated`, and every later requested record remains present. The component
does no subprocess work, and one record is bounded by the input and geometry
limits. Elapsed time is excluded from scientific identity; requested time budget
is included. A positive budget is not a guarantee that a batch completes.

Top-level status is `complete` only if all requested records are `ok`; otherwise
it is `partial`. A malformed envelope is `invalid_input` with no accepted record
roster. Coverage reports requested, returned, successful, failed/unsupported and
not-evaluated counts with exact partitioning. Warnings always disclose supplied
energies, reinitiation-only scope, historical *E. coli* applicability and lack of
native host calibration. An unsupported component is not a zero contribution.

The module CLI is `python -m regsite.coupling_cli request.json` (`-` for stdin).
It emits one complete JSON object after checking the 4,194,304-byte output cap.
Exit codes are 0 complete, 1 partial and 2 invalid envelope/input/I/O failure.
Inputs/outputs are local, with no credentials, service or runtime network access.
The separately pinned 0.9.0rc1 development package registers `regsite-coupling`
and has passed fresh offline installation.
Independent DEM-618 review and its focused repair recheck cover the strict
transport, arithmetic, geometry, missingness and schema contracts. This evidence
does not establish experimental accuracy. The separate package evidence below
verifies common integration without extending the biological scope.

```sh
PYTHONPATH=src python -m regsite.coupling_cli examples/coupling-single.json
PYTHONPATH=src python -m regsite.coupling_cli examples/coupling-batch.json
PYTHONPATH=src python -m regsite.coupling_cli examples/coupling-unsupported.json
```

The first two examples exit 0; the unsupported-distance example exits 1 with a
null score. They are synthetic arithmetic/coordinate controls, not validated
biological predictions. Request and result shapes are specified by the
[request schema](../../schemas/coupling-request-1.schema.json) and
[result schema](../../schemas/coupling-result-1.schema.json). Runtime validation
additionally checks codons/order, normalized coordinates, duplicate IDs, byte
caps and coefficient domains; schema acceptance alone is insufficient.

Focused verification:

```sh
PYTHONPATH=src python -m pytest -q tests/test_coupling*.py \
  --cov=regsite.coupling --cov=regsite.coupling_geometry \
  --cov=regsite.coupling_io --cov=regsite.coupling_cli --cov-report=term-missing
ruff check src/regsite/coupling*.py tests/test_coupling*.py
ruff format --check src/regsite/coupling*.py tests/test_coupling*.py
mypy src/regsite/coupling*.py
```


## Verified package boundary

Use source `c74ff8fac2331ba1e1e1836d953ea69036133b85` for the 0.9.0rc1
reinitiation development candidate. Its [immutable package receipt](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/8452e14/models/coupling/0.9.0rc1/package.json)
binds all 45 runtime files and the produced wheel/source archives. The wheel
SHA256 is `2c9a16b3a68ca90ddbc5be3d42d3b089bcfe80fc564989a4c766bb33bfc00643`;
the source archive is `93effbd16311dbc5f8e00f6d4f53686b9d832e24dbc6831a811f17127c552be1`.
All four coupling modules match independently reviewed code `180d8bd` byte-for-byte.

Fresh offline build/installation checks include single, batch, unsupported,
100-record Unicode transport and malformed-input CLI cases. The combined source
passed 5,932 tests with zero skips, 100% coverage of 15,365 statements and 5,970 branches,
plus Ruff/format/mypy. [Exact-source CI](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39689533173)
passed all eight Linux/macOS and Python 3.11/3.14 runtime/resource jobs. Earlier
candidate artifacts remain separate; no byte-identical compressed rebuild claim
is made. Reproduce the focused contract tests above when changing this component,
and rerun common package/native-backend gates for a new integrated candidate.

This completes the scoped supplied-energy reinitiation component. Full Operon
inference, sequence-derived energy, RNA-unfolding/sign ambiguity, native-host
calibration, consumer admission and publication retain their separate gates.
