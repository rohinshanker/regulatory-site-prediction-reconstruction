# Component calculator job contract

- Purpose: Run all eight reviewed command kinds in explicit, reproducible offline campaigns.
- Scope: Version-2 orchestration extension; implementation pending. No new model inference or consumer admission.
- Last verified: 2026-10-21

This extension retains the [version-1 job contract](offline-calculator-jobs.md)
and its exact five schema files. Version-1 manifests still admit only RBS,
Promoter, paired comparison, supplied transcript and conditional response. Their
CLI/library calls and schema shapes remain valid. Runtime identity changes still
prevent resuming an old campaign with changed package bytes; read-only verification
of an old campaign remains supported. No identity is silently upgraded.

## Version selection and dispatch

`regsite-jobs run`, `resume` and `verify` select the interface from the supplied
manifest. There is no mutable global version flag. New manifests use
`calculator-job-manifest-2` with the same exact top-level and per-job keys,
request-byte/path/hash rules, limits and ID rules as version 1. All eight kinds
are available in version 2. Existing five kinds retain their exact options and
backend rules. The three new kinds have no orchestration options:

| Kind | Fixed entry point | Required backend flag | Added arguments |
| --- | --- | --- | --- |
| `coupling` | `python -m regsite.coupling_cli` | `false` | None |
| `termination` | `python -m regsite.termination_cli` | `true` | `--backend-manifest {termination_backend_manifest}` |
| `drafting` | `python -m regsite.drafting_cli` | `false` | None |

Each receives `-` for the stored request on stdin, with the same interpreter
`-P -s`, environment and process supervision as version 1. None accepts
`--format json`. Unknown kinds/options and incorrect backend flags refuse;
version 1 rejects every new kind. The runner does not discover sites, transform
requests, split rosters or feed one component's output into another automatically.
Native requests and complete output streams stay opaque and unchanged.

Version-2 campaigns, attempt receipts and successful/partial/corrupted/incomplete
summaries use `calculator-job-campaign-2`, `calculator-job-receipt-2` and
`calculator-job-summary-2`. Their shapes match version 1 except the backend object
below and the eight-kind roster wherever a kind appears. Launch records retain
`calculator-job-launch-1`: no launch fields or process ownership rules change.
Authoritative campaign and receipt versions must agree with the manifest; mixed
versions are not accepted as equivalent. Like version 1, `summary.json` is a
replaceable derived report, not the source of truth: verify recomputes its returned
summary from verified immutable records rather than trusting the cached summary.

When no trusted summary can be produced, the CLI retains the existing bare
`calculator-job-summary-1` invalid envelope with `status: invalid` and a stable
error code, for either manifest version. This transport error envelope does not
claim that a version-2 campaign was created or verified.

## Explicit backend admission

`run` and `resume` add an optional CLI argument `--termination-backend-manifest`
and library keyword `termination_backend_manifest`. It must be supplied exactly
when a version-2 termination job is present, and otherwise refuses as unused.
Version-1 calls refuse that new argument as unused. It must name an absolute
regular, non-symlink file through non-symlink directories; no environment fallback,
automatic download, discovery, compiler invocation or installation is allowed.
The existing `--backend-root` rules apply only to kinds that actually use the
RNAstructure backend; a termination-only campaign does not require that root.
A mixed campaign can require both independently.

Version-2 `campaign.backend` has exactly three keys: `rnastructure`,
`conditional_original` and `termination`. Each is null when unused. The first two
reuse their existing verifiers unchanged. `termination` is exactly the public
identity returned by `termination_backend.load_backend(path).identity`, using
its unchanged manifest, engine and table verification. Paths are not identity;
source/binary/table hashes and all recorded native build parameters are. No
new builder or native verifier is introduced by this extension.

Verify termination identity before execution and after each job under the same
cooperative deadline policy as other identity checks. A valid but changed
manifest identity, binary or table stops reuse/execution rather than silently
switching engines. Caller backend argument validation must happen before creating
a campaign. A post-job verifier failure must preserve captured output and produce
the existing nonterminal runtime-change/deadline semantics. New refusal codes
must be stable and documented with the implementation. The bounded manifest and
native artifact reads are cooperative steps, not a hard wall-time or disk quota.

Read-only `verify` needs neither backend argument nor an installed native engine;
it validates the recorded identity shape and all applicable stored byte, version,
roster, command and outcome relationships. `resume` additionally requires the
current runtime and applicable native backend identities to match the campaign.
Do not weaken exact-original conditional admission for mixed campaigns.

## Preserved execution and acceptance

All version-1 constraints remain: sequential jobs, one owned child process group,
source/bytecode/interpreter identity, native caps, strict input parsing, absolute
external output storage, exclusive launch/receipt publication, bounded capture,
complete failed/null outputs, attempt budget, signal/deadline cleanup and no
rerun of verified terminal attempts. A command exit of zero is software success;
it does not validate biological meaning, native calibration or model equivalence.

Implementation acceptance requires:

- Existing version-1 schemas byte-identical, all existing tests passing, and
  read-only verification of a campaign produced by the frozen old package.
- Full tests for version selection, kind/option/backend dispatch, missing/unused/
  invalid backend paths, changed identity, corrupt/mixed-version receipts, limits,
  argument substitution and verify/resume. No mutable global context or arbitrary
  command interpolation.
- Artificial single/batch/unsupported new-component requests through real CLIs,
  with complete native stdout retained; at least one mixed campaign containing
  all eight kinds, separately admitted original RNAstructure and termination.
- Bounded actual native termination example and explicit resource failures;
  frozen source/build/table admission remains unchanged. No broad genome run.
- Fresh installed package run/verify/resume, independent exact-patch review,
  100% coverage of new paths, static gates and the existing platform matrix.

These are orchestration checks. Scientific numerical validation remains with
B's frozen independent drafting protocol, and new source admission remains with C.
