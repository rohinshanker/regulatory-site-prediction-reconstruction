# RBS context collection boundary

- Purpose: Execute one frozen two-profile input-context diagnostic and preserve auditable private attempt evidence.
- Scope: Independent collection under #34; no model fitting, translation labels or retry/resume path.
- Last verified: 2026-10-19

The [context metrics](rbs-context-metrics.md) compare measured-TSS and declared
genomic-flank inputs using unchanged profiles. The collector at
`benchmarks/rbs/context_collect.py` owns execution bookkeeping only. It imports
no scoring runtime. A caller must independently admit the package, installation,
backend and CI receipt, then freeze the plan and acknowledge the bounded stage.
Hash equality alone does not prove those external admission checks.

## Plan and admission

`make_plan` binds the exact LF-only UTF-8 panel, complete candidate receipt,
final package admission, installed CLI, all three backend binaries, build receipt,
table manifest and every table file. It includes the complete scenario roster,
ordered historical/context2017 jobs, exact arguments, output directory and
collector source hash. `preflight` requires independently supplied expected plan,
candidate and admission hashes plus the exact acknowledgement. It rejects changed
artifacts before execution and checks them again between profiles.

Freeze the independent extraction expectations and metric/helper source hashes
with the public stage acknowledgement. Recheck the installed package's recorded
wheel-member hashes and executable identity before collection. Do not import a
source checkout in place of the admitted installation. Children clear
`PYTHONPATH`/`PYTHONHOME`, disable user sites, fix numerical-library thread counts
at one and receive an explicit `REGSITE_RNASTRUCTURE` path.

The panel is not deduplicated: every scenario runs once under each profile,
preserving original evidence and IDs. Scientific settings are in the candidate
receipt. The stage uses 60 seconds per record, 3,600 per native batch and 7,200
for the entire collection. A 30-second serialization/exit allowance is inside
that whole-stage ceiling. Each actual launch uses the smaller fresh remaining
stage time and batch-plus-allowance. Durable writes consume the stage budget.

## Process and evidence ownership

`collect` requires a new private output directory; an existing directory is
always refused. Directory permissions are 0700 and files are exclusive 0600.
The complete plan and inputs precede subprocess creation. Each attempt records
and syncs its intent, rechecks remaining time after the durable work, records
the observed real exit before parsing output, then syncs validation and hashes
before another launch. Persistence errors stop the stage.

Only one child group runs at a time. The collector starts an isolated POSIX
process group, bounds each output stream to 64 MiB and kills/waits its own group
on cancellation or timeout. The admitted runtime's trusted backend executables
inherit that group; see [external process deadlines](rbs-runtime.md#external-process-deadlines).
Do not release the reserved folding slot merely because the CLI parent exited.
Unconfirmed cleanup requires checking the owned process group and reporting the
uncertainty; it never authorizes another scientific job. Arbitrarily substituted
or detached descendants are outside the admitted process contract.

Native outputs must preserve the full request roster, complete model/backend
identities, settings, statuses and actual CLI exit semantics. Valid per-record
failure is retained. A process failure, timeout, malformed/oversized output or
failed persistence stops later profiles. No retry, repacking, fallback model or
input/ID rewriting is allowed. Raw outputs and diagnostic reasons stay private.

## Read-only recovery and analysis

`recover(output, expected_plan_sha256=...)` never launches or writes. It checks
ordered events, type-sensitive observations, exact archived inputs, stream
hashes, final collection and receipt. An intent lacking observation is unknown,
even if the process might never have started. It is not an unstarted job that
can safely be retried. Truncated or unfinalized evidence is not analysis-ready.

Require `ready: true` before ordinary metric adaptation. Independently check
every extracted context against the pre-candidate expectations and validate
public native/core schemas before interpreting results. Preserve legitimate
record failures and all denominators. If recovery fails, report the attempted,
unstarted and unresolved counts without inventing score summaries; forensic
inspection remains read-only. A finalized failed stage does not justify a rerun.

Publish only independently reviewed aggregates and artifact identities.
Energy/rank changes describe input sensitivity, not measured translation
improvement or host calibration. Repeated contexts and loci are not independent
experimental measurements. The selected panel cannot become an untouched new
test after its outcomes have been inspected.

## Reviewed frozen result

The [completed 0.6 diagnostic](rbs-wave5-context-results.md) and its
[exact aggregate](../../benchmarks/rbs/wave5-context-aggregates.json) retain the
independently reviewed output-derived metrics. The separate source audit also
reconstructed the full 4,808-association census, six-stratum first-four selection,
all 24 loci, 31 source alternatives and 124 scenarios in order. The consumed
collection is immutable; reproduce arithmetic from saved outputs, without new
predictor execution.
