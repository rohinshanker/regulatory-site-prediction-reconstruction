# RBS live-reference acquisition contract

- Purpose: Acquire bounded, provenance-preserving live-reference outputs.
- Scope: Session B alone owns the isolated Chrome session and acquisition ledger.
- Last verified: 2026-10-16
- Panel: [12 exact diagnostic inputs](../../benchmarks/rbs/live-diagnostic-panel.json).

## Price, panel and stopping rules

The normal authenticated RBS prediction form at
<https://www.denovodna.com/software/predict_rbs_calculator> displayed **1 coin per
job** and “Version 2020.” Before submitting,
the owner was shown 12 jobs / at most 12 coins and the stopping rules below.
No credits, subscriptions or accounts were purchased.

The panel contains ATG/GTG/TTG/CTG variants, shorter/longer spacers, no-SD,
upstream-hairpin, leaderless and no-start cases, plus 2014 constructs 136 and 1.
Every full input, hash and selected zero-based start is frozen. These are
development diagnostics, not a blinded accuracy test. The service scans all
starts; retain every returned candidate and compare the declared target start
separately. Do not silently select whichever result matches best.

Select *E. coli* MG1655 (NC_000913), with long UTRs disabled. DH10B was not returned
by the form's host search. The two DH10B experiments therefore have a declared
host-configuration mismatch. The form exposes no temperature field; returned
settings must be recorded instead of inferred from defaults.

Stop if the displayed price changes, an unexpected debit appears, a job's
submission state is unknown, the account is exhausted, an export cannot be saved,
or the declared cap is reached. The owner explicitly authorized continued
acquisition with an unchanged balance while budgeting one coin per accepted job.
An unchanged balance alone therefore does not stop this panel. A job acceptance
with a result URL is a submitted job even while queued. Never resubmit it merely
because queueing is slow. Resolve
existing job state through the ordinary UI before any retry. No API entitlement
is inferred from browser login.

## Completed panel and billing discrepancy

All 12 frozen cases were attempted: **11 accepted jobs finished**, nine with CSV
exports and two with explicit no-candidate results. The 99-base `w1-leaderless`
input was rejected by the form's 100-character minimum. It was not padded,
replaced or resubmitted; no server job was created for it. This establishes a
form boundary, not the algorithm's handling of leaderless translation.

The CTG-only and no-start inputs both returned an explicit absence of canonical
start codons, with no CSV export control. Their rendered results were saved;
neither is represented as a zero-rate prediction. The CTG result is consistent
with the historical scanner excluding CTG even though its energy table contains
a CTG parameter. These two pages display Finished and a
nonzero runtime while their Ran field still says Waiting in the Queue; no actual
execution timestamp is inferred for them.

The nine CSV files contain 17 candidate rows. Every declared target for those
nine inputs is present; all row coordinates address start codons in their exact
frozen inputs. All component sums match total energy within 1e-8 kcal/mol
(largest residual 3.56e-15); none of these rows carries a warning. These are
serialization/arithmetic checks, not experimental accuracy. The two 2014
constructs each return five candidates, all retained, with their declared target
starts checked separately. No held-out outcomes were used.

The first `w1-atg` job finished and its supported CSV export was saved, along
with rendered structure/settings text. Its input record reports **v2.1.1**. It
returned one candidate at start 25, matching the independently counted zero-based
start (the one-based nucleotide coordinate is 26). The export preserves full
precision; the table rounds it. The initial-state structure has 60 unpaired
bases; the final structure has an ampersand strand separator and a 9-base rRNA
strand. This is one observed coordinate example, not a general coordinate proof.

Returned settings: upstream cutoff 100, downstream cutoff 35, dangles 0,
suboptimal aSD/SD energy gap 8 kcal/mol, footprint 13, temperature 37°C, parameter
file `rna_andronescu2007.par`, displayed rRNA string `ACCUCCUUA`. These settings
were checked on all 11 accepted jobs. The “maximum bulge” field is blank and
remains unknown. The final-state energy in the first job's expanded
total-change equation disagrees with the adjacent final-state sum by the
stacking contribution; the CSV and component sum agree. Treat this as a rendered
formula inconsistency, not evidence that the CSV algorithm omitted stacking.

After all accepted jobs completed, both the banner and normal account-settings
page still showed 100 coins (Pay As You Go plan), unchanged from the initial
balance. The observed balance change is zero, but the actual charge is
**unreconciled**, not asserted free. The owner authorized continuation after the
first-job discrepancy; the ledger reserves **11 coins** at one per accepted job,
within the original 12-coin cap. No duplicate submissions or purchases occurred.
The observed display cannot distinguish delayed billing from a waiver or an
account-specific policy. The final observation time is recorded in
[the public acquisition manifest](../../benchmarks/rbs/live-acquisition.json), which
contains hashes/settings/status only; it is not an accuracy claim.

## Private records and reproducibility

The private directory is `~/.local/share/reg-site-reference/wave1/`, mode 0700.
It holds `job-ledger.json`, nine CSV exports, rendered structure/settings or
explicit empty results, the form-rejection evidence,
the ordinary terms page, and browser artifacts. The ledger records a nonidentifying
session label, input hash, exact job ID, timestamps, estimate, observed balance,
charge status and export hashes. Never commit that ledger, account screenshots,
cookies, credentials or restricted raw outputs. The public panel and acquisition
manifest suffice to identify the input and verify a privately shared export.
Use `python -m benchmarks.rbs.live PANEL CASE_ID PRIVATE_CSV` to verify each CSV's
input hash, schema, coordinates, finite values and component sum independently of
runtime scoring. Raw CSV bytes, including line endings, determine the export hash.

The [terms](https://www.denovodna.com/terms), last updated 2020-11-30, permit
internal research and retain service intellectual-property restrictions; no
open redistribution licence for numerical exports was established. Keep raw
outputs private. A second lab-member account requires owner-provided browser
login and appropriate account-holder/provider permission; credentials stay in
that browser. Do not obtain accounts or share credentials yourself.

Before an action requiring a new credential, administrator password, macOS
permission, or other privilege, state the exact action/resource/reason in chat
and await the owner's decision. Do not use another mechanism to bypass a pending
or denied approval. Forward this requirement in every permitted handoff.

## Larger-panel proposal

Once billing is understood and both candidate model commits/settings are frozen,
a **96-case total panel** is a useful next stage: all 27 held-out 2017 constructs,
48 development constructs stratified over the 22 source design groups, and
21 synthetic mechanism/boundary cases. Include the existing 12 diagnostics in
these totals and reuse any completed exports with identical settings/version.
Freeze exact additional IDs before acquisition; this paragraph is a proposal,
not an already frozen 96-case manifest.

At the observed 1 coin/job, a 96-job panel costs at most 96 advertised coins;
reusing the 11 accepted diagnostics leaves at most 85 additional jobs/coins.
The rejected 99-base case needs an explicitly frozen replacement if it is to
count as one of those 96 server jobs. This estimate is not authorization to
extend the current panel. Do not infer available funding from the unchanged
banner. Budget at a changed price `c` is `96*c`, less only verified reusable jobs.
Request lab funding through the owner if required; do not purchase it.

For an iid proportion near 0.5, 12 observations have a descriptive Wilson
half-width about 0.246; 96 have about 0.098. These are planning calculations only:
shared-family dependence makes real precision worse. The 27-construct study has
only 18 translation measurements and one template, so buying more live predictions
on those sequences does not create independent experimental evidence. If biological
accuracy is the question, obtaining a new openly reusable study with independent
families, mRNA measurements and day-level replicates is more valuable than simply
scaling this same-family panel to hundreds of paid predictions.
