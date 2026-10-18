# Executed historical Promoter reference

- Purpose: Provide a reproducible source oracle and independent numerical/coordinate fixtures for the later Promoter runtime.
- Scope: Pinned historical and Barrick source inference on synthetic inputs; no new biological accuracy result.
- Last verified: 2026-10-17

The unmodified Barrick v1.2.4 inference and minimally adapted historical source
agree with **212 independently calculated states in 11 synthetic cases**, at
absolute/relative tolerance 1e-12. Every complete spacer/discriminator combination,
selected state, numerical term, transcription-score conversion and forward feature
interval is checked. A separate executed check reproduces both-strand range/key
behavior, the arbitrary scan's missing gap and ignored sigma levels. These
results extend the earlier [published-column audit](promoter-source-and-benchmarks.md);
they do not reproduce measured expression or establish hosted-site parity.

## Identities and rights

| Component | Exact identity and role |
| --- | --- |
| Historical source | SalisLabCode `46da9132740bce30bccd107f02808adf2215e2f0`; seven original inference assets checked against the immutable [source manifest](../../benchmarks/promoter/source-manifest.json). |
| Barrick fork | `0fe5f6f0fb2befc087556afa575f7241afd98fbf`, v1.2.4; installed Python/array files exactly match that checkout. |
| Coefficient array | SHA256 `fddf16b38bf29799481e8a45890b669111e16cf2e3448e99d1934d19a8f0b8e9`; 343 float64 entries, three fitted spacer entries unused by inference. |
| Intercept array | SHA256 `f7c66a8d838da71a6b2ab17936cd6ff2564e446af8c0676fba95de2116e99a7b`; one float64 value. |
| Historical compatibility | [Exact patch](../../benchmarks/promoter/historical-python3.patch): four Python 2 print statements and two `sparse=False` arguments changed to `sparse_output=False`. Applied in memory after original byte checks; no scoring or coordinate fix. |
| Optional environment | CPython 3.9.0, macOS x86_64; NumPy 2.0.2, SciPy 1.13.1, scikit-learn 1.6.1, Biopython 1.85, joblib 1.5.3, threadpoolctl 3.7.0. |
| Controlled wheel | Two builds with setuptools 80.9.0/wheel 0.45.1, no build isolation, `SOURCE_DATE_EPOCH=315532800`, produced SHA256 `2b1e7a5a786510df86406c8aafe785e865ef85d4cc48ada8e562ecc49d60329b`. |

The [environment manifest](../../benchmarks/promoter/reference-environment.json)
records installed source, interpreter, dependency wheel, metadata and notice
hashes, including build tools. [Hash-locked requirements](../../benchmarks/promoter/reference-requirements.txt)
cover the six optional dependency wheels for this platform. Package metadata and
installed inference bytes are rechecked by the execution tool. `pip check` passes.
This is an isolated legacy reference environment, not a production Python version
recommendation or an RBS package dependency request.

The source/arrays are GPL-3.0-or-later. [NOTICE](../../benchmarks/promoter/NOTICE),
[the exact original notice](../../benchmarks/promoter/ORIGINAL-NOTICE) and
[complete GPLv3 text](../../benchmarks/promoter/COPYING) accompany the derived
reference tools/parameter conversion. Preserve the 2021 La Fleur/Hossain/Salis
copyright line omitted by the fork's short notice. Dependency distributions retain
their own notices, including bundled numerical libraries. No experimental table
or restricted measurement workbook is redistributed. The required RBS runtime
and its dependency configuration are unchanged.

## Independent expectations and executed discrepancies

[The scalar oracle](../../benchmarks/promoter/reference_oracle.py) imports no
upstream inference. It maps lexically sorted A/C/G/T k-mers directly to array
indices, sums the declared categorical/numerical terms, and enumerates the 30
finite states. [Parameter JSON](../../benchmarks/promoter/reference-parameters.json)
is a lossless conversion of the two open arrays and four source utility tables;
the execution audit compares every converted entry to the installed sources.
[Frozen fixtures](../../benchmarks/promoter/reference-fixtures.json) were computed
before source execution from these equations, not copied from returned predictions.
Offline tests include an independently expressed Decimal homopolymer calculation,
known feature values and fixed coordinate/category checks. Independent validation
with a separately expressed 50-digit Decimal calculation agrees with all 212
states; the largest absolute score-term discrepancy is 1.51e-14, below the
declared 1e-12 tolerance. Counts describe synthetic states, not biological samples.

