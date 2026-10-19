# Specified-aptamer conditional-state admission

- Purpose: Define an executable open first slice without inventing missing ribosome/ligand states.
- Scope: Independent B #42 contract and synthetic fixtures; A owns runtime and release admission under parent #9.
- Last verified: 2026-10-18

## Admitted components and boundaries

The first sequence-based profile is `canonical_structure_pair`: evaluate the
same supplied RNA without constraints and with an explicitly supplied aptamer
constraint. Report both structures, their energies and their difference. The
[canonical component](riboswitch-constrained-reference.md) establishes this for
original RNAstructure 6.6, nested canonical pairs, at most 200 nt and 310.15 K.
Its constrained RNA folding energy is **not** a ligand-constrained ribosome-binding
energy or a predicted translation rate.

A separate `supplied_energy_response` profile can evaluate the published scalar
relationships from explicit caller-supplied OFF/ON ribosome-binding energies,
RNA structural energies, affinity, apparent beta and occupancy assumptions.
This is an equation reconstruction, not a recovered sequence-to-switch engine.
No calibrated affinity, aptamer location, intracellular concentration or host
parameter is inferred. Both profiles can be implemented independently.

The complete conditional sequence scorer remains unadmitted: canonical
single-strand Fold/efn2 does not provide constrained mRNA–rRNA binding, the
published constrained standby calculation, or pseudoknot terms. Running the
existing unconstrained RBS model twice does not supply these missing ON-state
interactions. Protein steric effects, discovery, kinetics and optimization are
outside these profiles. Keep parent #9 open.

## Source and equation identity

