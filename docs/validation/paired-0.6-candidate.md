# Paired 0.6.0rc1 candidate

- Purpose: Reproduce the exact current-versus-recoded package and its measured execution boundary.
- Scope: Synthetic paired RBS/Promoter checks and unchanged RBS context preparation; no native efficacy claim.
- Last verified: 2026-10-18

## Immutable package

The source candidate is `920215602a837b0fd2fed403512f3b3ed59bfda2`, in
[draft PR44](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/44).
It contains the reviewed paired runtime and schemas, raw UTF-8 transport repairs,
and package version 0.6.0rc1. Subsequent conditional development uses a different
version; do not substitute its working tree for this evaluation artifact.

| Artifact | SHA-256 |
| --- | --- |
| Wheel | `b87e7a34e09f1163e03dd69d5112307bc4cb3013e75b5ade0812cf7098ab449a` |
| Source archive | `94c44c4ebad8f9b7be143cc9863b0b8b51a310154d1a0fcd8e9d4829349545c7` |
| Candidate receipt | `b4d881f97873d0f9144c79578805f9b9d1e91ff5d8556af2656c058c1c9e041f` |
| Installed timing receipt | `c157fb2d2784aeae9f4d617c3bfd910cdb2cb2a14bf13053eb7c08c2bfe36f46` |

The [candidate](../../models/paired/0.6.0rc1/candidate.json) binds the
[source manifest](../../models/paired/0.6.0rc1/source-manifest.json), public
schemas, complete effective limits, explicit model/backend examples and smoke
result hashes. All wheel runtime members matched their source hashes. Build with
the locked tools, clean source and `SOURCE_DATE_EPOCH=1792369436`; the original
archive identities are recorded, but a bit-identical rebuild has not yet been
claimed for this package. A fresh environment installed the wheel with
`pip install --no-index --no-deps`; all examples ran from outside the source tree.

## Checks and resources

The focused runtime and transport suite passed 285 tests with 100% of 434
statements and 182 branches. The independent schema implementation passed 136
cases; the geometry checks also used B's 19 literal codon fixtures. Exact-patch
review accepted `e2f85846d9d311b2beff6de1602a8ecc75a0e8d6` after repairs for an
empty circular feature, raw CRLF input limits, inherited terminal encodings and
missing Promoter parameters. Final packaging added real-result schema assertions
and fresh-wheel CI commands, without changing scoring mathematics.

The installed package completed the two Promoter examples and the RBS
substitution example. All three full JSON results passed the public schema.
The unchanged Promoter example had zero score differences; the insertion CSV
had 24 scalar rows bound to the exact JSON identity. These are synthetic
consistency checks, not measurements of regulatory changes.

The [timing receipt](../../models/paired/0.6.0rc1/resources/receipt.json) and
[whole-process memory receipt](../../models/paired/0.6.0rc1/resources-memory/receipt.json)
cover five fixed inputs: three 5,000-base sequence compositions with 512 candidates
per side, a verbose 66-candidate-per-side request with 1,980 states per side,
and an intentionally exhausted deadline. The largest output was 24,206,824 bytes,
below half the 67,108,864-byte cap. Across these two one-repetition measurements,
the longest whole CLI call was 7.206 seconds; peak RSS was 147,390,464 bytes on
the measured macOS arm64/Python 3.14.7 host. The deadline case retained all 1,024
unscored candidates. RSS uses macOS `/usr/bin/time -l` bytes. These are finite
samples, not worst-input guarantees or RBS throughput measurements.

Reproduce each fixed request from an installed wheel with `regsite-compare
REQUEST.json`, redirecting complete JSON to a new file. On macOS, wrap that
command with `/usr/bin/time -l` for peak RSS. Preserve failed exits, input/output
hashes and authoritative JSON sizes. Do not rewrite the frozen receipts.

The eight required jobs in
[CI39180666203](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39180666203)
all passed on the exact source commit. The [CI admission receipt](../../models/paired/0.6.0rc1/ci-admission.json) binds every job/step, the log hash, test totals and
the synthetic receipts. The four runtime jobs each passed 3,152 full tests and
1,963 tests per repaired-backend run, with 100% required coverage; their fresh
offline wheel examples passed. The four resource jobs also passed. This covers
Ubuntu 24.04/macOS 14 and Python 3.11/3.14. B's separate frozen collection is complete
and independently reviewed: 36 jobs retained all 4,125 candidates and 53,404 scalar
comparisons matched the independent oracle. The 12 unchanged jobs retained zero
finite differences, including honest empty RBS controls. See the [complete
denominators and limitations](current-recoded-results.md). CI and synthetic
comparison success do not establish biological accuracy, production equivalence
or publication.

## Unchanged RBS context preparation

The [separate context preparation](../../models/paired/0.6.0rc1/rbs-context-preparation/candidate.json)
binds the complete historical/context2017 model objects and linker-3 backend.
All 22 prior runtime/model files other than the version module match reviewed
RBS source `9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923` byte for byte.

Ten synthetic context records per profile completed in 3.364 and 3.158 seconds:
seven successes, two unsupported contexts and one absent candidate each. Seven
cases come from the existing independent geometry panel; three additional
201-base controls exercise 100-base upstream/downstream contexts. The
[resource receipt](../../models/paired/0.6.0rc1/rbs-context-preparation/receipt.json)
preserves complete execution identities. No native inputs or outcomes informed
these measurements.

The completed native context stage used historical/context2017, supplied start,
60.0 seconds per record and 3,600.0 per batch, with a 7,200-second whole-stage
ceiling and one explicitly reserved local folding slot. B bound its frozen Tan
context panel, exact serialization, job counts and settings before collection.
The unchanged native CLI has a text loader: require explicit strict UTF-8,
LF-only request files with raw size at most 40 MB, no stdin. Clear `PYTHONPATH`
and `PYTHONHOME`, disable user sites and verify the installed package.
Retain every failed/unstarted scenario; no retries or repacking after outcomes.
Each 124-scenario profile retained 95 scores, 26 unsupported cases and three
absent candidates, with no failed or unstarted record. The [independently reviewed
report](rbs-wave5-context-results.md) preserves shared-input and locus denominators.
This measures input-context sensitivity, not translation accuracy or improvement;
the consumed panel cannot be reused as untouched improvement evidence.

The [paired contract](paired-regulatory-runtime.md) and
[independent comparison protocol](current-recoded-validation.md) define coordinate
and score semantics. No coin spending, cyano repository edits, public release or
native calibration follows from candidate admission.
