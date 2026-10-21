# Paired calculator consumer preview

- Purpose: Supply the smallest admitted RBS/Promoter paired artifact for a bounded visualizer preview.
- Scope: Existing 0.6.0rc1 package and synthetic examples; no new calculator expansion or publication.
- Last verified: 2026-10-21

## Immutable inputs

Use source `920215602a837b0fd2fed403512f3b3ed59bfda2`, version **0.6.0rc1**,
from [PR44](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/44).
The source worktree is
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-wave5-paired-regulatory`.
Do not substitute later conditional/transcript packages or a mutable sibling import.
The [candidate guide](paired-0.6-candidate.md) records the admitted scope and
independent comparison evidence. All eight CI jobs passed; publication remains pending.

| Artifact | SHA-256 |
| --- | --- |
| Wheel | `b87e7a34e09f1163e03dd69d5112307bc4cb3013e75b5ade0812cf7098ab449a` |
| Source archive | `94c44c4ebad8f9b7be143cc9863b0b8b51a310154d1a0fcd8e9d4829349545c7` |
| Candidate receipt | `b4d881f97873d0f9144c79578805f9b9d1e91ff5d8556af2656c058c1c9e041f` |
| CI admission receipt | `6cb1705b9e3c1d34713479c4da629a6de5f9715999de134a4926bfdd8ff132de` |
| Request schema | `3e38751e56a6b161196f419bb6d55cbee0f68cd39cca9ea4ab82014b84cb7cc5` |
| Result schema | `543e37d2d12851cb1172dacb594c503371ce93579b807f9cda9618eb23839e0e` |

The original wheel and source archive are in that source worktree's
`.cache/paired-candidate-9202156/artifacts/`, named
`regulatory_site_prediction_reconstruction-0.6.0rc1-py3-none-any.whl` and
`regulatory_site_prediction_reconstruction-0.6.0rc1.tar.gz`.
Both file hashes were rechecked for this handoff. They are local review artifacts,
not public package releases. Verify hashes after copying to a consumer-owned
cache; do not depend on the original absolute path at runtime.

## Small saved-result packet

The three complete synthetic results below total **253,631 bytes**. They are
available with their receipts at immutable evidence commit
`9c123721cfd16904474e78063e1bc45f7b39f0ba`, under
`models/paired/0.6.0rc1/`. Matching inputs are in `examples/`; the public schemas
are `schemas/paired-regulatory-{request,result}-1.schema.json`.
These saved outputs support initial importer/display checks without installing
the scorer or running a folding process. Label them as synthetic examples.

| Result file | File SHA-256 |
| --- | --- |
| `paired-promoter-unchanged.json` | `7634875794bb5cb4aff32a688a44e98d8974099365e4c5f0687ac5e0deda7557` |
| `paired-promoter-indel.json` | `60920a6d11016e5bd3d03c4bffcc03cbf49beb1a95c839235f2caa27657777c6` |
| `paired-rbs-substitution.json` | `c44da29ac031b47131858f8674fb7d872833e5ce9eff34ac3b829c370aa6393e` |

File SHA-256 and embedded canonical hashes are distinct. In the candidate's
`offline_smoke` receipt, `request_sha256` hashes the example file bytes; the
result's `request_sha256` hashes compact sorted finite JSON. Its
`prediction_sha256` hashes the complete canonical result excluding only that
field. All three file hashes and both embedded identities were rechecked.
Use the [exact runtime contract](paired-regulatory-runtime.md) for serialization.

## Consumer scope and semantics

B coordinates the isolated cyano branch `work/prediction-display-20261019`
from `07b27ed283241af9d964dabf62f0507f07d25310`. A reserves no viewer paths.
The first inventory/plan is B's existing Claude assignment; do not duplicate it
or the already landed TSS edit-count UI. The
[consumer boundary](cyano-integration.md) remains authoritative.

For `paired-regulatory-result-1`, retain both native results, complete candidate
rosters, coordinates, exact edit maps, units, model/backend/host identities,
warnings and coverage. Deltas mean **recoded minus current** only for comparable
successful values. Null is unavailable, not zero; partial diagnostics are not
a complete pair. An unmatched candidate or changed score does not establish
biological site gain/loss or altered expression. Preserve forward/reverse and
split circular paths; never draw an invented bounding interval across an edit.

Show predictions separately from measured TSS annotations. RBS accuracy and
Promoter host transfer remain limited; no native UTEX calibration or improvement
claim follows from the synthetic checks. Do not infer a new threshold or fit
against consumed/private outcomes. Any later bounded scoring uses the exact
package and explicit caller settings; Promoter needs only Python, while RBS
requires the separately admitted backend. No broad genome run is part of preview.

Producer implementation resumed on 2026-10-21 under the
[delivery program](calculator-delivery-program.md), while this preview stays
bounded and held by PV-R1. A new transcript adapter and the unaccepted
portable-original-backend task are outside the current wave. Preserve the
existing 0.8 CI without making it a preview dependency. This handoff authorizes
no new credentials,
privileges, account/coin use, main merge, tag, deployment or production admission.
Consumer code and rendered tests stay with B; package integrity stays with A.