The primary source is [Espah Borujeni et al. 2015](https://doi.org/10.1093/nar/gkv1289),
supplement Figure S1 (PDF page 3), S4–S19 (pages 23–27), and S20–S26 (pages 28–29).
The pinned PDF SHA256 is
`b68da105ea6c8f6c26f6e6f66863d066c34b1052dd0eeb23159c96d0c1a861fe`;
member identity and retrieval URL are in the
[source manifest](../../benchmarks/other-calculators/source-manifest.json).
The article/supplement grant is CC-BY-NC-4.0. It does not supply an open software
implementation grant. Keep the original PDF, figures and measurements external;
the independently expressed equations, synthetic fixtures and new implementation
carry the repository's GPL-3.0-or-later terms. No original fitted parameter table
is copied into the required runtime. RNAstructure remains a separately installed
GPL-2.0-only executable with its notices and existing binary/table identities.

Use kcal/mol for all energy terms, Kelvin for temperature and mol/L for all
concentrations. Relative molecular volumes are dimensionless ratios to one
solvent molecule. `beta_mol_per_kcal` is an explicit positive apparent coefficient;
it is not inferred from temperature and must not be silently replaced by `1/RT`.
The paper's nominal coefficient and fitted experimental slope are distinct.

With supplied ribosome-binding energies `E_off`, `E_on`, RNA folding energies
`G_off`, `G_on`, ligand-binding energy `G_bind` and fraction `f`:

```text
structural_cost = G_on - G_off
switching_energy = structural_cost + G_bind
log_AR_max = -beta * (E_on - E_off)
AR_max = exp(log_AR_max)
AR_conc = (1-f) + f * AR_max
q = exp(-beta * switching_energy) / (1 + exp(-beta * switching_energy))
AR_actual = 1 + q * (AR_conc - 1)   if switching_energy > 0
AR_actual = AR_conc                 otherwise
```

S4/S5 define proportional rates, not rates in physical time units. Preserve the
ratio direction ON/OFF. These equations also admit ratios below one; do not clamp
repression into activation. The scalar `q` is a conditional metastability factor,
not the concentration occupancy `f`. Applying it twice or applying it to stable
states changes the model. The source does not assign exactly zero switching
energy to a branch. This reconstruction chooses a strict-positive test, leaving
zero uncorrected, and identifies that choice as `strict_positive_zero_uncorrected`.
Its positive-side limit is one half, so this completion of the published piecewise
rule is discontinuous when `AR_conc != 1`; report this rather than smoothing or
fitting a threshold. A zero fraction gives ratio one even for different states.

S12 prints `RT ln(Kd)` without specifying a concentration standard. This contract
requires the explicit convention `G_bind = RT ln(Kd/standard_molar)`. Both
concentrations must be positive and in mol/L; zero Kd is invalid, not infinite
affinity. A direct supplied energy must declare the same reference convention.
Changing the standard changes the scientific input identity. It is not a unit
conversion. Do not equate a supplied Kd with the effective half-occupancy point
of the apparent-beta volume model.

The constant is `R = 8.31446261815324 / 4184` kcal/(mol K), from the exact SI
molar gas constant and the thermochemical kcal convention. The
[NIST constant entry](https://physics.nist.gov/cgi-bin/cuu/Value?r%7Csearch_for=R)
identifies its exact SI value. This constant is independent of the model beta.

## Explicit published volume reconstruction

The `published2015_volume` occupancy mode reconstructs S20–S26 literally with
the equal-volume approximation for free RNA and RNA–ligand complex shown in
Figure S1. It is not a generic Hill law, a multi-conformation folding partition
function, or a demonstrated hosted implementation. Inputs are total RNA `m`,
total ligand `l`, solvent molarity `Cs`, and relative volumes `Vm`, `Vl`, all
explicit. The paper's 55.14 M water concentration at 310.15 K and reporter/ligand
volume estimates are source assumptions, not universal host defaults.

For complex molarity `b` in `[0,min(m,l)]`:

```text
C_1 = m-b; C_ligand = l-b; C_3 = b
v_1 = Vm*(m-b)/Cs; v_ligand = Vl*(l-b)/Cs; v_3 = Vm*b/Cs
G_1 = G_off; G_ligand = 0; G_3 = G_on + G_bind
ln(Q_v,i) = -beta*G_i/V_i
beta*(F-F_ref) = sum_i v_i * (ln(v_i) - ln(Q_v,i) - 1)
```

Visually verified S23 uses the **power** `Q_i ** (1/V_i)`, not division by
volume. Define `0*ln(0)=0` by continuity. The free ligand reference is zero;
do not add its binding energy a second time. Under these explicit assumptions
the interior stationary condition is:

```text
D(b) = Vm*ln(b/(m-b)) - Vl*ln(Vl*(l-b)/Cs) + beta*switching_energy = 0
D'(b) = Vm*(1/b + 1/(m-b)) + Vl/(l-b) > 0
```

This reduction and uniqueness proof are independent algebra from the source
objective. With positive totals and finite energies, the limits of `D` have
opposite signs, so a bracketed solver has one interior solution. Never use an
unbounded optimizer, silently accept a nonconverged result, or discard mass
balance errors. Preserve the bracket, residual and iteration count. At `l=0`,
`b=f=0`. At `m=0`, `b=0` but `f` and response ratios are undefined: emit
`no_mrna` and null concentration/actual ratios, not a fabricated zero or one.

The reconstruction has no independently validated solvent conservation or
crowding law beyond S20–S26. Report its resulting volume fractions and flag sums
above one as an assumption warning. Do not impose a new packing constraint,
solvent species, unequal complex volume, excluded-volume penalty or standard-state
correction and retain this profile identity. The paper's stated relative volumes
also differ from ratios obtained from its approximate absolute volumes; require
explicit relative inputs rather than silently reconciling those estimates.

Even with both relative volumes equal to one and zero RNA structural cost, the
literal model has effective molar dissociation constant `Cs*exp(beta*G_bind)`.
It generally does not recover the supplied physical Kd after the S12 conversion.
This exposes the source's empirical-beta/standard-state convention; it is not
permission to add a compensating fitted factor or call the result physical Kd.

## Proposed producer input boundary

`conditional-aptamer-request-1` is one object with exactly:
`schema_version`, `id`, `profile`, `input`, `provenance`, `settings`.
IDs are nonempty strings of at most 128 characters. `provenance` is exactly
`{kind,reference}`: kind `user_supplied` or `synthetic`, and a nonempty reference
of at most 1,024 characters. It describes the supplied assumption/evidence;
it does not certify calibration or a licence. JSON booleans are never numbers.
Unknown keys and nonfinite numbers are invalid. No implicit normalization,
host selection or inference from an aptamer name is allowed.

For `canonical_structure_pair`, `input` is exactly
`{sequence,aptamer,temperature_kelvin}`:

- `sequence`: 1–200 uppercase ACGU bases, in transcript orientation.
- `aptamer`: exactly `{id,range,constraint}`; `range` is a nonempty zero-based
  half-open interval inside that sequence. Coordinates are genuine integers.
- Full constraint: exactly `{mode:"full",structure}`. The structure length
  equals the aptamer span; `()` specify pairs and `.` forces an unpaired base.
  Bases outside the aptamer stay free, rather than being forced unpaired.
- Partial constraint: exactly `{mode:"partial",pairs,unpaired}`. Pair points
  and unpaired points are **zero-based relative to the aptamer**. Each pair is
  ascending. Convert each point to full-sequence position by adding the span's
  start, then add one only at the backend file boundary. Empty partial demands
  are an explicit no-op control with a warning, not evidence of ligand binding.
- Require nested AU/UA/GC/CG/GU/UG pairs, no shared partner, no duplicate demands,
  no paired/unpaired conflict, and at least three enclosed bases for a pair.
  Unsupported pseudoknot symbols or crossing pairs receive an explicit refusal.
- `temperature_kelvin` must be 310.15 for this admitted backend profile. Other
  positive temperatures are unsupported pending independent component fixtures.

For `supplied_energy_response`, `input` is exactly
`{temperature_kelvin,beta_mol_per_kcal,energies,energy_basis,affinity,occupancy}`:

- `temperature_kelvin` and `beta_mol_per_kcal` are positive finite numbers.
  The caller asserts that every supplied energy and affinity applies at that
  temperature; the model does not extrapolate thermodynamic parameters.
- `energies` is exactly `{rna_off_kcal_mol,rna_on_kcal_mol,
  ribosome_off_kcal_mol,ribosome_on_kcal_mol}` with finite numbers. A negative
  structural cost contradicts the subset-minimum interpretation and is
  unsupported; do not clamp it or reinterpret it as ligand-binding energy.
- `energy_basis` is exactly `{rna,ribosome}`. Each object is exactly
  `{source_id,model_id,parameter_sha256,backend_sha256,sequence_sha256}` and
  describes the caller-asserted common basis of its OFF/ON pair. `source_id` is
  a required ID; other values are IDs/hashes or null if unknown. Hashes use 64
  lowercase hexadecimal characters. Unknown values produce
  `unverified_energy_basis`, not invented provenance or a sequence-derived claim.
  A receipt with incompatible OFF/ON identities cannot be silently collapsed
  into this common-basis object. Callers must supply a consistent energy pair;
  this scalar interface does not independently attest their calculations.
- `affinity` is either exactly `{mode:"delta_g",delta_g_kcal_mol,standard_molar}`
  or `{mode:"kd",kd_molar,standard_molar}`. The standard is always positive and
  explicit; direct energy is finite and Kd is positive finite.
- `occupancy` is either exactly `{mode:"supplied_fraction",fraction}` with
  `0 <= fraction <= 1`, or exactly `{mode:"published2015_volume",
  mrna_total_molar,ligand_total_molar,solvent_molar,mrna_relative_volume,
  ligand_relative_volume}`. Totals are nonnegative; solvent and volumes positive.
  A supplied fraction is an assumption, never a solved concentration response.

Proposed exact `settings` keys are profile-specific, with no omitted defaults:

| Profile | Keys and bounds |
| --- | --- |
| `canonical_structure_pair` | `seconds_per_job`, `seconds_total`: positive finite numbers, resolved/emitted as floats; per-job ≤120, total ≤480, per-job ≤total. |
| `supplied_energy_response` | `seconds_total`: positive finite number ≤30, resolved/emitted as float; `max_iterations`: genuine integer 1–256. |

The proposed scalar stopping contract requires both the molarity bracket width
divided by `min(m,l)` to be ≤`1e-12` and a dimensionless residual divided by
`max(1,Vm,Vl,abs(beta*switching_energy))` of magnitude ≤`1e-12`. An exact interior
zero may collapse its bracket. Boundary cases need no interior residual.
Exhaustion or unrepresentable values fail explicitly. These tolerances belong
to the model's numerical convention identity, not a tuning parameter.

The canonical component's 120-second job ceiling and 200-nt domain are already
admitted. A two-state request uses at most four backend processes with no retries.
The proposed single-object transport caps are 65,536 UTF-8 input bytes and
1,000,000 uncompressed/authoritative result bytes, inclusive. Reuse the Promoter
contract's strict finite JSON and authoritative serializer, including both wire
and reserialization caps. A must measure and review the whole-CLI limits before
freezing a candidate; this proposal does not claim those runtime tests ran.

## Result and failure boundary

The proposed `conditional-aptamer-result-1` has exactly these top-level fields:
`schema_version`, `id`, `profile`, `input`, `provenance`, `settings`, `model`,
`request_sha256`, `status`, `reasons`, `warnings`, `errors`, `states`,
`structural_cost_kcal_mol`, `response`, `complete`. Resolved input/provenance and
effective settings are retained; fields not successfully validated are null.
`request_sha256` hashes the original complete parsed finite request using compact
sorted ASCII-escaped JSON with no newline. A valid parsed request keeps its hash
even if later execution fails; malformed/nonfinite JSON has a null hash.

`model` is exactly `{id,implementation_version,source_manifest_sha256,
parameter_sha256,backend,convention_id}`. `backend` is null for supplied algebra,
otherwise exactly `{fold_sha256,efn2_sha256,table_manifest_sha256}`. Parameters
bind the gas constant, numerical conventions and fixed backend flags; user beta,
affinity and volumes remain scientific inputs. `convention_id` binds natural logs,
equal RNA/complex volume, explicit concentration standard and
`strict_positive_zero_uncorrected`. A hash cannot turn caller-supplied energies
into sequence-derived or measured values. Profile and provenance remain visible.

For the structural profile, return `unconstrained` and `constraint_compatible`
states, each with exactly `{id,status,reasons,sequence_sha256,constraint_sha256,
structure,pairs,fold_energy_kcal_mol,efn2_energy_kcal_mol,jobs}`. `id` is one of
those two state names; status is `ok`, `failed` or `not_run`. `pairs` use ascending
full-sequence zero-based points; absent structure/pairs/energies are null.
The constraint hash binds resolved full-sequence `{pairs,unpaired}` demands;
unconstrained uses a null hash. Jobs are ordered objects with exactly
`{program,status,exit_code,timed_out,stdout_sha256,stderr_sha256}`; no local path
is scientific identity. Keep the distinction between an absent Fold header
energy and a verified efn2 zero. Calculate a structural difference only when both
states succeed with identical backend/table/settings identities. A failure,
violated constraint, deadline or infeasible state cannot yield a guessed structure
or difference. A negative difference is a state-order consistency failure, not
proof of stabilization. Translation/occupancy/activation outputs remain null.

For supplied-energy response, `states` is empty and `response` is exactly
`{ligand_binding_kcal_mol,switching_kcal_mol,log_ar_max,ar_max,ar_conc,ar_actual,
metastability_factor,metastability_applied,occupancy}`. The structural cost is
the separate top-level field. `occupancy` is exactly
`{mode,status,fraction,concentrations,volume_fractions,solver}`; supplied fraction
leaves the last three fields null. Solved concentrations are exactly
`{mrna_free_molar,ligand_free_molar,complex_molar,mrna_balance_error_molar,
ligand_balance_error_molar}`. Volume fractions are exactly
`{mrna_free,ligand_free,complex,sum}`. Solver is exactly
`{iterations,bracket_molar,scaled_residual}` with null residual at boundary cases.
No RNA structures are invented. Structural profile `response` is null.

Top-level statuses distinguish `ok`, `invalid_input`, `unsupported`, `failed`
and `no_mrna`. `reasons` contains ordered unique codes; `warnings` and `errors`
contain `{code,message}` objects. `complete` is true only when every requested
calculation is fulfilled; the undefined per-mRNA response at `m=0` is incomplete.
Invalid inputs fail before
backend execution; recognized unadmitted profiles/features are unsupported.
Execution/numerical failures retain inspectable completed components but leave
dependent results null. Missing/overflowed/underflowed values are never substituted
by zero, infinity or a successful partial result. Log results may remain valid
when a linear ratio is outside binary64, but that linear field stays null with
`numerical_range`; numeric equality at a configured limit is allowed.

Required warnings distinguish supplied energies, assumed occupancy/concentrations,
backend differences from the published ViennaRNA configurations, the piecewise
zero boundary and lack of native-host calibration. Structural feasibility does
not establish aptamer binding, switching efficacy, or biological gained/lost sites.
A must confirm or revise this proposed JSON boundary before its candidate freeze
and B's runtime comparison. This document admits components and conventions;
it does not claim an implemented export or complete release.

## Frozen independent checks

The [scalar/equilibrium fixture file](../../benchmarks/riboswitch/conditional-fixtures.json)
has SHA256 `a4be58ed590267a4d6d3b39e6e456241c92b911beb084bcab3b74c0537df8165`.
Its eight response, six equilibrium/boundary and three affinity cases are
synthetic; 21 declared invalid cases cover signs, zero denominators, nonfinite
values and booleans. Decimal strings preserve 65-digit construction precision;
the proposed producer input instead uses JSON numbers. Beta 1 is an algebra
control, not a recovered calibration. Earlier five beta-0.45 fixtures stay
unchanged.

Hand checks include `AR_max=4`, `f=1/5`, `switching=ln(16/5)` and beta 1:
`AR_conc=8/5`, the conditional factor is `5/21`, and `AR_actual=8/7`.
Repression with `AR_max=1/4` under the same conditions gives `27/28`.
The volume case `m=l=1`, `Cs=4`, `Vm=2`, `Vl=1`, switching `ln(16/5)` has
stationary `b=1/5`; direct substitution makes its derivative zero. With both
volumes one and switching zero, `4b=(1-b)^2` gives `b=3-sqrt(8)`.
These are constructed arithmetic identities, not fitted measurements.

The [three proposed input examples](../../benchmarks/riboswitch/conditional-request-examples.json)
show the complete profile nesting and independently known output slices.
The structural example reuses the already executed hairpin control with
unconstrained/constrained efn2 energies −11.2 kcal/mol and zero structural cost.
It does not assert ligand binding. The other examples use supplied energy
assumptions; their fractions/ratios are algebraic expectations. No proposed
producer request has been executed. Runtime acceptance still requires the exact
frozen interface, independent input/result validation, real-backend checks,
finite resource handling and a fresh-install receipt.


## Executable independent reference

[`conditional_reference.py`](../../benchmarks/riboswitch/conditional_reference.py)
implements only `response(inputs)`, `affinity(inputs)` and
`partition(inputs, max_iterations=256)` with standard-library Decimal arithmetic.
Use the exact input dictionaries in the frozen fixture file. Returned values are
Decimal objects, with explicit booleans/statuses and a null fraction when mRNA is
absent. This reference is separate from the proposed producer JSON interface;
it is not a sequence scorer, runtime validator or calibrated efficacy model.

The arithmetic context is isolated at 80 digits, round-half-even, exponent limits
±9999. Inputs are ASCII decimal strings of 1–128 characters; nonzero adjusted
exponents must lie in [−1000,1000]. Nonfinite values, unsafe arithmetic and
unresolved roots raise `ValueError`. Unequal Kd/standard values are refused when
subtracting their logarithms loses more than 20 decimal orders; a rounded zero
must not silently change the strict-positive correction branch. These bounds define the reference's supported
numerical domain, not a physical admissibility criterion. The producer may use
binary64 with its separately stated tolerances and explicit range failures.

Bisection requires both bracket width divided by `min(m,l)` and derivative
residual divided by `max(Vm,Vl,abs(beta*switching))` at most `1e-50`, within at most
256 iterations. The bracket therefore also bounds absolute occupancy error.
Outward-rounded derivative intervals must certify both bracket endpoint signs
and the central residual tolerance. Logarithm error margins are explicit because
Decimal logarithms ignore directed rounding. If precision cannot certify these
bounds, the reference refuses rather than reporting a successful bracket.
The result preserves the bracket, residual, scale and iteration count; zero-total
boundaries use zero iterations and null residual/scale. It reports volume sums
greater than one without adding a packing constraint. Equivalent convex sums
retain small positive repression ratios without cancellation to zero.

```sh
PYTHONPATH=src:. python -m coverage run --branch \
  --source=benchmarks.riboswitch.conditional_reference \
  -m pytest -q tests/benchmarks/test_riboswitch_conditional_reference.py
python -m coverage report --fail-under=100
PYTHONPATH=src:. python -m pytest -q \
  tests/benchmarks/test_riboswitch_conditional_contract.py
```

Tests cover all frozen numerical/refusal cases, mass balances, an independently
expanded derivative and convex objective, ligand limitation, concentration scale
changes, the declared zero discontinuity, tiny repression, iteration exhaustion,
unsafe exponents, caller-context isolation and the earlier beta-0.45 fixtures.
Independent 240-digit regressions cover near-equal affinity values and severely
disproportionate concentrations/volumes that invalidate an 80-digit point estimate.
No folding or biological measurements are used by these tests.
