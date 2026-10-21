# Supplied-transcript 0.8.0rc1 candidate

- Purpose: Reproduce the explicit transcript/CDS component package and its bounded execution checks.
- Scope: Immutable development candidate for portable annotated results; no integrated Operon or biological recoding-effect claim.
- Last verified: 2026-10-21

Source `9e96bc00f56eb2dc107bc107860cdefa31731d2c` is frozen in
[draft PR48](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/48).
The [candidate receipt](../../models/transcript/0.8.0rc1/candidate.json) binds exact
schemas, complete effective limits, example model/backend identities, independent
review, the source manifest and installed execution. The library/CLI contract is
[supplied-transcript-runtime.md](supplied-transcript-runtime.md); caller input is
specified in [supplied-transcript-contract.md](supplied-transcript-contract.md).

| Artifact | SHA-256 |
| --- | --- |
| Wheel | `35633a1641ca3851a4ad171b37faff578794b9723a6625353cd9d8ad29f287af` |
| Source archive | `805ce2e48829749f24472ea184b4cf2b93b1e00e08050fc9b2dac14efc320ec3` |
| Installed receipt | `d5ffcc574a52855bf801a53b419c2ca3474df4d6c5b5c20c734e3e20616fdbaa` |
| Source manifest | `52ed05be2db05ec8fb3d75834228f3dca46e4e4bc4b5ff74e40a444763c08312` |
| Candidate receipt | `c12777b775afd9b8608806bba46332c1863c864974ec67c276ad2018277f5140` |
| CI admission receipt | `c979e61a9aedb1ae14ac1c0ea7bfc464387bf2ce525093415c9c849cab076886` |

## Reproduce the package

Build the clean source using the locked development tools and source epoch in
the installed receipt. All wheel runtime members matched the
[source manifest](../../models/transcript/0.8.0rc1/source-manifest.json).
The artifact hashes identify the produced containers; a bit-identical tar/gzip
rebuild has not been claimed. Install the wheel in a fresh environment with
`pip install --no-index --no-deps WHEEL.whl`. Clear `PYTHONPATH` and `PYTHONHOME`,
disable user sites and run outside the source tree. The wheel contains no folding
executable; the separately licensed RNAstructure installation remains external.

```sh
regsite-transcript REQUEST.json --backend-root /path/to/verified/RNAstructure
regsite-transcript REQUEST.json --backend-root /path/to/verified/RNAstructure --format csv
```

The installed checks used the explicit `rnastructure-6.6-linker-3` backend,
with its complete binary/table identity retained in every native result and the
candidate. These are unchanged RBS/Promoter models; no new equation, fitted
coefficient, transcription/translation product or hidden host choice is added.
RBS profile and anti-SD settings, Promoter calibration and both host labels remain
explicit. The request/result schemas ship in the source archive and repository.

## Verification and resources

The combined synthetic runtime/transport/schema suite passed 868 tests with
100% of 448 runtime statements and 184 branches; one unchanged real-engine case
was deliberately excluded from that run. Three additional no-folding regression
tests check the resource plan's partial exits. Another 398 adjacent contract/schema
tests passed. All twelve independent literal organization fixtures agree on
transcript sequence, eligibility, signed offsets and forward/reverse/circular
projection. Source fixtures remain unchanged; no private native outcomes were used.

Independent review accepted final source `9e96bc0`, including genuine-integer
projection, stable complete-result identities under shortened execution deadlines,
logarithmic units, binary CLI transport, empty/partial exports and strict result
schemas. The final recheck passed 127 focused tests; the preceding core and
transport reviews passed their full focused coverage checks. The actual installed
checks below supply separate real-backend evidence.

The fixed [resource plan](../../models/transcript/0.8.0rc1/resource-plan.json)
contains eight JSON requests and one declared CSV replay, run serially once on
the admitted candidate. Full [outputs and raw timings](../../models/transcript/0.8.0rc1/outputs/)
are retained alongside the [installed receipt](../../models/transcript/0.8.0rc1/receipt.json).
All eight JSON results validate against the public schema and recompute both
request/result hashes. The 52-row CSV replay binds the identical complete JSON
prediction hash and retains two component summaries.

