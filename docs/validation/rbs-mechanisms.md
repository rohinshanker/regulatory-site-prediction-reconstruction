# Published-mechanism reconstruction profiles

- Purpose: Specify reproducible refinements and their limits independently of fitted accuracy.
- Scope: RNAstructure 6.6 historical, footprint-only and extended-context profiles.
- Last verified: 2026-10-16

## Profiles and exact boundaries

The default `historical` profile keeps the Wave 1 algorithm and parameters.
`footprint2017` changes only downstream structural occupancy. `context2017`
also expands the bounded RNA context. Neither implements all of RBS Calculator
v2.0/v2.1.1. Profile names are selectable through `--profile` or the library's
`predict(..., profile=...)`; unknown names fail rather than selecting a default.

| Profile | Model ID | Upstream / downstream window | Coding footprint |
| --- | --- | --- | --- |
| historical | salis-v1-rnastructure-6.6-reconstruction-1 | 35 / 35 nt | 1000 nt; all downstream bases unfolded |
| footprint2017 | footprint2017-rnastructure-6.6-reconstruction-1 | 35 / 35 nt | 13 nt |
| context2017 | context2017-rnastructure-6.6-reconstruction-1 | 100 / 100 nt | 13 nt |

For a zero-based first coding nucleotide `s`, the coding footprint is
`[s, min(n,s+13))`. The start codon occupies its first three bases; the next
base is position +4 in the paper. The refolded suffix begins at `s+13`, not
`s+16`. Folding remains clipped to the supplied sequence and profile window.
The full occupied region also includes the chosen SD through the start codon;
`coding_footprint` reports only its coding portion. The upstream historical
four-base standby operation remains separate.

The footprint implementation folds the suffix independently, projects its pairs
into the full joint mRNA/aSD structure, and retains those pairs in both bound
states. Every complete state is reevaluated with `efn2 --simple`. Consequently,
`dG_post_footprint` is the isolated suffix's diagnostic folding energy, already
represented inside `dG_complex`; **do not add it again** to the total. Whole-state
dangles/coaxial interactions can make the total difference differ from this
isolated energy. The returned `post_footprint` structure uses suffix-relative
coordinates; the joint structures retain window-relative coordinates.

Historical result schema 1.0 remains unchanged. Refined results use
[schema 1.1](../../schemas/rbs-result-1.1.schema.json), adding `coding_footprint`,
`post_footprint` and `dG_post_footprint`. Non-successful sites keep these null.
Refined CSV summaries include schema, model and prediction identity columns;
historical CSV output remains byte-compatible. Requests retain [schema 1.0](../../schemas/rbs-request-1.0.schema.json); the profile
is an explicit execution setting included in model/prediction identity.

## Primary provenance and reconstruction choices

[Espah Borujeni et al. 2017](https://doi.org/10.1093/nar/gkx061), Methods,
“A biophysical model of translation initiation,” Eq. 3, separates pre-SD,
SD–aSD and post-footprint energies. Its footprint section specifies that
occupied coding bases cannot form secondary structure and that the remaining
suffix can refold. The published 13-nt parameter was selected using that paper's
experiments; it is not an independently estimated parameter in this package.
The historical study therefore cannot be a model-development-unseen test of
that published parameter, even when this reconstruction's own tuning excludes it.

Primary full text: [PMC5435973](https://pmc.ncbi.nlm.nih.gov/articles/PMC5435973/).
Europe PMC XML retrieved 2026-10-16, SHA-256
`63d10d9b55eb9d98430c88d1c2748e95fec8a6d8fe3b96af52bf228c0df3b3aa`.
No article prose, figure or restricted supplement is bundled. Equations and
biological facts are independently implemented; the inherited Salis GPL notice
and separate RNAstructure executable boundary remain in force.

[Espah Borujeni et al. 2014](https://doi.org/10.1093/nar/gkt1139), Methods and
“Genome-wide predictions of 5′ UTR translation rates,” supplies transcript-boundary
context and uses sequence through 100 coding nucleotides. The 2017 methods state
that at least 75 coding nucleotides were supplied. The extended profile's fixed
100/100 cap is a **declared bounded reconstruction choice**, not a recovered
published cutoff or a website-equivalent setting. In particular, the observed
website uses 100/35. A cap can miss distal RNA/standby effects. The footprint-only
profile isolates occupancy from this context change.

Primary full text: [PMC3936740](https://pmc.ncbi.nlm.nih.gov/articles/PMC3936740/).
Europe PMC XML SHA-256
`3410c14d94f74845fe5ffa8d879bd33144909c0fc72e439bc91e9ca032333a39`.

## Mechanism and parity matrix

| Mechanism | Current treatment | Remaining difference |
| --- | --- | --- |
| Start-codon and continuous spacing energies | Historical GPL source equations unchanged | Later production constants not independently recovered |
| Coding footprint | Explicit 13-nt constrained occupancy and suffix refolding | Open engine and joint-energy evaluation differ from original ViennaRNA model |
| Transcript context | Supplied RNA is clipped at its actual boundary; extended profile bounded at 100/100 | No claim that an arbitrary genomic window is an observed transcript |
| Standby | Historical signed four-base opening retained | 2014 module geometry, selective unfolding and sliding unimplemented |
| Search/ranking | 100 bounded cofold tracebacks; connected 3-kcal band; legacy ranking | Not exhaustive NUPACK search; not hosted 8-kcal search or globally optimized later final state |
| Sequence-specific stacking | RNAstructure native energy interactions only | No separately reconstructed production stacking term |
| Folding kinetics / ribosome drafting | Not implemented | Equilibrium folding cannot establish kinetic initiation behavior |
| Host calibration | Explicit aSD, temperature and descriptive host | No inferred host-specific coefficients or native-UTEX calibration |

The 2014 standby model describes surface area `15 + P + D - H` (H capped at
15), fitted distortion coefficients 0.038, -1.629 and 17.359, and optimization
over module-specific unfolding/sliding. Copying just the polynomial would omit
module selection and structural optimization. No such partial substitute is
silently inserted here; ticket 04 retains this unresolved mechanism scope.

## Reproduce the mechanism checks

```sh
export REGSITE_RNASTRUCTURE=/absolute/path/to/RNAstructure
.venv/bin/regsite examples/rbs-footprint.json --profile historical
.venv/bin/regsite examples/rbs-footprint.json --profile footprint2017
.venv/bin/regsite examples/rbs-footprint.json --profile context2017
.venv/bin/python -m pytest tests/test_profiles.py tests/test_backend.py
```

The synthetic nine-base `GGGAAACCC` suffix immediately outside the footprint
has independently verified isolated energy -1.2 kcal/mol. The refined joint
state retains its three pairs; the historical state unfolds them. This is a
mechanism check, not a measured translation-rate validation. Unit fixtures also
cover exact +13 boundaries, truncated coding regions, empty suffixes, reverse
projection, profile identity, invalid profile names and explicit missingness.
The longer real-engine fixture checks expanded bounds. Backends remain capped
at 200 single-strand bases, 100 leader bases and 212 CT positions, with the same
15-second subprocess and 60-second default/120-second maximum record budget.

Experimental ablations and independently evaluated claims belong to tickets
12/13/16/17. No parameter was fitted to website outputs, published held-out
measurements or final evaluator feedback to implement these profiles.

Longer leaders can spend the bounded 100 tracebacks on alternative upstream
folds rather than distinct SD sites. Expanded context therefore does not imply
more complete binding-site discovery. Coverage and SD-strength subgroups must
remain visible in comparison reports.
