# Native RBS data and frozen evaluation

- Purpose: Reproduce native evidence admission, leakage controls and independent evaluation without revealing final outcomes to model development.
- Scope: PCC 6803 supplied-start relative TE, source provenance and outcome-blind native partitions.
- Last verified: 2026-10-17
- Owner: Session B; source/evaluation artifacts only.

## Karlsen 2018: admitted relative TE

[Karlsen et al.](https://journals.asm.org/doi/10.1128/msystems.00126-18),
[Figshare Table S2](https://doi.org/10.6084/m9.figshare.6743276.v1), is CC BY 4.0.
The pinned workbook has 2,530 unique genes, 37 columns and 5,060 positive stored
TE values. It contains no formulas or Excel error cells; both TE columns contain
2,530 numeric cells in General format. Use the stored TE, not a ratio reconstructed
from rounded RPKM columns. Missing values and zero are distinct and never receive
an invented pseudocount. The published first-60-amino-acid column is a numeric
annotation, not a protein sequence. Its specific interpretation is unverified.

The host is Synechocystis PCC 6803, 30°C, BG11 turbidostat, 200 µmol photons
m−2 s−1 (90% red/10% blue), approximately 3.4% CO2 before removal. HC is −5 min;
LC is 24 h. ENA PRJEB28203 has seven runs: five RPF libraries and two RNA
libraries. Each endpoint has one library of each assay. Nearby HC RPF time points
used as technical proxies are not independent biological cultures. Gene-wise
resampling measures gene/family variability, not biological-repeat uncertainty.
RPF normalization uses ORF-mapped totals; RNA normalization uses genome-mapped
totals. The study's ≥128 RPF and ≥32 RNA read filter is retained, not reoptimized.
No raw-read alignment or source QC has been independently rerun.

The sequence reference is GCF_000009725.1_ASM972v1, five circular replicons,
annotation GCF_000009725.1-RS_2025_06_29. Exact FASTA/GFF/protein hashes and
NCBI checksum identities are in `benchmarks/rbs/native-sources.json`; NCBI public
sequence facts are not assigned a blanket CC licence. The paper-era annotation
was not recovered. Exact GFF current/old locus aliases yield 2,501 unique current
CDS mappings; 26 identifiers remain unmatched, one has multiple CDS models and
two are current pseudogenes. Of the 2,501, **2,412 chromosomal genes** are primary
and 89 plasmid genes are secondary. All 2,530 source rows remain in the admission
audit. There are 358 source/current protein-length differences and four assumed
100-nt downstream contexts extending beyond the CDS; these warnings do not
silently discard cases. Current annotation starts are supplied coordinates, not
experimentally established TIS labels.

Each mapped input uses an explicitly assumed 100-nt genomic flank upstream and
100 nt from the start. TSS and transcript end are unmeasured. Both annotated
1,489-nt 16S copies have terminal RNA `ACCUCCUUU`; this is an annotation-based
scenario, not evidence for mature-rRNA processing or host-specific calibration.

## Frozen partitions and information boundary

`native-splits.json` SHA-256:
`d989341afcb3e463112e85134a322086d968a4cea6ad4b9cb4fa8cc893312409`.
The source input-envelope hash is
`960abca83d72a94d7b423568d24a248767e676f44d5e0561bb8988366f5888de`.
No outcomes enter the partition code. All 3,698 current annotated CDS loci plus
unmatched source identifiers participate before study-specific selection.
MMseqs2 18-8cc5c protein matches at ≥30% identity, ≥80% reciprocal coverage and
E≤1e−5 contribute 1,021 undirected edges. Exact exhaustive normalized edit
similarity ≥0.85 at 200-nt, 105-nt and upstream 30-nt windows contributes 552
edges. Their union defines 3,210 connected components. MMseqs is a heuristic
homology proxy, not a verified orthology catalogue; residual distant homology
and shared study effects remain possible. Tool, command and artifact pins are
in `native-clustering.json`. Future studies join existing locus components
without moving families between partitions.

A deterministic component hash with seed `native-wave2-20261017-v1` assigns
60%/20%/20% buckets. Primary counts are **1,465 train / 479 validation / 468
final**, with 1,317 / 423 / 423 groups. All-source counts are 1,536 / 513 / 481.
`karlsen2018-development.json` releases only 1,944 primary HC training/validation
values (SHA-256 `53ba87998de7e3d423fb7d6818db48a1bf93ede98bdb46bb6137b0119cfa39a4`).
Final, LC and plasmid outcomes remain evaluator-private. The source workbook is
outcome-ordered: the scoring-only envelope sorts by ID and removes source row
numbers. It retains an original-envelope hash; full row provenance stays private.
Its SHA-256 is `9957f10416cd00dd2f5dae086db657d2d4eab22c119d4e2f955facd1eaca65d3`.

The immutable committed split is the release authority; its hash must be checked
when transferring data. The exporter checks input identity and consistency, not
an adversarially rewritten split. Public source availability does not make an
outcome unseen; model developers must not retrieve final source labels.

## Agreed primary native comparison

A and B agreed in issue #16 before label release: HC supplied-start relative TE;
intercept-only median log2 residual calibration fitted on development-train;
select champion and strongest eligible upstream comparator using validation;
retain train-only fit, then lock commits, weights and settings. Primary MAE log2
worthwhile gain is ≥0.20. Use paired homology-group bootstrap and 97.5% intervals
for two prespecified champion contrasts (frozen baseline and selected upstream).
Require a valid champion score on every baseline-valid primary case, no lower
coverage and ≥95% overall. Otherwise superiority is inconclusive. Spearman loss
must be ≤0.05; subgroup MAE deterioration ≤0.5 log2 for prespecified n≥30 strata.
Report inclusive 2×/5× success over all eligible cases, failures, successful-pair
errors and subgroup denominators. No outlier trimming or final recalibration.
LC, plasmids, cross-study challenges and the partially exposed 2017 benchmark
are secondary. PCC 6803 performance is not a UTEX 2973 accuracy claim.

## Reproduction

Use a separate ingestion environment with openpyxl 3.1.5. RapidFuzz 3.14.1 is an
optional exact edit-distance accelerator; ordinary tests and evaluators use the
standard library. These are not shared runtime dependencies. Source downloads
are hash checked and stored outside Git. Set shell variables to external paths:

```sh
python -m benchmarks.rbs.native fetch "$RAW"
python -m benchmarks.rbs.karlsen "$RAW" "$PRIVATE"
mmseqs easy-search "$PRIVATE/all-annotated-proteins.faa" "$PRIVATE/all-annotated-proteins.faa" "$CLUSTER/homology.tsv" "$CLUSTER/tmp" --min-seq-id 0.3 -c 0.8 --cov-mode 0 --alignment-mode 3 --seq-id-mode 0 -e 0.00001 -s 7.5 --max-seqs 10000 --threads 1 --split-memory-limit 2G --format-output query,target,pident,qcov,tcov,evalue,alnlen --remove-tmp-files 1
python -m benchmarks.rbs.partitions "$RAW" "$PRIVATE/karlsen-inputs.json" "$CLUSTER/homology.tsv" benchmarks/rbs/native-splits.json --rapidfuzz
python -m benchmarks.rbs.development "$PRIVATE/karlsen-inputs.json" "$PRIVATE/karlsen-outcomes-private.json" benchmarks/rbs/native-splits.json benchmarks/rbs/karlsen2018-development.json --inputs-output "$SHARED/karlsen-native-inputs.json"
python -m unittest discover -s tests/benchmarks
```

Keep private directories mode 0700 and unpartitioned outcome files mode 0600.
The extractor rejects repository-local raw-outcome destinations. Treat unknown
assay conditions, unresolved mappings and missing labels as explicit limitations.

ENA filereport row order is not stable. Only that metadata source uses the declared `tsv_header_sort_data_lines_v1` canonical identity; the fetcher retains raw bytes and their retrieval receipt. Experimental workbooks and genome files remain exact byte pins.
