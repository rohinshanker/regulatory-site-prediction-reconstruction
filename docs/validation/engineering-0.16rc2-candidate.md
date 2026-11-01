# Engineering package 0.16.0rc2

- Purpose: Install the independently accepted multi-target RBS implementation with its corrected confirmation reporting.
- Scope: Local/fresh software gates pass; replacement package review and platform CI remain pending. Scientific, consumer and publication gates are separate.
- Last verified: 2026-11-01

## Frozen identity and installation

The [package receipt](../../models/integration/0.16.0rc2/package.json) binds source
`d49dcaa485a3e5f91aa37e958a48d579cbb870f3`. It contains the accepted confirmation
repair `137585b`, preserves all original native models and the five-kind job
runner, and supersedes the [unreleased 0.16rc1 candidate](engineering-0.16-candidate.md).
Earlier archives and review evidence remain unchanged.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel | 226,715 | `4df4e1337b429942c1188f455fa0bf3cefd5ba98091d451f505ad22ba3645d16` |
| Source | 5,546,551 | `977d7c1b79942118df7cba8f5f3187cdbc01106082601fd8de95bf1b46a629f5` |

Execution-host artifacts are under
`/Users/Rohin/.cache/regsite-wave10-20261031/engineering-0.16rc2-installed`.
The external build/install receipt is 39,249 bytes, SHA256
`56550791ef9e522aacabe77e4b67cc3e2dfd3f4a0dba78a62ed82f68239c55e2`.
All 67 runtime files match source, wheel and fresh installation; all 78 schema
and example files match the source archive. Fifteen commands are installed.
No native binary, thermodynamic table or restrictive runtime dependency is
bundled. Reuse the [offline installation procedure](offline-jobs-0.10-candidate.md#installation-and-reproduction)
with these exact archives and the separately admitted backend.

```sh
regsite-rbs-vector-design /source/examples/rbs-vector-design.json --backend-root /absolute/RNAstructure
regsite-promoter-design /source/examples/promoter-design-single.json
regsite-conditional-sweep /source/examples/conditional-sweep.json
```

The [multi-target contract](rbs-vector-design.md) retains every candidate and
target, fixes all supplied coding intervals, ranks only complete successful
vectors and freshly confirms its selection. A fatal integrity failure during
confirmation now remains the stop reason even when the deadline is subsequently
observed. The deadline flag still reports the overrun, and no unverified sequence
is selected. Ordinary scoring, objectives and accepted successful outputs are
unchanged apart from the declared package version and derived identities.

## Verification and limits

The full local suite passed **7,994 tests and 1,551 subtests, zero skips**, with
100% measured coverage of **19,714 statements and 7,022 branches**. Real admitted
original RBS/conditional and termination backends were enabled. Eight existing
test-harness warnings remain. Lint/format checks pass for 275 files; the documented
typing selections pass for 78 files plus the separately scoped evaluator.

These gates ran at `c6ebb3f`. Later changes are documentation, corrected evidence,
ticket lifecycle and the independently reviewed public aggregate. Runtime, unit
tests, schemas, examples, package configuration and CI workflow are identical;
the receipt records the exact source comparison. The frozen source has 747
passing relative Markdown file targets in 135 files, checked after commit with
every Markdown blob compared against immutable Git. External URLs and anchors
are outside that check.

The exact CI installed-example body passed in a fresh offline wheel installation
without PYTHONPATH: **74 saved outputs**, empty stdout/stderr, 77.435 seconds.
Both-strand multi-target examples are compared against direct unchanged native
calls, including complete payloads, identities, rosters, locks, coordinates,
objectives, ranking, confirmation and typed cap refusal. These are engineering
controls, not measurements of biological accuracy.

C independently accepted the implementation and bounded repair after six
saved-envelope replay cases, with no new real prediction. The focused selection
passes 261 tests with full coverage of 306 statements and 64 branches. Its two
new regressions first failed on the original implementation. Review receipt
SHA256 is `b36c7b11b20090e37735c7b3284c6f1ba3536c77aefe0a8d6cc090c50123da88`.
The separate original documentation-attribution correction is also accepted;
all original receipts remain preserved and corrected source pins match Git.

Replacement [platform run 41326470205](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/41326470205)
and independent byte review of these new archives remain pending. Earlier green
package results do not replace those gates. The earlier 64-candidate/ten-target
resource control belongs to 0.16rc1 and has not been rerun or relabelled as a new
0.16rc2 measurement. No worst-case performance bound is claimed.

The [PCC 6803 report](rbs-native-development-recheck.md#frozen-012-results) remains
bound to original 0.12.0rc1, source `356abc2d40198a95f807967a38126a14b0f3d0c9`.
Its weak consumed-study associations do not establish UTEX calibration,
original-versus-recoded effect accuracy, complete Operon behavior, current hosted
equivalence or biological improvement from these searches. No main merge,
release tag, package publication or consumer admission follows from this guide.
