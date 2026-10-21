# Anchor-centered native Promoter pilot

- Purpose: Reproduce the original historical calculator on native UTEX 2973 windows, separately from reconstruction fidelity and measured-count association.
- Scope: Exploratory Tan 2018 gTSS localization; an exposed cohort, not untouched confirmation.
- Last verified: 2026-10-21

The unchanged original-source runner completed all **1,597 selected anchors**.
For native windows, at least one best-scoring position was within five bases of
the annotated start for **900/1,597 (56.36%)**; every tied best position was within
five bases for **890/1,597 (55.73%)**. The corresponding shuffled-window counts
were **398 (24.92%)** and **383 (23.98%)**. The native median annotated-start rank
was 6; the shuffled median was 22. These are descriptive localization results
under the historical *E. coli* calibration.

The [source and execution manifest](../../benchmarks/promoter/native-pilot-reference.json)
pins source, prepared files, runner, genome, labels and complete report. The
25,515,500-byte report stays in explicit external storage, outside Git and the
browser bundle. Its SHA-256 is
`f4021ed3941a66b656df9e40f4a6a406b4cf59c651ec00dd7c54865080ebbc5f`.

## Sampling and interpretation

The input contains 2,475 Tan Table S1 gTSS anchors. The unchanged selection rule
excluded 613 sharing a source locus with a selected anchor, 264 whose windows
overlapped selected windows, and one identical or reverse-complement window.
Selected anchors comprise 823 plus-strand and 774 minus-strand cases; 1,580 are
on NZ_CP006471.1 and 17 on NZ_CP006472.1. Locus exclusion uses the source tags,
without a current-annotation or operon join.

Each transcript-oriented circular window has 87 bases before the annotated
start and 40 after it. The runner scores all 41 candidate starts at offsets
−20 through +20, with 30 layouts per candidate. It also scores one deterministic
mononucleotide shuffle per window, using seed 2973. Thus the complete report
contains **130,954 candidate scores**. No failed or unfavorable case was removed.
The optimum minimizes total model energy; ties use absolute tolerance 1e-12
and zero relative tolerance. Reporting both any-best and all-best recovery
preserves the effect of ties.

This task already supplies the approximate start location. It is easier than
the earlier [fixed-grid evaluation](promoter-wave5-results.md), which recovered
47/292 in-window positives within three bases among the top ten predictions per
1,000-base tile. The populations, windows, tolerances and selection rules differ;
the percentages do not demonstrate that the model improved. Tan labels were
already exposed in earlier work. No coefficients, thresholds or selection rules
were fitted to this pilot.

Shuffled windows are synthetic controls, not verified promoter-negative DNA.
These results cannot establish specificity, false discovery rate, complete
promoter boundaries, native expression strength, or recoding-effect accuracy.
Distinct nonoverlapping source loci also do not prove independent operons or
homology blocks. Predicted rates retain *E. coli* calibration. The
[model card](promoter-model-card.md) explains the applicability limits.

## Reproduce the original execution

Use a separate checkout of the consumer repository at
`f80836248243983beefbfe3f85c83914e5f9d01b`; its preparation tool and runner are
unchanged. Retrieve the six exact URLs in the manifest into an external source
directory and verify every byte count and SHA-256 before preparation. The six
files total 29,750 bytes. Do not substitute a moving upstream branch. Preserve
the upstream licence and README with the prepared files.

The following paths are caller-supplied; neither the source download nor the
full native inputs are distributed by this result document. Run from that
pinned consumer checkout with its scientific Python environment:

```sh
python tools/prepare_promoter_calculator.py \
  --source-dir "$PILOT_SOURCE" --output-dir "$PILOT_PREPARED"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
python tools/regulatory_promoter.py \
  --fasta "$PILOT_FASTA" --tss "$PILOT_TSS" \
  --prepared "$PILOT_PREPARED" --output "$PILOT_OUTPUT" \
  --max-sites 2475 --seed 2973
```

The recorded run used Python 3.12.4, NumPy 2.5.3, SciPy 1.18.1,
scikit-learn 1.9.1 and Biopython 1.88. It exited successfully in 69.716 seconds
on the recorded Mac environment, with a 335,020,032-byte child peak RSS
(macOS cumulative child maximum, including small process-monitor samples).
This is one execution measurement, not a cross-platform performance guarantee.

All 77 focused preparation/native tests passed with no skips, including the
real downloaded-source and eight-anchor integration tests. A separate native
coordinate smoke checked 91 candidate positions on each strand. The coordinator
independently recomputed all tie sets, ranks, distances and aggregate counts
from the immutable complete report without rerunning the model. Canonical
producer and consumer checkouts were unchanged.

## Reconstructed-source comparison

The independently reviewed [fidelity checker](promoter-native-pilot-parity.md)
at `7893a55c1d2f8f4a118279f3382d0efb72cf6bd7` was integrated at
`2d69426929f499e5044136d4ea803f423caea9b7` and frozen before the native comparison.
The full source report above passed: **130,954/130,954 positions and
261,908/261,908 numeric comparisons**, with no calculation failures, numeric
mismatches, source-summary mismatches or reconstructed-summary mismatches.
All 3,194 native/control arm localizations completed. No tolerance or model
parameter changed after observing results.

The [complete compact parity result](../../benchmarks/promoter/native-pilot-parity-result.json)
retains the exact model, parameter, core-file, checker and input identities.
Its SHA-256 is
`f7508aa42340497338957e53b2da6255e4baf2f46fb3b0ca711517000e394ac4`;
the original external pre-execution freeze SHA-256 is
`267b41c27bfa8bf756ad4b63fc03f746de9ebee05252066a90497a108df94717`.
Execution took 65.113 seconds on Python 3.14.7 and exited 0. The core and
parameter bytes match their independently reviewed source, although the combined
development package identifies itself as 0.8.0rc1.

| Compared field | Maximum absolute difference | Maximum relative difference |
| --- | ---: | ---: |
| Total model score, source `dG_total` | 8.88 × 10⁻¹⁶ | 1.09 × 10⁻¹³ |
| Relative transcription score | 2.18 × 10⁻¹¹ | 2.44 × 10⁻¹⁵ |

Comparison uses absolute **or** relative tolerance 1e-12; the rate's absolute
maximum therefore does not imply a failure. Tie classification separately uses
absolute 1e-12 and zero relative tolerance. Complete cohort admission checks the
input-only selected-ID hash and all population counts, independently derived
before original scoring. Review repaired a truncated-cohort admission defect
and diagnostic-overflow reporting before the checker freeze; its 139 focused
tests have 100% statement/branch coverage and six independent CLI probes pass.

This result establishes fidelity to the pinned historical source on these
windows. It does not establish current hosted equivalence or improve the
model's biological accuracy. Original-source localization, reconstruction
fidelity and association with measured RNA counts remain separate checks;
none alone admits a runtime release or visualizer predictions.
