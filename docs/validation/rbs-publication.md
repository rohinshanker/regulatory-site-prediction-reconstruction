# RBS publication contract

- Purpose: Preserve the reviewed RBS archive identity while preparing an explicit, reproducible publication action.
- Scope: Provisional GitHub pre-release `v0.4.0rc1`; PyPI, final `0.4.0`, Promoter and consumer publication are separate.
- Last verified: 2026-10-18

## Immutable artifacts and review

The archive source is integration commit
`9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923`; scientific runtime is frozen at
`a11cb5bd13d3c021eedc98cf451609eb4710bb6a`. The cumulative release branch
`release/rbs-0.4.0rc1` adds documentation only after that integration. It must
preserve both commits in its ancestry. Neither a newer README nor a changed
release description changes the archived source or wheel.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `regulatory_site_prediction_reconstruction-0.4.0rc1.tar.gz` | 3149778 | `13b4975f01a4cc8472975f90531908badcc55a654f14df673c5d44539311e7f4` |
| `regulatory_site_prediction_reconstruction-0.4.0rc1-py3-none-any.whl` | 74558 | `f6ef1dd8f38157dc7367ebcb0465c37dd0c2f5910825c06f94a8c9f8b99f9c94` |

The exact source tree passed all four jobs in
[CI39088709792](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39088709792):
Ubuntu 24.04/macOS 14 and Python 3.11/3.14. The local combined suite passed
1,624 tests at 100% measured Python statement/branch coverage, and the separate
three-engine component suite passed 35 checks. These results do not cover all
upstream C++ or establish biological accuracy.

Independent cumulative review DEM-517 compared the complete `b779828..9edb989`
tree, verified all 430 source-archive members (423 tracked and seven generated),
all wheel RECORD hashes, the 23 frozen runtime files and licence notices. A
fresh offline installation reproduced six selected example outputs byte-for-byte.
The full suite and 35 component checks were confirmed from prior evidence,
not rerun by that review. Its disposition is suitable for a labeled provisional
pre-release, with the publication corrections below. No main merge, tag or
publication is authorized by this document.

## Publication preparation

Keep the original archives and metadata immutable. In a new staging directory:

1. Copy the exact two archives and verify the sizes and hashes above.
2. Copy the original `artifact-manifest.json` as
   `reviewed-artifact-manifest.json`, whose SHA256 is
   `360dc875b03ff53e3ef247bf1da006f7d7c0253a10637584ad2bf44de5a6cbd8`.
3. Copy [the corrected release body](../releases/rbs-0.4.0rc1.md) to `RELEASE.md`.
   It distinguishes a provisional package from production equivalence, includes
   the historical-profile comparison, and has no claim that publication has
   already happened or has not happened.
4. Derive a new `artifact-manifest.json` from the reviewed manifest: replace only
   the release-body digest and add preparation time, predecessor-manifest digest
   and a note that `published:false` describes preparation time. Preserve all
   scientific, archive, example and CI identities. Record changed metadata as a
   new artifact identity; do not pretend it is the earlier reviewed manifest.
5. Generate `SHA256SUMS` for both archives, both manifests and `RELEASE.md`.
   Recheck every digest and confirm that the archives equal the originals.

The publication body corrects the archived candidate-era wording. The updated
README and release guide on the cumulative branch add the same interpretation
and reproducible-wheel instructions. Archive documents remain historical
snapshots. Rebuilding a wheel from a newer documentation commit can change its
metadata and therefore its hash; it is not the reviewed wheel.

The tracked `.github/workflows/ci.yml` at `9edb989` contains the offline smoke
recipe corresponding to the original manifest's untracked helper. Follow that
recipe or the [runtime contract](rbs-runtime.md); the helper path alone is not a
portable command. The independently downloaded backend archive and compiler
remain installation prerequisites. The upstream download URL's continued
availability is not guaranteed.

## Approval-ready publication action

After explicit owner authorization for the concrete main merge, tag and GitHub
pre-release, recheck the approved branch head, clean state, current main and
staged hashes. Stop if the approved content or relevant base changes.

1. Integrate the reviewed cumulative release branch into main while preserving
   commit ancestry: a normal merge or approved fast-forward. Never squash or
   rebase this release history. Canonical checkout changes remain a separate
   worktree operation; never overwrite unrelated local changes.
2. Create the annotated tag `v0.4.0rc1` at **`9edb989`**, the exact archive source,
   rather than at a later documentation or merge commit. Refuse an existing
   conflicting tag; never retag a published release.
3. Publish a GitHub pre-release, not marked latest, using `RELEASE.md`. Attach the
   exact wheel, source archive, both manifests and `SHA256SUMS`. Do not rebuild.
4. Verify downloaded release-asset hashes and the tag target, then record the
   actual publication URL and status in the release guide and #6. Only the owner
   of a completed scoped ticket closes it; broad unfulfilled tickets stay open.
5. Reconcile older incremental PRs as superseded only after the cumulative
   integration is verified. B's evidence branches were integrated by content;
   lack of ancestry alone does not show their evidence is missing. Coordinate
   closure of their PRs with B and retain all scientific reports.

PyPI requires a separate packaging decision: the source distribution combines
GPL-3.0-or-later runtime and isolated GPL-2.0-only backend components, while its
current package metadata names only the former. Component notices are present,
but PyPI metadata and repository-relative long-description links need correction
before that channel is used. Such a change requires new artifacts and validation.
Windows and a final `0.4.0` release also remain unverified/separate scopes.

## Interpretation that must survive publication

The independent joint-selection advancement gate failed. The historical
default's Spearman 0.501889 exceeds standby's 0.436250 descriptively, but their
paired 95% interval includes zero. Joint was about 3.45 times slower than standby
on the measured collection. None establishes superiority, native UTEX
calibration, hosted equivalence or NUPACK-equivalent folding. See the
[full independent results](rbs-wave4-results.md). The consumed final panel cannot
be tuned against and then presented as untouched validation.