| Fixture/property | Expected and observed behavior |
| --- | --- |
| Interior TSS | Discriminator 6–10 × spacer 15–20 gives 30 states, visited discriminator-first then spacer. |
| Minimum window | Length 77/TSS 57 yields none; length 78/TSS 58 yields exactly the6/15 state. Length 87/TSS 67 admits all 30. |
| Right edge | Length 200/TSS 180 admits 30; TSS 181 admits none. A complete 200-base scan has 123 eligible TSS positions by independent enumeration. |
| Exact ties | Homopolymer A has tied discriminator states; the minimum spacer is 17 and first visited discriminator 6 wins. |
| Numerical controls | A12 groove proxy 30; A44 rigidity 25.2; A20 hybrid difference −5.6 from seven nonoverlapping dimers; spacer 17 term −0.0924. |
| Coordinate windows | TSS100/discriminator 6/spacer17: UP[40,64), gap[64,65), hex35[65,71), extended10[85,87), ITR[100,120). Reverse interval[a,b) maps to[L−b,L−a). |
| Reverse key | For length 200 and requested range[100,101), source reverse scan uses oriented TSS 99, exports key 101; its corrected forward base is 100. In general legacy key L−t differs from base L−1−t. Do not reuse a key as a base coordinate. |
| Arbitrary scan | On A78 the only complete state starts ITR at 58, but `scan_arbitrary` reports 57 because its distance sum omits the one-base UP/hex35 gap. Both sources reproduce this bug. |
| Organism/sigma | K 42 throughout; beta 1.636217004872062 for exact E.coli/default/unknown organism, beta 0.81632623 only for exact `in vitro`. Setting sigma 70 to zero does not change the source score. Unknown-host fallback is not calibration. |
| Fork state information | `worker(..., min_only=False)` exposes all 30 states; public `predict(..., min_only=False)` still returns only one per TSS because the parallelizer does not forward that argument. Tests record the loss rather than treating it as a complete search export. |
| Python 3.14 | Installation succeeds, but unmodified fork prediction raises `AttributeError` in `PromoCalcResults.__getitem__` because the instance lacks `__annotations__`. This failed environment is preserved in the manifest; no claim of 3.14 compatibility. |

The fork's 200-base local-window implementation is exercised with a 350-base
synthetic input and checked against the historical full-sequence coordinates.
This is bounded numerical parity, not a proof over all sequences, invalid inputs,
parallel worker modes or every CLI/wrapper feature. Reference execution uses one
worker and explicit no-op callbacks where the low-level fork API requires one.

The field names `dG_total`/`dG_apparent` are inherited source names. These are
learned score terms, not independently calibrated physical free energies.
Likewise `42*exp(-beta*score)` is the source's relative transcription-score rule,
not evidence of an absolute rate or native cyanobacterial accuracy. Promoter
runtime work remains #7/#33. Owner authorization at `457ac340` permits isolated
implementation alongside RBS release preparation; collection and publication
retain their separate gates.

## Reproduction

Use a separate CPython 3.9 x86_64 environment; install the exact hash-locked
requirements and the controlled fork wheel. Clone/check out the pinned Barrick
commit; obtain the seven historical files from the URLs in `source-manifest.json`
under `HISTORICAL_ROOT/upstream/Promoter_Calculator/`. The tool checks their hashes
before applying its explicit in-memory compatibility patch. Never use a mutable
upstream branch or silently patch the installed fork.

The serialized compatibility patch contains exactly six changed lines with no
context markers; `git apply --unidiff-zero --whitespace=error` reproduces the
same adapted bytes on a separate copy of the original files. The benchmark tool
uses its hash-gated in-memory substitutions, leaving the original source intact.

```sh
python -m pip install --require-hashes -r benchmarks/promoter/reference-requirements.txt
python -m pip install setuptools==80.9.0 wheel==0.45.1
SOURCE_DATE_EPOCH=315532800 python -m pip wheel --no-deps --no-build-isolation PINNED_FORK --wheel-dir NEW_WHEEL_DIRECTORY
python -m pip install --no-deps NEW_WHEEL_DIRECTORY/promotercalculator-1.2.4-py3-none-any.whl
python -m pip check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=. python -m benchmarks.promoter.reference_run HISTORICAL_ROOT NEW_OUTPUT.json
python -m unittest discover -s tests/benchmarks -p test_promoter_reference.py
```

