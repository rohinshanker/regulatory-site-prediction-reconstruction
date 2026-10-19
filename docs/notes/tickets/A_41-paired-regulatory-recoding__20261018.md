# A_41-paired-regulatory-recoding__20261018 — Active

- Scope: Implement a producer-side comparison of supplied reference and recoded sequences using version-pinned RBS/Promoter predictors, with portable results for the cyano visualizer.
- Status: active
- Opened: 2026-10-18
- Updated: 2026-10-18
- Current State: A real paired RBS/Promoter library, strict UTF-8 JSON/CSV CLI, versioned schemas and three runnable examples are integrated in wave5/paired-regulatory. Independent review DEM546 accepted the circular empty-feature and transport repairs through e2f8584; Claude DEM547 supplied schemas at4c308e1, reviewed and integrated by A. Package0.6.0rc1 has its own implementation identity; the frozen0.5Promoter evaluation candidate is preserved. Source/resource/fresh-install receipts and B's immutable producer comparison are being prepared.
- Verification: Focused integration passes285tests with100%434statements/182branches across the paired core/CLI/I/O and corrected PromoterCLI. Six real sequential RBS records now also validate against the new result schema; unchanged, changed and circular reverse-standby cases pass. B's SHA-pinned19codon fixtures match exact paths and correspondence rows; those are geometry checks, not biological evidence. Earlier edit-map tests cover57cases/100%. Fifteen whole-CLI synthetic Promoter resource runs retain512candidates/side or132all-state candidate sites; largest result24206824bytes, longest run17.006seconds; tight deadlines retain all1024positions explicitly. Final immutable package/resource verification and independent B producer comparison remain.
- Cleanup: Session A alone resolves this scoped ticket after tested implementation, reusable contract distillation and index cleanup.

- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/41
- Priority: P1
- Dependencies: RBS runtime; Promoter #33 for its adapter; independent synthetic comparison fixtures #39.

Owner: Session A (baf5b738-1792172297). Session B owns independent synthetic comparison fixtures and scientific evaluation. Implement independent edit geometry in a separate producer worktree while the Promoter candidate is reviewed. Bind final predictor integration/evaluation to an immutable candidate; preserve existing runtime profiles and all consumed benchmark panels.

Deliver a local library/CLI accepting both supplied sequences, explicit host/model/backend settings, reference and recoded identities, scan/candidate universe and an explicit edit/alignment map. Support substitution-only recoding first and indels with validated maps; do not guess an alignment when ambiguity changes site identity. Preserve transcript orientation, genomic mappings, circular boundaries and original/recoded coordinates independently. Hash both exact sequences and all effective settings.

Produce paired per-candidate predictions, mapped/unmapped/new/deleted candidate accounting, scalar score/term deltas only when both results are comparable, modelled feature interval changes, and explicit failure/unsupported/not-evaluated states. Preserve every candidate and report coverage before aggregate changes. A candidate added/lost by sequence or coordinate changes is not automatically a biologically gained/lost regulatory site. Require caller-supplied predeclared thresholds for any threshold-based classification and keep raw scores available; no thresholds selected from final Tan/native outcomes. Do not treat TSSs as translation-initiation measurements.

Define a versioned portable feature/change export with model/source/calibration/backend identity, provenance, coordinates, warning and coverage fields. Keep measured/transferred evidence separate from predictions. The producer must not import consumer code or mutate the canonical cyano checkout. Consumer admission, visualization/rendering and release pins remain under #10 and its consumer-owned tickets.

Acceptance: real offline paired RBS and Promoter examples; equality controls and stale identity rejection; both strands and circular cases; substitutions, insertions/deletions, ambiguous maps, overlaps, boundary/missing/error cases; independent B fixtures; 100% statement/branch coverage on new modules; deterministic IDs, schemas, resource caps, fresh-install smoke and focused independent review. No optimizer or claim of improved expression is implied by predicted deltas. No main merge, tag, publication, coins/browser/credentials/cyano writes. Disclose any new privilege/credential requirement before the action and await owner.
