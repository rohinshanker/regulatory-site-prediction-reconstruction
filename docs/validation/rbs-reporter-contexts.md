# Cyanobacterial reporter/context evidence

- Purpose: Admit independently recovered construct contexts without inventing numerical measurements.
- Scope: Thiel et al.2018 PCC 6803 reporter study and its seven supplements.
- Last verified: 2026-10-17
- Owner: Session B.

[Thiel et al., DOI10.1186/s12934-018-0882-2](https://doi.org/10.1186/s12934-018-0882-2)
provides CC BY4.0 article/supplements, with a data CC0 notice subject to any
separate identification. The source ledger pins the article XML and all seven
publisher PDFs. All seven match the EuropePMC supplemental archive byte-for-byte.
No embedded data files were present in the inspected PDFs. Publication/version
checks found no identified correction; this bounded check does not prove absence.

The study contains **32 constructs**: 13 sYFP2,13 GFPmut3b,six efe. Table2 gives
13 distinct 22-nt upstream RBS strings followed by ATG. Italic prefix bases
already belong to the common 27-nt insulator; duplicating them would change the
construct. The portable extractor preserves the typography and reconstructs
leader = insulator + nonitalic variable sequence. The source's 1,514-nt synthetic
GFP/cassette insert supplies a conditional GFP CDS interval[0,720), including the
ATG overlapping NsiI and the terminal TAA[717,720). This is a documented assembly
interpretation, not a clone-specific sequence trace. A black-font-only extraction
would incorrectly omit the leading ATGCAT.

`benchmarks/rbs/thiel2018-contexts.json` contains every construct, source row,
sequence identity and explicit missingness. Its SHA-256 is
`8fef97f56c2ead181f2b571f1e027fe0e10ce3a2ddd88024f3747b76cbdf280b`.
**13 GFP local contexts** are available under that assembly interpretation;
19 exact sYFP2/efe synthesized reporter junctions remain unavailable. Cited
accessions are templates, not proof of the actual synthesized junction. No full
transcript boundaries are claimed. All13 GFP35up/70CDS windows independently
match the source-audit extraction. Their shared reporter and six borrowed A–E/Z
RBSs must remain grouped in any later quantitative evaluation. Those borrowed
series account for14 constructs and are not independent new sequence families.

The 58 principal assay endpoints are graph-only: 26 full fluorescence endpoints,
26 one-day endpoints and six product endpoints. Exact means, SDs and raw replicate
arrays were not found in the article or seven supplements. All exported numerical
observations remain null; no bars are silently digitized. Full fluorescence has
six biological cultures with three technical readings each; caption n18 is not
18 independent biological replicates. One-day panels have one biological culture
and three technical readings. Relative fluorescence percentages have no recovered
explicit reference denominator. OD750 normalization is not mRNA normalization.
The six efe constructs were selected after reporter screening. The product figure
prints C2H2 while the text names ethylene (C2H4); retain the unit conflict.

The paper's reported correlation coefficients cannot be independently recomputed
without numerical outcomes. A narrower arithmetic check is possible: under a
conventional two-sided Pearson test on13 construct means, Table4's r=.186 gives
p≈.5429 rather than its printed.346; Table3 r=.801 gives p≈.000999, consistent
with.001. For the reported ten-construct subset, r=.781 gives p≈.00765, consistent
with.008. The denominator/test implementation behind the inconsistent pair is
unresolved; do not infer fabricated values or a corrected empirical correlation.
The subset excludes selected constructs and cannot be treated as an untouched
validation set. Predicted folding/strength bars are not experimental labels.

Admission is **reporter/context evidence only**, not a scored numerical accuracy
dataset. It motivates falsifiable CDS-context and RNA-abundance hypotheses, but
supplies no native UTEX 2973 calibration and no absolute initiation measurements.

```sh
python -m benchmarks.rbs.native fetch "$RAW"
python -m benchmarks.rbs.reporter "$RAW" benchmarks/rbs/thiel2018-contexts.json
python -m unittest discover -s tests/benchmarks -p 'test_reporter.py'
```

Extraction uses standard-library XML parsing and an existing system `pdftotext`
command. It verifies original hashes before conversion and leaves source files
untouched. Synthetic tests cover italic-prefix handling, one-copy ATG, stop/frame
boundaries, absent outcomes and construct-count validation. No optional model or
shared packaging change is needed.
