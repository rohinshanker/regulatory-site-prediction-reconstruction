# Promoter source and benchmark contract

- Purpose: Define reusable Promoter source, parameter and benchmark evidence.
- Scope: Preparation for #7; runtime follows the first RBS release milestone #6.
- Last verified: 2026-10-17

No project Promoter runtime or hosted prediction was run. The later
[executed reference package](promoter-executed-reference.md) now verifies bounded
historical/fork inference, complete optional environment pins and documented
compatibility/coordinate discrepancies. This document preserves the earlier
source and published-column audit; its immutable source manifest records that
audit's pre-execution status.

## Reuse decision

Admit the seven-file historical inference component at
[SalisLabCode 46da913](https://github.com/hsalis/SalisLabCode/tree/46da9132740bce30bccd107f02808adf2215e2f0/Promoter_Calculator).
Its directory is identical at paper tag `r2022`, commit
`561990e2278f8da80207f721f05b0c1b935c7a97`. It contains source, utilities,
`__init__.py`, two parameter arrays, README and licence; no private `DNAc` import.
[Source manifest](../../benchmarks/promoter/source-manifest.json) pins all seven
files, the paper/supplements, source locations and dependency evidence.

The directory grant is **GPL-3.0-or-later**, including the arrays with no separate
restriction located. Retain the original 2021 copyright/warranty notice and full
GPL text in a derivative. The paper is CC-BY-4.0 with its third-party-material
exception; that is not a blanket grant for external repositories. This package
redistributes arithmetic/aggregate findings, not the raw measurement workbooks.

Assess the existing [Barrick v1.2.4 fork](https://github.com/barricklab/promoter-calculator/tree/0fe5f6f0fb2befc087556afa575f7241afd98fbf)
before writing another port. It has the same arrays and inspected mathematical
body, Python 3 fixes, packaging and CLI. Static comparison alone is not executed parity.
Its shorter GPL notice omits the original copyright line: preserve the original
when combining sources. The later executed reference contract records the tested
isolated installation; production runtime/dependency admission remains separate.

Required upstream imports are NumPy, SciPy, scikit-learn and Biopython. Reported
development versions are Python 3.7.7, NumPy 1.21.2, SciPy 1.7.3 and scikit-learn
1.0.2; no Biopython version was located. Versioned NumPy/SciPy/scikit-learn notices
are BSD-3-Clause. A selected Biopython release, binary/transitive notices and
fresh-install lock remain implementation/release gates. Original code has Python
2 `print` syntax and `OneHotEncoder(sparse=False)`; the fork repairs these. Pandas,
matplotlib and FlowCal are paper-analysis dependencies, not imports of this
inference component. Session A owns any package changes; this audit only needs
optional `openpyxl==3.1.5` outside the installed calculator.

The arrays are finite little-endian float64, shapes `(343,)` and `(1,)`; intercept
is `-0.9583584537583338`. All 336 categorical and four active numeric coefficients
match Supplementary Data 1 exactly. Array entries 336:339 are unused historical
spacer coefficients; inference instead uses `0.1463*s*s - 4.9113*s + 41.119`.
Its six values for lengths 15..20 match the workbook. Thus the workbook's 346
parameter rows do not imply three missing weights. Exact training IDs/seed,
fitting script, final regularization choice and normalization provenance were
not recovered. This is usable historical inference, not reproducible training,
the paper's design optimizer, or an identified current hosted version.

## Scientific and coordinate boundaries

[LaFleur et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9440211/), DOI
`10.1038/s41467-022-32829-5`, measures triplicate RNA/DNA barcode abundance in
three-hour, 37 C in-vitro reactions with E. coli RNAP holoenzyme (Methods
sections 15/17). Relative transcript production and natural-log/RT comparisons
are not absolute transcripts/second or demonstrated kcal/mol energies.

Public defaults are K=42 and beta=1.636217004872062 for E. coli MG1655 **and any
unrecognized organism**. Exact string `in vitro` chooses beta=0.81632623. The
stored `sigmaLevels` does not alter scoring. There is no temperature argument.
Do not export these metadata as evidence of alternative-host/sigma calibration.

TSS is the zero-based first ITR base in the oriented sequence. Half-open slices
use UP=24 nt, a one-base gap, -35=6, spacer=15..20, -10=6, discriminator=6..10,
ITR=20; extended -10 is `spacer[-3:-1]`. The paper's discussion of UP=20 and
discriminator scans from 5 differs from this code. A full internal TSS has 30
candidate states; ties keep the first visited discriminator/spacer combination.

On reverse output the upstream dictionary key is `L-t`, while nested TSS and
feature intervals stay reverse-oriented. Forward-reference **base** conversion
is `L-1-t`; interval `[a,b)` maps to `[L-b,L-a)`. Name the conversion explicitly.
Legacy `scan_arbitrary` omits the one-base gap in its TSS distance sum.
[Seven independent fixtures](../../benchmarks/promoter/source-fixtures.json)
cover scalar definitions and coordinate algebra without executing a predictor:
spacer 17 =-0.0924; A12 groove = 30; A44 rigidity = 25.2; A20 hybrid difference = -5.6
(the source uses seven stride-two dimers); TSS 100 / discriminator 6 / spacer 17 gives
UP [40,64), -35[65,71), -10[88,94), ITR [100,120). Minimum complete context is 78
bases, maximum 87; length 200 has 123 evaluable forward TSS positions.

## Published-column reproduction

The [aggregate result](../../benchmarks/promoter/results/published-column-audit.json)
comes from independently recomputing supplied measured/predicted columns, not
new inference. Pearson squared is distinct from uncalibrated explained-variance
R-squared. No rows were trimmed or regression fitted by this runner.

| Worksheet cohort | Paired rows | Pearson squared | Spearman |
| --- | ---: | ---: | ---: |
| LaFleur | 5,391 | 0.789635 | 0.803909 |
| Urtecho | 10,898 | 0.595799 | 0.669977 |
| Hossain | 4,350 | 0.454857 | 0.684915 |
| Yu | 1,493 | 0.652602 | 0.695615 |
| Lagator PL | 2,903 | 0.466142 | 0.772300 |
| Lagator PR | 12,194 | 0.347723 | 0.727142 |
| Lagator 36N | 11,485 | 0.187614 | 0.384486 |

The first four total 22,132, including 5,391 development-study records. These are
not 22,132 untouched tests. Source-specific limitations:

- Methods describes 5,388 precision-filtered constructs; the raw workbook has
  5,391 at CV<0.4, including after the six >=50-count filters. Raw IDs number
  13,481; 13,480 pass those count filters. The 5,193 high-quality single-TSS flag
  is another cohort. Exact 4,673/520 training/test membership is unavailable.
- Table S2 selects models using test correlation and positive controls. The
  published test split is not demonstrated untouched model-selection evaluation.
- Benchmark-specific calibration is fitted on benchmark outcomes (Methods 26).
  Supplied slope diagnostics are separately labelled. For Urtecho, slope 0.7526
  gives MAE 0.930521 / MSE 1.281928; workbook squared-error formulas instead use 0.75
  and cached MSE 1.281979. Both round 1.28. Hossain slope 1.98352291 gives
  MAE 1.076537 / MSE 1.879962. These are fitted-domain errors, not prospective errors.
- The quadratic comparator trains on all 10,898 Urtecho records (Methods 20).
  A table-wide “unseen” designation cannot apply to every model on that cohort.
- Tables S4–S6 use 36N denominator 11,523; the linear worksheet contains 11,485.
  The 38 omitted original sequences all have `estimate_bin=0`. Other comparator
  tables include them; join the same population before comparing errors.
- PL has 2,902 distinct strings in 2,903 rows; two strings cross PL/PR. Sequence
  families and loci need grouping beyond exact matching. Yu's republished IPTG
  condition remains unidentified. Fluorescence studies also measure effects of
  translation and RNA stability, not isolated transcription initiation.

The runner reproduces columns and all active parameter identities. It does not
reproduce raw sequencing, every F-test, all supplementary figures or the exact
paper-training procedure. Current hosted performance is unmeasured.

## Independent evaluation admission

Use published cohorts as **exposed historical replication**. Keep reconstruction
versus experiment, hosted versus experiment and reconstruction versus hosted
separate. Freeze a future candidate commit/settings and any calibration on
development-only studies before new final evaluation.

The best newly recovered candidate is author data for **GSE144621**, commit
`484abdb6ba2d398501009ee6eb25ca7f190d3b4c` (Urtecho genome-wide; reviewed preprint
`10.7554/eLife.92558.1`, precursor 2020). It has 17,767 rows / 17,617 unique strings,
MG1655/U00096.2, LB, two RNA replicates with DNA normalization, and no exact
full-string overlap with the republished Urtecho2019/Yu sets. It is **reserved,
not admitted as a fully open final set**: repository/data terms, exact reporter
flanks/temperature, primary version and locus/near-family overlap remain gates.
Group overlapping genomic windows and controls across partitions; inactive
reporter labels are not universal biological negatives. Public since 2020 does
not mean unseen by later predictors. Original Lagator CSVs have no located
project-wide licence; article CC-BY does not settle that repository's terms.
Johns2018 and PromoterAtlas2026 remain leads, not admitted benchmarks.

The later [GSE144621 admission update](../../benchmarks/promoter/gse144621-admission-update.json)
recovers the publisher's pinned reviewed-preprint v1 PDF, SHA256
`0d3de36b5d48880b5ebef0b3a86b415678ad416c037ccd2d37ebbc14482e4d06`.
Its Methods page 21 specifies MG1655 genomic landing pads and a 150-base local
window from −120 to +30 around clustered TSSs; page 25 establishes **30°C** expression
growth, with two biological and two technical preparations per biological replicate.
The earlier 37°C/42°C steps are not the expression-growth condition. Page 38 and
its linked licence identify article CC-BY-4.0. See the
[publisher's exact PDF](https://raw.githubusercontent.com/elifesciences/enhanced-preprints-data/02e328ec4db0c6aaa097239df28048d9d63fc700/data/92558/v1/92558-v1.pdf).

The author repository still has no located project-wide data/code grant; nested
BBMap/deepTools notices do not supply one. Full reporter flanks, per-row construct
identity and locus/family overlap remain unresolved. Reconcile the paper's design
counts (17,635 TSS regions, 500 negative controls, 112 positive controls) with the
previously acquired table before defining a denominator; do not invent exclusions
from the count difference. No new measurement rows were read, predictions run or
data redistributed for this update. The candidate remains reserved, not admitted.

## Reproduction and release handoff

Recover the pinned seven raw GitHub files and Europe PMC supplementary archive
from the manifest into an external source directory. The service regenerates ZIP
timestamps: the recorded archive hash identifies the acquisition, not a stable
download gate. Extract the named workbook to `paper/` and verify its **member
hash**; the runner rejects changed workbook/array bytes. An independent fresh
download had a different ZIP hash but all 31 uncompressed members were identical.
Then run:

```sh
python -m benchmarks.promoter.audit SOURCE_ROOT benchmarks/promoter/source-manifest.json output.json
python -m unittest discover -s tests/benchmarks -p test_promoter_audit.py
```

Actual arithmetic used Python 3.14.7/openpyxl 3.1.5. Tests need only stdlib and mock
workbook I/O; actual workbook/hash/NPY reads were also executed. The output is
deterministic and contains no construct-level outcomes. Before implementation,
A should verify fork installation/parity, preserve original notices, select an
explicit dependency lock, and resolve the coordinate/host contracts above. Those
steps follow #6; this evidence work does not implement Promoter runtime.
