
Native transcript contexts: `python -m benchmarks.rbs.native fetch RAW_DIR` and
`python -m benchmarks.rbs.native prepare-tan RAW_DIR OUTPUT_JSON` reproduce the
pinned Tan/UTEX envelope outside Git. Spreadsheet ingestion alone requires
optional openpyxl 3.1.5; parser/evaluator tests remain dependency-independent.
See the [native evidence contract](../docs/validation/rbs-native-validation.md)
for mappings, counts, annotation disagreements and the explicit 16S-tail scenario.
