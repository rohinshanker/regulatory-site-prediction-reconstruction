# Operon coupling source boundary

- Purpose: Admit a bounded historical translational reinitiation calculation while retaining unresolved RNA-unfolding semantics.
- Scope: Session C, child #60 of #8; bounded reinitiation admitted by independent review DEM-615.
- Last verified: 2026-10-21

## Pinned source

Tian and Salis (2015), [DOI 10.1093/nar/gkv635](https://doi.org/10.1093/nar/gkv635),
published pages 7137–7151. The primary paper, [Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4538824/fullTextXML)
and [supplement bundle](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4538824/supplementaryFiles)
were retrieved 2026-10-21. The PDF was obtained from the
[Semantic Scholar mirror of the paper](https://pdfs.semanticscholar.org/90f1/52d8ef4a5b6108c8c48a185a7f0e132753ff.pdf).
Exact hashes and source locations are in the [manifest](../../benchmarks/operon-coupling/source-manifest.json).
Printed page 7141 was visually checked; formula images are absent from XML text.
The supplemental PDF contains five figure pages and no additional equations.
The workbook was not opened or used as a calibration/validation dataset.

The article/supplement are CC-BY-NC-4.0, distinct from software permissions.
They remain external reference material. This repository independently expresses
mathematical relationships and original synthetic checks; it does not copy
article images, prose, source code or measurement tables into a required runtime.
No complete coupling implementation was found in the pinned SalisLabCode tree
`46da9132740bce30bccd107f02808adf2215e2f0`. Existing source admission also records
iDOG Operon implementation only as bytecode. This bounded search does not prove
that no other implementation exists.

## Unambiguous component proposed for admission

Equation (3), printed page 7141, gives the reinitiation contribution
`q_reinit = k_P * k_reinit(d) * exp(-beta * G_upstream)`.
Equation (2), page 7140, adds this to the downstream de novo contribution.
Define `q_up = exp(-beta*G_up)` and `q_independent = exp(-beta*G_down)`.
Then an explicitly **reinitiation-only** model is
`q_total = q_independent + k_P*k_reinit*q_up`.
The downstream supplied energy is the independent-start calculation; it contains
no inferred upstream RNA-unfolding correction. This is a bounded component of the
paper, not its full sequence-to-function model.

All `q` values use the same dimensionless exponential scale, with no unexplained
RBS score intercept or fluorescence conversion. `G` has kcal/mol units and beta
has mol/kcal units. Both energies must have the same energy convention and beta.
Callers provide those assumptions and provenance explicitly. No calculation of
sequence-derived energies or automatically selected host defaults is admitted.
Logarithms are natural; retaining log quantities avoids exponential overflow.

The source uses beta 0.45 and `k_P=10`; the latter converts the reporter-specific
coefficient into its model contribution and is not a universal measured rate.
The distance section, page 7142, states `k_reinit=0.0072` for `0 <= d <= 25`,
and `0.0220` for `d=-4`. Those exact stated domains are the proposed preset.
The model does not extrapolate other negative distances or distances above 25.
The described negative-distance slope alone does not uniquely specify the
intercept, clipping and transition, so those cases remain unsupported.
The model's synthetic-operon experiments were in *E. coli* DH10B; its natural
atp-operon comparison was in *E. coli*. No native cyanobacterial calibration follows.

Distance is `downstream_start - upstream_stop_start - 3` in 5'-to-3' transcript
coordinates. With complete CDS half-open intervals including their stop codons,
it is exactly `downstream_CDS_start - upstream_CDS_end`. A four-base overlap is
`d=-4`. Do not measure from the first stop base without the final subtraction.
Supplied annotation order is essential; adjacent genomic features alone do not
establish a shared transcript. Reverse-strand coordinates must first be mapped
onto the explicit transcript orientation.

## RNA-unfolding interpretation remains gated

Printed Eq. (4) is
`G_down = G_mRNA:rRNA + G_spacing + G_start + G_standby - G_noncoupling - G_coupling*F`.
Printed Eq. (5) is `F = 1 / (1 + C*exp(beta*G_up))`, with fitted `C=0.81`.
The text and figure captions describe negative coupling energies. Increasing
upstream initiation increases F, so the literal subtraction raises the downstream
energy penalty for a negative coupling energy. The surrounding explanation instead
describes upstream unfolding as relieving that penalty. This is an unresolved
source inconsistency; neither `F -> 1-F` nor a sign flip is silently admitted.
Sequence-based partitioning of inhibitory structures, partial unfolding and
backend equivalence are additional unimplemented dependencies.

Figure 1D on printed page 7140 explicitly uses the factor
`1/(1+C*exp(-beta*G_up))`, whereas Eq. (5) uses a positive exponent. These
competing formulas disagree in the primary source itself. The Figure 1 factor
is also not `1-F` at the same C: when `exp(-beta*G_up)=4` and C=0.81, they
are approximately 0.235849 and 0.168399 respectively. Selecting a formula,
complementing F or refitting C requires separate authoritative evidence.

The full coupled-state energy, unfolding correction, structural fraction,
protein abundance and complete Operon prediction therefore remain unavailable.
The proposed result must explicitly identify `reinitiation_only` and carry this
limitation alongside its numeric contribution. Source fidelity of these equations
is distinct from an experimental accuracy claim.

## Independent synthetic checks

The [fixtures](../../benchmarks/operon-coupling/synthetic-fixtures.json) use
hand-computable supplied exponential-scale inputs, never measurements.
With zero energies, both independent rates equal one: `d=0` gives a reinitiation
contribution of `0.072` and total `1.072`; `d=-4` gives `0.22` and total `1.22`.
If upstream and downstream log rates are `ln(4)` and `ln(2)`, those totals are
`2.288` and `2.88`. The independent score remains a separate reported quantity.
Unsupported distances stay missing, not zero or an interpolated coefficient.

Independent GPT-6 Astra review DEM-615 checked exact sources, equations,
coefficient domains, coordinate conversions and all fixtures using Decimal
arithmetic. It admitted only this bounded component. Its Figure 1D conflict
and host-page findings are incorporated here and in the manifest. The unresolved
unfolding gate remains explicit. Fixtures retain their original byte identities.
