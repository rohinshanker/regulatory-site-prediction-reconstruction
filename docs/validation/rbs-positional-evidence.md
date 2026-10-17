# Native positional evidence and conditional start challenge

- Purpose: Reproduce source-tiered positive TIS admission and independent candidate ranking.
- Scope: PCC 6803 PCC-M annotated small-protein starts; conditional supplied-stop selection, not genome-wide discovery.
- Last verified: 2026-10-17
- Owner: Session B; final positional labels remain evaluator-private.

## Source identity and admission

The admitted source is [Hadjeras et al., bioRxiv v3, 2026-07-30](https://doi.org/10.64898/2025.12.20.695498),
Table S4 in the [S1–S4 workbook](https://www.biorxiv.org/content/biorxiv/early/2026/07/30/2025.12.20.695498/DC4/embed/media-4.xlsx),
SHA-256 `c5ce6b83aae56f696a936f31af244277511115947e6003fb8ec4bcff3bee569a`.
The v3 XML hash is `2d23fbd6b2e83a37ba640f5a43bce8ab3d5c19842e5022103d5f6be377951df2`.
Its CC BY-NC-ND 4.0 terms keep raw and derived case-level evidence outside the
open release. Public code, synthetic tests, acquisition identities and aggregate
facts permit independent reproduction with separately obtained evidence.
The earlier [Research Square version](https://doi.org/10.21203/rs.3.rs-8767029/v1)
is one version of the same study, not an independent dataset. Author-lab status
mentions journal acceptance; no final journal DOI or identified correction was
located in the bounded audit. These observations do not prove absence.

GEO GSE246336 / BioProject PRJNA1032574 contain the study's samples; PXD060427 is
a proteomics lead, not independently reprocessed here. Host is PCC-M, BG11,
30°C, 40 µmol photons m−2 s−1. Two independent biological replicates, retapamulin
10 µg/mL for 15 min with DMSO control, Api137 10 µM for 15 min with mock control.
The reported TIS analysis uses 32-nt reads and separate 3′-end offsets 2, 4 and
19 nt; TTS analysis uses different offsets/read classes. Source coordinates are
already genomic coordinates: the extractor never subtracts a read offset again.
No raw-read peak calling, replicate reproducibility or peptide reanalysis is
claimed. “Detectable” peptide counts are theoretical, not observed detections.

Study genome sequence matches the five pinned GCF_000009725.1 replicons exactly.
The study's older Kazusa/Hess annotation is distinct from current RefSeq feature
boundaries. Reproduction scripts are pinned at
`RickGelhausen/Synechocystis_pub_scripts_2025@a8c0c6ffaf80b622fbcebd3a43fb66471db890b6`
(GPL-3.0); ORFBounder 2.0.0 tag commit
`da56bf98e35706b14416185849cee930e8ccb85e`. A sixth replicon in a script repository
is not silently added to this five-replicon evaluation universe.

Table S4 has 165 annotated small-protein rows: 92 plain author TIS-support flags,
eight weak flags, and 65 unlabelled. One plain-support row lacks a source sequence
and has an irregular interval. **91 plain-support starts** have exact source
sequence/start agreement and complete triplet intervals; they form the primary
positive set. Eight weak-support starts are secondary. Two source endpoints are
not genomic stop codons; those rows remain unsupported. Another unlabelled
interval is not a whole number of triplets. No blank/no/weak flag becomes a
negative. TSSs, annotated starts without support and peak heights are not added
as true TIS labels. Source S1's selected offset/extension cases and S3's mixed
manual candidates require separate adjudication and are not pooled here.

These labels support *reported initiation at an annotated small-protein start*.
They do not establish an exclusive start, validate novel start correction or
remove annotation ascertainment. An annotation lookup baseline is inherently
favored and can be trivially correct; this challenge cannot prove a de novo
localizer beats annotation. Alternative unobserved starts remain unlabelled.

## Candidate universe frozen without positive coordinates

For every source row, use only its replicon, strand and terminal-stop anchor.
Search upstream in the same reading frame to the preceding stop, capped at
3,000 nt. Enumerate ATG/GTG/TTG/CTG between those stops. Add 100 genomic bases on
each side as an explicit transcript-boundary assumption. Minus-strand and
circular-origin extraction are tested using independently hand-counted synthetic
sequences. No window is centered on a hidden start. All 165 source rows are
retained, including the unlabelled and two unsupported stop anchors; **1,018
candidate starts** are observable. Query IDs hash only stop-anchor identity;
source row, locus and start-bearing source ID are withheld. Sort by query ID.

Frozen input SHA-256:
`a82062067f43542c50b1beaa234426aad5dabdffcfaa42abf08047be1e7b9a5e`.
The genome and input hashes are checked before scoring. Inputs already have
transcript orientation, `strand: "+"`, explicit `start_positions`, temperature
30°C and annotated-tail scenario `ACCUCCUUU`. Genomic strand remains provenance.
Records with `admission_status: unsupported_nonstop_source_anchor` have no
sequence/candidates; retain their failure rather than construct a substitute.

A supplied annotated stop and frame constrain the task. This is conditional start
selection among known ORF-frame candidates, not genome-wide gene discovery.
The same genes/genome may have appeared in upstream pretraining; absence of that
exposure has not been established. No positional training or tuning on these
labels is authorized. Keep primary and weak-tier reports separate.

## Metrics and reproduction

`benchmarks.rbs.position.evaluate` defaults to `source_tier="plain"` and explicitly
counts excluded weak evidence. `source_tier="weak"` gives the secondary report;
only an explicit `source_tier="combined"` pools supported tiers. It reports candidate-universe truth coverage,
positive scoring recall, complete-candidate coverage, exact top1, secondary
±3-nt top1 and MRR. With tied highest scores, strict top1 requires every tied
candidate to match; uniform-tie expected top1 is separate. MRR uses the worst
possible rank of the first positive within the relevant tie. Incomplete candidate
scoring gives zero top1/MRR over all positive queries; it cannot improve rank by
omitting competitors. Unknown queries are unlabelled. Precision and PR-AUC remain
undefined because justified negatives are absent. All failures and denominators
must accompany aggregate performance.

```sh
python -m benchmarks.rbs.tis "$TIS_WORKBOOK" "$BLINDED_NATIVE_INPUTS" "$PRIVATE"
python -m unittest discover -s tests/benchmarks -p 'test_position.py'
python -m unittest discover -s tests/benchmarks -p 'test_tis.py'
```

Use the isolated openpyxl ingestion environment. Raw labels/output destinations
must be outside Git (0700 directory/0600 files). Runtime and comparator predictions
are joined by query ID and candidate start, never by label-bearing source order.
