# Native Promoter pilot kernel parity

- Purpose: Check that the reconstructed Promoter core reproduces an original-source native localization pilot report.
- Scope: Producer-side arithmetic, tie and summary parity on an external schema-1 report; no biological accuracy, hosted equivalence or runtime-release admission.
- Last verified: 2026-10-21

The cyano consumer's pinned historical runner writes a schema-1 report from the
SalisLabCode `46da913` source. It scores 128-nt transcription-oriented windows
(87 nt before the anchor, 40 after) at 41 starts (offsets −20..+20) with all 30
layouts, plus one mononucleotide shuffle per window. The checker rescores every
native and control sequence with `regsite.promoter.score_site` at the explicit
`ecoli_mg1655` calibration. It does not import source code, run subprocesses,
use the network, or read a genome or TSS table.

```sh
PYTHONPATH=src:. python -m experiments.promoter.pilot_parity \
  --reference /external/report.json --sha256 EXPECTED \
  --output /external/NEW-parity.json [--allow-bounded-cohort]
```

The output must not exist; the checker never overwrites it or its input. It
records the result in all three outcomes.

| Exit | Meaning |
| --- | --- |
| 0 | Every position, numeric field and summary agrees, on a full eligible cohort. Bounded cohorts also exit 0 when `--allow-bounded-cohort` is given. |
| 1 | Parity failure: calculation failure, numeric mismatch or summary mismatch. |
| 2 | Input integrity failure (report written) or setup error: unreadable input, existing output, broken core parameters. |
| 3 | A bounded sample passed, but the full cohort was required. |

## Input contract

The input is refused before scoring if it exceeds the tool-local 128 MiB limit,
if its SHA-256 does not match `--sha256`, or if it is not strict UTF-8 JSON.
Duplicate keys, `NaN`/`Infinity`, overflowing numbers and integers outside the
float range are also refused. A full 2,475-case report is about 37 MiB.

Exactly these items are pinned:

- schema version `1`, scope and the MG1655 model host;
- genome FASTA and Tan table hashes, upstream commit, and all six prepared-file
  hashes;
- producer script SHA-256 `7d3440ad…4766` from consumer commit `f808362`;
- every fixed protocol parameter, including geometry, the 30 layouts and the
  `1e-12` absolute tie tolerance.

Interpreter and library versions are recorded as declared, not verified.

Each case must have the exact key set and a pinned replicon. Position must be in
range, the sequence must be 128 uppercase ACGT bases, and its hash must match.
`native_positions` must equal the independently computed 1-based circular list on
the stated strand. Each curve must list offsets −20..+20 exactly once, in order,
with finite energies and positive rates. A control must match the native base
composition and carry its own hash, the fixed kind and a correct
`identical_to_native` flag. It must have no coordinate fields. Across the cohort,
ids, sites, loci, and windows (up to reverse complement) must be unique, and
windows on one replicon must not overlap. The selected plus excluded counts must
equal the input anchors. A `sample_limit` exclusion requires the selected count to
equal `max_sites`.

The cohort is `full_eligible` only at `max_sites` 2,475 with no `sample_limit`
exclusion. Any other cohort is `bounded_sample`. A bounded report never counts
as the full pilot.

## Comparison contract

- Every case × {native, control} × 41 starts is attempted. A start must return
  `ok` with exactly 30 states and a finite score status. Exceptions, partial
  coverage, failed status or overflow are recorded per start as
  `calculation_failure`. The start stays in the denominator.
- `dG_total` and `ecoli_model_Tx_rate` are compared at the predeclared `rel_tol`
  and `abs_tol` of `1e-12`. These values were fixed before any native comparison;
  never tune them on observed results. The report gives the maximum absolute and
  relative differences.
- The tie set, best/worst anchor ranks, distance bounds and
  `best_native_tss_positions` are recomputed at abs `1e-12`, rel 0. This is done
  twice: from the reference curve (`source_summary_mismatch`) and from the
  reconstructed curve (`reconstructed_summary_mismatch`). A difference that is
  within tolerance can therefore still show up as a changed tie class.
- Anchor count, strand and replicon tallies, ±5-nt counts and median ranks are
  rebuilt from both sides. The reconstructed aggregate is skipped if any arm is
  incomplete.

Each failure records its category, source id, arm, offset and field, with the
reference and observed values. The report also states the input bytes and hash,
the tool and core file hashes, the six-key model identity, calibration,
tolerances, and complete denominators. It does not repeat the source curves.
The original and reconstructed model identities stay separate.

## Verification

```sh
PYTHONPATH=src:. python -m pytest -q tests/test_promoter_pilot_parity.py \
  --cov=experiments.promoter --cov-branch --cov-fail-under=100
```

The independent success case is the frozen pre-runtime homopolymer fixture. Its
minimum state gives the expected energy and rate at every start of a poly(A)
window. Other reports are scored by the core itself. They exercise every
validation, mismatch, kernel-failure, CLI and determinism branch; they are not
parity evidence. A mocked kernel appears only in deliberate failure tests. Real
native results come from the separate source execution, compared at a reviewed,
frozen checker commit.