| Control | Expected accounting |
| --- | --- |
| Single CDS and two CDS examples | Complete native components |
| Incompatible supplied start | Partial; preserve the incompatible annotation |
| Three 5,000-base compositions, ten unsupported CDS starts, 512 Promoter positions | Partial; all starts retained, all Promoter positions scored |
| Ten supported starts and 512 Promoter positions, reverse circular projection | Complete; ten RBS scores and 512 Promoter scores |
| Exhausted whole-request deadline | Unavailable; both components unstarted, complete requested rosters retained |

The largest full result was 6,017,426 bytes, below half of the 33,554,432-byte
output cap. Maximum whole-CLI wall time was 5.161 seconds; peak whole-process RSS
was 85,491,712 bytes on macOS arm64/Python 3.14.7. Measure RSS with macOS
`/usr/bin/time -l`; its resident-set value is bytes. These are finite samples,
not worst-input guarantees, an operating-system memory quota or evidence that all
profiles finish every admitted request before its deadline. Partial outputs count
as correctly accounted controls only when their predeclared statuses match.

The [rejected plan admission](../../models/transcript/0.8.0rc1/rejected-plan-admission.json)
preserves the earlier incorrect expectation of exit 0 for unsupported-start
controls. Such controls require exit 1 and retained successful Promoter results.
The correction changes the acceptance plan, not request bytes or runtime scoring.
No partial or mismatched attempt is labeled a successful package admission.

All eight jobs in [CI39193463857](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39193463857)
passed on the exact frozen commit. The separate
[CI admission receipt](../../models/transcript/0.8.0rc1/ci-admission.json) binds
the job/step results, log hash, original package receipts and test/coverage totals.
Each of the four runtime jobs passed 5,044 full tests, with one documented skip,
and 2,873 tests for each of the two repaired backends. Required statement/branch
coverage was 100%; all four resource jobs also passed. The matrix covers Ubuntu
24.04/macOS 14 with Python 3.11/3.14.

The sole full-suite skip is the existing conditional original-binary integration
test, which requires its separately admitted backend. Its installed structural
checks remain in the [conditional candidate](conditional-0.7-candidate.md);
this CI does not admit additional conditional structural binaries. Transcript
runtime checks passed. The package gate is complete, independently of scientific
accuracy, publication or consumer admission.

## Consumer and evidence boundary

The output describes caller-supplied RNA and CDS organization. It does not infer
operons, validate gene annotations, model coupling/elongation/decay/termination,
or estimate joint protein abundance. Distinct transcript isoforms require
distinct explicit requests. For indel recodes, intervals must describe the
recoded construct; an old chromosome projection cannot silently establish
unchanged genomic correspondence. The paired calculator's explicit edit-map
contract remains the separate correspondence mechanism.

Backend/model/parameter settings must match before comparing scalar predictions.
Complete accounting may include unscored candidates; inspect component coverage
and per-candidate status. The 2026-10-21 owner instruction resumes producer
implementation; this wave integrates the already reviewed component. It does
not add a new transcript adapter or use this candidate for a new collection.
The bounded consumer preview stays on the
[paired 0.6 artifact](paired-consumer-preview.md); this completed 0.8 gate does not
change that selection or authorize a new stage. Publication and cyano consumer
admission remain separate, and parent #8 retains the full Operon scope.

## Combined development integration

The combined development branch retains these immutable source/package receipts
and the reviewed transcript modules, schemas and examples byte for byte, while
incorporating the separately reviewed Promoter validation-reuse kernel and
original RNAstructure installer from `1ec44e5`. Its version remains 0.8.0rc1, but
its package bytes differ from the frozen artifact above. That artifact's admission
does not certify the combined package; independent integration review and final
combined gates remain required. The conditional structural binary allowlist is
unchanged: building an original backend does not automatically admit it.