The [executed receipt](../../benchmarks/promoter/results/executed-reference.json)
was identical across two complete runs. The output is exclusively created with 0600, carries runner/fixture/parameter/
environment/compatibility hashes and contains synthetic aggregate checks only.
The offline test command requires no optional source environment; its source API
mocks test audit plumbing, while the separately executed receipt substantiates
actual upstream inference. Source failures and earlier development attempts remain
outside Git; do not erase or mislabel them as successful unmodified execution.

## Public runtime parity panel

The [source-parity input](../../benchmarks/promoter/source-parity-request.json)
contains the 11 frozen cases in both local strand orientations: 22 records and
424 expected complete states. Reverse inputs are reverse complements, so they
exercise the same source arithmetic with independently transformed coordinates.
Each record requests all states and the selected state's elements, plus the
explicit legacy key. Synthetic projections cover both sequence strands and
linear/circular origins; they carry no native labels. The
[expectation artifact](../../benchmarks/promoter/source-parity-expectations.json)
keeps state order, exact selected/tie expectations, all numerical terms, log and
relative scores, local/oriented/genomic intervals and strand-correct TSS points.

The [builder](../../benchmarks/promoter/source_parity.py) uses the existing
independent oracle, verifies each source state's frozen numerical values, then
maps individual bases before assembling genomic intervals. It imports no
reconstruction. The synthetic panel is frozen before the runtime candidate:

| Artifact | SHA256 |
| --- | --- |
| Runtime request | `fbc5b8b9c99c7ffc4558ff5a423c1b7bdd237a7ebc993aac9505890c4a9c89d3` |
| Numerical/coordinate expectations | `bc7121f05f7b1a87e93995bd627a1a44a808e09b5167236c75fd5547eb6f33fc` |
| Independently re-executed historical/fork receipt | `a2934ceab65a72e15e6b96cb16fe2ddd0b1ff19fc66c8a471e313594eb739353` |

The source receipt is byte-identical to the earlier checked-in executed receipt;
this is source execution, not new-runtime or native collection. The optional
source environment remains isolated and unchanged. Reproduce panel bytes and
independent per-base geometry checks without that optional environment:

```sh
PYTHONPATH=src:. python -m pytest -q tests/benchmarks/test_promoter_source_parity.py
PYTHONPATH=. python - <<'PY'
from benchmarks.promoter.source_parity import build_panel
from pathlib import Path
request, expectations = build_panel()
assert request == Path("benchmarks/promoter/source-parity-request.json").read_bytes()
assert expectations == Path("benchmarks/promoter/source-parity-expectations.json").read_bytes()
PY
```

At collection, bind the exact request and expected artifacts to A's immutable
candidate/model/settings/resource receipt. Source parity uses absolute/relative
1e-12 tolerance; record selection, state order/count, coordinate values and
status/tie semantics are exact. Model and batch identities are additional receipt
checks, not contained in these candidate-independent expected score fields.
Retain no-candidate cases in the 22-record denominator. A failed, missing or
partial source-parity record cannot be credited as a pass. Do not consume native
outcomes to repair a source discrepancy.

The [public-result checker](../../benchmarks/promoter/source_parity_check.py)
accepts exact CLI result bytes and a separately frozen adapter-format identity/
settings manifest. Both CLI defaults must be null because this panel explicitly
requests mixed profiles and all states. It checks the source parameter file against the frozen expectation hash and
binds model/source/array identity,
full model object, limits/deadlines, batch/prediction/site/state IDs, input hashes,
complete record/state rosters, numerical terms, selection, coordinates, elements
and coverage. Missing, failed, reordered or partial records fail parity. Received
and authoritative pretty JSON sizes are independently bounded. Warnings must be code/message objects; the panel requires the legacy-key code
and, for its host-absent E. coli records, host_unspecified. Missing, duplicate
or inapplicable codes fail; explanatory wording is not an identity key. The successful audit records
candidate/wheel/manifest, input/expectation/result and both checker/adapter hashes.

```python
from benchmarks.promoter.source_parity_check import check
# result_bytes came from the frozen candidate's public CLI; manifest is the
# reviewed candidate/settings receipt, never inferred from the observed result.
audit = check(result_bytes, manifest)
```

This function neither launches inference nor proves that the asserted wheel was
used; the collection receipt must independently bind that execution. Synthetic
mutation tests check the validator, not source parity of an unexecuted candidate:

```sh
PYTHONPATH=src:. python -m pytest -q tests/benchmarks/test_promoter_source_parity_check.py
```
