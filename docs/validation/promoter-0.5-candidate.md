# Promoter 0.5.0rc1 candidate verification

- Purpose: Reproduce and audit the frozen historical Promoter candidate without confusing source fidelity with native accuracy.
- Scope: Source `2dff23cb5697507281f7ffa73fc617d56989b40c`; no package publication or consumer admission.
- Last verified: 2026-10-18

The [candidate receipt](../../models/promoter/lafleur2022/0.5.0rc1/candidate.json)
pins the full model, parameters, six-key model identity, 20 effective limits,
CLI options, source files, artifact hashes and synthetic checks. Its SHA256 is
`9d7c4f178ea550aa85af41f7927043f857498e01ecf710d261619eb1a18654ad`.
The later [admission receipt](../../models/promoter/lafleur2022/0.5.0rc1/admission.json)
binds all eight successful jobs in
[CI 39177114783](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39177114783)
and the separately frozen B native-stage manifests. Neither receipt is edited
after issuance; subsequent limitations or results are separate artifacts.

## Installation and reconstruction checks

The wheel SHA256 is
`4443e3558c6c689373fe09af4eabc1530b4af2a166391773056a69053939b1ff`;
the original source archive is
`6a20cb6a71123d141332646dfe6bebc904ac98d94cfdf51448b8322c11444fbd`.
Verify the appropriate hash before installing an artifact. The wheel contains
the runtime, parameter data and original notice; it excludes benchmark tools,
test data and separately licensed folding executables. Promoter inference uses
only the Python standard library.

For a source rebuild, use a clean separate checkout/archive of the exact commit,
install `requirements-dev.lock` with `--require-hashes`, set
`SOURCE_DATE_EPOCH=1792366486`, and run `python -m build --no-isolation`.
The [fresh archive rebuild](../../models/promoter/lafleur2022/0.5.0rc1/rebuild.json)
reproduced the wheel byte for byte. The sdist's member paths and contents were
identical, but tar member and gzip timestamps differed: its rebuilt SHA256 is
`f867598d879a8a70eb80bb1abbc77c286d2c7f9daba88f094e4f53996b0d4eea`.
Do not claim bit-identical sdist reproducibility or replace either pinned artifact.

```sh
python -m venv /path/to/fresh-environment
/path/to/fresh-environment/bin/python -m pip install --no-index --no-deps /path/to/verified.whl
/path/to/fresh-environment/bin/regsite-promoter examples/promoter-contract-single.json
/path/to/fresh-environment/bin/regsite-promoter examples/promoter-contract-batch.json
/path/to/fresh-environment/bin/regsite-promoter examples/promoter-projected.json --format csv
/path/to/fresh-environment/bin/regsite-promoter examples/promoter-projected.json --format gff3
```

Every CI platform/Python combination passed 2,726 original-backend tests and
two 1,632-test repaired-backend selections, with full measured statement/branch
coverage. The branch denominator is 4,208 in the full suite; Python 3.11 and
3.14 report different statement denominators. These are software checks, not
biological sample sizes. The [CI receipt](../../models/promoter/lafleur2022/0.5.0rc1/ci-complete.json)
retains exact job and step identities. Fresh wheel CLI examples also passed on
Ubuntu 24.04 and macOS 14 with Python 3.11 and 3.14.

The [public source result](../../models/promoter/lafleur2022/0.5.0rc1/source-result.json)
and [independent checker audit](../../models/promoter/lafleur2022/0.5.0rc1/source-audit.json)
cover 22 requests, 424 states and four explicit no-candidate records at absolute
and relative tolerance 1e-12. Reuse the pinned request/expectation files and
`benchmarks/promoter/source_parity_check.py`; do not regenerate expected values
from this runtime. This is synthetic numerical/coordinate fidelity only.

## Resource checks

Each of the four CI platforms ran the same 14 synthetic scenarios three times.
The candidate receipt names and hashes their complete resource receipts, plus
the local and deliberately incomplete deadline diagnostics. Run
`python tools/measure_promoter_resources.py --check-receipt PATH` from the exact
candidate checkout to check a receipt's internal consistency. That check does
not authenticate a timer or establish the worst possible DNA input.

Effective caps are 1,000 sites/record, 4,000/batch and 2,000 all-state entries
per record and batch. Largest measured authoritative JSON was 29,130,504 bytes,
below the 33,554,432-byte safety threshold for the 64 MiB output cap. The slowest
CI nonmixed sample coefficient was 0.011793567791044809 seconds/site; multiplying
by the record cap gives 11.7936 seconds, within half the default 30-second
record budget. The separate loaded-host coefficient was 0.013577899881708088
and also passed. These finite measurements do not guarantee completion of an
arbitrary input before its deadline. Every unfinished requested site remains
explicit in the result.

## Transport limitation and native-stage admission

This frozen CLI opens files as text and checks input bytes after newline
translation; CRLF padding can bypass its intended raw-wire byte cap. Stdin
decoding also inherits the interpreter's text encoding. This was found during
the subsequent paired-runtime review and has a correction under review for the next package, without
rewriting this candidate or changing its model equations.

The bounded B native stage is restricted to independently checked UTF-8 files
with LF only, at most 4,000,000 raw bytes, passed as explicit file paths rather
than stdin. B confirmed all 92 files meet those conditions (largest 6,507 bytes), with
unchanged hashes; the [transport addendum](../../models/promoter/lafleur2022/0.5.0rc1/transport-addendum.json)
binds that confirmation. Final protocol acknowledgement still precedes collection. It also checks received and authoritative JSON output
sizes/hashes. The stage retains 366 requests, 92 batches, 364,416 candidate points,
395,892 supplied bases and a 3,600-second whole-stage ceiling, with no retries,
repacking or settings changes after outcomes. Failed and unstarted cases remain
in the denominator. Private per-case outcomes stay with B; reviewed aggregates
belong in its independent results document.

No measured-strength, native cyanobacterial calibration, hosted equivalence,
site-gain/loss or optimizer claim follows from this admission. See the
[model card](promoter-model-card.md) for interpretation.
